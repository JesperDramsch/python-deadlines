#!/usr/bin/env python3
"""Build the deadline desk's daily worklist as JSON.

Every piece of work is routed to one skill: ``enricher`` for a series with an
entry in _data/conferences.yml, ``new-year-checker`` for a series known only
from _data/archive.yml or _data/legacy.yml, and ``scouter`` for anything else.
Work comes from four places, in this order in the output:

1. Deadline checks: entries whose effective deadline (cfp_ext, else cfp) fell
   1, 3 or 7 days before today. The deadline is read in the entry's timezone
   (AoE, UTC-12, when unset) and counted from the UTC date it falls on, so a
   check never comes before the deadline has passed: 23:59 AoE on the 12th is
   11:59 UTC on the 13th, and its 1-day check is on the 14th.
2. Queue items read from a checkout of the desk-queue branch, matched to a
   series by name the way cfp_candidates.py matches: after
   normalize_conference_name and the titles.yml mappings, ignoring case,
   accents and whitespace. A matched item takes the year of the entry it is
   bound to: the entry for its own year, else the next edition that has not
   ended. A differing queue year is kept in context["queue_year"].
3. Rotations: entries whose cfp is TBA or TBD (not None, which means no public
   CfP, or Cancelled) and stale series from cfp_candidates.py,
   each picked on one weekday in seven by a hash of its name.
4. One open-ended scouting item, unless --no-scout is given.

Items for the same skill, conference and year are merged. The same data,
queue and date always give the same output. Nothing here touches the network.

It needs the same packages as sort_yaml.py (the pixi or uv environment),
because the title normalisation in tidy_conf imports pandas, pydantic,
thefuzz and tqdm.

Usage::

    python utils/desk_worklist.py --queue-dir ../desk-queue --today 2026-10-14
"""

import argparse
import hashlib
import json
import re
import sys
import zoneinfo
from collections.abc import Iterable
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from datetime import tzinfo
from pathlib import Path
from typing import Any

try:
    from cfp_candidates import entry_keys
    from cfp_candidates import find_candidates
    from cfp_candidates import load_data
    from cfp_candidates import series_key
    from sort_yaml import DATEFORMAT
    from sort_yaml import DEFAULT_CFP_TIME
    from tidy_conf.titles import normalize_conference_name
    from tidy_conf.yaml import load_title_mappings
except ImportError:
    from .cfp_candidates import entry_keys
    from .cfp_candidates import find_candidates
    from .cfp_candidates import load_data
    from .cfp_candidates import series_key
    from .sort_yaml import DATEFORMAT
    from .sort_yaml import DEFAULT_CFP_TIME
    from .tidy_conf.titles import normalize_conference_name
    from .tidy_conf.yaml import load_title_mappings

DATA_PATHS = {
    "conferences": "_data/conferences.yml",
    "archive": "_data/archive.yml",
    "legacy": "_data/legacy.yml",
}
REASONS = (
    "deadline-check",
    "signal",
    "question",
    "redirect",
    "drift",
    "candidate",
    "registry",
    "tba-rotation",
    "stale-series",
    "scout",
)
QUEUE_KINDS = ("signal", "question", "redirect", "drift", "candidate", "registry")
ENRICHER_KINDS = ("question", "redirect", "drift")
CANDIDATE_SKILLS = {"MISSING_EDITION": "new-year-checker", "NEW_SERIES": "scouter", "MAYBE": "scouter"}
CHECK_DAYS = (1, 3, 7)
# cfp values that mean the deadline is still to come. None (no public CfP) and Cancelled are settled.
ROTATION_CFP = ("tba", "tbd")
ROTATION_DAYS = 7
AOE = timezone(timedelta(hours=-12), "AoE")

WATCH_PREFIX = re.compile(r"^\s*\[conference\]\s*", re.IGNORECASE)
WATCH_SUFFIX = re.compile(r"\s+(?:(?P<year>\d{4})\s+)?-\s+(?:main|cfp)\s*$", re.IGNORECASE)
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$")
UTC_OFFSET = re.compile(r"^UTC([+-])(\d{1,2})$")


