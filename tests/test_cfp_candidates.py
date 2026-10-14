"""Tests for cfp_candidates: archived series that have no entry in conferences.yml.

A series counts as tracked when its name or any alt_name matches the name or
alt_name of an entry in conferences.yml, after normalize_conference_name and
the titles.yml mappings, ignoring case, accents and whitespace.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from cfp_candidates import entry_names
from cfp_candidates import find_candidates
from cfp_candidates import load_data
from cfp_candidates import main
from cfp_candidates import series_key

# Real entries: archive.yml at 3d34de3, conferences.yml before 405fc07 and 219d0b0,
# when the upcoming editions were spelt differently from their archived ones.
ARCHIVE_XTREME_PYTHON = {
    "conference": "Xtreme Python",
    "year": 2025,
    "link": "https://xtremepython.dev/2025/",
    "cfp": "2025-09-20 23:59:00",
    "place": "Online",
    "start": date(2025, 11, 18),
    "end": date(2025, 11, 18),
    "sponsor": "https://xtremepython.dev/2025/sponsors/",
    "sub": "PY",
}
CURRENT_XTREMEPYTHON = {
    "conference": "XtremePython",
    "year": 2026,
    "link": "https://xtremepython.dev/",
    "cfp": "TBA",
    "place": "Online",
    "start": date(2026, 11, 17),
    "end": date(2026, 11, 17),
    "sub": "PY",
}
ARCHIVE_PYHEP_DEV = {
    "conference": "PyHEP.dev",
    "alt_name": "PyHEP",
    "year": 2025,
    "link": "https://indico.cern.ch/event/1515852/",
    "cfp": "2025-07-08 23:59:00",
    "place": "Seattle, USA",
    "start": date(2025, 7, 14),
    "end": date(2025, 7, 17),
    "sub": "SCIPY",
}
CURRENT_PYHEP = {
    "conference": "PyHEP",
    "year": 2026,
    "link": "https://indico.cern.ch/category/7971/",
    "cfp": "TBA",
    "timezone": "Europe/Zurich",
    "place": "Geneva, Switzerland",
    "start": date(2026, 9, 7),
    "end": date(2026, 9, 9),
    "sub": "PY",
}


def edition(conference, year, **fields):
    """Build a minimal archived edition."""
    return {"conference": conference, "year": year, "link": f"https://example.org/{year}/", **fields}


def names(candidates):
    return [c["conference"] for c in candidates]


class TestSeriesKey:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("Xtreme Python", "XtremePython"),
            ("PyDay Copiapó", "PyDay Copiapo"),
            ("PyCon mini Tokai", "PyCon Mini Tokai"),
            ("PyCon NZ", "Kiwi PyCon"),
            ("EuroPython Conference", "EuroPython"),
            ("PyCon Greece 2027", "PyCon Greece"),
        ],
    )
    def test_same_series(self, left, right):
        assert series_key(left) == series_key(right)

    @pytest.mark.parametrize(("left", "right"), [("PyHEP.dev", "PyHEP"), ("PyData Berlin", "PyData Paris")])
    def test_different_series(self, left, right):
        assert series_key(left) != series_key(right)


class TestEntryNames:
    def test_conference_then_alt_name(self):
        assert entry_names({"conference": "PyHEP.dev", "alt_name": "PyHEP"}) == ["PyHEP.dev", "PyHEP"]

    def test_skips_missing_and_blank(self):
        assert entry_names({"conference": "PyCon", "alt_name": " "}) == ["PyCon"]


class TestFindCandidates:
    def test_xtreme_python_spelling_is_tracked(self):
        """Archive "Xtreme Python" is tracked by an upcoming "XtremePython"."""
        assert find_candidates([CURRENT_XTREMEPYTHON], [ARCHIVE_XTREME_PYTHON], current_year=2026) == []

    def test_xtreme_python_spelling_reversed(self):
        archive = [{**CURRENT_XTREMEPYTHON, "year": 2025}]
        current = [{**ARCHIVE_XTREME_PYTHON, "year": 2026}]
        assert find_candidates(current, archive, current_year=2026) == []

    def test_pyhep_dev_alt_name_is_tracked(self):
        """Archive "PyHEP.dev" (alt_name PyHEP) is tracked by an upcoming "PyHEP"."""
        assert find_candidates([CURRENT_PYHEP], [ARCHIVE_PYHEP_DEV], current_year=2026) == []

    def test_pyhep_tracked_through_upcoming_alt_name(self):
        """Archive "PyHEP" is tracked by an upcoming "PyHEP.dev" whose alt_name is PyHEP."""
        current = [{**ARCHIVE_PYHEP_DEV, "year": 2026}]
        archive = [{**CURRENT_PYHEP, "year": 2025}]
        assert find_candidates(current, archive, current_year=2026) == []

    def test_reported_without_the_other_spelling(self):
        candidates = find_candidates([], [ARCHIVE_XTREME_PYTHON, ARCHIVE_PYHEP_DEV], current_year=2026)
        assert names(candidates) == ["PyHEP.dev", "Xtreme Python"]

    def test_punctuation_is_not_folded(self):
        """Without the alt_name, "PyHEP.dev" and "PyHEP" stay separate series."""
        archive = [{k: v for k, v in ARCHIVE_PYHEP_DEV.items() if k != "alt_name"}]
        assert names(find_candidates([CURRENT_PYHEP], archive, current_year=2026)) == ["PyHEP.dev"]

    def test_accents_and_case(self):
        current = [edition("PyDay Copiapo", 2026)]
        archive = [edition("PyDay Copiapó", 2025), edition("pycon mini tokai", 2025)]
        assert names(find_candidates(current, archive, current_year=2026)) == ["pycon mini tokai"]

    def test_titles_mapping(self):
        """titles.yml maps "PyCon NZ" to "Kiwi PyCon"."""
        assert find_candidates([edition("Kiwi PyCon", 2026)], [edition("PyCon NZ", 2025)], current_year=2026) == []

    def test_any_archived_alt_name_counts(self):
        """The alt_name of an older edition still tracks the series, so a rename is not lost."""
        archive = [edition("PyCon Old Name", 2024, alt_name="PyCon New Name"), edition("PyCon Old Name", 2025)]
        current = [edition("PyCon New Name", 2026)]
        assert find_candidates(current, archive, current_year=2026) == []

    def test_host_alt_name_hides_the_series(self):
        """Known cost of the rule above: an old edition named after its host hides the series.

        The 2023 edition was hosted by PyCon Japan and carries it as alt_name, so the
        upcoming PyCon Japan tracks PyCon Asia Pacific although it has no entry of its own.
        """
        archive = [
            edition("PyCon Asia Pacific", 2025, alt_name="PyCon Philippines"),
            edition("PyCon Asia Pacific", 2023, alt_name="PyCon Japan"),
        ]
        current = [edition("PyCon Japan", 2027)]
        assert find_candidates(current, archive, current_year=2026) == []
        assert names(find_candidates(current, archive[:1], current_year=2026)) == ["PyCon Asia Pacific"]

    def test_spellings_grouped_into_one_series(self):
        archive = [edition("PyCon Mini Tokai", 2024), edition("PyCon mini Tokai", 2025)]
        candidates = find_candidates([], archive, current_year=2026)
        assert [(c["conference"], c["latest_year"]) for c in candidates] == [("PyCon mini Tokai", 2025)]

    def test_lookback(self):
        archive = [edition("Old Conf", 2023), edition("Recent Conf", 2024)]
        assert names(find_candidates([], archive, current_year=2026)) == ["Recent Conf"]
        assert names(find_candidates([], archive, current_year=2026, lookback=3)) == ["Recent Conf", "Old Conf"]

    def test_carries_fields_of_latest_edition(self):
        archive = [
            edition("PyCon Example", 2024, place="Old Town", sub="PY"),
            edition("PyCon Example", 2025, place="New Town", sub="PY", cfp_link="https://example.org/cfp"),
        ]
        assert find_candidates([], archive, current_year=2026) == [
            {
                "conference": "PyCon Example",
                "latest_year": 2025,
                "link": "https://example.org/2025/",
                "place": "New Town",
                "sub": "PY",
                "cfp_link": "https://example.org/cfp",
            },
        ]

    def test_order_newest_first_then_name(self):
        archive = [edition("B Conf", 2025), edition("A Conf", 2025), edition("C Conf", 2026)]
        assert names(find_candidates([], archive, current_year=2026)) == ["C Conf", "A Conf", "B Conf"]


class TestCli:
    @freeze_time("2026-10-14")
    def test_output_shape(self, tmp_path, monkeypatch, capsys):
        data = tmp_path / "_data"
        data.mkdir()
        (data / "conferences.yml").write_text(yaml.safe_dump([CURRENT_XTREMEPYTHON]), encoding="utf-8")
        (data / "archive.yml").write_text(
            yaml.safe_dump([ARCHIVE_XTREME_PYTHON, edition("PyCon Example", 2025)]),
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", ["cfp_candidates.py", "--base", str(tmp_path)])

        main()

        output = json.loads(capsys.readouterr().out)
        assert output == {
            "generated": "2026",
            "count": 1,
            "candidates": [{"conference": "PyCon Example", "latest_year": 2025, "link": "https://example.org/2025/"}],
        }

    def test_load_data_missing_files(self, tmp_path):
        assert load_data(tmp_path) == {"conferences": [], "archive": [], "legacy": []}
