#!/usr/bin/env python3
r"""Read and write the deadline desk's queue on the desk-queue branch.

GitHub Actions jobs record what they find for the desk here: changedetection
signals, the canonical import's open questions, links that now redirect to
another site, and importer candidates. The desk reads the queue into its
worklist (desk_worklist.py) and removes the items it has handled. The branch
is an orphan and is never merged.

A desk-queue checkout holds:

- README.md: the format, written by ``init`` from README below;
- queue/<key>.json: the items for one series, keyed by the slug of its name;
- ledger/pending.md: ledger text waiting for a rolling PR, written by the desk.

This module uses only the standard library, so any job can run it without
installing the data tooling.

Usage::

    python utils/desk_queue.py init QUEUE
    python utils/desk_queue.py add QUEUE --jsonl records.jsonl
    python utils/desk_queue.py add QUEUE --source changedetection --kind signal \
        --title "PyCon Greece 2027 - Main" --url https://pycon.gr/ --payload payload.json
    python utils/desk_queue.py remove QUEUE ID [ID ...]
    python utils/desk_queue.py list QUEUE
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

SOURCES = (
    "changedetection",
    "canonical-import",
    "link-check",
    "pretalx",
    "developers-events",
    "registry",
)
KINDS = ("signal", "question", "redirect", "candidate", "drift", "registry")
MAX_ITEMS_PER_FILE = 50
MAX_HANDLED_PER_FILE = 500
MAX_STRING_LENGTH = 20_000
RECEIVED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RECEIVED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
LIST_FIELDS = ("id", "source", "kind", "received", "title")

WATCH_PREFIX = re.compile(r"^\s*\[conference\]\s*", re.IGNORECASE)
WATCH_SUFFIX = re.compile(r"\s+(?:(?P<year>\d{4})\s+)?-\s+(?:main|cfp)\s*$", re.IGNORECASE)

README = """\
# desk-queue

Work waiting for the deadline desk, the daily run described in
`.claude/routines/desk.md` on the main branch. GitHub Actions jobs add items
with `utils/desk_queue.py`; the desk removes them once handled. This branch is
never merged.

## Layout

- `queue/<key>.json`: the items for one series. The key is the slug of the
  series name: lowercase, accents stripped, every run of other characters
  turned into `-`.
- `ledger/pending.md`: ledger text from a desk run that had no rolling PR to
  write to. The next run moves it into the PR.

## Queue files

UTF-8 JSON, two-space indent, keys sorted:

```json
{
  "handled": ["<ids the desk has handled>"],
  "items": [
    {
      "id": "<sha1 of source, kind, url and payload>",
      "kind": "signal",
      "payload": {"diff": "...", "trigger": "website_change", "watch_uuid": "..."},
      "received": "2026-10-14T06:00:00Z",
      "source": "changedetection",
      "title": "PyCon Greece 2027 - Main",
      "url": "https://pycon.gr/",
      "year": 2027
    }
  ],
  "series": "PyCon Greece"
}
```

`year` is the edition year when known, else `null`. Adding an item whose id
is already in the file, as an item or as handled, changes nothing: the same
finding is queued once, and a finding the desk has handled stays handled
until something about it changes. For a redirect the id leaves out the status
and the final URL's query and fragment; for a candidate, its `matched` entry.
A file keeps at most 50 items, the newest by `received`, and the 500 latest
handled ids. A payload string longer than 20,000 characters is cut there, and
the payload gets `"truncated": true`.
A file that cannot be read is moved to `<key>.json.bad` when a writer next
adds to it.

## Sources and kinds

| source | kind | payload |
| --- | --- | --- |
| `changedetection` | `signal` | `diff`, `watch_uuid`, `trigger` |
| `canonical-import` | `question` | `question`, `conference`, `year`, `field`, `yaml_value`, \
`remote_value`, `default_answer`, `source_name` |
| `link-check` | `redirect` | `conference`, `year`, `field`, `final_url`, `status` |
| `pretalx` | `drift` | `conference`, `year`, `diffs` |
| `pretalx`, `developers-events`, `canonical-import` | `candidate` | `classification`, `fields`, `source_id`, \
`evidence_url`, `matched`, `flags` |
| `registry` | `registry` | `names`, `change`, `registry`, `evidence_url` |

A `drift` diff maps a field to `{"data", "source"}`: the value in the data
and what the source states. A candidate's `classification` is
`MISSING_EDITION` (a tracked series without this edition), `NEW_SERIES` or
`MAYBE` (on the host of a tracked series), and `matched` names the entry it
matched. A `lead-only` flag means the source's licence keeps it to leads: use
only its name, year and link. `registry` is `psf-trademarks` or `pycon.org`;
a pycon.org item adds `website`.