def clean_watch_title(title: str) -> tuple[str, int | None]:
    """Strip the decoration a changedetection watch title carries.

    Parameters
    ----------
    title : str
        Raw title, e.g. "[Conference] PyCon Greece 2027 - Main".

    Returns
    -------
    tuple[str, int | None]
        The bare name ("PyCon Greece") and the year from the suffix, if any.
    """
    name = WATCH_PREFIX.sub("", title)
    year = None
    match = WATCH_SUFFIX.search(name)
    if match:
        name = name[: match.start()]
        if match["year"]:
            year = int(match["year"])
    return name.strip(), year


def rotation_slot(text: str) -> int:
    """Return the weekday (Monday is 0) on which a rotating item is due.

    Parameters
    ----------
    text : str
        "<conference>|<year>" for a TBA entry, the series name for a stale series.

    Returns
    -------
    int
        A number from 0 to 6, compared with date.weekday().
    """
    return int(hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest(), 16) % ROTATION_DAYS


def timezone_for(name: Any) -> tuple[str, tzinfo, bool]:
    """Resolve an entry's timezone field.

    Parameters
    ----------
    name : Any
        The timezone value: an IANA name, "AoE", "UTC+N" or "UTC-N", or empty.

    Returns
    -------
    tuple[str, tzinfo, bool]
        The label used, the zone, and False when the value was set but not recognised
        (AoE is used instead).
    """
    if not isinstance(name, str) or not name.strip() or name.strip() == "AoE":
        return "AoE", AOE, True
    label = name.strip()
    iana = UTC_OFFSET.sub(lambda m: f"Etc/GMT{'-' if m[1] == '+' else '+'}{int(m[2])}", label)
    try:
        return label, zoneinfo.ZoneInfo(iana), True
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return "AoE", AOE, False


def _deadline_text(value: Any) -> str | None:
    """Return a dated deadline as "YYYY-MM-DD HH:MM:SS", or None for TBA and the like."""
    if isinstance(value, datetime):
        return value.strftime(DATEFORMAT)
    if isinstance(value, date):
        return value.isoformat() + DEFAULT_CFP_TIME
    if isinstance(value, str) and DATED.match(value.strip()):
        text = value.strip()
        return text if " " in text else text + DEFAULT_CFP_TIME
    return None


def effective_deadline(entry: dict) -> dict | None:
    """Return the deadline a deadline check counts from.

    Parameters
    ----------
    entry : dict
        A conferences.yml entry.

    Returns
    -------
    dict | None
        "moment" (aware datetime), "field" ("cfp_ext" or "cfp"), "timezone" (label) and
        "timezone_valid", or None when cfp is not a date.
    """
    if _deadline_text(entry.get("cfp")) is None:
        return None
    label, zone, valid = timezone_for(entry.get("timezone"))
    for field in ("cfp_ext", "cfp"):
        text = _deadline_text(entry.get(field))
        if text is None:
            continue
        try:
            moment = datetime.strptime(text, DATEFORMAT).replace(tzinfo=zone)
        except ValueError:
            continue
        return {"moment": moment, "field": field, "timezone": label, "timezone_valid": valid}
    return None


def _as_date(value: Any) -> date | None:
    """Return a YAML date value as a date, or None."""
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


def _as_year(value: Any) -> int | None:
    """Return a year value as an int, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}", value.strip()):
        return int(value)
    return None


def _jsonable(value: Any) -> Any:
    """Return a copy of a YAML value that json.dumps can write, dates as strings."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.strftime(DATEFORMAT)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _edition_order(entry: dict) -> tuple[int, str]:
    """Sort key that puts the newest edition last."""
    return _as_year(entry.get("year")) or 0, str(entry.get("start") or "")


