#!/usr/bin/env python3
"""Point old editions' links to the archived page that shows that edition.

A series that serves every edition from one URL shows only its newest edition
there, so an old edition's link ends up showing a later one. A link that is
gone shows nothing at all. This script replaces both with a Wayback Machine
capture from the edition's own time, and does the weekly link check:

1. **Superseded links.** An edition is superseded once it has ended and a later
   edition of the same ``conference`` is in the data. Each of its URL fields
   (``link``, ``cfp_link``, ``sponsor``, ``finaid``, ``coc``) that holds no
   four-digit year and is not an archive link already is a candidate.
2. **Link check** (skipped with ``--no-probe``). Every live URL in the data is
   requested once, ``WORKERS`` at a time in threads of this one process and at
   most ``PER_HOST`` at a time per site. A URL that redirects to another site is queued for the desk
   (``DESK_QUEUE_OUT``), as before. A URL that is gone (see ``Probe.broken``)
   on an edition that has ended is a candidate.
3. **Replacement.** CDX lists each candidate page's captures: one request per
   host for the pages of a host with several candidates (a filter on the
   archive's side keeps the answer to those pages), one per page otherwise and
   on hosts that carry many sites (``SHARED_HOSTS``). The last capture on or
   before the edition's ``end`` plus 14 days (``wayback.pick_capture``)
   replaces the URL, with its full timestamp. When there is none, the URL stays
   and is listed for the maintainer. When the archive turns the run away, the
   run stops asking at once and leaves the rest for the next run, which finds
   the same candidates again; nothing waits for the archive to come back.
4. **Mastodon.** Accounts that moved are followed to their new address.

Year URLs (``2024.pycon.de``), the editions that are not superseded and links
that are archive links already are never touched.

Run the sort afterwards: this script edits entries in place and leaves the
ordering to ``utils/sort_yaml.py``.

Usage::

    python utils/archive_resolve.py --changes changes.md --needs needs.md
    python utils/archive_resolve.py --no-probe   # superseded links only, no link check
"""

import argparse
import re
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

try:
    import wayback
    from tidy_conf import write_conference_yaml
    from tidy_conf.links import Probe
    from tidy_conf.links import check_mastodon_migration
    from tidy_conf.links import probe
    from tidy_conf.links import record_redirect
    from tidy_conf.links import site_host
except ImportError:
    from . import wayback
    from .tidy_conf import write_conference_yaml
    from .tidy_conf.links import Probe
    from .tidy_conf.links import check_mastodon_migration
    from .tidy_conf.links import probe
    from .tidy_conf.links import record_redirect
    from .tidy_conf.links import site_host

DATA_FILES = ("conferences.yml", "archive.yml", "legacy.yml")
URL_FIELDS = ("link", "cfp_link", "sponsor", "finaid", "coc")
# A four-digit year that is not part of a longer number
YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
DEFAULT_DELAY = 1.0
# Threads for the link check, and how many of them may request one site at a time
WORKERS = 16
PER_HOST = 2
# Hosts that carry many unrelated sites: a whole-host CDX query there would
# scan far more than the few pages asked for, so their pages are looked up one by one
SHARED_HOSTS = frozenset(
    {
        "docs.google.com",
        "drive.google.com",
        "forms.gle",
        "github.com",
        "pydata.org",
        "pretalx.com",
        "sessionize.com",
        "papercall.io",
        "events.linuxfoundation.org",
        "indico.cern.ch",
        "eventbrite.com",
        "meetup.com",
        "easychair.org",
        "youtube.com",
        "bit.ly",
        "goo.gl",
        "tinyurl.com",
        "lu.ma",
        "luma.com",
    },
)
# Most "no capture" lines the rolling PR lists; the rest are counted
NEEDS_LIMIT = 50


@dataclass(frozen=True)
class Candidate:
    """A URL field that should point to an archived copy.

    Attributes
    ----------
    entry : dict
        The edition, edited in place when the URL is replaced
    field : str
        The URL field
    url : str
        The URL it holds
    reason : str
        "superseded" or "broken"
    """

    entry: dict
    field: str
    url: str
    reason: str


@dataclass(frozen=True)
class Outcome:
    """What happened to one candidate.

    Attributes
    ----------
    candidate : Candidate
        The URL field
    new_url : str | None
        The archive link that replaced the URL, or None when it was kept
    detail : str
        Why it was kept, or which capture replaced it
    kind : str
        "replaced"; "no-capture" when the archive has none from the edition's
        time; "failed" when the lookup failed; "deferred" when the archive
        turned the run away before the lookup
    """

    candidate: Candidate
    new_url: str | None
    detail: str
    kind: str = "replaced"