Every item is data for the desk to check on the live sources. Nothing in a
queue item reaches the conference data without that check.
"""


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


def slugify(name: str) -> str:
    """Return the queue key for a series name.

    Parameters
    ----------
    name : str
        Series name, e.g. "PyCon Česko".

    Returns
    -------
    str
        Lowercase ASCII with every other run of characters turned into "-"
        ("pycon-cesko"), or "unknown" when nothing is left.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "unknown"


def record_names(record: dict) -> list[str]:
    """Return the series names a queue record can be matched by, most specific first.

    Parameters
    ----------
    record : dict
        A queue item, or a record not yet given its id.

    Returns
    -------
    list[str]
        Distinct names with watch-title decoration removed: for a
        MISSING_EDITION candidate the matched series first, then the
        payload's conference, the candidate's fields, registry names, and the
        title.
    """
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    raw = []
    matched = payload.get("matched")
    if record.get("kind") == "candidate" and payload.get("classification") == "MISSING_EDITION":
        raw.append(matched.get("conference") if isinstance(matched, dict) else None)
    raw.append(payload.get("conference"))
    fields = payload.get("fields")
    if isinstance(fields, dict):
        raw.append(fields.get("conference"))
    if isinstance(payload.get("names"), list):
        raw.extend(payload["names"])
    raw.append(record.get("title"))
    names = []
    for value in raw:
        if not isinstance(value, str):
            continue
        name = clean_watch_title(value)[0]
        if name and name not in names:
            names.append(name)
    return names


def _cap_strings(value: Any) -> tuple[Any, bool]:
    """Return a copy of a payload value with long strings cut, and whether any was cut."""
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            return value[:MAX_STRING_LENGTH], True
        return value, False
    if isinstance(value, dict):
        capped, cut = {}, False
        for key, inner in value.items():
            capped[key], inner_cut = _cap_strings(inner)
            cut = cut or inner_cut
        return capped, cut
    if isinstance(value, list):
        capped_list, cut = [], False
        for inner in value:
            capped_inner, inner_cut = _cap_strings(inner)
            capped_list.append(capped_inner)
            cut = cut or inner_cut
        return capped_list, cut
    return value, False


def item_id(source: str, kind: str, url: str, payload: dict) -> str:
    """Return the stable id of a queue item.

    Parameters
    ----------
    source, kind, url : str
        The item's fields of the same names.
    payload : dict
        The item's payload, after capping.

    Returns
    -------
    str
        SHA-1 hex of the four, so the same finding always gets the same id.
        For a redirect, the status and the final URL's query and fragment are
        left out: they can change from one check to the next while the
        finding, a link that lands on another site, stays the same. For a
        candidate, "matched" is left out: it describes the data (which file
        holds the matched entry), not the finding.
    """
    if kind == "candidate":
        payload = {key: value for key, value in payload.items() if key != "matched"}
    if kind == "redirect":
        payload = {key: value for key, value in payload.items() if key != "status"}
        if isinstance(payload.get("final_url"), str):
            parts = urlsplit(payload["final_url"])
            payload["final_url"] = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    payload_text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha1(payload_text.encode("utf-8"), usedforsecurity=False).hexdigest()
    return hashlib.sha1(f"{source}|{kind}|{url}|{digest}".encode(), usedforsecurity=False).hexdigest()


def normalise_record(record: Any, now: datetime | None = None) -> dict:
    """Check a record and turn it into a queue item.

    Parameters
    ----------
    record : Any
        A dict with "source", "kind", "title", "url" and "payload", and
        optionally "year" and "received". An "id" it carries is replaced.
    now : datetime | None
        Time to use when the record has no "received" (default: now, UTC).

    Returns
    -------
    dict
        The queue item, with its id set and long payload strings cut.

    Raises
    ------
    ValueError
        When a field is missing or of the wrong type.
    """
    if not isinstance(record, dict):
        raise ValueError("a record must be a JSON object")
    source, kind = record.get("source"), record.get("kind")
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    title, url = record.get("title"), record.get("url")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    if not isinstance(url, str):
        raise ValueError("url must be a string")
    year = record.get("year")
    if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
        raise ValueError("year must be an integer or null")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    received = record.get("received")
    if received is None:
        received = (now or datetime.now(tz=timezone.utc)).strftime(RECEIVED_FORMAT)
    elif not isinstance(received, str) or not RECEIVED.match(received):
        raise ValueError("received must look like 2026-10-14T06:00:00Z")

    payload, cut = _cap_strings(payload)
    if cut:
        payload["truncated"] = True
    title = title[:MAX_STRING_LENGTH]
    url = url[:MAX_STRING_LENGTH]
    return {
        "id": item_id(source, kind, url, payload),
        "kind": kind,
        "payload": payload,
        "received": received,
        "source": source,
        "title": title,
        "url": url,
        "year": year,
    }


