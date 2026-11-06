import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from tqdm import tqdm
from urllib3.exceptions import NameResolutionError

try:
    from tidy_conf.queue_out import QUEUE_OUT_ENV
    from tidy_conf.queue_out import append_queue_record
    from tidy_conf.queue_out import utc_now
except ImportError:
    from .queue_out import QUEUE_OUT_ENV
    from .queue_out import append_queue_record
    from .queue_out import utc_now

# Sub-page link fields that must point somewhere other than the main link.
# A cfp_link/sponsor/finaid/coc that is just the homepage again carries no
# information (e.g. "cfp_link: https://2027.pycon.de/" on the PyCon DE entry
# whose link is https://2027.pycon.de/) - it should be a different page, a
# subdomain, or at least a #anchor on the homepage. The bare root of the
# series site (e.g. "cfp_link: https://pycon.de/" next to
# "link: https://2027.pycon.de/") carries no information either. A homepage
# is not a Code of Conduct page, so coc is held to the same rule.
REDUNDANT_LINK_FIELDS = ("cfp_link", "sponsor", "finaid", "coc")

# Public suffixes with two labels, under which a registrable domain has three
# labels (pycon.org.au rather than org.au). This is not the full Public Suffix
# List, only the suffixes conference sites are likely to use.
TWO_LEVEL_PUBLIC_SUFFIXES = frozenset(
    {
        "ac.uk",
        "co.uk",
        "gov.uk",
        "org.uk",
        "com.au",
        "net.au",
        "org.au",
        "com.br",
        "org.br",
        "co.jp",
        "ne.jp",
        "or.jp",
        "com.ar",
        "org.ar",
        "co.za",
        "org.za",
        "co.nz",
        "com.mx",
        "com.tr",
        "co.in",
        "com.cn",
        "com.sg",
        "co.il",
        "org.il",
        "or.tz",
        "org.pl",
        # Shared hosts, where each tenant is a site of its own:
        # pyconx.github.io and squatter.github.io are different sites.
        "github.io",
        "gitlab.io",
        "netlify.app",
        "pages.dev",
        "vercel.app",
        "readthedocs.io",
    },
)

# Hosts whose links always redirect to another site, mapped to the registrable
# domains those redirects are expected to land on. forms.gle is the Google
# Forms short link (it lands on docs.google.com) and lu.ma is the old Luma
# domain, which now redirects to luma.com.
EXPECTED_REDIRECT_TARGETS = {
    "forms.gle": frozenset({"google.com"}),
    "lu.ma": frozenset({"luma.com"}),
}

# General URL shorteners. A short link lands wherever it was made to point, so
# a redirect from one to another site says nothing about the link.
URL_SHORTENERS = frozenset({"bit.ly", "goo.gl", "tinyurl.com"})

# Statuses that mean a page is gone. See ``Probe.broken``.
BROKEN_STATUSES = frozenset({404, 410})

# Redirects to a different site found by utils/archive_resolve.py. A link that
# now lands on another site (a lapsed domain, a parked page, a new home for
# the series) needs a person to look at it, so the link is kept as it is and
# the redirect is recorded here instead.
REDIRECT_RECORDS: list[dict] = []

# When this environment variable names a file, every redirect record is also
# appended to it as one JSON line for the desk queue (see queue_out.py).
REDIRECT_RECORDS_ENV = QUEUE_OUT_ENV


def normalize_url_pointer(url: str) -> tuple:
    """Normalize a URL for same-pointer comparison.

    Two URLs are the same pointer when they only differ by scheme
    (http/https), a "www." prefix, host case, or a trailing slash.
    Anything else - path, subdomain, query, or #fragment - makes them
    different pointers.

    Parameters
    ----------
    url : str
        URL to normalize

    Returns
    -------
    tuple
        Comparable (host, path, params, query, fragment) tuple
    """
    parsed = urlparse(str(url).strip())
    netloc = parsed.netloc.lower().removeprefix("www.")
    return (netloc, parsed.path.rstrip("/"), parsed.params, parsed.query, parsed.fragment)


def site_host(url: str) -> str:
    """Return the host of a URL in lower case, without port or a "www." prefix.

    Parameters
    ----------
    url : str
        URL to take the host from

    Returns
    -------
    str
        Host name, or an empty string when the URL has none
    """
    host = urlparse(str(url).strip()).hostname or ""
    return host.lower().removeprefix("www.")


