#!/usr/bin/env python3
"""Emit conference series that likely need a new edition checked.

A candidate is a series with no entry in _data/conferences.yml (nothing
upcoming or TBA) whose latest archived edition is recent enough that the
series is plausibly still alive. Output is JSON on stdout, newest first.

Intended for the cfp-scout routine: run once at session start, then work
from the JSON instead of re-reading the data files.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

CARRY_FIELDS = ("link", "place", "sub", "alt_name", "cfp_link")


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return yaml.safe_load(fh) or []


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
    cutoff = current_year - args.lookback

    current_names = {c["conference"] for c in load(args.base / "_data/conferences.yml")}

    latest: dict[str, dict] = {}
    for conf in load(args.base / "_data/archive.yml"):
        name = conf.get("conference")
        year = conf.get("year") or 0
        if not name or name in current_names:
            continue
        if year > latest.get(name, {}).get("latest_year", 0):
            entry = {"conference": name, "latest_year": year}
            entry.update({k: conf[k] for k in CARRY_FIELDS if conf.get(k)})
            latest[name] = entry

    candidates = sorted(
        (info for info in latest.values() if info["latest_year"] >= cutoff),
        key=lambda x: (-x["latest_year"], x["conference"]),
    )
    print(json.dumps({"generated": f"{current_year}", "count": len(candidates), "candidates": candidates}, indent=2))


if __name__ == "__main__":
    main()