def _new_item(
    skill: str,
    reason: str,
    conference: str | None = None,
    year: int | None = None,
    *,
    entry: dict | None = None,
    latest_edition: dict | None = None,
    queue_refs: list[dict] | None = None,
    context: dict | None = None,
    ambiguous_matches: list[dict] | None = None,
) -> dict:
    """Create one worklist item in the output key order."""
    item = {
        "id": None,
        "skill": skill,
        "reasons": [reason],
        "conference": conference,
        "year": year,
        "entry": _jsonable(entry) if entry is not None else None,
        "latest_edition": _jsonable(latest_edition) if latest_edition is not None else None,
        "queue_refs": list(queue_refs or []),
        "context": dict(context or {}),
    }
    if ambiguous_matches:
        item["ambiguous_matches"] = ambiguous_matches
    return item


def _item_id(item: dict) -> str:
    """Return a stable id for a merged item."""
    year = "" if item["year"] is None else item["year"]
    text = f"{item['skill']}|{item['conference'] or ''}|{year}"
    if item["reasons"] == ["scout"]:
        text = "scout"
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def _by_name(item: dict) -> tuple[str, int]:
    """Sort key for items within one group."""
    return (item["conference"] or "").casefold(), item["year"] or 0


def deadline_checks(conferences: Iterable[dict], today: date) -> list[dict]:
    """Return an enricher item for each entry whose deadline passed 1, 3 or 7 days ago.

    Days are counted from the UTC date the deadline falls on. The desk runs early in the UTC day, and an
    AoE deadline closes at noon UTC the day after its own date, so a count from that date could send a
    check while the CfP is still open.

    Parameters
    ----------
    conferences : Iterable[dict]
        Entries from conferences.yml.
    today : date
        The UTC date the worklist is for.

    Returns
    -------
    list[dict]
        Items with reason "deadline-check", most recent deadline first.
    """
    items = []
    for entry in conferences:
        deadline = effective_deadline(entry)
        if deadline is None:
            continue
        days_since = (today - deadline["moment"].astimezone(timezone.utc).date()).days
        if days_since not in CHECK_DAYS:
            continue
        context = {
            "effective_deadline": deadline["moment"].isoformat(),
            "deadline_field": deadline["field"],
            "timezone": deadline["timezone"],
            "days_since": days_since,
        }
        if not deadline["timezone_valid"]:
            context["unknown_timezone"] = str(entry.get("timezone"))
        items.append(
            _new_item(
                "enricher",
                "deadline-check",
                entry.get("conference"),
                _as_year(entry.get("year")),
                entry=entry,
                context=context,
            ),
        )
    return sorted(items, key=lambda item: (item["context"]["days_since"], *_by_name(item)))


def tba_rotation(conferences: Iterable[dict], today: date) -> list[dict]:
    """Return an enricher item for each TBA or TBD entry whose rotation slot is today.

    An entry whose cfp is None (no public CfP) or Cancelled has no deadline to find, so it is not rotated.

    Parameters
    ----------
    conferences : Iterable[dict]
        Entries from conferences.yml.
    today : date
        The UTC date the worklist is for.

    Returns
    -------
    list[dict]
        Items with reason "tba-rotation" for entries that start after today.
    """
    items = []
    for entry in conferences:
        if str(entry.get("cfp", "")).lower().strip() not in ROTATION_CFP:
            continue
        start = _as_date(entry.get("start"))
        if start is None or start <= today:
            continue
        if rotation_slot(f"{entry.get('conference')}|{entry.get('year')}") != today.weekday():
            continue
        items.append(
            _new_item("enricher", "tba-rotation", entry.get("conference"), _as_year(entry.get("year")), entry=entry),
        )
    return sorted(items, key=_by_name)


