#!/usr/bin/env python3
"""Find leads for the deadline desk on pretalx, developers.events and the pycon.org registry.

Each source writes queue records as JSON lines, which utils/desk_queue.py adds
to the desk-queue branch. Nothing here writes the data files: the desk checks
every record on the primary source before anything changes.

- ``pretalx``: for each upcoming entry with a pretalx.com CfP, the deadline its
  CfP page states when that differs from the entry's (kind ``drift``), and the
  next edition's CfP page, guessed from the latest edition's slug (kind
  ``candidate``). Only the public ``/<slug>/cfp`` pages are read, because the
  robots.txt of pretalx.com disallows ``/api/``.
- ``developers-events``: upcoming Python events on developers.events that the
  data does not track (kind ``candidate``).
- ``pycon-org``: events in the pycon.org registry that the data does not
  track (kind ``registry``).
- ``listing``: the lines a changedetection watch on a page that lists many
  events saw added, one event per line (kind ``candidate``, flag ``listing``),
  for the editions and series the data does not track. ``--lines`` names the
  file, ``--url`` the page. The PSF PyCon trademark list comes this way.

A find is tracked when it is the same series as an entry in any of the three
data files, by the rules in AGENTS.md "Names": its name (year and a trailing
"Conference" removed) matches a conference or alt_name after the titles.yml
mappings, ignoring case, accents and whitespace, or its link matches an
entry's link once years are taken out of the host and path. A tracked find
for a year the data has no edition of is a MISSING_EDITION candidate. A find
whose host matches an entry's host is MAYBE, unless the host carries many
series (pydata.org, pretalx.com and the like). Anything else is NEW_SERIES.

It needs the same packages as sort_yaml.py (the pixi or uv environment),
because the title normalisation in tidy_conf imports pandas, pydantic,
thefuzz and tqdm.

Usage::

    python utils/desk_leads.py pretalx --out records.jsonl
    python utils/desk_leads.py developers-events --today 2026-10-14
    python utils/desk_leads.py pycon-org --base . --out records.jsonl
"""

import argparse
import json
import re
import sys
import time
import zoneinfo
from collections.abc import Iterable
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
import yaml

try:
    from cfp_candidates import entry_keys
    from cfp_candidates import load_data
    from cfp_candidates import series_key
    from desk_queue import resolve_watch_url
    from desk_worklist import effective_deadline
    from sort_yaml import DATEFORMAT
    from tidy_conf.yaml import load_title_mappings
except ImportError:
    from .cfp_candidates import entry_keys
    from .cfp_candidates import load_data
    from .cfp_candidates import series_key
    from .desk_queue import resolve_watch_url
    from .desk_worklist import effective_deadline
    from .sort_yaml import DATEFORMAT
    from .tidy_conf.yaml import load_title_mappings

SOURCES = ("pretalx", "developers-events", "pycon-org")
DATA_FILES = ("conferences", "archive", "legacy")
USER_AGENT = "pythondeadlin.es desk leads (+https://pythondeadlin.es)"
TIMEOUT = 20
PRETALX_DELAY = 1.0
SHARED_HOSTS = (
    "pydata.org",
    "events.linuxfoundation.org",
    "pretalx.com",
    "sessionize.com",
    "web.archive.org",
    "github.com",
    "meetup.com",
    "forms.gle",
    "docs.google.com",
)
TBA_VALUES = ("tba", "tbd")

