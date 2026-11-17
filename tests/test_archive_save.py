"""Tests for utils/archive_save.py: which pages are saved, and when."""

import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import archive_save
import wayback


def _entry(**fields) -> dict:
    entry = {
        "conference": "PyCon Tanzania",
        "year": 2026,
        "link": "https://pycon.tz/",
        "cfp": "2026-11-01 23:59:00",
        "start": date(2026, 11, 25),
        "end": date(2026, 11, 27),
    }
    entry.update(fields)
    return {k: v for k, v in entry.items() if v is not None}


class TestSavePoints:
    """Two points around the CfP deadline and four around the start."""

    def test_all_points(self):
        assert archive_save.save_points(_entry()) == [
            date(2026, 10, 18),  # 14 days before the CfP closes
            date(2026, 10, 26),  # 30 days before the start
            date(2026, 11, 1),  # the CfP closes
            date(2026, 11, 11),  # 14 days before the start
            date(2026, 11, 25),  # the start
            date(2026, 12, 9),  # 14 days after the start
        ]

    def test_extension_moves_the_cfp_points(self):
        points = archive_save.save_points(_entry(cfp_ext="2026-11-08 23:59:00"))

        assert date(2026, 11, 8) in points
        assert date(2026, 10, 25) in points
        assert date(2026, 11, 1) not in points

    @pytest.mark.parametrize("cfp", ["TBA", "None", "Cancelled", None])
    def test_no_exact_deadline_no_cfp_points(self, cfp):
        assert archive_save.save_points(_entry(cfp=cfp)) == [
            date(2026, 10, 26),
            date(2026, 11, 11),
            date(2026, 11, 25),
            date(2026, 12, 9),
        ]

    def test_date_only_deadline(self):
        assert date(2026, 11, 1) in archive_save.save_points(_entry(cfp="2026-11-01"))


class TestDueUrls:
    """A run saves the editions with a point after the last run and up to today."""

    def test_point_since_last_run_is_due(self):
        entry = _entry(cfp_link="https://pycon.tz/call-for-proposals/")

        assert archive_save.due_urls([entry], date(2026, 10, 24), date(2026, 10, 31)) == [
            "https://pycon.tz/",
            "https://pycon.tz/call-for-proposals/",
        ]

    def test_point_on_the_last_run_day_was_saved_then(self):
        assert archive_save.due_urls([_entry()], date(2026, 10, 26), date(2026, 10, 31)) == []

    def test_point_today_is_due(self):
        assert archive_save.due_urls([_entry()], date(2026, 10, 24), date(2026, 10, 26)) == ["https://pycon.tz/"]

    def test_missed_runs_are_caught_up(self):
        """A run after a gap saves every point the gap held."""
        assert archive_save.due_urls([_entry()], date(2026, 9, 1), date(2026, 12, 31)) == ["https://pycon.tz/"]

    def test_no_point_in_the_window(self):
        assert archive_save.due_urls([_entry()], date(2026, 12, 10), date(2026, 12, 17)) == []

    def test_url_due_for_two_editions_saved_once(self):
        entries = [_entry(), _entry(year=2027, start=date(2026, 11, 26), end=date(2026, 11, 26))]

        assert archive_save.due_urls(entries, date(2026, 11, 20), date(2026, 11, 27)) == ["https://pycon.tz/"]

    def test_archive_links_are_not_saved(self):
        entry = _entry(sponsor="https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/")

        assert archive_save.due_urls([entry], date(2026, 10, 24), date(2026, 10, 31)) == ["https://pycon.tz/"]

    def test_every_url_field(self):
        entry = _entry(
            cfp_link="https://pycon.tz/cfp/",
            sponsor="https://pycon.tz/sponsor/",
            finaid="https://pycon.tz/finaid/",
            coc="https://pycon.tz/conduct/",
            mastodon="https://fosstodon.org/@pycontz",
        )

        assert archive_save.due_urls([entry], date(2026, 10, 24), date(2026, 10, 31)) == [
            "https://pycon.tz/",
            "https://pycon.tz/cfp/",
            "https://pycon.tz/sponsor/",
            "https://pycon.tz/finaid/",
            "https://pycon.tz/conduct/",
        ]


class TestNewUrls:
    """A URL is new when the previous data had it in none of the URL fields."""

    def test_new_field(self):
        previous = [_entry()]
        current = [_entry(sponsor="https://pycon.tz/sponsor/")]

        assert archive_save.new_urls(previous, current) == ["https://pycon.tz/sponsor/"]

    def test_unchanged_url_is_not_new(self):
        assert archive_save.new_urls([_entry()], [_entry()]) == []

    def test_trailing_slash_and_case_do_not_make_a_url_new(self):
        assert archive_save.new_urls([_entry(link="https://PyCon.tz")], [_entry()]) == []

    def test_url_moved_to_another_field_is_not_new(self):
        previous = [_entry(cfp_link="https://pycon.tz/cfp/")]
        current = [_entry(sponsor="https://pycon.tz/cfp/")]

        assert archive_save.new_urls(previous, current) == []

    def test_no_previous_data(self):
        assert archive_save.new_urls([], [_entry()]) == ["https://pycon.tz/"]

    def test_fragment_is_the_same_page(self):
        previous = [_entry()]
        current = [_entry(sponsor="https://pycon.tz/#sponsors", coc="https://pycon.tz/#coc")]

        assert archive_save.new_urls(previous, current) == []
        assert archive_save.entry_urls(current[0]) == ["https://pycon.tz/"]