def is_parent_domain(parent: str, host: str) -> bool:
    """Check whether ``parent`` is a parent domain of ``host``.

    A public suffix such as ``de``, ``co.uk`` or ``github.io`` does not count
    as a parent.

    Parameters
    ----------
    parent : str
        Candidate parent host, e.g. ``pycon.de``
    host : str
        Host to test, e.g. ``2027.pycon.de``

    Returns
    -------
    bool
        True when ``host`` is a subdomain of ``parent``
    """
    if "." not in parent or parent in TWO_LEVEL_PUBLIC_SUFFIXES:
        return False
    return host.endswith("." + parent)


def registrable_domain(host: str) -> str:
    """Return the registrable domain of a host.

    This is the last two labels, or the last three when the last two are a
    known two-level public suffix (see ``TWO_LEVEL_PUBLIC_SUFFIXES``).

    Parameters
    ----------
    host : str
        Host name, e.g. ``2027.pycon.de``

    Returns
    -------
    str
        Registrable domain, e.g. ``pycon.de``
    """
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in TWO_LEVEL_PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_different_site(url: str, other: str) -> bool:
    """Check whether two URLs belong to different sites.

    They are different sites when the hosts differ after dropping "www.",
    neither host is a subdomain of the other, and their registrable domains
    differ. ``ug.pycon.org`` and ``africa.pycon.org`` are the same site;
    ``pythoncamp.de`` and ``barcamps.eu`` are not.

    Parameters
    ----------
    url : str
        First URL
    other : str
        Second URL

    Returns
    -------
    bool
        True when the URLs are on different sites; False when either has no host
    """
    host, other_host = site_host(url), site_host(other)
    if not host or not other_host or host == other_host:
        return False
    if is_parent_domain(host, other_host) or is_parent_domain(other_host, host):
        return False
    return registrable_domain(host) != registrable_domain(other_host)


def is_expected_redirect(url: str, final_url: str) -> bool:
    """Check whether a redirect to another site is what the link is for.

    A link on a general URL shortener (see ``URL_SHORTENERS``) may land
    anywhere. A link on a host listed in ``EXPECTED_REDIRECT_TARGETS`` must
    land on one of the registrable domains listed for it: ``forms.gle`` on
    ``google.com``, ``lu.ma`` on ``luma.com``. Any other redirect is not
    expected.

    Parameters
    ----------
    url : str
        URL as stored in the data
    final_url : str
        URL the redirect chain ended on

    Returns
    -------
    bool
        True when the redirect is one the link is expected to make
    """
    origin = registrable_domain(site_host(url))
    if origin in URL_SHORTENERS:
        return True
    targets = EXPECTED_REDIRECT_TARGETS.get(origin, frozenset())
    return registrable_domain(site_host(final_url)) in targets


def record_redirect(
    url: str,
    final_url: str,
    status: int,
    conference: str | None = None,
    year: int | None = None,
    field: str | None = None,
) -> dict:
    """Record a redirect to a different site for review.

    The record is appended to ``REDIRECT_RECORDS`` and, when the
    ``DESK_QUEUE_OUT`` environment variable names a file, written to that
    file as one JSON line. It holds the fields of a queue item with source
    "link-check" and kind "redirect", except "id": the queue writer assigns
    the id, and the series key of the file the item goes in, when it adds
    the line.

    Parameters
    ----------
    url : str
        URL as stored in the data
    final_url : str
        URL the redirect chain ended on
    status : int
        HTTP status code of the final response
    conference : str | None
        Conference name, when known
    year : int | None
        Conference year, when known
    field : str | None
        Data field holding the URL (link, cfp_link, sponsor, finaid or coc), when known

    Returns
    -------
    dict
        The record that was stored
    """
    record = {
        "source": "link-check",
        "kind": "redirect",
        "received": utc_now(),
        "title": conference or url,
        "url": url,
        "year": year,
        "payload": {
            "conference": conference,
            "year": year,
            "field": field,
            "final_url": final_url,
            "status": status,
        },
    }
    REDIRECT_RECORDS.append(record)
    append_queue_record(record)
    return record


def is_bare_site_root(url: str) -> bool:
    """Check whether a URL is the bare root of a site.

    A bare root has an empty or "/" path and no params, query or #fragment.

    Parameters
    ----------
    url : str
        URL to check

    Returns
    -------
    bool
        True when the URL points at nothing more specific than the site itself
    """
    parsed = urlparse(str(url).strip())
    if not parsed.hostname or parsed.path not in {"", "/"}:
        return False
    return not (parsed.params or parsed.query or parsed.fragment)