def stale_series(data: dict[str, list[dict]], today: date, known_mappings: dict) -> list[dict]:
    """Return a new-year-checker item for each stale series whose rotation slot is today.

    Parameters
    ----------
    data : dict[str, list[dict]]
        Entries keyed "conferences", "archive" and "legacy".
    today : date
        The UTC date the worklist is for; its year is the lookback reference.
    known_mappings : dict
        Reverse titles.yml mapping from load_title_mappings(reverse=True).

    Returns
    -------
    list[dict]
        Items with reason "stale-series", each with the latest archived edition.
    """
    archive = data.get("archive") or []
    editions: dict[tuple, dict] = {}
    for entry in archive:
        editions.setdefault((entry.get("conference"), entry.get("year")), entry)
    candidates = find_candidates(
        data.get("conferences") or [],
        archive,
        current_year=today.year,
        known_mappings=known_mappings,
    )
    items = [
        _new_item(
            "new-year-checker",
            "stale-series",
            candidate["conference"],
            latest_edition=editions.get((candidate["conference"], candidate["latest_year"])),
            context={"latest_year": candidate["latest_year"]},
        )
        for candidate in candidates
        if rotation_slot(candidate["conference"]) == today.weekday()
    ]
    return sorted(items, key=_by_name)


def _index(data: dict[str, list[dict]], known_mappings: dict) -> tuple[dict, dict]:
    """Index every edition by series.

    Returns ``editions`` (series key to a list of (file, entry)) and ``lookup`` (the key of
    every conference name and alt_name to the set of series keys it names).
    """
    editions: dict[str, list[tuple[str, dict]]] = {}
    lookup: dict[str, set[str]] = {}
    for name, path in DATA_PATHS.items():
        for entry in data.get(name) or []:
            conference = entry.get("conference")
            if not isinstance(conference, str) or not conference.strip():
                continue
            key = series_key(conference, known_mappings)
            editions.setdefault(key, []).append((path, entry))
            for name_key in entry_keys(entry, known_mappings):
                lookup.setdefault(name_key, set()).add(key)
    return editions, lookup


def _queue_names(item: dict, payload: dict) -> list[str]:
    """Return the names a queue item can be matched by, most specific first."""
    raw = []
    matched = payload.get("matched")
    if item.get("kind") == "candidate" and payload.get("classification") == "MISSING_EDITION":
        raw.append(matched.get("conference") if isinstance(matched, dict) else None)
    raw.append(payload.get("conference"))
    fields = payload.get("fields")
    if isinstance(fields, dict):
        raw.append(fields.get("conference"))
    if isinstance(payload.get("names"), list):
        raw.extend(payload["names"])
    raw.extend((item.get("title"), item.get("series")))
    names = []
    for value in raw:
        if not isinstance(value, str):
            continue
        name = clean_watch_title(value)[0]
        if name and name not in names:
            names.append(name)
    if not names and isinstance(item.get("file"), str):
        names.append(Path(item["file"]).stem)
    return names


def _queue_year(item: dict, payload: dict) -> int | None:
    """Return the edition year a queue item is about, when known."""
    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
    title = item.get("title")
    title_year = clean_watch_title(title)[1] if isinstance(title, str) else None
    for value in (item.get("year"), payload.get("year"), fields.get("year"), title_year):
        year = _as_year(value)
        if year is not None:
            return year
    return None


def _match(names: list[str], lookup: dict, known_mappings: dict) -> tuple[str | None, list[str]]:
    """Match names to series: the first unique match wins, else the first ambiguous one."""
    ambiguous = None
    for name in names:
        found = sorted(lookup.get(series_key(name, known_mappings), ()))
        if len(found) == 1:
            return name, found
        if found and ambiguous is None:
            ambiguous = (name, found)
    if ambiguous is not None:
        return ambiguous
    return (names[0] if names else None), []


def _pick_upcoming(upcoming: list[dict], year: int | None, today: date) -> dict:
    """Return the upcoming entry for the year, else the next edition that has not ended.

    When every entry has ended (conferences.yml not yet sorted), the newest one is returned.
    """
    for entry in upcoming:
        if year is not None and _as_year(entry.get("year")) == year:
            return entry
    running = [entry for entry in upcoming if (_as_date(entry.get("end")) or date.max) >= today]
    if running:
        return min(running, key=_edition_order)
    return max(upcoming, key=_edition_order)


def _edition_for(editions: list[tuple[str, dict]], year: int | None) -> dict | None:
    """Return a series' edition for the year, from conferences.yml first, or None."""
    if year is None:
        return None
    for _, entry in editions:
        if _as_year(entry.get("year")) == year:
            return entry
    return None