PRETALX_CFP = "https://pretalx.com/{slug}/cfp"
DEVELOPERS_EVENTS = "https://developers.events/all-events.json"
PYCON_ORG_FILES = "https://data.jsdelivr.com/v1/packages/gh/PyCon/pycon.org@master?structure=flat"
PYCON_ORG_RAW = "https://raw.githubusercontent.com/PyCon/pycon.org/master"

ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(.+)$", re.IGNORECASE)
LINK_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
NAME_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
TRAILING_CONFERENCE = re.compile(r"[\s,:-]*\bconference\s*$", re.IGNORECASE)
PARENTHESES = re.compile(r"\s*\([^)]*\)")
PRETALX_SLUG = re.compile(r"^https?://(?:www\.)?pretalx\.com/([A-Za-z0-9][A-Za-z0-9_.-]*)(?:[/?#]|$)", re.IGNORECASE)
PRETALX_RESERVED = {"api", "download", "locale", "me", "media", "orga", "p", "redirect", "static"}
SUBMISSIONS = re.compile(r"Submissions (close|closed) on (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) \(([^()<>\s]+)\)")
PROPOSALS_CLOSED = "Proposals are closed"
# Inside longer words too: EuroPython, EuroSciPy, DjangoCon, JupyterCon, FlaskCon
PYTHON_NAME = re.compile(r"\bpy|python|django|flask|fastapi|scipy|jupyter|wagtail|plone", re.IGNORECASE)
EXCLUDED_NAME = re.compile(r"financial aid|hatchery|sprint", re.IGNORECASE)
REGISTRY_PATH = re.compile(r"^/_(?:national|regional)/[^/]+\.yml$")
FRONT_MATTER = re.compile(r"\A\s*---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


class SourceError(Exception):
    """A source that could not be read as a whole.

    Parameters
    ----------
    message : str
        What failed.
    records : list[dict] | None
        Records found before the failure, still worth queueing.
    """

    def __init__(self, message: str, records: list[dict] | None = None) -> None:
        super().__init__(message)
        self.records = list(records or [])


def report(message: str) -> None:
    """Print a message for the job log on stderr.

    Parameters
    ----------
    message : str
        The message, without the "desk_leads: " prefix.
    """
    print(f"desk_leads: {message}", file=sys.stderr)


def first_line(error: Exception) -> str:
    """Return the first line of an error message, for a one-line report.

    Parameters
    ----------
    error : Exception
        The error.

    Returns
    -------
    str
        Its first non-empty line, or the error's type name.
    """
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return lines[0] if lines else type(error).__name__


def as_year(value: Any) -> int | None:
    """Return a year value as an int, or None.

    Parameters
    ----------
    value : Any
        A YAML year: an int or a four-digit string.

    Returns
    -------
    int | None
        The year, or None when the value is not one.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}", value.strip()):
        return int(value)
    return None


def as_date(value: Any) -> date | None:
    """Return a YAML date value as a date, or None.

    Parameters
    ----------
    value : Any
        A date, a datetime, or an ISO date string.

    Returns
    -------
    date | None
        The date, or None when the value is not one.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def unwrap_archive(url: str) -> str:
    """Return the archived URL inside a web.archive.org link, or the link itself.

    Parameters
    ----------
    url : str
        A link, possibly ``https://web.archive.org/web/<timestamp>/<url>``.

    Returns
    -------
    str
        The URL the archive holds (AGENTS.md: the archived URL counts), else the
        link, stripped.
    """
    text = url.strip()
    match = ARCHIVED.match(text)
    if not match:
        return text
    inner = match[1]
    return inner if re.match(r"^https?://", inner, re.IGNORECASE) else f"http://{inner}"


def _strip_years(part: str) -> str:
    """Remove four-digit years from a host label or path segment, and the separators they leave."""
    return LINK_YEAR.sub("", part).strip("-_.")


def _link_parts(url: Any) -> tuple[str, list[str]] | None:
    """Split a link into its host and path segments with years removed, or return None."""
    if not isinstance(url, str) or not url.strip():
        return None
    parts = urlsplit(unwrap_archive(url))
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower().removeprefix("www.")
    labels = [label for label in (_strip_years(label) for label in host.split(".")) if label]
    segments = [segment for segment in (_strip_years(seg) for seg in parts.path.lower().split("/")) if segment]
    if not labels:
        return None
    return ".".join(labels), segments


def link_key(url: Any) -> str | None:
    """Return the key two links of the same series share.

    Parameters
    ----------
    url : Any
        A link.

    Returns
    -------
    str | None
        Host and path, lowercased, without a leading "www.", a query or a
        fragment, with four-digit years taken out of host labels and path
        segments and empty segments dropped: ``https://2027.pycon.gr/`` and
        ``https://2026.pycon.gr/`` both give "pycon.gr". None for anything
        that is not an http(s) link.
    """
    parts = _link_parts(url)
    if parts is None:
        return None
    host, segments = parts
    return "/".join([host, *segments])


def link_host(url: Any) -> str | None:
    """Return a link's host with years removed, as link_key builds it.

    Parameters
    ----------
    url : Any
        A link.

    Returns
    -------
    str | None
        The host part of link_key, or None.
    """
    parts = _link_parts(url)
    return parts[0] if parts else None


def is_shared_host(host: str) -> bool:
    """Return whether a host carries many series, so that only the path tells them apart.

    Parameters
    ----------
    host : str
        A host as link_host returns it.

    Returns
    -------
    bool
        True for SHARED_HOSTS and their subdomains.
    """
    return any(host == shared or host.endswith(f".{shared}") for shared in SHARED_HOSTS)


def name_variants(name: str) -> list[str]:
    """Return the forms of a find's name to match against the data.

    Parameters
    ----------
    name : str
        The name as a source gives it, e.g. "SciPy India 2026 Conference".

    Returns
    -------
    list[str]
        Distinct non-empty forms: without years, then also without a trailing
        "Conference" ("SciPy India") and without parentheses ("PyCon MEA" for
        "PyCon MEA (Middle East & Africa)"). Matching tries every form, so
        "Plone Conference" still finds the series of that name.
    """
    no_year = " ".join(NAME_YEAR.sub(" ", name).split()).strip(" ,:-")
    forms = [no_year, TRAILING_CONFERENCE.sub("", no_year).strip(" ,:-")]
    forms.extend([PARENTHESES.sub("", form).strip(" ,:-") for form in forms])
    variants: list[str] = []
    for form in forms:
        if form and form not in variants:
            variants.append(form)
    return variants


def clean_name(name: str) -> str:
    """Return a find's name without years, as a series name for the desk.

    Parameters
    ----------
    name : str
        The name as a source gives it, e.g. "PyData Lagos 2027".

    Returns
    -------
    str
        The first of name_variants ("PyData Lagos"), or the name when nothing is left.
    """
    variants = name_variants(name)
    return variants[0] if variants else name.strip()


def _edition_order(edition: tuple[str, dict]) -> tuple[int, str]:
    """Sort key that puts the newest edition last."""
    entry = edition[1]
    return as_year(entry.get("year")) or 0, str(entry.get("start") or "")


class TrackingIndex:
    """The series the three data files track, for deciding what a find is.

    Parameters
    ----------
    known_mappings : dict
        Reverse titles.yml mapping from load_title_mappings(reverse=True).
    """

    def __init__(self, known_mappings: dict) -> None:
        self.known_mappings = known_mappings
        self.editions: dict[str, list[tuple[str, dict]]] = {}
        self.names: dict[str, set[str]] = {}
        self.links: dict[str, set[str]] = {}
        self.hosts: dict[str, list[tuple[str, dict]]] = {}

    @classmethod
    def from_data(cls, data: dict[str, list[dict]], known_mappings: dict | None = None) -> "TrackingIndex":
        """Index every edition in the data.

        Parameters
        ----------
        data : dict[str, list[dict]]
            Entries keyed "conferences", "archive" and "legacy", as from cfp_candidates.load_data.
        known_mappings : dict, optional
            Reverse titles.yml mapping. Loaded when omitted.

        Returns
        -------
        TrackingIndex
            The index.
        """
        if known_mappings is None:
            _, known_mappings = load_title_mappings(reverse=True)
        index = cls(known_mappings)
        for file in DATA_FILES:
            for entry in data.get(file) or []:
                if isinstance(entry, dict):
                    index.add(file, entry)
        return index

    def add(self, file: str, entry: dict) -> None:
        """Add one edition.

        Parameters
        ----------
        file : str
            The data file it is in: "conferences", "archive" or "legacy".
        entry : dict
            The entry.
        """
        conference = entry.get("conference")
        if not isinstance(conference, str) or not conference.strip():
            return
        key = series_key(conference, self.known_mappings)
        self.editions.setdefault(key, []).append((file, entry))
        for name_key in entry_keys(entry, self.known_mappings):
            self.names.setdefault(name_key, set()).add(key)
        entry_link = link_key(entry.get("link"))
        if entry_link:
            self.links.setdefault(entry_link, set()).add(key)
        host = link_host(entry.get("link"))
        if host and not is_shared_host(host):
            self.hosts.setdefault(host, []).append((file, entry))

    def name_series(self, name: Any) -> set[str]:
        """Return the series a name matches.

        Parameters
        ----------
        name : Any
            A find's name.

        Returns
        -------
        set[str]
            Series keys, empty when no form of the name matches.
        """
        if not isinstance(name, str):
            return set()
        found: set[str] = set()
        for variant in name_variants(name):
            found |= self.names.get(series_key(variant, self.known_mappings), set())
        return found

    def link_series(self, url: Any) -> set[str]:
        """Return the series whose entry link has the same link key.

        Parameters
        ----------
        url : Any
            A find's link.

        Returns
        -------
        set[str]
            Series keys. A bare shared host (``https://pretalx.com/``) matches nothing.
        """
        parts = _link_parts(url)
        if parts is None:
            return set()
        host, segments = parts
        if is_shared_host(host) and not segments:
            return set()
        return set(self.links.get("/".join([host, *segments]), set()))

    def has_edition(self, series: Iterable[str], year: int | None) -> bool:
        """Return whether any of the series has an edition for the year.

        Parameters
        ----------
        series : Iterable[str]
            Series keys.
        year : int | None
            The edition year; None never matches.

        Returns
        -------
        bool
            True when an edition for that year is in any data file.
        """
        if year is None:
            return False
        return any(as_year(entry.get("year")) == year for key in series for _, entry in self.editions.get(key, []))

    def latest(self, series: Iterable[str]) -> tuple[str, dict] | None:
        """Return the newest edition of the series, with the file it is in.

        Parameters
        ----------
        series : Iterable[str]
            Series keys.

        Returns
        -------
        tuple[str, dict] | None
            (file, entry), or None when the series has no editions.
        """
        editions = [edition for key in sorted(series) for edition in self.editions.get(key, [])]
        return max(editions, key=_edition_order) if editions else None

    def is_tracked_name(self, name: Any) -> bool:
        """Return whether a name matches a series in the data.

        Parameters
        ----------
        name : Any
            A name.

        Returns
        -------
        bool
            True when name_series finds a series.
        """
        return bool(self.name_series(name))

    def classify(self, name: Any, year: int | None, link: Any) -> dict | None:
        """Decide what a find is.

        Parameters
        ----------
        name : Any
            The find's name.
        year : int | None
            The find's edition year.
        link : Any
            The find's link.

        Returns
        -------
        dict | None
            None when the series is tracked and has an edition for the year.
            Otherwise {"classification", "matched"}: MISSING_EDITION with the
            series' latest edition (score 100), MAYBE with the latest entry on
            the same host (score 50), or NEW_SERIES with matched None.
        """
        by_name = self.name_series(name)
        series = by_name | self.link_series(link)
        if series:
            if self.has_edition(series, year):
                return None
            file, entry = self.latest(by_name or series)
            return {"classification": "MISSING_EDITION", "matched": _matched(file, entry, 100)}
        host = link_host(link)
        if host and not is_shared_host(host) and self.hosts.get(host):
            file, entry = max(self.hosts[host], key=_edition_order)
            return {"classification": "MAYBE", "matched": _matched(file, entry, 50)}
        return {"classification": "NEW_SERIES", "matched": None}


def _matched(file: str, entry: dict, score: int) -> dict:
    """Return the "matched" payload naming an entry."""
    return {"conference": entry.get("conference"), "file": file, "year": as_year(entry.get("year")), "score": score}


def fetch(url: str, language: str | None = None) -> requests.Response:
    """Fetch a URL, following redirects.

    Parameters
    ----------
    url : str
        The URL.
    language : str | None
        Value for an Accept-Language header, if any.

    Returns
    -------
    requests.Response
        The response, whatever its status.
    """
    headers = {"User-Agent": USER_AGENT}
    if language:
        headers["Accept-Language"] = language
    return requests.get(url, headers=headers, timeout=TIMEOUT)


def fetch_json(url: str) -> Any:
    """Fetch a JSON document.

    Parameters
    ----------
    url : str
        The URL.

    Returns
    -------
    Any
        The parsed document.

    Raises
    ------
    SourceError
        When the request fails, the status is not 2xx, or the body is not JSON.
    """
    try:
        response = fetch(url)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        raise SourceError(f"{url}: {first_line(error)}") from error


class PageFetcher:
    """Fetch pretalx pages one at a time, pausing between requests, and keep each result.

    Parameters
    ----------
    delay : float
        Seconds to wait before every fetch after the first.
    """

    def __init__(self, delay: float = PRETALX_DELAY) -> None:
        self.delay = delay
        self.pages: dict[str, requests.Response | None] = {}
        self.attempts = 0
        self.failures = 0

    def get(self, url: str) -> requests.Response | None:
        """Return the response for a URL, fetching it once.

        Parameters
        ----------
        url : str
            The page.

        Returns
        -------
        requests.Response | None
            The response, or None when the request failed or the server
            answered 5xx, 401, 403, 429 or 451 (reported on stderr).
        """
        if url in self.pages:
            return self.pages[url]
        if self.attempts and self.delay:
            time.sleep(self.delay)
        self.attempts += 1
        response: requests.Response | None = None
        try:
            response = fetch(url, language="en")
        except requests.RequestException as error:
            report(f"pretalx: {url}: {first_line(error)}, skipped")
        else:
            # A refusal (401, 403, 451) counts as a failure, so a blocked job
            # fails as a whole instead of finding nothing; a 404 does not
            if response.status_code >= 500 or response.status_code in (401, 403, 429, 451):
                report(f"pretalx: {url} returned {response.status_code}, skipped")
                response = None
        if response is None:
            self.failures += 1
        self.pages[url] = response
        return response

    def all_failed(self) -> bool:
        """Return whether pages were fetched and every one failed.

        Returns
        -------
        bool
            True when the source as a whole could not be read.
        """
        return self.attempts > 0 and self.failures == self.attempts


def pretalx_slug(url: Any) -> str | None:
    """Return the pretalx.com event slug of a link.

    Parameters
    ----------
    url : Any
        A link, e.g. ``https://pretalx.com/pycon-namibia-2027/cfp``. An archived
        copy on web.archive.org counts as the URL it holds.

    Returns
    -------
    str | None
        The slug ("pycon-namibia-2027"), or None for other hosts and for
        pretalx's own paths (/api/, /orga/ and the like).
    """
    if not isinstance(url, str):
        return None
    match = PRETALX_SLUG.match(unwrap_archive(url))
    if not match or match[1].lower() in PRETALX_RESERVED:
        return None
    return match[1]


def entry_slug(entry: dict) -> str | None:
    """Return the pretalx slug of an entry's cfp_link, else of its link.

    Parameters
    ----------
    entry : dict
        A conference entry.

    Returns
    -------
    str | None
        The slug, or None when neither link is on pretalx.com.
    """
    for field in ("cfp_link", "link"):
        slug = pretalx_slug(entry.get(field))
        if slug:
            return slug
    return None


def next_slug(slug: str, year: int) -> str | None:
    """Guess the slug of the next edition from this edition's slug.

    Parameters
    ----------
    slug : str
        A pretalx slug, e.g. "pycon-namibia-2026" or "pycongr26".
    year : int
        The edition year the slug belongs to.

    Returns
    -------
    str | None
        The slug with the year, as four digits anywhere or as a trailing two
        digits, moved on by one ("pycon-namibia-2027", "pycongr27"), or None
        when the slug carries neither.
    """
    four = re.compile(rf"(?<!\d){year}(?!\d)")
    if four.search(slug):
        return four.sub(str(year + 1), slug)
    two = re.compile(rf"(?<!\d){year % 100:02d}$")
    if two.search(slug):
        return two.sub(f"{(year + 1) % 100:02d}", slug)
    return None


def parse_submissions(text: str) -> dict | None:
    """Read the deadline sentence of a pretalx CfP page.

    Parameters
    ----------
    text : str
        The page HTML.

    Returns
    -------
    dict | None
        "sentence" (as found, without the relative time that follows it),
        "closed" (bool), "cfp" ("YYYY-MM-DD HH:MM:00"), "timezone" (as
        written, legacy aliases such as "Poland" included) and "moment" (an
        aware datetime, None when the zone is unknown). None when the page has
        no such sentence.
    """
    match = SUBMISSIONS.search(text)
    if not match:
        return None
    verb, day, clock, zone = match.groups()
    try:
        tz = zoneinfo.ZoneInfo(zone)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError):
        tz = None
    try:
        moment = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=tz or timezone.utc)
    except ValueError:
        return None
    return {
        "sentence": match[0],
        "closed": verb == "closed",
        "cfp": moment.strftime(DATEFORMAT),
        "timezone": zone,
        "moment": moment if tz is not None else None,
    }