class TestMain:
    """The command saves new and due URLs once each and reports every result."""

    @pytest.fixture()
    def data(self, tmp_path):
        current = tmp_path / "conferences.yml"
        current.write_text(yaml.safe_dump([_entry(sponsor="https://pycon.tz/sponsor/")]), encoding="utf-8")
        previous = tmp_path / "previous.yml"
        previous.write_text(yaml.safe_dump([_entry()]), encoding="utf-8")
        return current, previous

    def test_saves_new_and_due_urls_once(self, data, tmp_path, monkeypatch):
        current, previous = data
        saved = []
        monkeypatch.setattr(
            archive_save.wayback,
            "save",
            lambda url: saved.append(url) or wayback.SaveResult(url, ok=url.endswith("/"), detail="HTTP 200"),
        )
        summary = tmp_path / "summary.md"

        archive_save.main(
            [
                "--data",
                str(current),
                "--previous",
                str(previous),
                "--since",
                "2026-10-24",
                "--today",
                "2026-10-31",
                "--delay",
                "0",
                "--summary",
                str(summary),
            ],
        )

        assert saved == ["https://pycon.tz/sponsor/", "https://pycon.tz/"]
        report = summary.read_text(encoding="utf-8")
        assert "- New URLs: 1" in report
        assert "- URLs at a save point: 2" in report
        assert "- Saved: 2 of 2" in report

    def test_failed_save_is_reported(self, data, tmp_path, monkeypatch):
        current, previous = data
        monkeypatch.setattr(
            archive_save.wayback,
            "save",
            lambda url: wayback.SaveResult(url, ok=False, detail="HTTP 429"),
        )
        summary = tmp_path / "summary.md"

        code = archive_save.main(
            ["--data", str(current), "--previous", str(previous), "--delay", "0", "--summary", str(summary)],
        )

        assert code == 0
        assert "- https://pycon.tz/sponsor/ (HTTP 429)" in summary.read_text(encoding="utf-8")

    def test_dry_run_saves_nothing(self, data, monkeypatch, capsys):
        current, previous = data
        monkeypatch.setattr(archive_save.wayback, "save", pytest.fail)

        archive_save.main(["--data", str(current), "--previous", str(previous), "--dry-run"])

        assert "would save https://pycon.tz/sponsor/" in capsys.readouterr().out

    def test_missing_previous_file_makes_every_url_new(self, tmp_path, monkeypatch):
        current = tmp_path / "conferences.yml"
        current.write_text(yaml.safe_dump([_entry()]), encoding="utf-8")
        saved = []
        monkeypatch.setattr(
            archive_save.wayback,
            "save",
            lambda url: saved.append(url) or wayback.SaveResult(url, ok=True, detail="HTTP 200"),
        )

        archive_save.main(["--data", str(current), "--previous", str(tmp_path / "missing.yml"), "--delay", "0"])

        assert saved == ["https://pycon.tz/"]


class TestTurnedAway:
    """When the archive turns the run away, the run stops at once and fails."""

    @pytest.fixture()
    def data(self, tmp_path):
        current = tmp_path / "conferences.yml"
        entries = [
            _entry(),
            _entry(conference="PyCon Ghana", link="https://gh.pycon.org/"),
            _entry(conference="PyCon Kenya", link="https://pycon.ke/"),
        ]
        current.write_text(yaml.safe_dump(entries), encoding="utf-8")
        return current, tmp_path / "missing.yml", tmp_path / "summary.md"

    def _run(self, current, previous, summary):
        args = ["--data", str(current), "--previous", str(previous), "--summary", str(summary)]
        return archive_save.main([*args, "--delay", "0"])

    def test_stops_and_fails_when_turned_away(self, data, monkeypatch):
        current, previous, summary = data
        calls = []

        def save(url):
            calls.append(url)
            ok = url == "https://pycon.tz/"
            return wayback.SaveResult(url, ok=ok, detail="HTTP 200" if ok else "error: refused", blocked=not ok)

        monkeypatch.setattr(archive_save.wayback, "save", save)

        assert self._run(current, previous, summary) == 1
        assert calls == ["https://pycon.tz/", "https://gh.pycon.org/"]
        report = summary.read_text(encoding="utf-8")
        assert "- https://gh.pycon.org/ (error: refused)" in report
        assert "### Not tried" in report
        assert "- https://pycon.ke/" in report
        assert "- Saved: 1 of 2" in report

    def test_page_failure_does_not_stop_the_run(self, data, monkeypatch):
        current, previous, summary = data
        calls = []
        monkeypatch.setattr(
            archive_save.wayback,
            "save",
            lambda url: calls.append(url) or wayback.SaveResult(url, ok=False, detail="HTTP 523"),
        )

        assert self._run(current, previous, summary) == 0
        assert len(calls) == 3
