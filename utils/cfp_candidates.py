#!/usr/bin/env python3
"""Emit conference series that likely need a new edition checked.

A candidate is a series with no entry in _data/conferences.yml (nothing
upcoming or TBA) whose latest archived edition is recent enough that the
series is plausibly still alive. Output is JSON on stdout, newest first.

A series counts as tracked when its name or any of its alt_names matches the
name or alt_name of an entry in _data/conferences.yml. Names are compared
after normalize_conference_name (which applies the titles.yml mappings),
ignoring case, accents and whitespace, so "Xtreme Python" and "XtremePython"
are the same series.

Intended for the cfp-scout routine: run once at session start, then work
from the JSON instead of re-reading the data files.
"""

import argparse
import json
from collections.abc import Iterable
from datetime import datetime
from datetime import timezone
from pathlib import Path

import yaml

try:
    from tidy_conf.titles import normalize_conference_name
    from tidy_conf.utils import fold_name
    from tidy_conf.yaml import load_title_mappings
except ImportError:
    from .tidy_conf.titles import normalize_conference_name
    from .tidy_conf.utils import fold_name
    from .tidy_conf.yaml import load_title_mappings

CARRY_FIELDS = ("link", "place", "sub", "alt_name", "cfp_link")
DATA_FILES = ("conferences", "archive", "legacy")


def load(path: Path) -> list[dict]:
    """Load one conference data file.

    Parameters
    ----------
    path : Path
        Location of the YAML file.

    Returns
    -------
    list[dict]
        The entries in the file, or an empty list when the file is missing or empty.
    """
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def load_data(base: Path) -> dict[str, list[dict]]:
    """Load conferences.yml, archive.yml and legacy.yml from a repository checkout.

    Parameters
    ----------
    base : Path
        Repository root.

    Returns
    -------
    dict[str, list[dict]]
        Entries keyed by file stem: "conferences", "archive" and "legacy".
    """
    return {name: load(base / "_data" / f"{name}.yml") for name in DATA_FILES}


def series_key(name: str, known_mappings: dict | None = None) -> str:
    """Return the key two names of the same series share.

    Parameters
    ----------
    name : str
        A conference name, alt_name or raw title.
    known_mappings : dict, optional
        Reverse titles.yml mapping from load_title_mappings(reverse=True). Loaded when omitted.

    Returns
    -------
    str
        The normalised name with case, accents and whitespace folded away.
    """
    if known_mappings is None:
        _, known_mappings = load_title_mappings(reverse=True)
    return "".join(fold_name(normalize_conference_name(name, known_mappings)).split())


def entry_names(entry: dict) -> list[str]:
    """Return the conference name and alt_names of one entry.

    Parameters
    ----------
    entry : dict
        A conference entry.

    Returns
    -------
    list[str]
        Non-empty names, conference first.
    """
    alt_names = entry.get("alt_name")
    if not isinstance(alt_names, list):
        alt_names = [alt_names]
    return [name for name in (entry.get("conference"), *alt_names) if isinstance(name, str) and name.strip()]


def entry_keys(entry: dict, known_mappings: dict) -> set[str]:
    """Return the series keys of an entry's conference name and alt_names.

    Parameters
    ----------
    entry : dict
        A conference entry.
    known_mappings : dict
        Reverse titles.yml mapping from load_title_mappings(reverse=True).

    Returns
    -------
    set[str]
        One key per distinct name.
    """
    return {series_key(name, known_mappings) for name in entry_names(entry)}


def tracked_keys(conferences: Iterable[dict], known_mappings: dict) -> set[str]:
    """Return the series keys of every name and alt_name in conferences.yml.

    Parameters
    ----------
    conferences : Iterable[dict]
        Entries from conferences.yml.
    known_mappings : dict
        Reverse titles.yml mapping from load_title_mappings(reverse=True).

    Returns
    -------
    set[str]
        Keys that count as tracked.
    """
    keys: set[str] = set()
    for entry in conferences:
        keys |= entry_keys(entry, known_mappings)
    return keys


def find_candidates(
    conferences: list[dict],
    archive: list[dict],
    current_year: int,
    lookback: int = 2,
    known_mappings: dict | None = None,
) -> list[dict]:
    """Find archived series without an entry in conferences.yml.

    Parameters
    ----------
    conferences : list[dict]
        Entries from conferences.yml.
    archive : list[dict]
        Entries from archive.yml.
    current_year : int
        Year the lookback counts back from.
    lookback : int
        Only report series whose latest edition is at most this many years before current_year.
    known_mappings : dict, optional
        Reverse titles.yml mapping from load_title_mappings(reverse=True). Loaded when omitted.

    Returns
    -------
    list[dict]
        One dict per series with "conference", "latest_year" and the CARRY_FIELDS of the
        latest edition, newest first, then by name.
    """
    if known_mappings is None:
        _, known_mappings = load_title_mappings(reverse=True)
    tracked = tracked_keys(conferences, known_mappings)
    cutoff = current_year - lookback

    series: dict[str, dict] = {}
    for conf in archive:
        name = conf.get("conference")
        if not isinstance(name, str) or not name.strip():
            continue
        info = series.setdefault(series_key(name, known_mappings), {"keys": set(), "latest": None})
        info["keys"] |= entry_keys(conf, known_mappings)
        if info["latest"] is None or (conf.get("year") or 0) > (info["latest"].get("year") or 0):
            info["latest"] = conf

    candidates = []
    for info in series.values():
        latest = info["latest"]
        latest_year = latest.get("year") or 0
        if info["keys"] & tracked or latest_year < cutoff:
            continue
        candidate = {"conference": latest["conference"], "latest_year": latest_year}
        candidate.update({k: latest[k] for k in CARRY_FIELDS if latest.get(k)})
        candidates.append(candidate)

    return sorted(candidates, key=lambda x: (-x["latest_year"], x["conference"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookback",
        type=int,
        default=2,
        help="Only consider series whose latest edition is within this many years (default: 2)",
    )
    parser.add_argument("--base", type=Path, default=Path(), help="Repository root")
    args = parser.parse_args()

    current_year = datetime.now(tz=timezone.utc).year
    candidates = find_candidates(
        load(args.base / "_data/conferences.yml"),
        load(args.base / "_data/archive.yml"),
        current_year=current_year,
        lookback=args.lookback,
    )
    print(json.dumps({"generated": f"{current_year}", "count": len(candidates), "candidates": candidates}, indent=2))


if __name__ == "__main__":
    main()