def _route_queue_item(item: dict, editions: dict, lookup: dict, known_mappings: dict, today: date) -> dict:
    """Turn one queue item into a worklist item.

    A matched item takes its year from the entry it is bound to. Watch titles keep the year
    of the edition they were created for, so a queue year that names no upcoming entry, or
    an edition the new-year-checker already has, is moved to context["queue_year"].

    A question, redirect or drift always goes to the enricher. When its series has no
    upcoming entry, the item is bound to the edition for its year in any data file, and
    otherwise context["no_entry"] says why entry is empty.
    """
    kind = item.get("kind")
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    reason = kind if kind in QUEUE_KINDS else "signal"
    year = _queue_year(item, payload)
    name, matches = _match(_queue_names(item, payload), lookup, known_mappings)
    upcoming = {key: [e for path, e in editions[key] if path == DATA_PATHS["conferences"]] for key in matches}

    if not matches:
        skill = "scouter"
    elif any(upcoming.values()):
        skill = "enricher"
    else:
        skill = "new-year-checker"
    if kind in ENRICHER_KINDS:
        skill = "enricher"
    elif kind == "registry":
        skill = "scouter"
    elif kind == "candidate":
        skill = CANDIDATE_SKILLS.get(payload.get("classification"), skill)

    refs = [{"file": item.get("file"), "id": item.get("id")}]
    if len(matches) != 1:
        conference = normalize_conference_name(name, known_mappings) if name else None
        representatives = []
        for key in matches:
            if upcoming[key]:
                path, entry = DATA_PATHS["conferences"], _pick_upcoming(upcoming[key], year, today)
            else:
                path, entry = max(editions[key], key=lambda edition: _edition_order(edition[1]))
            representatives.append(
                {"conference": entry.get("conference"), "year": _as_year(entry.get("year")), "file": path},
            )
        representatives.sort(key=lambda match: (match["conference"].casefold(), match["year"] or 0))
        context = {"no_entry": "no data file holds this series"} if skill == "enricher" and not matches else {}
        return _new_item(
            skill,
            reason,
            conference or name,
            year,
            queue_refs=refs,
            context=context,
            ambiguous_matches=representatives,
        )

    key = matches[0]
    latest = max(editions[key], key=lambda edition: _edition_order(edition[1]))[1]
    chosen = _pick_upcoming(upcoming[key], year, today) if upcoming[key] else None
    conference = (chosen or latest).get("conference")
    if skill == "enricher" and chosen is not None:
        entry_year = _as_year(chosen.get("year"))
        context = {"queue_year": year} if year is not None and year != entry_year else {}
        return _new_item(skill, reason, conference, entry_year, entry=chosen, queue_refs=refs, context=context)
    if skill == "new-year-checker":
        context = {}
        if year is not None and year <= (_as_year(latest.get("year")) or 0):
            context, year = {"queue_year": year}, None
        return _new_item(skill, reason, conference, year, latest_edition=latest, queue_refs=refs, context=context)
    if skill == "enricher":
        edition = _edition_for(editions[key], year)
        if edition is not None:
            return _new_item(skill, reason, edition.get("conference"), year, entry=edition, queue_refs=refs)
        context = {"no_entry": "no data file holds an edition of this series for this year"}
        return _new_item(skill, reason, conference, year, queue_refs=refs, context=context)
    return _new_item(skill, reason, conference, year, queue_refs=refs)


def _merge(items: list[dict]) -> list[dict]:
    """Merge items for the same (skill, conference, year), keeping first-seen order."""
    merged: dict[tuple, dict] = {}
    for item in items:
        key = (item["skill"], item["conference"], item["year"])
        target = merged.get(key)
        if target is None:
            merged[key] = item
            continue
        target["reasons"] = sorted(set(target["reasons"]) | set(item["reasons"]), key=REASONS.index)
        target["queue_refs"].extend(ref for ref in item["queue_refs"] if ref not in target["queue_refs"])
        for field in ("entry", "latest_edition"):
            if target[field] is None:
                target[field] = item[field]
        for name, value in item["context"].items():
            target["context"].setdefault(name, value)
        if "ambiguous_matches" in item:
            matches = target.setdefault("ambiguous_matches", [])
            matches.extend(match for match in item["ambiguous_matches"] if match not in matches)
    return list(merged.values())