def entry_deadline(entry: dict) -> tuple[str, datetime | None] | None:
    """Return an entry's effective deadline, as text for the desk and as an instant.

    Parameters
    ----------
    entry : dict
        A conferences.yml entry.

    Returns
    -------
    tuple[str, datetime | None] | None
        ("TBA", None) for a TBA cfp; for a dated one the value of cfp_ext,
        else cfp, with its zone ("2026-10-26 23:59:00 AoE" when the entry has
        no timezone) and the aware instant; None for "None", "Cancelled" and
        anything else that is not a deadline.
    """
    cfp = entry.get("cfp")
    if isinstance(cfp, str) and cfp.strip().lower() in TBA_VALUES:
        return "TBA", None
    deadline = effective_deadline(entry)
    if deadline is None:
        return None
    text = f"{deadline['moment'].strftime(DATEFORMAT)} {deadline['timezone']}"
    if not deadline["timezone_valid"]:
        text += f" (timezone {entry.get('timezone')!r} not recognised)"
    if deadline["field"] == "cfp_ext":
        text += " (cfp_ext)"
    return text, deadline["moment"]


def drift_record(entry: dict, page_url: str, page: dict) -> dict | None:
    """Return a drift record when a CfP page states another deadline than the entry.

    Parameters
    ----------
    entry : dict
        A conferences.yml entry.
    page_url : str
        The CfP page's final URL.
    page : dict
        The page's deadline, from parse_submissions.

    Returns
    -------
    dict | None
        The record, or None when both name the same instant, the entry has no
        deadline to compare, or the page's zone is unknown.
    """
    deadline = entry_deadline(entry)
    if deadline is None:
        return None
    data_text, moment = deadline
    # pretalx shows minutes only: 23:59:59 in the data is its 23:59
    if moment is not None and (page["moment"] is None or page["moment"] == moment.replace(second=0, microsecond=0)):
        return None
    year = as_year(entry.get("year"))
    return {
        "source": "pretalx",
        "kind": "drift",
        "title": entry.get("conference"),
        "url": page_url,
        "year": year,
        "payload": {
            "conference": entry.get("conference"),
            "year": year,
            # The time and zone only: the sentence turns from "close" to
            # "closed" when the deadline passes, which would change the id
            "diffs": {"cfp": {"data": data_text, "source": f"{page['cfp'][:16]} ({page['timezone']})"}},
        },
    }


