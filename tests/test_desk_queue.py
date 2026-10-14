"""Tests for desk_queue: the deadline desk's queue on the desk-queue branch."""

import json
import sys
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import MAX_HANDLED_PER_FILE
from desk_queue import MAX_ITEMS_PER_FILE
from desk_queue import MAX_STRING_LENGTH
from desk_queue import README
from desk_queue import add_items
from desk_queue import init_queue
from desk_queue import item_id
from desk_queue import list_items
from desk_queue import main
from desk_queue import normalise_record
from desk_queue import record_names
from desk_queue import remove_items
from desk_queue import slugify
from desk_worklist import build_worklist
from desk_worklist import load_queue

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


def signal(title="PyCon Greece 2027 - Main", diff="CfP closes 1 March", **fields):
    record = {
        "source": "changedetection",
        "kind": "signal",
        "title": title,
        "url": "https://pycon.gr/",
        "year": 2027,
        "payload": {"diff": diff, "watch_uuid": "uuid-1", "trigger": "website_change"},
    }
    record.update(fields)
    return record


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TestSlugify:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("PyCon Greece", "pycon-greece"),
            ("PyDay Hurlingham", "pyday-hurlingham"),
            ("PyCon Česko", "pycon-cesko"),
            ("Python Pizza  Istanbul!", "python-pizza-istanbul"),
            ("FOSDEM: Python Devroom", "fosdem-python-devroom"),
            ("--", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_slug(self, name, expected):
        assert slugify(name) == expected


class TestRecordNames:
    def test_watch_title_is_cleaned(self):
        assert record_names(signal(title="[Conference] PyCon Greece 2027 - CFP")) == ["PyCon Greece"]

    def test_payload_conference_comes_before_title(self):
        record = {
            "kind": "redirect",
            "title": "https://old.example/",
            "payload": {"conference": "PyTennessee", "year": 2019},
        }
        assert record_names(record) == ["PyTennessee", "https://old.example/"]

    def test_missing_edition_names_the_matched_series_first(self):
        record = {
            "kind": "candidate",
            "title": "PyCon SK",
            "payload": {
                "classification": "MISSING_EDITION",
                "matched": {"conference": "PyCon Slovakia", "file": "archive", "year": 2026, "score": 90},
                "fields": {"conference": "PyCon SK"},
            },
        }
        assert record_names(record) == ["PyCon Slovakia", "PyCon SK"]

    def test_registry_names(self):
        record = {"kind": "registry", "title": "registry", "payload": {"names": ["PyCon Nepal", "PyCon NP"]}}
        assert record_names(record) == ["PyCon Nepal", "PyCon NP", "registry"]


class TestNormaliseRecord:
    def test_sets_id_and_received(self):
        item = normalise_record(signal(), NOW)
        assert item["received"] == "2026-10-14T06:00:00Z"
        assert item["id"] == item_id("changedetection", "signal", "https://pycon.gr/", item["payload"])
        assert sorted(item) == ["id", "kind", "payload", "received", "source", "title", "url", "year"]

    def test_id_ignores_received_and_a_supplied_id(self):
        first = normalise_record(signal(received="2026-10-01T00:00:00Z", id="mine"))
        second = normalise_record(signal(received="2026-10-14T00:00:00Z"))
        assert first["id"] == second["id"] != "mine"

    def test_id_depends_on_the_payload(self):
        assert normalise_record(signal(diff="a"), NOW)["id"] != normalise_record(signal(diff="b"), NOW)["id"]

    def test_redirect_id_ignores_status_and_query(self):
        def redirect(final_url, status):
            payload = {"conference": "PyTennessee", "year": 2019, "field": "sponsor"}
            payload.update(final_url=final_url, status=status)
            record = {
                "source": "link-check",
                "kind": "redirect",
                "title": "PyTennessee",
                "url": "https://pytennessee.org/p",
            }
            return normalise_record({**record, "payload": payload}, NOW)

        first = redirect("https://casino.example/landing?session=1#top", 200)
        second = redirect("https://casino.example/landing?session=2", 403)
        assert first["id"] == second["id"]
        assert first["payload"]["final_url"] == "https://casino.example/landing?session=1#top"
        assert redirect("https://other.example/landing", 200)["id"] != first["id"]

    def test_long_strings_are_cut_and_flagged(self):
        item = normalise_record(signal(diff="x" * (MAX_STRING_LENGTH + 5)), NOW)
        assert len(item["payload"]["diff"]) == MAX_STRING_LENGTH
        assert item["payload"]["truncated"] is True

    def test_nested_long_strings_are_cut(self):
        record = signal()
        record["payload"] = {"diffs": {"cfp": {"data": "y" * (MAX_STRING_LENGTH + 1), "source": "z"}}}
        item = normalise_record(record, NOW)
        assert len(item["payload"]["diffs"]["cfp"]["data"]) == MAX_STRING_LENGTH
        assert item["payload"]["truncated"] is True

    def test_short_payload_is_not_flagged(self):
        assert "truncated" not in normalise_record(signal(), NOW)["payload"]

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"source": "somewhere"}, "unknown source"),
            ({"kind": "rumour"}, "unknown kind"),
            ({"title": ""}, "title"),
            ({"title": None}, "title"),
            ({"url": None}, "url"),
            ({"year": "2027"}, "year"),
            ({"year": True}, "year"),
            ({"payload": "diff"}, "payload"),
            ({"received": "yesterday"}, "received"),
        ],
    )
    def test_rejects_bad_fields(self, change, message):
        with pytest.raises(ValueError, match=message):
            normalise_record(signal(**change), NOW)

    def test_rejects_non_objects(self):
        with pytest.raises(ValueError, match="JSON object"):
            normalise_record(["not", "a", "record"], NOW)