def to_date(value: object) -> date | None:
    """Read a date from a data value.

    Parameters
    ----------
    value : object
        A ``date``, ``datetime`` or an ISO date string

    Returns
    -------
    date | None
        The date, or None when the value is not one
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def live_url(value: object) -> str | None:
    """Return a URL field's value when it is a live link, not an archive link.

    Parameters
    ----------
    value : object
        A URL field's value

    Returns
    -------
    str | None
        The URL, or None for an empty field or an archive link
    """
    text = str(value or "").strip()
    if not text or wayback.is_archived(text):
        return None
    return text


def has_year(url: str) -> bool:
    """Check whether a URL holds a four-digit year, as edition-specific URLs do.

    Parameters
    ----------
    url : str
        A link

    Returns
    -------
    bool
        True for URLs such as ``https://2024.pycon.de/`` or ``https://pycon.hk/2024/``
    """
    return bool(YEAR.search(url))


def superseded(entries: list[dict], today: date) -> list[dict]:
    """Return the editions that have ended and have a later edition in the data.

    Parameters
    ----------
    entries : list[dict]
        Every edition, from all data files
    today : date
        The day of the run

    Returns
    -------
    list[dict]
        The superseded editions, in data order
    """
    latest: dict[str, date] = {}
    for entry in entries:
        start = to_date(entry.get("start"))
        name = entry.get("conference")
        if start and (name not in latest or start > latest[name]):
            latest[name] = start
    result = []
    for entry in entries:
        start, end = to_date(entry.get("start")), to_date(entry.get("end"))
        if start and end and end < today and start < latest[entry.get("conference")]:
            result.append(entry)
    return result


def superseded_candidates(entries: list[dict], today: date) -> list[Candidate]:
    """Return the yearless live URLs of superseded editions.

    Parameters
    ----------
    entries : list[dict]
        Every edition, from all data files
    today : date
        The day of the run

    Returns
    -------
    list[Candidate]
        One candidate per URL field
    """
    candidates = []
    for entry in superseded(entries, today):
        for field in URL_FIELDS:
            url = live_url(entry.get(field))
            if url and not has_year(url):
                candidates.append(Candidate(entry, field, url, "superseded"))
    return candidates


def check_links(
    entries: list[dict],
    today: date,
    request: Callable[[str], Probe] | None = None,
) -> list[Candidate]:
    """Request every live URL once, queue redirects to other sites and return the broken ones.

    Parameters
    ----------
    entries : list[dict]
        Every edition, from all data files
    today : date
        The day of the run; only editions that ended before it get candidates
    request : Callable[[str], Probe] | None
        Requests one URL. Default: ``probe``

    Returns
    -------
    list[Candidate]
        The broken URLs of editions that have ended
    """
    request = request or probe
    by_url: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    for entry in entries:
        for field in URL_FIELDS:
            url = live_url(entry.get(field))
            if url:
                by_url[url].append((entry, field))

    results = request_all(list(by_url), request)
    candidates = []
    for url, uses in by_url.items():
        result = results[url]
        for entry, field in uses:
            if result.redirects_elsewhere:
                record_redirect(
                    url,
                    result.final_url,
                    result.status,
                    conference=entry.get("conference"),
                    year=entry.get("year"),
                    field=field,
                )
            end = to_date(entry.get("end"))
            if result.broken and end and end < today:
                candidates.append(Candidate(entry, field, url, "broken"))
    print(f"Checked {len(by_url)} URLs: {len(candidates)} broken on editions that have ended", flush=True)
    return candidates


def request_all(urls: list[str], request: Callable[[str], Probe]) -> dict[str, Probe]:
    """Request URLs in threads: ``WORKERS`` at once, at most ``PER_HOST`` per site.

    Parameters
    ----------
    urls : list[str]
        The URLs, each once
    request : Callable[[str], Probe]
        Requests one URL

    Returns
    -------
    dict[str, Probe]
        Each URL's result
    """
    limits: dict[str, threading.Semaphore] = {}
    for url in urls:
        limits.setdefault(site_host(url), threading.Semaphore(PER_HOST))

    def one(url: str) -> Probe:
        with limits[site_host(url)]:
            return request(url)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return dict(zip(urls, pool.map(one, urls), strict=True))


def lookup_plan(candidates: list[Candidate]) -> list[tuple[str | None, list[str]]]:
    """Group the candidates' URLs into CDX requests.

    Parameters
    ----------
    candidates : list[Candidate]
        The URL fields to resolve

    Returns
    -------
    list[tuple[str | None, list[str]]]
        One item per request: the host and its URLs for a whole-host request,
        or None and a single URL for a page request; in candidate order
    """
    by_host: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        host = urlparse(candidate.url).hostname or ""
        host = host.lower().removeprefix("www.")
        if candidate.url not in by_host[host]:
            by_host[host].append(candidate.url)
    plan: list[tuple[str | None, list[str]]] = []
    for host, urls in by_host.items():
        if len(urls) > 1 and host and host not in SHARED_HOSTS:
            plan.append((host, urls))
        else:
            plan.extend((None, [url]) for url in urls)
    return plan


def resolve(
    candidates: Iterable[Candidate],
    lookup: Callable[[str], list[str]] | None = None,
    delay: float = DEFAULT_DELAY,
    lookup_host: Callable[[str, list[str], date | None], dict[str, list[str]]] | None = None,
) -> list[Outcome]:
    """Replace each candidate's URL with the capture that shows its edition.

    Parameters
    ----------
    candidates : Iterable[Candidate]
        The URL fields to resolve; a field listed twice is resolved once
    lookup : Callable[[str], list[str]] | None
        Lists one page's capture timestamps. Default: ``wayback.captures``
    delay : float
        Seconds to wait between CDX requests
    lookup_host : Callable[[str, list[str], date | None], dict[str, list[str]]] | None
        Lists the captures of several pages on one host, by ``wayback.page_key``.
        Default: ``wayback.host_captures``

    Returns
    -------
    list[Outcome]
        One outcome per URL field
    """
    lookup = lookup or wayback.captures
    lookup_host = lookup_host or wayback.host_captures
    unique: dict[tuple[int, str], Candidate] = {}
    for candidate in candidates:
        unique.setdefault((id(candidate.entry), candidate.field), candidate)
    todo = list(unique.values())

    limits: dict[str, date] = {}
    for candidate in todo:
        end = to_date(candidate.entry.get("end"))
        if end:
            limit = end + timedelta(days=wayback.END_GRACE_DAYS)
            limits[candidate.url] = max(limit, limits.get(candidate.url, limit))

    found: dict[str, list[str] | wayback.WaybackError] = {}
    blocked: wayback.WaybackBlockedError | None = None
    for i, (host, urls) in enumerate(lookup_plan(todo)):
        if i:
            time.sleep(delay)
        try:
            if host is None:
                found[urls[0]] = lookup(urls[0])
            else:
                by_key = lookup_host(host, urls, max(limits[url] for url in urls if url in limits))
                for url in urls:
                    found[url] = by_key.get(wayback.page_key(url), [])
        except wayback.WaybackBlockedError as e:
            blocked = e
            print(f"The archive turned the run away, stopping lookups: {e}", flush=True)
            break
        except wayback.WaybackError as e:
            for url in urls:
                found[url] = e

    outcomes = []
    for candidate in todo:
        stamps = found.get(candidate.url)
        if stamps is None:
            outcomes.append(Outcome(candidate, None, f"not looked up: {blocked}", "deferred"))
            continue
        if isinstance(stamps, wayback.WaybackError):
            outcomes.append(Outcome(candidate, None, f"lookup failed: {stamps}", "failed"))
            continue
        end = to_date(candidate.entry.get("end"))
        stamp = wayback.pick_capture(stamps, end)
        if not stamp:
            outcomes.append(Outcome(candidate, None, f"no capture on or before {end}", "no-capture"))
            continue
        new_url = wayback.archive_url(stamp, candidate.url)
        candidate.entry[candidate.field] = new_url
        outcomes.append(Outcome(candidate, new_url, f"capture {stamp}"))
    return outcomes


def follow_mastodon(entries: list[dict], check: Callable[[str], str | None] | None = None) -> int:
    """Update Mastodon accounts that moved, checking each account once.

    Parameters
    ----------
    entries : list[dict]
        Every edition, edited in place
    check : Callable[[str], str | None] | None
        Returns an account's new address, or None when it has not moved. Default: ``check_mastodon_migration``

    Returns
    -------
    int
        The number of entries updated
    """
    check = check or check_mastodon_migration
    moved: dict[str, str | None] = {}
    updated = 0
    for entry in entries:
        account = entry.get("mastodon")
        if not account:
            continue
        if account not in moved:
            moved[account] = check(account)
        if moved[account]:
            entry["mastodon"] = moved[account]
            updated += 1
    return updated


def describe(outcome: Outcome) -> str:
    """Describe one outcome as a Markdown list item.

    Parameters
    ----------
    outcome : Outcome
        A resolved or kept URL field

    Returns
    -------
    str
        The line, a checkbox for a URL that was kept
    """
    candidate = outcome.candidate
    name = f"{candidate.entry.get('conference')} {candidate.entry.get('year')}"
    if outcome.new_url:
        return f"- {name}: `{candidate.field}` {candidate.url} → {outcome.new_url}"
    return f"- [ ] {name}: `{candidate.field}` {candidate.url} ({candidate.reason}) kept: {outcome.detail}"


def load(base: Path) -> dict[Path, list[dict]]:
    """Load the three data files.

    Parameters
    ----------
    base : Path
        The repository root

    Returns
    -------
    dict[Path, list[dict]]
        Each file's path and entries
    """
    files = {}
    for name in DATA_FILES:
        path = base / "_data" / name
        if path.exists():
            with path.open(encoding="utf-8") as f:
                files[path] = [entry for entry in yaml.safe_load(f) or [] if isinstance(entry, dict)]
    return files


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        The parser
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", type=Path, default=Path(), help="Repository root")
    parser.add_argument("--today", type=date.fromisoformat, help="Day of the run (default: today, UTC)")
    parser.add_argument("--no-probe", action="store_true", help="Skip the link check and the Mastodon check")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds between CDX lookups")
    parser.add_argument("--changes", type=Path, help="File to write the replaced URLs to, as Markdown")
    parser.add_argument("--needs", type=Path, help="File to write the URLs with no capture to, as a checklist")
    parser.add_argument("--summary", type=Path, help="File to append the run's counts to, as Markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Resolve old editions' links and write the data back when anything changed.

    Parameters
    ----------
    argv : list[str] | None
        Command-line arguments, without the program name

    Returns
    -------
    int
        0; a URL that could not be resolved is reported, not an error
    """
    args = build_parser().parse_args(argv)
    today = args.today or datetime.now(tz=timezone.utc).date()
    files = load(args.base)
    entries = [entry for file_entries in files.values() for entry in file_entries]

    candidates = superseded_candidates(entries, today)
    print(f"{len(candidates)} yearless URLs on superseded editions", flush=True)
    moved = 0
    if not args.no_probe:
        candidates += check_links(entries, today)
        moved = follow_mastodon(entries)

    outcomes = resolve(candidates, delay=args.delay)
    by_kind: dict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        by_kind[outcome.kind].append(outcome)
    for outcome in outcomes:
        print(describe(outcome))
    report = summary(by_kind, moved)
    print(report, flush=True)

    if by_kind["replaced"] or moved:
        for path, file_entries in files.items():
            write_conference_yaml(file_entries, path)
    if args.changes:
        args.changes.write_text("".join(f"{describe(o)}\n" for o in by_kind["replaced"]), encoding="utf-8")
    if args.needs:
        args.needs.write_text(needs_list(by_kind["no-capture"]), encoding="utf-8")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write(report)
    return 0