def pretalx_drift(conferences: Iterable[dict], today: date, pages: PageFetcher) -> list[dict]:
    """Compare upcoming entries' deadlines with their pretalx CfP pages.

    Parameters
    ----------
    conferences : Iterable[dict]
        Entries from conferences.yml.
    today : date
        Entries that ended before this date are left out.
    pages : PageFetcher
        Fetcher for the CfP pages.

    Returns
    -------
    list[dict]
        Drift records, in data order.
    """
    records = []
    for entry in conferences:
        end = as_date(entry.get("end"))
        slug = entry_slug(entry)
        if end is None or end < today or slug is None or entry_deadline(entry) is None:
            continue
        url = PRETALX_CFP.format(slug=slug)
        response = pages.get(url)
        if response is None:
            continue
        if response.status_code != 200:
            report(f"pretalx: {url} returned {response.status_code}, skipped")
            continue
        page = parse_submissions(response.text)
        if page is None:
            report(f"pretalx: {response.url} states no deadline, skipped")
            continue
        if page["moment"] is None:
            report(f"pretalx: {response.url} names an unknown zone {page['timezone']!r}")
        record = drift_record(entry, response.url, page)
        if record is not None:
            records.append(record)
    return records


def pretalx_probe(index: TrackingIndex, today: date, pages: PageFetcher) -> list[dict]:
    """Look for the next edition's CfP page of series that use pretalx.

    Parameters
    ----------
    index : TrackingIndex
        The data's series.
    today : date
        Only series whose latest edition is this year or last year are probed.
    pages : PageFetcher
        Fetcher for the CfP pages.

    Returns
    -------
    list[dict]
        MISSING_EDITION candidate records, by series key.
    """
    records = []
    seen: set[str] = set()
    for key in sorted(index.editions):
        file, latest = index.latest([key])
        year = as_year(latest.get("year"))
        slug = entry_slug(latest)
        if year not in (today.year, today.year - 1) or slug is None:
            continue
        slug_next = next_slug(slug, year)
        conference = latest.get("conference")
        if slug_next is None or slug_next in seen:
            continue
        if index.has_edition({key} | index.name_series(conference), year + 1):
            continue
        seen.add(slug_next)
        response = pages.get(PRETALX_CFP.format(slug=slug_next))
        if response is None or response.status_code == 404:
            continue
        if response.status_code != 200:
            report(f"pretalx: {response.url} returned {response.status_code}, skipped")
            continue
        page = parse_submissions(response.text)
        if page is None and PROPOSALS_CLOSED not in response.text:
            continue
        records.append(
            {
                "source": "pretalx",
                "kind": "candidate",
                "title": f"{conference} {year + 1}",
                "url": response.url,
                "year": year + 1,
                "payload": {
                    "classification": "MISSING_EDITION",
                    "fields": {
                        "conference": conference,
                        "year": year + 1,
                        "cfp_link": response.url,
                        "cfp": page["cfp"] if page else None,
                        "timezone": page["timezone"] if page else None,
                    },
                    "source_id": slug_next,
                    "evidence_url": response.url,
                    "matched": _matched(file, latest, 100),
                    "flags": [],
                },
            },
        )
    return records