class TestAddItems:
    def test_creates_one_file_per_series(self, tmp_path):
        results = add_items(tmp_path, [signal(), signal(title="PyCon Greece 2027 - CFP", diff="other")], NOW)
        assert [result["status"] for result in results] == ["added", "added"]  # same series, two findings
        document = read(tmp_path / "queue" / "pycon-greece.json")
        assert document["series"] == "PyCon Greece"
        assert len(document["items"]) == 2

    def test_existing_id_is_a_no_op(self, tmp_path):
        add_items(tmp_path, [signal()], NOW)
        before = (tmp_path / "queue" / "pycon-greece.json").read_text(encoding="utf-8")
        results = add_items(tmp_path, [signal(received="2026-10-15T06:00:00Z")], NOW)
        assert results[0]["status"] == "exists"
        assert (tmp_path / "queue" / "pycon-greece.json").read_text(encoding="utf-8") == before

    def test_file_layout(self, tmp_path):
        add_items(tmp_path, [signal(diff="Ελληνικά")], NOW)
        text = (tmp_path / "queue" / "pycon-greece.json").read_text(encoding="utf-8")
        assert text.endswith("}\n")
        assert "Ελληνικά" in text
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def test_keeps_the_newest_items(self, tmp_path):
        records = [
            signal(diff=f"change {n}", received=f"2026-10-{1 + n // 24:02d}T{n % 24:02d}:00:00Z")
            for n in range(MAX_ITEMS_PER_FILE + 2)
        ]
        results = add_items(tmp_path, records, NOW)
        assert [result["status"] for result in results[:2]] == ["dropped", "dropped"]
        items = read(tmp_path / "queue" / "pycon-greece.json")["items"]
        assert len(items) == MAX_ITEMS_PER_FILE
        assert {item["payload"]["diff"] for item in items} == {f"change {n}" for n in range(2, MAX_ITEMS_PER_FILE + 2)}

    def test_bad_record_is_reported_and_others_kept(self, tmp_path):
        results = add_items(tmp_path, [signal(kind="rumour"), signal()], NOW)
        assert "error" in results[0]
        assert results[1]["status"] == "added"

    def test_same_finding_under_two_titles_is_one_item(self, tmp_path):
        """A watch on link and one on cfp_link with the same URL send the same diff."""
        results = add_items(tmp_path, [signal(), signal(title="PyCon Greece 2027 - CFP")], NOW)
        assert [result["status"] for result in results] == ["added", "exists"]

    def test_unnamed_series_uses_the_title(self, tmp_path):
        record = signal(title="[Conference] Some Brand New Conf 2027 - Main")
        add_items(tmp_path, [record], NOW)
        assert read(tmp_path / "queue" / "some-brand-new-conf.json")["series"] == "Some Brand New Conf"