def build_worklist(
    data: dict[str, list[dict]],
    queue_items: Iterable[dict],
    today: date,
    *,
    scout: bool = True,
    generated: str | None = None,
    known_mappings: dict | None = None,
) -> dict:
    """Build the worklist document.

    Parameters
    ----------
    data : dict[str, list[dict]]
        Entries keyed "conferences", "archive" and "legacy", as from cfp_candidates.load_data.
    queue_items : Iterable[dict]
        Queue items as from load_queue: the queue schema fields plus "file"
        ("queue/<key>.json") and "series" (the file's series name).
    today : date
        The UTC date the worklist is for.
    scout : bool
        Add the open-ended scouting item.
    generated : str, optional
        Timestamp for the "generated" field. Defaults to the current UTC time.
    known_mappings : dict, optional
        Reverse titles.yml mapping from load_title_mappings(reverse=True). Loaded when omitted.

    Returns
    -------
    dict
        {"generated", "today", "items"}; see the module docstring for the order.
    """
    if known_mappings is None:
        _, known_mappings = load_title_mappings(reverse=True)
    conferences = data.get("conferences") or []
    editions, lookup = _index(data, known_mappings)

    items = deadline_checks(conferences, today)
    queue_order = sorted(queue_items, key=lambda q: (str(q.get("file")), str(q.get("received")), str(q.get("id"))))
    items.extend(_route_queue_item(queue_item, editions, lookup, known_mappings, today) for queue_item in queue_order)
    items.extend(tba_rotation(conferences, today))
    items.extend(stale_series(data, today, known_mappings))
    items = _merge(items)
    if scout:
        items.append(_new_item("scouter", "scout"))
    for item in items:
        item["id"] = _item_id(item)

    if generated is None:
        generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"generated": generated, "today": today.isoformat(), "items": items}


def load_queue(queue_dir: Path) -> list[dict]:
    """Read every queue/<key>.json file of a desk-queue checkout.

    Parameters
    ----------
    queue_dir : Path
        The checkout, or its queue/ directory.

    Returns
    -------
    list[dict]
        Each item with "file" ("queue/<name>.json") and "series" (from the file) added.
        Unreadable files are reported on stderr and skipped.
    """
    root = queue_dir / "queue" if (queue_dir / "queue").is_dir() else queue_dir
    items = []
    for path in sorted(root.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"desk_worklist: skipping {path}: {error}", file=sys.stderr)
            continue
        if not isinstance(document, dict) or not isinstance(document.get("items"), list):
            print(f"desk_worklist: skipping {path}: no items list", file=sys.stderr)
            continue
        series = document.get("series")
        items.extend(
            {**raw, "file": f"queue/{path.name}", "series": series}
            for raw in document["items"]
            if isinstance(raw, dict)
        )
    return items


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue-dir", type=Path, help="Checkout of the desk-queue branch, or its queue/ directory")
    parser.add_argument("--base", type=Path, default=Path(), help="Repository root (default: current directory)")
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        help="Date to build the worklist for, YYYY-MM-DD (default: today in UTC)",
    )
    parser.add_argument("--no-scout", action="store_true", help="Leave out the open-ended scouting item")
    args = parser.parse_args(argv)

    if args.queue_dir is not None and not args.queue_dir.is_dir():
        parser.error(f"--queue-dir {args.queue_dir} is not a directory")
    today = args.today or datetime.now(tz=timezone.utc).date()
    queue_items = load_queue(args.queue_dir) if args.queue_dir is not None else []
    worklist = build_worklist(load_data(args.base), queue_items, today, scout=not args.no_scout)
    print(json.dumps(worklist, indent=2))


if __name__ == "__main__":
    main()
