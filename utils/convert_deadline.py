#!/usr/bin/env python3
"""Re-express a CfP deadline in another time zone at the same instant.

A conference entry has one ``timezone`` for both ``cfp`` and ``cfp_ext``.
When a deadline conflict (AGENTS.md "Deadline conflicts") sets a new zone,
the existing ``cfp`` must keep its instant, so it is converted here rather
than by hand. No zone means Anywhere on Earth (UTC-12), as on the site.

This module uses only the standard library.

Usage::

    python utils/convert_deadline.py "2026-10-26 23:59:00" --from AoE --to America/Los_Angeles
    2026-10-27 04:59:00

Exit codes: 0 when the converted deadline was printed, 2 when an argument is
not usable.
"""

import argparse
import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

FORMAT = "%Y-%m-%d %H:%M:%S"
AOE = timezone(timedelta(hours=-12), "AoE")


def zone(name: str) -> timezone | ZoneInfo:
    """Return the zone a ``timezone`` value names.

    Parameters
    ----------
    name : str
        An IANA name, or ``AoE`` (also an empty string) for Anywhere on Earth.

    Returns
    -------
    timezone | ZoneInfo
        The zone.

    Raises
    ------
    ValueError
        When ``name`` is not an IANA zone.
    """
    if name in ("", "AoE"):
        return AOE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"not an IANA time zone: {name!r}") from error


def convert(deadline: str, source: str, target: str) -> str:
    """Convert a deadline from one zone to another, keeping its instant.

    Parameters
    ----------
    deadline : str
        The deadline as the data writes it, ``YYYY-MM-DD HH:MM:SS``.
    source : str
        The zone it is stated in: an IANA name, or ``AoE``.
    target : str
        The zone to state it in: an IANA name, or ``AoE``.

    Returns
    -------
    str
        The same instant in ``target``, as ``YYYY-MM-DD HH:MM:SS``.

    Raises
    ------
    ValueError
        When ``deadline`` is not in that format or a zone is not known.
    """
    local = datetime.strptime(deadline, FORMAT).replace(tzinfo=zone(source))
    return local.astimezone(zone(target)).strftime(FORMAT)


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface.

    Parameters
    ----------
    argv : list[str] | None, optional
        The arguments, by default those of the process.

    Returns
    -------
    int
        The exit code, as the module docstring describes.
    """
    parser = argparse.ArgumentParser(description="Re-express a CfP deadline in another time zone.")
    parser.add_argument("deadline", help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--from", dest="source", required=True, help="IANA zone, or AoE")
    parser.add_argument("--to", dest="target", required=True, help="IANA zone, or AoE")
    args = parser.parse_args(argv)
    try:
        print(convert(args.deadline, args.source, args.target))
    except ValueError as error:
        print(f"convert_deadline: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