class TestRemoveItems:
    def test_removes_and_remembers(self, tmp_path):
        italia = signal(title="PyCon Italia 2027 - Main", url="https://pycon.it/")
        first, second = add_items(tmp_path, [signal(), italia], NOW)
        removed = remove_items(tmp_path, [first["id"], "missing"])
        assert removed == {first["id"]}
        document = read(tmp_path / "queue" / "pycon-greece.json")
        assert document["items"] == []
        assert document["handled"] == [first["id"]]
        assert read(tmp_path / "queue" / "pycon-italia.json")["handled"] == []
        assert [row["id"] for row in list_items(tmp_path)] == [second["id"]]

    def test_handled_finding_is_not_queued_again(self, tmp_path):
        (first,) = add_items(tmp_path, [signal()], NOW)
        remove_items(tmp_path, [first["id"]])
        (again,) = add_items(tmp_path, [signal(received="2026-10-21T06:00:00Z")], NOW)
        assert again == {"file": "queue/pycon-greece.json", "id": first["id"], "status": "handled"}
        assert read(tmp_path / "queue" / "pycon-greece.json")["items"] == []

    def test_changed_finding_is_queued(self, tmp_path):
        (first,) = add_items(tmp_path, [signal()], NOW)
        remove_items(tmp_path, [first["id"]])
        (changed,) = add_items(tmp_path, [signal(diff="CfP extended to 15 March")], NOW)
        assert changed["status"] == "added"

    def test_keeps_the_latest_handled_ids(self, tmp_path):
        ids = []
        for batch in range(0, MAX_HANDLED_PER_FILE + 3, 40):
            records = [signal(diff=f"change {n}") for n in range(batch, min(batch + 40, MAX_HANDLED_PER_FILE + 3))]
            added = [result["id"] for result in add_items(tmp_path, records, NOW)]
            remove_items(tmp_path, added)
            ids.extend(added)
        handled = read(tmp_path / "queue" / "pycon-greece.json")["handled"]
        assert len(ids) == MAX_HANDLED_PER_FILE + 3
        assert handled == ids[-MAX_HANDLED_PER_FILE:]

    def test_keeps_other_items_in_the_file(self, tmp_path):
        first, second = add_items(tmp_path, [signal(), signal(diff="other")], NOW)
        remove_items(tmp_path, [first["id"]])
        assert [item["id"] for item in read(tmp_path / "queue" / "pycon-greece.json")["items"]] == [second["id"]]

    def test_no_queue_directory(self, tmp_path):
        assert remove_items(tmp_path, ["x"]) == set()
        assert list_items(tmp_path) == []

    def test_broken_files_are_skipped(self, tmp_path, capsys):
        (first,) = add_items(tmp_path, [signal(title="PyCon Italia 2027 - Main", url="https://pycon.it/")], NOW)
        (tmp_path / "queue" / "pycon-greece.json").write_text('{"items": [},', encoding="utf-8")
        assert [row["id"] for row in list_items(tmp_path)] == [first["id"]]
        assert remove_items(tmp_path, [first["id"]]) == {first["id"]}
        assert "skipping queue/pycon-greece.json" in capsys.readouterr().err


class TestBrokenFile:
    def test_moved_aside_and_writers_carry_on(self, tmp_path):
        add_items(tmp_path, [signal()], NOW)
        broken = tmp_path / "queue" / "pycon-greece.json"
        broken.write_text('{"items": [},', encoding="utf-8")
        italia = signal(title="PyCon Italia 2027 - Main", url="https://pycon.it/")
        results = add_items(tmp_path, [signal(diff="new"), italia], NOW)
        assert "moved to queue/pycon-greece.json.bad" in results[0]["error"]
        assert [result.get("status") for result in results[1:]] == ["added", "added"]
        assert (tmp_path / "queue" / "pycon-greece.json.bad").read_text(encoding="utf-8") == '{"items": [},'
        assert [item["payload"]["diff"] for item in read(broken)["items"]] == ["new"]

    def test_file_without_items_list(self, tmp_path):
        (tmp_path / "queue").mkdir()
        (tmp_path / "queue" / "pycon-greece.json").write_text('{"series": "PyCon Greece"}', encoding="utf-8")
        results = add_items(tmp_path, [signal()], NOW)
        assert "no items list" in results[0]["error"]
        assert results[1]["status"] == "added"


