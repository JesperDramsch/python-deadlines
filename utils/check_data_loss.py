"""Guard against silent conference loss during automated data merges.

Compares snapshots of the conference data files taken before a merge with the
files after the merge. Every (conference, year) pair that existed before must
still exist afterwards - in any of the given files, since conferences may
legitimately move between conferences.yml, archive.yml and legacy.yml.

Exits non-zero if any conference disappeared, so CI can block the commit.
A legitimate rename (via titles.yml mappings) will also trip this check;
that is intentional - renames of existing entries should be reviewed by a
human, not auto-committed.
"""

import argparse
import sys
from pathlib import Path

import yaml


def load_conference_keys(paths: list[str]) -> set[tuple[str, int | str]]:
    """Collect (conference, year) pairs from a list of YAML data files.

    Missing files are skipped, so the same invocation works whether or not
    optional files like legacy.yml exist.
    """
    keys = set()
    for path in paths:
        file = Path(path)
        if not file.exists():
            continue
        with file.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            conference = entry.get("conference")
            year = entry.get("year")
            if conference:
                keys.add((str(conference).strip(), year))
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail if conferences disappeared from the data files.",
    )
    parser.add_argument(
        "--before",
        nargs="+",
        required=True,
        help="Data files snapshotted before the merge",
    )
    parser.add_argument(
        "--after",
        nargs="+",
        required=True,
        help="Data files after the merge",
    )
    args = parser.parse_args()

    before = load_conference_keys(args.before)
    after = load_conference_keys(args.after)
    missing = before - after

    if missing:
        print(
            f"ERROR: {len(missing)} conference(s) disappeared during the merge:",
            file=sys.stderr,
        )
        for conference, year in sorted(missing, key=str):
            print(f"  - {conference} ({year})", file=sys.stderr)
        print(
            "\nAn automated merge must never delete or rename existing conferences.\n"
            "This usually means two distinct conferences were fuzzy-matched into one\n"
            "(e.g. 'PyCon Africa' vs 'PyCon South Africa'). Add the pair to\n"
            "utils/tidy_conf/data/rejections.yml, or if the rename is intentional,\n"
            "apply it manually.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all {len(before)} conference entries survived the merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
