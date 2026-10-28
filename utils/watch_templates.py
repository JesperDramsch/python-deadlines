#!/usr/bin/env python3
"""Choose when a changedetection watch moves on to the next edition's page.

A watch that follows a series from year to year carries a jinja2-time year
template in its URL, ``{% now 'utc' + 'months=N', '%Y' %}``: the year of today
plus N months. N decides on which day the watch stops fetching this edition's
page and starts fetching the next one's (the rollover).

The rollover comes 14 days after the CfP closes, since a deadline can still
move in those two weeks, and at the latest when the conference starts, so the
watch also sees some of the site's updates. With no CfP deadline it is the
start. The template can only change at the start of a month, so the rollover
is the first day of the month on or after that day: never earlier.

This module uses only the standard library.
"""

import re
from datetime import date
from datetime import datetime
from datetime import timedelta

try:
    from desk_queue import WATCH_URL_TEMPLATE
except ImportError:
    from .desk_queue import WATCH_URL_TEMPLATE

# How long after the CfP closes its deadline can still change
SETTLE = timedelta(days=14)


def as_day(value: object) -> date | None:
    """Return the date in a data value: a date, or text starting YYYY-MM-DD; else None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def rollover_day(entry: dict) -> date | None:
    """Return the day a watch on this edition should move on to the next one.

    Parameters
    ----------
    entry : dict
        A conference entry with ``start`` and, when known, ``cfp`` and ``cfp_ext``.

    Returns
    -------
    date | None
        14 days after the effective deadline (``cfp_ext``, else ``cfp``), or
        ``start`` when that comes first or there is no deadline; None without
        a ``start``.
    """
    start = as_day(entry.get("start"))
    if start is None:
        return None
    closes = as_day(entry.get("cfp_ext")) or as_day(entry.get("cfp"))
    if closes is None:
        return start
    return min(closes + SETTLE, start)


def rollover_offset(entry: dict) -> int | None:
    """Return the months offset whose template moves on at this edition's rollover.

    Parameters
    ----------
    entry : dict
        A conference entry with ``year`` and ``start``.

    Returns
    -------
    int | None
        N for ``months=N``: the template gives the edition's year before the
        first day of the month on or after the rollover, and the next year
        from then on. None when the entry has no year or rollover day.
    """
    day = rollover_day(entry)
    year = entry.get("year")
    if day is None or not isinstance(year, int):
        return None
    month = day.year * 12 + day.month - 1  # months since year 0, January being 0
    if day.day > 1:
        month += 1
    return max(0, 12 * (year + 1) - month)


def retemplate(url: str, offset: int) -> str:
    """Set the months offset of a watch URL's year templates.

    Parameters
    ----------
    url : str
        A watch URL.
    offset : int
        The months offset, as ``rollover_offset`` gives it.

    Returns
    -------
    str
        The URL with every month-based or offset-free template set to
        ``months=<offset>``, its ``%Y`` or ``%y`` kept. Templates counted in
        years or days stay as they are.
    """

    def replace(match: re.Match) -> str:
        if match["unit"] not in (None, "months"):
            return match[0]
        return f"{{% now 'utc' + 'months={offset}', '{match['format']}' %}}"

    return WATCH_URL_TEMPLATE.sub(replace, url)
