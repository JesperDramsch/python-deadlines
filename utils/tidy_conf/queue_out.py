"""Hand findings to the deadline desk's queue as JSON lines.

Jobs that run the data tooling in GitHub Actions set ``DESK_QUEUE_OUT`` to a
file path. Code that finds something only a person or the desk can judge (a
link that now redirects to another site, a merge question with no one to
answer it) appends a record to that file, and the job adds the file to the
desk-queue branch with ``utils/desk_queue.py add --jsonl``. The records lack
"id": the queue writer assigns it, and the series key of the file each item
goes in, so both are defined in one place.
"""

import json
import os
from datetime import datetime
from datetime import timezone
from pathlib import Path

QUEUE_OUT_ENV = "DESK_QUEUE_OUT"


def utc_now() -> str:
    """Return the current time in the queue's "received" format."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_queue_record(record: dict) -> bool:
    """Append a record to the file ``DESK_QUEUE_OUT`` names, if it names one.

    Parameters
    ----------
    record : dict
        A queue item without "id".

    Returns
    -------
    bool
        True when the record was written.
    """
    out_path = os.environ.get(QUEUE_OUT_ENV)
    if not out_path:
        return False
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    return True
