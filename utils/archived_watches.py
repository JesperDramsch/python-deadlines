#!/usr/bin/env python3
"""Find the changedetection watches on links the data replaced with an archived copy.

When a conference link dies or its domain is taken over, the data keeps the
Internet Archive copy instead (``https://web.archive.org/web/<timestamp>/<url>``).
A watch that still fetches the old URL only reports the dead page or the new
owner's content, so the sync pauses it. Pausing keeps its history and can be
undone.

A watch is paused only when the page it fetches today is such a link and no
entry still holds that URL as a live link. A watch whose URL carries a year
template is compared by the page the template gives today, so a series watch
that has moved on to a later edition stays on when an old edition's page is
archived. URLs compare ignoring scheme, ``www.``, case and a trailing slash.

This module uses only the standard library; the sync workflow loads the data.
"""

import re
from collections.abc import Iterable
from collections.abc import Mapping
from datetime import date

try:
    from desk_queue import resolve_watch_url
except ImportError:
    from .desk_queue import resolve_watch_url

ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(?P<url>.+)$", re.IGNORECASE)
URL_FIELDS = ("link", "cfp_link")


def archived_original(url: object) -> str | None:
    """Return the URL an Internet Archive link holds, or None for any other link.

    Parameters
    ----------
    url : object
        A link from the data.

    Returns
    -------
    str | None
        The archived URL, or None when ``url`` is not an archive link.
    """
    if not isinstance(url, str):
        return None
    match = ARCHIVED.match(url.strip())
    return match["url"] if match else None


def normalise_url(url: str) -> str:
    """Return a URL without scheme, ``www.``, trailing slash or case, for comparing.

    Parameters
    ----------
    url : str
        A URL.

    Returns
    -------
    str
        The comparable form.
    """
    url = re.sub(r"^https?://", "", url.strip().lower())
    return url.removeprefix("www.").rstrip("/")


def replaced_links(before: Iterable[Mapping], after: Iterable[Mapping]) -> list[tuple[str, int | None, str]]:
    """List the links a change replaced with their archived copy.

    Parameters
    ----------
    before : Iterable[Mapping]
        The entries of the three data files before the change.
    after : Iterable[Mapping]
        The entries after it.

    Returns
    -------
    list[tuple[str, int | None, str]]
        (``conference``, ``year``, old link) for each ``link`` or ``cfp_link``
        that now holds an archived copy of the link it held before.
    """
    old = {(entry.get("conference"), entry.get("year")): entry for entry in before}
    replaced = []
    for entry in after:
        key = (entry.get("conference"), entry.get("year"))
        previous = old.get(key)
        if previous is None:
            continue
        for field in URL_FIELDS:
            was, original = previous.get(field), archived_original(entry.get(field))
            if (
                isinstance(was, str)
                and original
                and archived_original(was) is None
                and normalise_url(original) == normalise_url(was)
            ):
                replaced.append((str(key[0]), key[1], was))
    return replaced


def live_links(entries: Iterable[Mapping]) -> set[str]:
    """Return the links the data still uses live, in comparable form.

    Parameters
    ----------
    entries : Iterable[Mapping]
        The entries of the three data files.

    Returns
    -------
    set[str]
        Every ``link`` and ``cfp_link`` that is not an archive link, normalised.
    """
    return {
        normalise_url(url)
        for entry in entries
        for field in URL_FIELDS
        if isinstance(url := entry.get(field), str) and archived_original(url) is None
    }


def watches_to_pause(
    watches: Mapping[str, Mapping],
    dead_links: Iterable[str],
    live: set[str],
    today: date | None = None,
) -> list[str]:
    """Return the watches that fetch a dead link and are not paused yet.

    Parameters
    ----------
    watches : Mapping[str, Mapping]
        Watch uuid to watch, as ``GET /api/v1/watch`` returns them.
    dead_links : Iterable[str]
        Links the data replaced with an archived copy.
    live : set[str]
        Links the data still uses, as ``live_links`` returns them.
    today : date | None, optional
        The day a year template is filled in for, by default today in UTC.

    Returns
    -------
    list[str]
        The uuids to pause, sorted.
    """
    dead = {normalise_url(link) for link in dead_links} - live
    found = []
    for uuid, watch in watches.items():
        url = watch.get("url")
        if not isinstance(url, str) or watch.get("paused"):
            continue
        if normalise_url(resolve_watch_url(url, today)) in dead:
            found.append(uuid)
    return sorted(found)
