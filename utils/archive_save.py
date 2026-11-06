#!/usr/bin/env python3
"""Ask the Wayback Machine to save conference pages while they show their edition.

A site that serves every edition from one URL shows only its newest edition.
``utils/archive_resolve.py`` later replaces an old edition's links with the
capture that shows that edition, so a capture has to exist from before the
site moves on. This script makes the captures. It saves a URL:

- when it is new: in the data now, but not in the previous version of the data;
- at an edition's save points: 14 days before its CfP closes and on the day it
  closes (``cfp_ext`` when set, else ``cfp``), 30 and 14 days before ``start``,
  on ``start``, and 14 days after ``start``.

The workflow runs weekly and on pushes to the data, so a point is saved on the
first run on or after it: every point after ``--since`` and up to ``--today``.
A CfP with no exact deadline (TBA, None, Cancelled) has no CfP points. Each URL
is saved at most once per run, whichever points it is due for.

Only ``_data/conferences.yml`` is read: an edition stays there until well after
its last save point.

Usage::

    python utils/archive_save.py --previous old-conferences.yml --since 2026-10-31

It needs ``requests`` and PyYAML only.
"""

import argparse
import re
import sys
import time
from collections.abc import Iterable
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import yaml

try:
    import wayback
except ImportError:
    from . import wayback

URL_FIELDS = ("link", "cfp_link", "sponsor", "finaid", "coc")
# Days relative to the CfP deadline and to the start, at which an edition's pages are saved
CFP_POINTS = (-14, 0)
START_POINTS = (-30, -14, 0, 14)
DEADLINE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
DEFAULT_DELAY = 5.0


def to_date(value: object) -> date | None:
    """Read a date from a data value.

    Parameters
    ----------
    value : object
        A ``date``, ``datetime`` or a string starting with ``YYYY-MM-DD``

    Returns
    -------
    date | None
        The date, or None when the value holds no exact date (TBA, None, ...)
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = DEADLINE.match(str(value or "").strip())
    if not match:
        return None
    try:
        return date.fromisoformat(match[1])
    except ValueError:
        return None


def normalise(url: str) -> str:
    """Normalise a URL for comparing data versions: lower case, no trailing slash.

    Parameters
    ----------
    url : str
        A link from the data

    Returns
    -------
    str
        The comparable form
    """
    return str(url).strip().rstrip("/").lower()


def entry_urls(entry: Mapping) -> list[str]:
    """Return an entry's live URLs: its URL fields that are not archive links.

    Parameters
    ----------
    entry : Mapping
        One edition from the data

    Returns
    -------
    list[str]
        The URLs, in field order
    """
    urls = []
    for field in URL_FIELDS:
        value = entry.get(field)
        if value and not wayback.is_archived(str(value)):
            urls.append(str(value).strip())
    return urls


def save_points(entry: Mapping) -> list[date]:
    """Return the dates on which an edition's pages are saved.

    Parameters
    ----------
    entry : Mapping
        One edition from the data

    Returns
    -------
    list[date]
        The save points, sorted; the CfP points only when the CfP has an exact deadline
    """
    points = []
    deadline = to_date(entry.get("cfp_ext")) or to_date(entry.get("cfp"))
    if deadline:
        points.extend(deadline + timedelta(days=days) for days in CFP_POINTS)
    start = to_date(entry.get("start"))
    if start:
        points.extend(start + timedelta(days=days) for days in START_POINTS)
    return sorted(points)


def due_urls(entries: Iterable[Mapping], since: date, today: date) -> list[str]:
    """Return the URLs of editions with a save point after ``since`` and up to ``today``.

    Parameters
    ----------
    entries : Iterable[Mapping]
        Editions from the data
    since : date
        The day of the last successful run; its points were saved then
    today : date
        The day of this run

    Returns
    -------
    list[str]
        The URLs, each once, in data order
    """
    urls = []
    for entry in entries:
        if any(since < point <= today for point in save_points(entry)):
            urls.extend(entry_urls(entry))
    return list(dict.fromkeys(urls))


def new_urls(previous: Iterable[Mapping], current: Iterable[Mapping]) -> list[str]:
    """Return the URLs in the current data that the previous data did not have.

    Parameters
    ----------
    previous : Iterable[Mapping]
        Editions from the previous version of the data
    current : Iterable[Mapping]
        Editions from the data now

    Returns
    -------
    list[str]
        The new URLs, each once, in data order
    """
    known = {normalise(url) for entry in previous for url in entry_urls(entry)}
    urls = [url for entry in current for url in entry_urls(entry) if normalise(url) not in known]
    return list(dict.fromkeys(urls))


def load(path: Path) -> list[dict]:
    """Load a data file, or nothing when it is missing or empty.

    Parameters
    ----------
    path : Path
        A conference data file

    Returns
    -------
    list[dict]
        Its entries
    """
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [entry for entry in data or [] if isinstance(entry, dict)]


def render_summary(results: list[wayback.SaveResult], new_count: int, due_count: int) -> str:
    """Render the run's report as Markdown for the workflow summary.

    Parameters
    ----------
    results : list[wayback.SaveResult]
        One result per URL the run asked the archive to save
    new_count : int
        How many of the URLs were new in the data
    due_count : int
        How many were due for a save point

    Returns
    -------
    str
        The report
    """
    failed = [result for result in results if not result.ok]
    lines = [
        "## Web Archive saves",
        "",
        f"- New URLs: {new_count}",
        f"- URLs at a save point: {due_count}",
        f"- Saved: {len(results) - len(failed)} of {len(results)}",
    ]
    if failed:
        lines.extend(("", "### Not saved", ""))
        lines.extend(f"- {result.url} ({result.detail})" for result in failed)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        The parser
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=Path("_data/conferences.yml"), help="Data file to read")
    parser.add_argument("--previous", type=Path, help="Previous version of the data file, for new URLs")
    parser.add_argument("--since", type=date.fromisoformat, help="Day of the last successful run, for save points")
    parser.add_argument("--today", type=date.fromisoformat, help="Day of this run (default: today, UTC)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds between save requests")
    parser.add_argument("--summary", type=Path, help="File to append the Markdown report to")
    parser.add_argument("--dry-run", action="store_true", help="List the URLs without saving them")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Save the URLs that are new or at a save point.

    Parameters
    ----------
    argv : list[str] | None
        Command-line arguments, without the program name

    Returns
    -------
    int
        0; a page the archive did not save is reported, not an error
    """
    args = build_parser().parse_args(argv)
    today = args.today or datetime.now(tz=timezone.utc).date()
    current = load(args.data)

    fresh = new_urls(load(args.previous), current) if args.previous else []
    due = due_urls(current, args.since, today) if args.since else []
    urls = list(dict.fromkeys(fresh + due))
    print(f"{len(fresh)} new URLs, {len(due)} at a save point, {len(urls)} to save")

    results = []
    for i, url in enumerate(urls):
        if args.dry_run:
            print(f"would save {url}")
            continue
        if i:
            time.sleep(args.delay)
        result = wayback.save(url)
        print(f"{'saved' if result.ok else 'not saved'}: {url} ({result.detail})")
        results.append(result)

    if args.summary and not args.dry_run:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write(render_summary(results, len(fresh), len(due)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
