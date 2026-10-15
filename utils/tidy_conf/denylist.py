"""Keep conferences on denylisted domains out of the automated imports.

``data/denylist.yml`` lists domains with a reason each: on ``reject``, event
farms and fake events; on ``review``, finds a person has to judge. The critic
applies the same list to the desk's finds. A domain also covers its
subdomains.

An import drops every remote row whose link is on a listed domain. A row on a
``review`` domain is also handed to the desk queue as a candidate (see
queue_out.py), so the maintainer decides it instead of the merge.
"""

import logging
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import yaml

try:
    from tidy_conf.queue_out import append_queue_record
    from tidy_conf.queue_out import utc_now
except ImportError:
    from .queue_out import append_queue_record
    from .queue_out import utc_now

DENYLIST_PATH = Path(__file__).parent / "data" / "denylist.yml"
VERDICTS = ("reject", "review")
LINK_COLUMNS = ("link", "cfp_link")


def load_denylist(path: Path = DENYLIST_PATH) -> dict[str, dict[str, str]]:
    """Read the denylist.

    Parameters
    ----------
    path : Path
        The denylist file.

    Returns
    -------
    dict[str, dict[str, str]]
        {"reject": {domain: reason}, "review": {domain: reason}}, domains lowercased.
    """
    with Path(path).open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    denylist: dict[str, dict[str, str]] = {verdict: {} for verdict in VERDICTS}
    for verdict in VERDICTS:
        for entry in data.get(verdict) or []:
            if isinstance(entry, dict) and isinstance(entry.get("domain"), str):
                denylist[verdict][entry["domain"].strip().lower()] = str(entry.get("reason", ""))
    return denylist


def denied(url: object, denylist: dict[str, dict[str, str]]) -> tuple[str, str, str] | None:
    """Return why a URL is denied, if it is.

    Parameters
    ----------
    url : object
        The link to check; anything but a string is not denied.
    denylist : dict[str, dict[str, str]]
        As load_denylist returns it.

    Returns
    -------
    tuple[str, str, str] | None
        (verdict, domain, reason) for the first listed domain covering the
        URL's host, rejects before reviews, or None.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if "://" not in url:
        url = "//" + url  # "www.example.org/x" still names its host
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not host:
        return None
    for verdict in VERDICTS:
        for domain, reason in denylist.get(verdict, {}).items():
            if host == domain or host.endswith("." + domain):
                return verdict, domain, reason
    return None


def _year(value: object) -> int | None:
    """Return a row's year as an int, or None."""
    try:
        return None if value is None or pd.isna(value) else int(value)
    except (TypeError, ValueError):
        return None


def drop_denied(
    df: pd.DataFrame,
    source_name: str,
    denylist: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Drop remote rows whose link or CfP link is on a denylisted domain.

    Parameters
    ----------
    df : pd.DataFrame
        Remote rows with "conference" and "link" (and optionally "year" and "cfp_link").
    source_name : str
        The remote source, recorded with queued candidates.
    denylist : dict[str, dict[str, str]] | None
        As load_denylist returns it (default: read data/denylist.yml).

    Returns
    -------
    pd.DataFrame
        The rows that are not denied.
    """
    logger = logging.getLogger(__name__)
    if df.empty:
        return df
    if denylist is None:
        denylist = load_denylist()
    keep = []
    for _, row in df.iterrows():
        hit = next(
            (
                (column, found)
                for column in LINK_COLUMNS
                if column in row.index and (found := denied(row[column], denylist))
            ),
            None,
        )
        keep.append(hit is None)
        if hit is None:
            continue
        column, (verdict, domain, reason) = hit
        conference = row.get("conference")
        year = _year(row.get("year"))
        link = row[column] if isinstance(row[column], str) else ""
        logger.warning(f"Skipping {conference} {year or ''}: {domain} is on the denylist ({verdict}: {reason})")
        if verdict == "review":
            append_queue_record(
                {
                    "source": "canonical-import",
                    "kind": "candidate",
                    "received": utc_now(),
                    "title": f"{conference} {year}" if year else str(conference),
                    "url": link,
                    "year": year,
                    "payload": {
                        "classification": "MAYBE",
                        "fields": {"conference": conference, "year": year, "link": link},
                        "source_id": source_name,
                        "evidence_url": link,
                        "matched": None,
                        "flags": [f"denylist-review: {domain}: {reason}"],
                    },
                },
            )
    return df[keep]
