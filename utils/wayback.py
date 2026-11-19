#!/usr/bin/env python3
"""Talk to the Internet Archive's Wayback Machine: list captures and save pages.

This is the one place the data tooling talks to the Wayback Machine. Two jobs use it:

- ``utils/archive_save.py`` asks the archive to save conference pages while they
  still show their edition.
- ``utils/archive_resolve.py`` replaces the links of old editions with the
  capture that shows that edition.

A capture is chosen by date, never by content: a page that changed between two
captures does not say which edition it showed. ``pick_capture`` takes the last
capture on or before the edition's end plus ``END_GRACE_DAYS``, so the
post-event page (slides, videos) counts, and a capture taken after the site
moved on to a later edition does not.

This module needs only ``requests``, so the save workflow runs it without the
rest of the data tooling's dependencies.
"""

import re
from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from urllib.parse import urlparse

import requests
from urllib3.exceptions import ReadTimeoutError

CDX_URL = "https://web.archive.org/cdx/search/cdx"
SAVE_URL = "https://web.archive.org/save/"
USER_AGENT = "Pythondeadlin.es Archiver/1.0 (https://pythondeadlin.es)"
TIMEOUT = 60
# Seconds to wait for the archive to accept the connection. A refusal arrives at
# once; a long wait here means the archive is not answering at all.
CONNECT_TIMEOUT = 10
# Statuses with which the archive itself turns the client away (rate limit,
# too many sessions), as opposed to failing to capture one page
BLOCKED_STATUSES = frozenset({429, 509})
# Days after an edition's end in which a capture still shows that edition
END_GRACE_DAYS = 14

ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(?P<url>.+)$", re.IGNORECASE)
TIMESTAMP = re.compile(r"^\d{14}$")


class WaybackError(Exception):
    """A Wayback Machine request that failed or returned something unusable."""


class WaybackBlockedError(WaybackError):
    """The archive turned the client away: a refused connection or a rate limit.

    Unlike a failed lookup for one page, every further request in the same run
    would fail the same way, so the caller stops and leaves the rest for its
    next run.
    """


@dataclass(frozen=True)
class SaveResult:
    """The outcome of one save request.

    Attributes
    ----------
    url : str
        The page the archive was asked to save
    ok : bool
        True when the archive accepted the request
    detail : str
        The HTTP status, or the error, for the run's report
    blocked : bool
        True when the archive turned the client away (connection refused or
        failed, rate limited) rather than failing on this page
    """

    url: str
    ok: bool
    detail: str
    blocked: bool = False


def is_archived(url: str) -> bool:
    """Check whether a link already points into the Wayback Machine.

    Parameters
    ----------
    url : str
        A link from the data

    Returns
    -------
    bool
        True for a ``web.archive.org/web/<timestamp>/<url>`` link
    """
    return bool(ARCHIVED.match(str(url).strip()))


def archive_url(timestamp: str, url: str) -> str:
    """Return the Wayback link for one capture of a page.

    Parameters
    ----------
    timestamp : str
        The capture's 14-digit timestamp, as CDX lists it
    url : str
        The page's URL

    Returns
    -------
    str
        ``https://web.archive.org/web/<timestamp>/<url>``

    Raises
    ------
    ValueError
        When the timestamp is not 14 digits
    """
    if not TIMESTAMP.match(timestamp):
        msg = f"not a 14-digit capture timestamp: {timestamp!r}"
        raise ValueError(msg)
    return f"https://web.archive.org/web/{timestamp}/{url}"


