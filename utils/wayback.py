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

import requests

CDX_URL = "https://web.archive.org/cdx/search/cdx"
SAVE_URL = "https://web.archive.org/save/"
USER_AGENT = "Pythondeadlin.es Archiver/1.0 (https://pythondeadlin.es)"
TIMEOUT = 60
# Days after an edition's end in which a capture still shows that edition
END_GRACE_DAYS = 14

ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(?P<url>.+)$", re.IGNORECASE)
TIMESTAMP = re.compile(r"^\d{14}$")


class WaybackError(Exception):
    """A Wayback Machine request that failed or returned something unusable."""


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
    """

    url: str
    ok: bool
    detail: str


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
    WaybackError
        When the request fails or the answer is not a CDX listing. A failed
        lookup is not the same as a page with no captures.
    """
    params = {"url": url, "output": "json", "fl": "timestamp,statuscode", "filter": "statuscode:200"}
    try:
        response = requests.get(CDX_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        msg = f"CDX request for {url} failed: {e}"
        raise WaybackError(msg) from e
    if response.status_code != 200:
        msg = f"CDX request for {url} returned HTTP {response.status_code}"
        raise WaybackError(msg)
    if not response.text.strip():
        return []
    try:
        rows = response.json()
    except ValueError as e:
        msg = f"CDX answer for {url} is not JSON"
        raise WaybackError(msg) from e
    if not isinstance(rows, list):
        msg = f"CDX answer for {url} is not a listing"
        raise WaybackError(msg)
    # The first row is the header: ["timestamp", "statuscode"]
    stamps = [str(row[0]) for row in rows[1:] if isinstance(row, list) and row and TIMESTAMP.match(str(row[0]))]
    return sorted(stamps)


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


def save(url: str) -> SaveResult:
    """Ask the Wayback Machine to save a page now.

    Parameters
    ----------
    url : str
        The page to save

    Returns
    -------
    SaveResult
        Whether the archive accepted the request, with the status or error
    """
    try:
        response = requests.get(SAVE_URL + url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return SaveResult(url, ok=False, detail=f"error: {e}")
    return SaveResult(url, ok=response.status_code == 200, detail=f"HTTP {response.status_code}")
