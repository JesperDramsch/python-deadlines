#!/usr/bin/env python3
"""
List active conference series for monitoring.

This script identifies which conference series have had recent activity
and should be prioritized for monitoring.
"""

import argparse
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from pathlib import Path

import yaml


def load_all_conferences(base_path: Path = Path()) -> list[dict]:
    """Load conferences from all data files."""
    conferences = []
    for file in ["_data/conferences.yml", "_data/archive.yml", "_data/legacy.yml"]:
        path = base_path / file
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f) or []
                conferences.extend(data)
    return conferences


def get_series_info(conferences: list[dict]) -> dict:
    """Group conferences by series and extract metadata."""
    series = defaultdict(
        lambda: {
            "years": [],
            "latest_url": None,
            "latest_year": 0,
            "places": set(),
            "category": None,
        },
    )

    for conf in conferences:
        name = conf.get("conference", "")
        year = conf.get("year", 0)

        if not name:
            continue

        series[name]["years"].append(year)
        series[name]["places"].add(conf.get("place", "Unknown"))
        series[name]["category"] = conf.get("sub", "PY")

        if year > series[name]["latest_year"]:
            series[name]["latest_year"] = year
            series[name]["latest_url"] = conf.get("link", "")

    # Sort years
    for name in series:
        series[name]["years"] = sorted(series[name]["years"], reverse=True)

    return dict(series)


def filter_active_series(series: dict, years_threshold: int = 2) -> dict:
    """Filter to only series with recent activity."""
    current_year = datetime.now(tz=timezone.utc).year
    cutoff = current_year - years_threshold

    return {name: info for name, info in series.items() if info["latest_year"] >= cutoff}


def output_for_changedetection(series: dict, output_format: str = "text") -> None:
    """Output series in a format suitable for changedetection.io import."""
    if output_format == "json":
        import json

        urls = [{"url": info["latest_url"], "title": name} for name, info in series.items() if info["latest_url"]]
        print(json.dumps(urls, indent=2))

    elif output_format == "csv":
        print("title,url,category")
        for name, info in sorted(series.items()):
            if info["latest_url"]:
                print(f'"{name}","{info["latest_url"]}","{info["category"]}"')

    else:  # text
        print(f"{'Conference':<40} {'Latest':<6} {'Years':<5} {'URL'}")
        print("-" * 100)
        for name, info in sorted(series.items(), key=lambda x: -x[1]["latest_year"]):
            years_count = len(info["years"])
            url = info["latest_url"][:50] + "..." if len(info["latest_url"] or "") > 50 else info["latest_url"]
            print(f"{name:<40} {info['latest_year']:<6} {years_count:<5} {url}")


def main():
    parser = argparse.ArgumentParser(description="List active conference series for monitoring")
    parser.add_argument(
        "--years",
        type=int,
        default=2,
        help="Consider series active if they had an instance within this many years (default: 2)",
    )
    parser.add_argument("--all", action="store_true", help="Show all series, not just active ones")
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--category", type=str, help="Filter by category (PY, SCIPY, DATA, WEB, BIZ, GEO)")

    args = parser.parse_args()

    # Load and process
    conferences = load_all_conferences()
    series = get_series_info(conferences)

    if not args.all:
        series = filter_active_series(series, args.years)

    if args.category:
        series = {name: info for name, info in series.items() if info["category"] == args.category.upper()}

    # Output
    print(f"# Found {len(series)} {'active ' if not args.all else ''}conference series\n")
    output_for_changedetection(series, args.format)


if __name__ == "__main__":
    main()