def _cdx(params: dict[str, str | list[str]], what: str) -> list[list]:
    """Send one CDX request and return its rows without the header row.

    Parameters
    ----------
    params : dict[str, str | list[str]]
        Query parameters; a list sends the parameter once per value
    what : str
        What the request is for, for error messages

    Returns
    -------
    list[list]
        The rows; empty when the archive has none

    Raises
    ------
    WaybackBlockedError
        When the archive refuses the connection or rate limits the client
    WaybackError
        When the request fails otherwise or the answer is not a CDX listing
    """
    try:
        response = requests.get(
            CDX_URL,
            params={"output": "json", **params},
            headers={"User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT, TIMEOUT),
        )
    except requests.ConnectionError as e:
        msg = f"CDX request for {what} failed: {e}"
        if _is_read_timeout(e):
            raise WaybackError(msg) from e
        raise WaybackBlockedError(msg) from e
    except requests.RequestException as e:
        msg = f"CDX request for {what} failed: {e}"
        raise WaybackError(msg) from e
    if response.status_code in BLOCKED_STATUSES:
        msg = f"CDX request for {what} returned HTTP {response.status_code}"
        raise WaybackBlockedError(msg)
    if response.status_code != 200:
        msg = f"CDX request for {what} returned HTTP {response.status_code}"
        raise WaybackError(msg)
    if not response.text.strip():
        return []
    try:
        rows = response.json()
    except ValueError as e:
        msg = f"CDX answer for {what} is not JSON"
        raise WaybackError(msg) from e
    if not isinstance(rows, list):
        msg = f"CDX answer for {what} is not a listing"
        raise WaybackError(msg)
    return [row for row in rows[1:] if isinstance(row, list) and row]


def captures(url: str) -> list[str]:
    """List the timestamps of a page's successful captures, oldest first.

    One CDX request per page. Captures that did not return HTTP 200 (redirects,
    errors) are left out, since they do not show the page.

    Parameters
    ----------
    url : str
        The page's URL

    Returns
    -------
    list[str]
        14-digit timestamps, oldest first; empty when the archive has none

    Raises
    ------
    WaybackBlockedError
        When the archive refuses the connection or rate limits the client
    WaybackError
        When the request fails otherwise or the answer is not a CDX listing.
        A failed lookup is not the same as a page with no captures.
    """
    rows = _cdx({"url": url, "fl": "timestamp,statuscode", "filter": "statuscode:200"}, url)
    return sorted(str(row[0]) for row in rows if TIMESTAMP.match(str(row[0])))


def page_key(url: str) -> str:
    """Return the key under which the archive files a page.

    CDX treats ``www.`` and the bare host, http and https, a trailing slash
    and a #fragment as the same page, so the key drops them all.

    Parameters
    ----------
    url : str
        A page's URL

    Returns
    -------
    str
        Host without ``www.``, path without a trailing slash, and the query
    """
    parsed = urlparse(str(url).strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    key = host + parsed.path.rstrip("/")
    return f"{key}?{parsed.query}" if parsed.query else key


def _original_pattern(host: str, urls: list[str]) -> str:
    """Build the regex that keeps only the given pages of a host in a CDX answer.

    Parameters
    ----------
    host : str
        The host, without ``www.``
    urls : list[str]
        Pages on that host

    Returns
    -------
    str
        A regex for CDX's ``original`` field
    """
    tails = []
    for url in urls:
        parsed = urlparse(str(url).strip())
        tail = re.escape(parsed.path.rstrip("/"))
        if parsed.query:
            tail += re.escape("?" + parsed.query)
        tails.append(tail)
    alternatives = "|".join(sorted(set(tails)))
    return rf"^https?://(www\.)?{re.escape(host)}(:\d+)?({alternatives})/?$"


def host_captures(host: str, urls: list[str], until: date | None = None) -> dict[str, list[str]]:
    """List the captures of several pages on one host with a single CDX request.

    The request asks for every capture under the host, and a filter on the
    archive's side keeps only the given pages, so the answer stays small.

    Parameters
    ----------
    host : str
        The host, without ``www.``
    urls : list[str]
        Pages on that host
    until : date | None
        The last day a capture can be useful; later ones are not listed

    Returns
    -------
    dict[str, list[str]]
        ``page_key`` of each page to its capture timestamps, oldest first; a
        page with no capture is missing

    Raises
    ------
    WaybackBlockedError
        When the archive refuses the connection or rate limits the client
    WaybackError
        When the request fails otherwise or the answer is not a CDX listing
    """
    params: dict[str, str | list[str]] = {
        "url": f"{host}/*",
        "fl": "original,timestamp",
        "filter": ["statuscode:200", f"original:{_original_pattern(host, urls)}"],
        "collapse": "timestamp:8",
    }
    if until:
        params["to"] = until.strftime("%Y%m%d")
    found: dict[str, list[str]] = {}
    for row in _cdx(params, f"{host} ({len(urls)} pages)"):
        if len(row) >= 2 and TIMESTAMP.match(str(row[1])):
            found.setdefault(page_key(str(row[0])), []).append(str(row[1]))
    return {key: sorted(stamps) for key, stamps in found.items()}


def pick_capture(stamps: list[str], end: date, grace_days: int = END_GRACE_DAYS) -> str | None:
    """Pick the capture that shows an edition: the last one by its end plus the grace days.

    Parameters
    ----------
    stamps : list[str]
        14-digit capture timestamps, in any order
    end : date
        The edition's last day
    grace_days : int
        Days after ``end`` in which a capture still counts

    Returns
    -------
    str | None
        The chosen timestamp, or None when no capture falls on or before the limit
    """
    limit = (end + timedelta(days=grace_days)).strftime("%Y%m%d")
    eligible = [stamp for stamp in stamps if stamp[:8] <= limit]
    return max(eligible) if eligible else None


def _is_read_timeout(error: requests.ConnectionError) -> bool:
    """Check whether a ConnectionError is a read timeout while the body downloads.

    requests raises ``ReadTimeout`` when the headers are late, but re-raises a
    timeout in the body as ``ConnectionError(ReadTimeoutError)``.

    Parameters
    ----------
    error : requests.ConnectionError
        The error a request raised

    Returns
    -------
    bool
        True when the error wraps a urllib3 ``ReadTimeoutError``
    """
    return any(isinstance(arg, ReadTimeoutError) for arg in error.args) or isinstance(
        error.__context__,
        ReadTimeoutError,
    )


def save(url: str) -> SaveResult:
    """Ask the Wayback Machine to save a page now.

    Parameters
    ----------
    url : str
        The page to save

    Returns
    -------
    SaveResult
        Whether the archive accepted the request, with the status or error, and
        whether the archive turned the client away
    """
    try:
        response = requests.get(
            SAVE_URL + url,
            headers={"User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT, TIMEOUT),
        )
    except requests.ConnectionError as e:
        # Refused, reset or not answering: the archive, not the page. A read
        # timeout while the body downloads also arrives as a ConnectionError.
        return SaveResult(url, ok=False, detail=f"error: {e}", blocked=not _is_read_timeout(e))
    except requests.RequestException as e:
        # A read timeout: the capture can still finish on the archive's side
        return SaveResult(url, ok=False, detail=f"error: {e}")
    status = response.status_code
    return SaveResult(url, ok=status == 200, detail=f"HTTP {status}", blocked=status in BLOCKED_STATUSES)