def is_redundant_site_root(value: str, link: str) -> bool:
    """Check whether a sub-page link is only the bare root of the main link's site.

    The site is the same when the hosts are equal after dropping "www.", or
    when the sub-page host is a parent domain of the main link's host
    (``pycon.de`` for ``2027.pycon.de``). The reverse is not redundant: a
    year subdomain is more specific than the series site.

    Parameters
    ----------
    value : str
        Sub-page link (cfp_link, sponsor, finaid or coc)
    link : str
        Main conference link

    Returns
    -------
    bool
        True when ``value`` adds nothing over ``link``
    """
    if not is_bare_site_root(value):
        return False
    value_host, link_host = site_host(value), site_host(link)
    if not value_host or not link_host:
        return False
    return value_host == link_host or is_parent_domain(value_host, link_host)


def drop_redundant_link_fields(data: list) -> list:
    """Drop sub-page link fields that are the same pointer as the main link.

    Goes through cfp_link/sponsor/finaid/coc on each conference and
    removes any that just repeat the conference's main link. This catches
    upstream sources that fill every URL column with the homepage. A field
    that is only the bare root of the same site (``https://pycon.de/`` next
    to ``https://2027.pycon.de/``) is dropped as well.

    Parameters
    ----------
    data : list
        List of conference dictionaries

    Returns
    -------
    list
        The same list with redundant link fields removed
    """
    for q in data:
        if not isinstance(q, dict):
            continue
        link = q.get("link")
        if not link:
            continue
        base = normalize_url_pointer(link)
        for field in REDUNDANT_LINK_FIELDS:
            value = q.get(field)
            if not value:
                continue
            if normalize_url_pointer(value) == base:
                reason = "is the same pointer as the main link"
            elif is_redundant_site_root(value, link):
                reason = f"is only the root of the same site as the main link '{link}'"
            else:
                continue
            tqdm.write(f"Dropping redundant '{field}' from {q.get('conference')} {q.get('year')}: '{value}' {reason}")
            del q[field]
    return data


@dataclass(frozen=True)
class Probe:
    """The outcome of one request for a link.

    Attributes
    ----------
    url : str
        The link as stored in the data
    final_url : str
        Where the redirect chain ended; the link itself when the request failed
    status : int | None
        HTTP status of the final response, or None when there was none
    error : str | None
        Why the request failed, or None when a response came back
    """

    url: str
    final_url: str
    status: int | None
    error: str | None = None

    @property
    def broken(self) -> bool:
        """Whether the link is gone, rather than slow, blocked or briefly down.

        A 404 or 410, a host that does not resolve, a refused connection and
        a failed TLS handshake (an expired or foreign certificate) count. A
        timeout, a connection reset or dropped mid-request, a 403 or 429 (often
        a bot filter) and a 5xx do not: replacing a link is not undone, so only
        a lasting failure counts. See ``is_lasting_connection_failure``.
        """
        return self.status in BROKEN_STATUSES or self.error == "connection"

    @property
    def redirects_elsewhere(self) -> bool:
        """Whether the link now lands on another site, other than as its kind of link does."""
        return (
            self.status is not None
            and is_different_site(self.url, self.final_url)
            and not is_expected_redirect(self.url, self.final_url)
        )


def probe(url: str, timeout: int = 10) -> Probe:
    """Request a link once, following redirects.

    Parameters
    ----------
    url : str
        The link to request
    timeout : int
        Seconds to wait for a response

    Returns
    -------
    Probe
        The status and final URL, or why there was no response
    """
    headers = {"User-Agent": "Pythondeadlin.es Link Checker/0.2 (https://pythondeadlin.es)"}
    try:
        response = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers)
    except requests.Timeout:
        return Probe(url, url, None, "timeout")
    except requests.ConnectionError as e:
        # A reset or a dropped connection mid-request is a ConnectionError too,
        # but says nothing lasting about the site.
        return Probe(url, url, None, "connection" if is_lasting_connection_failure(e) else "reset")
    except requests.RequestException as e:
        return Probe(url, url, None, type(e).__name__)
    return Probe(url, response.url or url, response.status_code)