def needs_list(outcomes: list[Outcome], limit: int = NEEDS_LIMIT) -> str:
    """Render the URLs that have no capture from their edition's time, for the rolling PR.

    Only these need a person: a failed or deferred lookup is tried again on the
    next run. The list is cut at ``limit`` lines to keep the PR body under
    GitHub's size limit; the run log has every line.

    Parameters
    ----------
    outcomes : list[Outcome]
        The "no-capture" outcomes
    limit : int
        The most lines to list

    Returns
    -------
    str
        A Markdown checklist, empty when there is nothing to list
    """
    lines = [f"{describe(outcome)}\n" for outcome in outcomes[:limit]]
    if len(outcomes) > limit:
        lines.append(f"- {len(outcomes) - limit} more without a capture: see the Archive Resolve run log\n")
    return "".join(lines)


def summary(by_kind: dict[str, list[Outcome]], moved: int) -> str:
    """Render the run's counts as Markdown.

    Parameters
    ----------
    by_kind : dict[str, list[Outcome]]
        Outcomes by kind
    moved : int
        Mastodon accounts updated

    Returns
    -------
    str
        The report
    """
    return (
        "## Archive resolve\n\n"
        f"- Pointed to an archived page: {len(by_kind.get('replaced', []))}\n"
        f"- No capture from their edition's time: {len(by_kind.get('no-capture', []))}\n"
        f"- Lookup failed: {len(by_kind.get('failed', []))}\n"
        f"- Left for the next run (the archive turned this one away): {len(by_kind.get('deferred', []))}\n"
        f"- Mastodon accounts moved: {moved}\n"
    )


if __name__ == "__main__":
    sys.exit(main())