class TestInit:
    def test_writes_layout_and_refreshes_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("old", encoding="utf-8")
        add_items(tmp_path, [signal()], NOW)
        init_queue(tmp_path)
        assert (tmp_path / "README.md").read_text(encoding="utf-8") == README
        assert (tmp_path / "queue" / ".gitkeep").exists()
        assert (tmp_path / "queue" / "pycon-greece.json").exists()


class TestWorklistRoundTrip:
    def test_items_load_and_route(self, tmp_path):
        add_items(tmp_path, [signal(title="[Conference] PyCon Greece 2027 - Main")], NOW)
        queue_items = load_queue(tmp_path)
        assert queue_items[0]["file"] == "queue/pycon-greece.json"
        assert queue_items[0]["series"] == "PyCon Greece"
        data = {
            "conferences": [],
            "archive": [
                {
                    "conference": "PyCon Greece",
                    "year": 2026,
                    "link": "https://2026.pycon.gr/",
                    "cfp": "2026-03-01 23:59:00",
                    "place": "Athens, Greece",
                    "start": date(2026, 6, 1),
                    "end": date(2026, 6, 2),
                    "sub": "PY",
                },
            ],
            "legacy": [],
        }
        worklist = build_worklist(data, queue_items, date(2026, 10, 14), scout=False)
        assert [(item["skill"], item["conference"]) for item in worklist["items"]] == [
            ("new-year-checker", "PyCon Greece"),
        ]
        assert worklist["items"][0]["queue_refs"] == [{"file": "queue/pycon-greece.json", "id": queue_items[0]["id"]}]

    def test_redirect_record_from_the_link_checker(self, tmp_path, monkeypatch):
        from tidy_conf import links

        out = tmp_path / "records.jsonl"
        monkeypatch.setenv("DESK_QUEUE_OUT", str(out))
        monkeypatch.setattr(links, "REDIRECT_RECORDS", [])
        links.record_redirect(
            "https://pytennessee.org/prospectus",
            "https://casino.example/",
            200,
            conference="PyTennessee",
            year=2019,
            field="sponsor",
        )
        assert main(["add", str(tmp_path / "queue-checkout"), "--jsonl", str(out)]) == 0
        items = load_queue(tmp_path / "queue-checkout")
        assert [(item["file"], item["kind"], item["payload"]["final_url"]) for item in items] == [
            ("queue/pytennessee.json", "redirect", "https://casino.example/"),
        ]


class TestCli:
    def test_add_jsonl_skips_bad_lines(self, tmp_path, capsys):
        records = tmp_path / "records.jsonl"
        records.write_text(json.dumps(signal()) + "\n\nnot json\n" + json.dumps(signal(kind="rumour")) + "\n")
        assert main(["add", str(tmp_path / "q"), "--jsonl", str(records)]) == 0
        captured = capsys.readouterr()
        assert captured.out.startswith("added queue/pycon-greece.json ")
        assert captured.err.count("desk_queue: record rejected: ") == 2
        assert (tmp_path / "q" / "README.md").exists()

    def test_add_from_options(self, tmp_path, capsys):
        payload = tmp_path / "payload.json"
        payload.write_text(json.dumps({"diff": "new dates", "watch_uuid": None, "trigger": "website_change"}))
        argv = [
            "add",
            str(tmp_path / "q"),
            "--source",
            "changedetection",
            "--kind",
            "signal",
            "--title",
            "PyCon Italia 2027 - Main",
            "--url",
            "https://pycon.it/",
            "--payload",
            str(payload),
        ]
        assert main(argv) == 0
        item = read(tmp_path / "q" / "queue" / "pycon-italia.json")["items"][0]
        assert item["payload"]["diff"] == "new dates"
        assert item["year"] is None

    def test_add_needs_a_record(self, tmp_path):
        with pytest.raises(SystemExit):
            main(["add", str(tmp_path)])

    def test_jsonl_excludes_options(self, tmp_path):
        with pytest.raises(SystemExit):
            main(["add", str(tmp_path), "--jsonl", "-", "--title", "x"])

    def test_remove_and_list(self, tmp_path, capsys):
        first, _ = add_items(tmp_path, [signal(), signal(diff="other")], NOW)
        assert main(["remove", str(tmp_path), first["id"], "nope"]) == 0
        captured = capsys.readouterr()
        assert "removed 1" in captured.out
        assert "no item nope" in captured.err
        assert main(["list", str(tmp_path)]) == 0
        rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert len(rows) == 1
        assert rows[0]["file"] == "queue/pycon-greece.json"