def _causes(error: BaseException) -> list[BaseException]:
    """Return an exception and every exception it wraps, through causes, contexts, reasons and arguments.

    Parameters
    ----------
    error : BaseException
        The exception requests raised

    Returns
    -------
    list[BaseException]
        The exceptions found, the outermost first
    """
    found: list[BaseException] = []
    todo: list[object] = [error]
    while todo:
        current = todo.pop(0)
        if not isinstance(current, BaseException) or any(current is seen for seen in found):
            continue
        found.append(current)
        todo.extend((getattr(current, "reason", None), current.__cause__, current.__context__, *current.args))
    return found


def is_lasting_connection_failure(error: requests.ConnectionError) -> bool:
    """Check whether a connection error means the site is gone rather than briefly unreachable.

    A failed TLS handshake, a host that does not resolve and a refused
    connection count. A reset or a connection dropped mid-request does not.

    Parameters
    ----------
    error : requests.ConnectionError
        The exception requests raised

    Returns
    -------
    bool
        True for a lasting failure
    """
    if isinstance(error, requests.exceptions.SSLError):
        return True
    return any(
        isinstance(cause, ConnectionRefusedError | socket.gaierror | NameResolutionError) for cause in _causes(error)
    )


def parse_mastodon_url(url: str) -> tuple[str, str] | None:
    """Parse a Mastodon URL into (instance, username).

    Args:
        url: Full Mastodon profile URL (e.g., https://fosstodon.org/@pycon)

    Returns
    -------
    tuple[str, str] | None
        Tuple of (instance, username) or None if URL format is invalid.
    """
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        # Match /@username or @username patterns
        match = re.match(r"^/?@(\w+)$", parsed.path)
        if match:
            return (parsed.netloc, match.group(1))
        return None
    except Exception:
        return None


def check_mastodon_migration(mastodon_url: str, max_depth: int = 5) -> str | None:
    """Check if a Mastodon account has migrated and return the new URL.

    Follows migration chains (A→B→C) until finding the final destination.
    A chain that loops back to an account already visited (A→B→A) has no
    canonical destination, so it returns None and the stored URL is left
    untouched; anything else would flip-flop between the accounts on every
    link check.

    Args:
        mastodon_url: Full Mastodon profile URL (e.g., https://fosstodon.org/@pycon)
        max_depth: Maximum number of migration hops to follow (default: 5)

    Returns
    -------
    str | None
        New URL if migrated, None if no migration detected or on error.
    """
    parsed = parse_mastodon_url(mastodon_url)
    if not parsed:
        tqdm.write(f"Warning: Could not parse Mastodon URL: {mastodon_url}")
        return None

    current_url = mastodon_url
    current_instance, current_username = parsed
    visited = {f"{current_username}@{current_instance}"}

    for _ in range(max_depth):
        # Query the Mastodon API
        api_url = f"https://{current_instance}/api/v1/accounts/lookup?acct={current_username}"
        headers = {"User-Agent": "Pythondeadlin.es Link Checker/0.1 (https://pythondeadlin.es)"}

        try:
            response = requests.get(api_url, headers=headers, timeout=10)

            if response.status_code == 404:
                tqdm.write(f"Warning: Mastodon account not found: {current_url}")
                return None

            if response.status_code == 429:
                tqdm.write(f"Warning: Rate limited by {current_instance}, skipping migration check")
                return None

            if response.status_code != 200:
                tqdm.write(f"Warning: Mastodon API error ({response.status_code}) for {current_url}")
                return None

            data = response.json()

            # Check if account has moved
            if data.get("moved"):
                moved_to = data["moved"]
                new_url = moved_to.get("url")
                if not new_url:
                    break

                # Parse the new URL for the next iteration
                new_parsed = parse_mastodon_url(new_url)

                # A circular migration has no canonical destination: keep the
                # stored URL rather than flip-flopping between the accounts.
                if new_parsed and f"{new_parsed[1]}@{new_parsed[0]}" in visited:
                    tqdm.write(f"Warning: Circular migration detected for {mastodon_url}")
                    return None

                tqdm.write(f"Mastodon migration detected: {current_url} → {new_url}")
                current_url = new_url

                if not new_parsed:
                    # If we can't parse the new URL, return it anyway
                    return new_url
                current_instance, current_username = new_parsed
                visited.add(f"{current_username}@{current_instance}")

                # Rate limit: wait 1 second between API calls
                time.sleep(1)
            else:
                # No migration, we've reached the final destination
                break

        except requests.RequestException as e:
            tqdm.write(f"Warning: Error checking Mastodon migration for {current_url}: {e}")
            return None

    # Return new URL only if it changed from the original
    if current_url != mastodon_url:
        return current_url
    return None
