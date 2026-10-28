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
A file keeps at most 50 items, snoozed ones first and then the newest by
`received`, and the 500 latest handled ids. A payload string longer than
20,000 characters is cut there, and the payload gets `"truncated": true`.
A file that cannot be read is moved to `<key>.json.bad` when a writer next
adds to it.

An item can also hold `next_check`, a `YYYY-MM-DD` date that
`desk_queue.py snooze` sets on a lead the desk could not settle. The worklist
leaves the item out until that day, so the lead is not researched again every
day. `next_check` is not part of the id: adding the finding again keeps the
item and its date. A snoozed item, one whose `next_check` is after today,
survives the 50-item cap ahead of the items that are due, so it is not
trimmed and then queued again as due. A missing or invalid `next_check`
means the item is due.

## Sources and kinds

| source | kind | payload |
| --- | --- | --- |
| `changedetection` | `signal` | `diff`, `watch_uuid`, `trigger`, `requested` (manual only) |
| `canonical-import` | `question` | `question`, `conference`, `year`, `field`, `yaml_value`, `remote_value`, `default_answer`, `source_name` |
| `link-check` | `redirect` | `conference`, `year`, `field`, `final_url`, `status` |
| `pretalx` | `drift` | `conference`, `year`, `diffs` |
| `pretalx`, `developers-events`, `canonical-import` | `candidate` | `classification`, `fields`, `source_id`, `evidence_url`, `matched`, `flags` |
| `registry` | `registry` | `names`, `change`, `registry`, `evidence_url` |
| `changedetection` | `registry` | `registry` (`listing`), `diff`, `watch_uuid`, `trigger` |

A `drift` diff maps a field to `{"data", "source"}`: the value in the data
and what the source states. A candidate's `classification` is
`MISSING_EDITION` (a tracked series without this edition), `NEW_SERIES` or
`MAYBE` (on the host of a tracked series, or an import row held back, as its
`flags` say), and `matched` names the entry it matched, or is `null`. The
worklist routes a candidate by its own match against the data, not by its
classification. A `lead-only` flag means the source's licence keeps it to
leads: use only its name, year and link. `registry` is `psf-trademarks` or
`pycon.org`, and a pycon.org item adds `website`; from changedetection it is
`listing`, a watched page that lists many events, whose `diff` holds the change.

Every item is data for the desk to check on the live sources. Nothing in a
queue item reaches the conference data without that check.