def pretalx_leads(
    data: dict[str, list[dict]],
    index: TrackingIndex,
    today: date,
    slug: str | None = None,
) -> list[dict]:
    """Run both pretalx checks, or the deadline check for one CfP page.

    Parameters
    ----------
    data : dict[str, list[dict]]
        Entries keyed "conferences", "archive" and "legacy".
    index : TrackingIndex
        The data's series.
    today : date
        The date the run is for.
    slug : str | None, optional
        A pretalx event slug. When given, only the upcoming entries on that
        event's CfP page get the deadline check, and no next edition is
        probed: a changedetection watch saw that one page change.

    Returns
    -------
    list[dict]
        Drift records, then candidate records.

    Raises
    ------
    SourceError
        When pages were fetched and every one failed.
    """
    pages = PageFetcher()
    conferences = data.get("conferences") or []
    if slug is not None:
        conferences = [entry for entry in conferences if (entry_slug(entry) or "").lower() == slug.lower()]
    records = pretalx_drift(conferences, today, pages)
    if slug is None:
        records.extend(pretalx_probe(index, today, pages))
    if pages.all_failed():
        raise SourceError(f"every one of {pages.attempts} page fetches failed", records)
    return records


def event_start(event: dict) -> date | None:
    """Return a developers.events event's start date.

    Parameters
    ----------
    event : dict
        An event from all-events.json.

    Returns
    -------
    date | None
        The UTC date of ``date[0]`` (epoch milliseconds), or None.
    """
    dates = event.get("date")
    if not isinstance(dates, list) or not dates:
        return None
    first = dates[0]
    if isinstance(first, bool) or not isinstance(first, int | float):
        return None
    try:
        return datetime.fromtimestamp(first / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def is_python_event(event: dict) -> bool:
    """Return whether a developers.events event is about Python.

    Parameters
    ----------
    event : dict
        An event from all-events.json.

    Returns
    -------
    bool
        True for a Python word in the name, unless the name is a financial aid
        programme, a hatchery or a sprint. A "python" tag alone is not enough:
        it marks general events with a Python talk (DevFests, SQLSaturdays),
        which AGENTS.md leaves out.
    """
    name = event.get("name")
    if not isinstance(name, str) or EXCLUDED_NAME.search(name):
        return False
    return bool(PYTHON_NAME.search(name))


def developers_events_records(events: Iterable[Any], index: TrackingIndex, today: date) -> list[dict]:
    """Turn developers.events events into candidate records for untracked editions.

    Parameters
    ----------
    events : Iterable[Any]
        Events from all-events.json.
    index : TrackingIndex
        The data's series.
    today : date
        Events that start before this date are left out.

    Returns
    -------
    list[dict]
        One record per untracked edition, in source order.
    """
    records = []
    seen: set[tuple] = set()
    for event in events:
        if not isinstance(event, dict) or not is_python_event(event):
            continue
        if str(event.get("status") or "").strip().lower() not in ("", "open"):
            continue
        start, link = event_start(event), event.get("hyperlink")
        if start is None or start < today or not isinstance(link, str) or not link.strip():
            continue
        name, year, link = event["name"].strip(), start.year, link.strip()
        if (name, year, link) in seen:
            continue
        seen.add((name, year, link))
        found = index.classify(name, year, link)
        if found is None:
            continue
        # developers.events data is licensed CC BY-NC 4.0. We use it only to find
        # leads: a record carries the event's name, year and link, and nothing
        # else (no dates, deadlines or places), so every value that reaches the
        # data comes from the conference's own pages.
        records.append(
            {
                "source": "developers-events",
                "kind": "candidate",
                "title": name,
                "url": link,
                "year": year,
                "payload": {
                    "classification": found["classification"],
                    "fields": {"conference": clean_name(name), "year": year, "link": link},
                    "source_id": link,
                    "evidence_url": link,
                    "matched": found["matched"],
                    "flags": ["lead-only"],
                },
            },
        )
    return records


def listing_names(line: str) -> list[str]:
    """Return the event names on one line of a watched listing page.

    Parameters
    ----------
    line : str
        One line, e.g. "PyData Amsterdam" or ``"PyCon AT", "PyCon Austria" in Austria``.

    Returns
    -------
    list[str]
        The quoted names when the line quotes any, else the whole line.
    """
    quoted = [name.strip() for name in re.findall(r"[\"“]([^\"“”]+)[\"”]", line) if name.strip()]
    return quoted or [line.strip()]


def listing_records(lines: Iterable[str], page_url: str, index: TrackingIndex) -> list[dict]:
    """Turn the lines a watched listing page added into candidate records.

    A changedetection watch on a page that lists many events keeps one event
    per line, so each added line is one find. A line with a year is checked
    edition by edition; a line without one (a series registry, or a list
    that names no years) only says whether the series exists.

    Parameters
    ----------
    lines : Iterable[str]
        The added lines.
    page_url : str
        The watched page, which is where each find came from.
    index : TrackingIndex
        The data's series.

    Returns
    -------
    list[dict]
        One record per line whose series, or whose edition for the line's
        year, the data does not track, in line order.
    """
    records = []
    seen: set[str] = set()
    for raw in lines:
        # diff_added_clean has no markers; strip them anyway in case a body sends diff_added
        line = re.sub(r"^(?:\(added\)|\+)\s*", "", " ".join(raw.split()))
        if not line or line in seen:
            continue
        seen.add(line)
        names = listing_names(line)
        match = NAME_YEAR.search(line)
        year = int(match[0]) if match else None
        if year is None:
            if any(index.is_tracked_name(name) for name in names):
                continue
            found = {"classification": "NEW_SERIES", "matched": None}
        else:
            results = [index.classify(name, year, None) for name in names]
            if any(result is None for result in results):
                continue
            found = next((r for r in results if r["classification"] != "NEW_SERIES"), results[0])
        records.append(
            {
                "source": "changedetection",
                "kind": "candidate",
                "title": line[:200],
                "url": page_url,
                "year": year,
                "payload": {
                    "classification": found["classification"],
                    "fields": {"conference": clean_name(names[0]), "year": year},
                    "source_id": f"{page_url}#{line}",
                    "evidence_url": page_url,
                    "matched": found["matched"],
                    "flags": ["listing"],
                    "names": names,
                },
            },
        )
    return records


def developers_events_leads(index: TrackingIndex, today: date) -> list[dict]:
    """Fetch developers.events and return its candidate records.

    Parameters
    ----------
    index : TrackingIndex
        The data's series.
    today : date
        The date the run is for.

    Returns
    -------
    list[dict]
        Candidate records.

    Raises
    ------
    SourceError
        When all-events.json cannot be read.
    """
    events = fetch_json(DEVELOPERS_EVENTS)
    if not isinstance(events, list):
        raise SourceError(f"{DEVELOPERS_EVENTS}: not a list of events")
    return developers_events_records(events, index, today)


def front_matter(text: str) -> dict | None:
    """Parse the YAML front matter of a pycon.org registry file.

    Parameters
    ----------
    text : str
        The file, starting with a ``---`` line.

    Returns
    -------
    dict | None
        The front matter, or None when there is none or it is not a mapping.
    """
    match = FRONT_MATTER.match(text)
    if not match:
        return None
    try:
        value = yaml.safe_load(match[1])
    except yaml.YAMLError:
        return None
    return value if isinstance(value, dict) else None


def registry_paths(listing: Any) -> list[str]:
    """Return the national and regional event files of a jsDelivr file listing.

    Parameters
    ----------
    listing : Any
        The listing JSON, {"files": [{"name": "/_national/x.yml"}, ...]}.

    Returns
    -------
    list[str]
        Sorted paths under /_national/ and /_regional/.

    Raises
    ------
    ValueError
        When the listing has no files list.
    """
    files = listing.get("files") if isinstance(listing, dict) else None
    if not isinstance(files, list):
        raise ValueError("no files list")
    names = (item.get("name") for item in files if isinstance(item, dict))
    return sorted(name for name in names if isinstance(name, str) and REGISTRY_PATH.match(name))


def pycon_org_record(meta: dict, raw_url: str, index: TrackingIndex) -> dict | None:
    """Return a registry record for a pycon.org event the data does not track.

    Parameters
    ----------
    meta : dict
        The file's front matter.
    raw_url : str
        Where the file was read.
    index : TrackingIndex
        The data's series.

    Returns
    -------
    dict | None
        The record, or None for a discontinued, nameless or tracked event.
    """
    if str(meta.get("discontinued", "")).strip().lower() in ("true", "yes"):
        return None
    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    name = " ".join(name.split())
    website = str(meta.get("website") or "").strip()
    if index.is_tracked_name(name) or index.link_series(website):
        return None
    return {
        "source": "registry",
        "kind": "registry",
        "title": name,
        "url": website,
        "year": None,
        "payload": {
            "names": [name],
            "change": "untracked",
            "registry": "pycon.org",
            "evidence_url": raw_url,
            "website": website,
        },
    }


def pycon_org_leads(index: TrackingIndex) -> list[dict]:
    """Read the pycon.org registry.

    Parameters
    ----------
    index : TrackingIndex
        The data's series.

    Returns
    -------
    list[dict]
        Registry records for the events the data does not track.

    Raises
    ------
    SourceError
        When the registry's file listing cannot be read.
    """
    listing = fetch_json(PYCON_ORG_FILES)
    try:
        paths = registry_paths(listing)
    except ValueError as error:
        raise SourceError(f"{PYCON_ORG_FILES}: {error}") from error
    records = []
    for path in paths:
        raw_url = f"{PYCON_ORG_RAW}{path}"
        try:
            response = fetch(raw_url)
            response.raise_for_status()
        except requests.RequestException as error:
            report(f"pycon-org: {raw_url}: {first_line(error)}, skipped")
            continue
        meta = front_matter(response.text)
        if meta is None:
            report(f"pycon-org: {raw_url} has no front matter, skipped")
            continue
        record = pycon_org_record(meta, raw_url, index)
        if record is not None:
            records.append(record)
    return records


def collect(source: str, data: dict[str, list[dict]], index: TrackingIndex, today: date) -> list[dict]:
    """Run one source.

    Parameters
    ----------
    source : str
        One of SOURCES.
    data : dict[str, list[dict]]
        Entries keyed "conferences", "archive" and "legacy".
    index : TrackingIndex
        The data's series.
    today : date
        The date the run is for.

    Returns
    -------
    list[dict]
        The source's records, each once.

    Raises
    ------
    ValueError
        For an unknown source.
    """
    if source == "pretalx":
        records = pretalx_leads(data, index, today)
    elif source == "developers-events":
        records = developers_events_leads(index, today)
    elif source == "pycon-org":
        records = pycon_org_leads(index)
    else:
        raise ValueError(f"unknown source {source!r}")
    return _unique(records)


def _unique(records: Iterable[dict]) -> list[dict]:
    """Drop repeated records, keeping the first."""
    seen: set[str] = set()
    unique = []
    for record in records:
        text = json.dumps(record, sort_keys=True, ensure_ascii=False)
        if text not in seen:
            seen.add(text)
            unique.append(record)
    return unique


def write_records(records: Iterable[dict], out: Path | None) -> None:
    """Write records as JSON lines.

    Parameters
    ----------
    records : Iterable[dict]
        Queue records without "id".
    out : Path | None
        File to append to, or None for stdout.
    """
    lines = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    if out is None:
        sys.stdout.write(lines)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface.

    Parameters
    ----------
    argv : list[str] | None
        Arguments (default: sys.argv).

    Returns
    -------
    int
        0, or 1 when the source as a whole could not be read. Records found
        before the failure are still written.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # listing reads the lines a watch saw added, not a source of its own, so collect() leaves it out
    parser.add_argument("source", choices=(*SOURCES, "listing"))
    parser.add_argument("--base", type=Path, default=Path(), help="Repository root (default: current directory)")
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        help="Date to run for, YYYY-MM-DD (default: today in UTC)",
    )
    parser.add_argument("--out", type=Path, help="File to append the records to (default: stdout)")
    parser.add_argument(
        "--url",
        help=(
            "pretalx: check just the entries on this CfP page, which may carry a watch's year template; "
            "listing: the watched page the lines came from"
        ),
    )
    parser.add_argument("--lines", type=Path, help="listing only: file with the lines the watched page added")
    args = parser.parse_args(argv)

    if args.source == "listing":
        if args.lines is None or args.url is None:
            parser.error("the listing source needs --lines and --url")
        try:
            lines = args.lines.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            parser.error(f"cannot read {args.lines}: {error}")
        records = listing_records(lines, args.url, TrackingIndex.from_data(load_data(args.base)))
        write_records(records, args.out)
        print(f"desk_leads: listing: {len(records)} record(s)", file=sys.stderr)
        return 0
    if args.lines is not None:
        parser.error("--lines works with the listing source only")

    slug = None
    if args.url is not None:
        if args.source != "pretalx":
            parser.error("--url works with the pretalx and listing sources only")
        slug = pretalx_slug(resolve_watch_url(args.url))
        if slug is None:
            print(f"desk_leads: pretalx: {args.url} is not a pretalx.com event page, nothing to check", file=sys.stderr)
            return 0

    today = args.today or datetime.now(tz=timezone.utc).date()
    data = load_data(args.base)
    index = TrackingIndex.from_data(data)
    status = 0
    try:
        records = pretalx_leads(data, index, today, slug) if slug else collect(args.source, data, index, today)
    except SourceError as error:
        report(f"{args.source}: {error}")
        records, status = _unique(error.records), 1
    write_records(records, args.out)
    print(f"desk_leads: {args.source}: {len(records)} record(s)", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