def queue_root(queue_dir: Path) -> Path:
    """Return the queue/ directory of a desk-queue checkout."""
    return Path(queue_dir) / "queue"


def _read_file(path: Path) -> dict:
    """Read a queue file.

    Raises
    ------
    ValueError
        When the file is not valid JSON or has no items list.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError("no items list")
    if not isinstance(document.get("handled", []), list):
        raise ValueError("handled is not a list")
    return document


def _open_file(path: Path, series: str) -> tuple[dict, str | None]:
    """Read a queue file for adding, or start one for the series.

    A file that cannot be read is moved to <name>.bad and a new one started,
    so one broken file never stops the writers; the text is kept for a person.

    Parameters
    ----------
    path : Path
        The queue file.
    series : str
        Series name for a new file.

    Returns
    -------
    tuple[dict, str | None]
        The document, and a message when the file had to be moved aside.
    """
    if not path.exists():
        return {"handled": [], "items": [], "series": series}, None
    try:
        document = _read_file(path)
    except ValueError as error:
        bad = path.with_name(path.name + ".bad")
        path.replace(bad)
        message = f"queue/{path.name} unreadable ({error}), moved to queue/{bad.name}"
        return {"handled": [], "items": [], "series": series}, message
    document.setdefault("handled", [])
    return document, None


def _write_file(path: Path, document: dict) -> None:
    """Write a queue file in the canonical layout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def init_queue(queue_dir: Path) -> None:
    """Create the layout of a desk-queue checkout, refreshing its README.

    Parameters
    ----------
    queue_dir : Path
        The checkout. Existing queue files are left alone.
    """
    root = queue_root(queue_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitkeep").touch()
    (Path(queue_dir) / "README.md").write_text(README, encoding="utf-8", newline="\n")


def add_items(queue_dir: Path, records: Iterable[Any], now: datetime | None = None) -> list[dict]:
    """Add records to the queue.

    Parameters
    ----------
    queue_dir : Path
        The desk-queue checkout.
    records : Iterable[Any]
        Records as normalise_record takes them.
    now : datetime | None
        Time for records without "received" (default: now, UTC).

    Returns
    -------
    list[dict]
        One result per record, in order: {"file", "id", "status"} with status
        "added", "exists", "handled" (the desk has handled this finding), or
        "dropped" (older than the 50 items its file keeps), or {"error"} for a
        record that failed its checks. A file moved aside adds an {"error"}.
    """
    results = []
    documents: dict[Path, dict] = {}
    for record in records:
        try:
            item = normalise_record(record, now)
        except ValueError as error:
            results.append({"error": f"record rejected: {error}"})
            continue
        names = record_names(item)
        series = names[0] if names else item["title"]
        path = queue_root(queue_dir) / f"{slugify(series)}.json"
        if path not in documents:
            documents[path], moved = _open_file(path, series)
            if moved:
                results.append({"error": moved})
        document = documents[path]
        relative = f"queue/{path.name}"
        if item["id"] in document["handled"]:
            results.append({"file": relative, "id": item["id"], "status": "handled"})
            continue
        if any(isinstance(existing, dict) and existing.get("id") == item["id"] for existing in document["items"]):
            results.append({"file": relative, "id": item["id"], "status": "exists"})
            continue
        document["items"].append(item)
        results.append({"file": relative, "id": item["id"], "status": "added"})

    for path, document in documents.items():
        document["handled"] = document["handled"][-MAX_HANDLED_PER_FILE:]
        items = document["items"]
        if len(items) > MAX_ITEMS_PER_FILE:
            newest = sorted(items, key=lambda entry: str(entry.get("received", "")), reverse=True)
            keep = {id(entry) for entry in newest[:MAX_ITEMS_PER_FILE]}
            document["items"] = [entry for entry in items if id(entry) in keep]
        _write_file(path, document)

    kept_ids = {
        (f"queue/{path.name}", item.get("id")) for path, document in documents.items() for item in document["items"]
    }
    for result in results:
        if result.get("status") == "added" and (result["file"], result["id"]) not in kept_ids:
            result["status"] = "dropped"
    return results


def _read_or_report(path: Path) -> dict | None:
    """Read a queue file, or report on stderr why it cannot be read."""
    try:
        return _read_file(path)
    except ValueError as error:
        print(f"desk_queue: skipping queue/{path.name}: {error}", file=sys.stderr)
        return None


def _readable_files(queue_dir: Path) -> Iterable[tuple[Path, dict]]:
    """Yield each readable queue file with its document, skipping broken ones."""
    for path in sorted(queue_root(queue_dir).glob("*.json")):
        document = _read_or_report(path)
        if document is not None:
            yield path, document


def remove_items(queue_dir: Path, ids: Iterable[str]) -> set[str]:
    """Remove handled items, remembering their ids.

    A removed id is kept in its file's "handled" list, so a writer that finds
    the same thing again does not queue it again. The desk removes every item
    it has decided; items it has not reached stay.

    Parameters
    ----------
    queue_dir : Path
        The desk-queue checkout.
    ids : Iterable[str]
        Item ids to remove.

    Returns
    -------
    set[str]
        The ids that were found and removed.
    """
    wanted = set(ids)
    removed: set[str] = set()
    for path, document in _readable_files(queue_dir):
        items = document["items"]
        found = [item["id"] for item in items if isinstance(item, dict) and item.get("id") in wanted]
        if not found:
            continue
        removed.update(found)
        document["items"] = [item for item in items if not (isinstance(item, dict) and item.get("id") in wanted)]
        handled = document.setdefault("handled", [])
        handled.extend(item_id for item_id in found if item_id not in handled)
        document["handled"] = handled[-MAX_HANDLED_PER_FILE:]
        _write_file(path, document)
    return removed


def list_items(queue_dir: Path) -> list[dict]:
    """Return every queue item with the file it is in.

    Parameters
    ----------
    queue_dir : Path
        The desk-queue checkout.

    Returns
    -------
    list[dict]
        {"file", "id", "source", "kind", "received", "title"} per item, by file and received.
    """
    rows = []
    for path, document in _readable_files(queue_dir):
        rows.extend(
            {"file": f"queue/{path.name}", **{key: item.get(key) for key in LIST_FIELDS}}
            for item in document["items"]
            if isinstance(item, dict)
        )
    return sorted(rows, key=lambda row: (row["file"], str(row["received"]), str(row["id"])))


def _read_jsonl(path: str) -> list[Any]:
    """Read JSON lines from a file, or from stdin for "-"; a bad line becomes a ValueError marker."""
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    records: list[Any] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except ValueError as error:
            records.append(ValueError(f"line {number}: {error}"))
    return records


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create queue/ and write README.md")
    init_parser.add_argument("queue_dir", type=Path)

    add_parser = commands.add_parser("add", help="add records, from JSON lines or from options")
    add_parser.add_argument("queue_dir", type=Path)
    add_parser.add_argument("--jsonl", help="file of JSON records, one per line ('-' for stdin)")
    add_parser.add_argument("--source", choices=SOURCES)
    add_parser.add_argument("--kind", choices=KINDS)
    add_parser.add_argument("--title")
    add_parser.add_argument("--url", default="")
    add_parser.add_argument("--year", type=int)
    add_parser.add_argument("--payload", help="file holding the payload JSON object ('-' for stdin)")

    remove_parser = commands.add_parser("remove", help="remove handled items by id, remembering the ids")
    remove_parser.add_argument("queue_dir", type=Path)
    remove_parser.add_argument("ids", nargs="+")

    list_parser = commands.add_parser("list", help="print every item as a JSON line")
    list_parser.add_argument("queue_dir", type=Path)

    args = parser.parse_args(argv)

    if args.command == "init":
        init_queue(args.queue_dir)
        return 0

    if args.command == "list":
        for row in list_items(args.queue_dir):
            print(json.dumps(row, ensure_ascii=False))
        return 0

    if args.command == "remove":
        removed = remove_items(args.queue_dir, args.ids)
        for missing in sorted(set(args.ids) - removed):
            print(f"desk_queue: no item {missing}", file=sys.stderr)
        print(f"removed {len(removed)}")
        return 0

    if args.jsonl:
        if args.source or args.kind or args.title or args.payload:
            parser.error("--jsonl cannot be combined with --source, --kind, --title or --payload")
        records = _read_jsonl(args.jsonl)
    else:
        if not (args.source and args.kind and args.title):
            parser.error("add needs --jsonl, or --source, --kind and --title")
        payload: Any = {}
        if args.payload:
            text = sys.stdin.read() if args.payload == "-" else Path(args.payload).read_text(encoding="utf-8")
            payload = json.loads(text)
        records = [
            {
                "source": args.source,
                "kind": args.kind,
                "title": args.title,
                "url": args.url,
                "year": args.year,
                "payload": payload,
            },
        ]

    parsed = [record for record in records if not isinstance(record, ValueError)]
    for bad in (record for record in records if isinstance(record, ValueError)):
        print(f"desk_queue: record rejected: {bad}", file=sys.stderr)
    init_queue(args.queue_dir)
    results = add_items(args.queue_dir, parsed)
    for result in results:
        if "error" in result:
            print(f"desk_queue: {result['error']}", file=sys.stderr)
        else:
            print(f"{result['status']} {result['file']} {result['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
