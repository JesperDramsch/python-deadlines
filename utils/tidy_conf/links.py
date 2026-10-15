import re
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

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

# Redirects to a different site found by check_link_availability. A link that
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


def get_cache_location():
    # Check if the URL is cached
    cache_file = Path("utils", "tidy_conf", "data", ".tmp", "no_archive.txt")
    cache_file_archived = Path("utils", "tidy_conf", "data", ".tmp", "archived_links.txt")
    # The cache directory is gitignored, so it does not exist in a fresh checkout
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    return cache_file, cache_file_archived


def get_cache():
    cache_file, cache_file_archived = get_cache_location()

    # Create the cache file if it doesn't exist
    cache_file.touch()
    cache_file_archived.touch()

    # Read the cache file
    cache = set(cache_file.read_text(encoding="utf-8").split("\n")[:-1])
    cache_archived = set(cache_file_archived.read_text(encoding="utf-8").split("\n")[:-1])

    return cache, cache_archived


def check_link_availability(
    url,
    start,
    cache=None,
    cache_archived=None,
    *,
    conference: str | None = None,
    year: int | None = None,
    field: str | None = None,
) -> str:
    """Checks if a URL is available.

    If not, tries to retrieve an archived version from the Wayback Machine.
    Can't use caching because we have different years for the same url.

    Automatically redirects to the final URL if it was redirected within the same domain.

    A redirect that ends on a different site (see ``is_different_site``) is not
    treated as healthy: the original URL is returned unchanged, with no Wayback
    lookup, and the redirect is recorded with ``record_redirect`` for review.
    A short link that lands where it is expected to (see ``is_expected_redirect``),
    such as forms.gle on docs.google.com, is not recorded: it is checked like
    any other link, so on a 200 the original URL is kept and, when the
    conference is still to come, saved to the Wayback Machine.

    Automatically caches old (5+ years) URLs.

    Note: Some URLs may not be available or archived. These return the original URL and are logged.

    Parameters
    ----------
    url : str
        URL to check
    start : datetime.date
        Start date of the conference the URL belongs to
    cache : set | None
        URLs known to have no archived version, read from disk when None
    cache_archived : set | None
        URLs already archived, read from disk when None
    conference : str | None
        Conference name, only used to describe a recorded redirect
    year : int | None
        Conference year, only used to describe a recorded redirect
    field : str | None
        Data field holding the URL, only used to describe a recorded redirect

    Returns
    -------
    str
        The URL to keep: the original, a same-domain redirect target, or an archived copy
    """
    # If it's archived already, return the URL
    if url.startswith(("https://web.archive.org", "http://web.archive.org")):
        return url

    # Get the cache
    if cache is None or cache_archived is None:
        cache, cache_archived = get_cache()

    cache_file, _ = get_cache_location()

    # Check if the URL is in the cache
    if url in cache and url not in cache_archived:
        tqdm.write(f"URL {url} is cached as not found. Returning original URL.")
        return url

    # If the URL is younger than 5 years, check if it's available
    if start > datetime.now(tz=timezone.utc).date() - timedelta(days=5 * 365):
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            final_url = response.url
            # A redirect to another site is not a healthy link: keep the URL as it
            # is and leave the decision to a person. Short links such as
            # forms.gle redirect to another site by design and are left out.
            if is_different_site(url, final_url) and not is_expected_redirect(url, final_url):
                tqdm.write(
                    f"URL {url} was redirected to a different site: {final_url} "
                    f"(status code: {response.status_code}). Keeping the original URL for review.",
                )
                record_redirect(
                    url,
                    final_url,
                    response.status_code,
                    conference=conference,
                    year=year,
                    field=field,
                )
                return url
            # Check if the final URL is within the same domain as the original URL
            if urlparse(url).netloc == urlparse(final_url).netloc and final_url != url:
                # Don't cache the redirect if it suddenly has a query string
                tqdm.write(f"URL {url} was redirected within the same domain to: {final_url}")
                if "?" in final_url and "?" not in url:
                    tqdm.write("Warning: The final URL contains a query string, but the original URL does not.")
                    # Return original URL to avoid using redirected URL with query string
                    return url
                return final_url  # Use the final URL for the rest of the process
            if response.status_code != 200:
                tqdm.write(
                    (
                        f"Link {url} is not available (status code: {response.status_code})."
                        "Trying to find an archived version..."
                    ),
                )
            else:
                if start > datetime.now(tz=timezone.utc).date():
                    attempt_archive_url(url, cache_archived)
                return url
        except requests.RequestException as e:
            tqdm.write(f"An error occurred: {e}. Trying to find an archived version...")

    # Try to get an archived version from the Wayback Machine or return original URL
    archive_url = f"https://archive.org/wayback/available?url={url}&timestamp={start.strftime('%Y%m%d%H%M%S')}"
    try:
        archive_response = requests.get(archive_url, timeout=10)
        # Make sure the status code is valid (200)
        if archive_response.status_code == 200:
            data = archive_response.json()
            # Get the "closest available" snapshot URL to a date
            if (
                "archived_snapshots" in data
                and data["archived_snapshots"]
                and "closest" in data["archived_snapshots"]
                and data["archived_snapshots"]["closest"]
                and data["archived_snapshots"]["closest"].get("available", False)
            ):
                archived_url = data["archived_snapshots"]["closest"]["url"].replace(":80/", "/")
                if archived_url[4] == ":":
                    archived_url = archived_url[:4] + "s" + archived_url[4:]
                tqdm.write(f"Found archived version: {archived_url}")
                return archived_url
            tqdm.write("No archived version found.")
            attempt_archive_url(url, cache_archived)
            with cache_file.open("a") as f:
                f.write(url + "\n")
            return url

        tqdm.write("Failed to retrieve archived version.")
        return url
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while retrieving the archived version: {e}")
        return url


def attempt_archive_url(url, cache=None):
    """Attempts to archive a URL using the Wayback Machine."""
    # Read the cache file
    if cache is None:
        _, cache = get_cache()

    # Check if the URL is in the cache
    if url in cache:
        tqdm.write(f"URL {url} was already archived.")
        return

    try:
        tqdm.write(f"Attempting archive of {url}.")
        headers = {"User-Agent": "Pythondeadlin.es Archival Attempt/0.1 (https://pythondeadlin.es)"}
        archive_response = requests.get("https://web.archive.org/save/" + url, timeout=30, headers=headers)
        if archive_response.status_code == 200:
            _, cache_file = get_cache_location()
            with cache_file.open("a") as f:
                f.write(url + "\n")
            tqdm.write(f"Successfully archived {url}.")
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while attempting to archive: {e}")


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
