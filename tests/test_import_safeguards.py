"""Tests for the safeguards that let the canonical import run on a schedule.

Run against live sources on 2026-10-14, the import added a duplicate of Xtreme
Python 2026 under its alt_name, a duplicate of Python Nordeste 2026 named
"Python Nordeste (PyNE )", a fake event on a denylisted domain, and two sheet
rows without a website that failed validation and stopped the sort.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import normalise_record
from import_python_organizers import drop_rows_without_link
from tidy_conf.denylist import denied
from tidy_conf.denylist import drop_denied
from tidy_conf.denylist import load_denylist
from tidy_conf.interactive_merge import apply_alt_names
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.titles import normalize_conference_name

DENYLIST = {
    "reject": {"codehut.co.uk": "domain does not resolve"},
    "review": {"pyconf.org": "domain registered after the claimed CfP"},
}


def rows(*entries):
    columns = ["conference", "year", "link", "cfp", "place", "start", "end"]
    return pd.DataFrame([dict(zip(columns, entry, strict=False)) for entry in entries], columns=columns)


class TestBrackets:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Python Nordeste (PyNE 2026)", "Python Nordeste"),
            ("Python Nordeste (PyNE) 2026", "Python Nordeste"),
            ("Some Summit (2026)", "Some Summit"),
            ("Some Summit ( Online )", "Some Summit (Online)"),
            ("EuroPython 2026", "EuroPython"),
        ],
    )
    def test_year_removal_leaves_tidy_brackets(self, name, expected):
        assert normalize_conference_name(name) == expected


class TestAltNames:
    def yaml(self, *entries):
        return pd.DataFrame(
            [{"conference": name, "alt_name": alt, "year": 2026} for name, alt in entries],
        )

    def test_alt_name_becomes_the_series(self, mock_title_mappings):
        df_remote = apply_alt_names(self.yaml(("Xtreme Python", "XtremePython")), rows(("XtremePython", 2026)))
        assert df_remote["conference"].tolist() == ["Xtreme Python"]

    def test_case_and_accents_are_ignored(self, mock_title_mappings):
        df_remote = apply_alt_names(self.yaml(("PyCon Slovakia", "PyCon SK")), rows(("pycon sk", 2026)))
        assert df_remote["conference"].tolist() == ["PyCon Slovakia"]

    def test_shared_alt_name_is_left_alone(self, mock_title_mappings):
        df_yml = self.yaml(("Summit North", "The Summit"), ("Summit South", "The Summit"))
        assert apply_alt_names(df_yml, rows(("The Summit", 2026)))["conference"].tolist() == ["The Summit"]

    def test_a_yaml_name_is_kept(self, mock_title_mappings):
        df_yml = self.yaml(("PyData Berlin", "PyCon Berlin"), ("PyCon Berlin", None))
        assert apply_alt_names(df_yml, rows(("PyCon Berlin", 2026)))["conference"].tolist() == ["PyCon Berlin"]

    def test_without_alt_names_nothing_changes(self, mock_title_mappings):
        df_remote = rows(("XtremePython", 2026))
        assert apply_alt_names(pd.DataFrame({"conference": ["Xtreme Python"]}), df_remote) is df_remote

    def test_fuzzy_match_merges_the_alt_name_edition(self, mock_title_mappings):
        df_yml = rows(
            (
                "Xtreme Python",
                2026,
                "https://xtremepython.dev/2026/",
                "TBA",
                "Online",
                "2026-11-17",
                "2026-11-17",
            ),
        )
        df_yml["alt_name"] = ["XtremePython"]
        df_remote = rows(
            (
                "XtremePython",
                2026,
                "https://xtremepython.dev/",
                "TBA",
                "Online",
                "2026-11-17",
                "2026-11-17",
            ),
        )
        df_merged, df_remote, report = fuzzy_match(df_yml, df_remote)
        assert report.exact_matches == 1
        assert df_merged.index.tolist() == df_remote.index.tolist() == ["Xtreme Python"]


class TestDenylist:
    def test_repository_list_loads(self):
        denylist = load_denylist()
        assert "codehut.co.uk" in denylist["reject"]
        assert "pyconf.org" in denylist["review"]

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://codehut.co.uk/2026/", ("reject", "codehut.co.uk", "domain does not resolve")),
            ("https://EVENTS.codehut.co.uk/x", ("reject", "codehut.co.uk", "domain does not resolve")),
            ("https://pyconf.org/", ("review", "pyconf.org", "domain registered after the claimed CfP")),
            ("https://notcodehut.co.uk/", None),
            ("https://pycon.org/", None),
            ("", None),
            (float("nan"), None),
        ],
    )
    def test_denied(self, url, expected):
        assert denied(url, DENYLIST) == expected

    def test_drop_denied(self, monkeypatch, tmp_path):
        out = tmp_path / "records.jsonl"
        monkeypatch.setenv("DESK_QUEUE_OUT", str(out))
        df = rows(
            ("Python E-Commerce Forum", 2026, "https://codehut.co.uk/2026/"),
            ("PyConf", 2026, "https://pyconf.org/"),
            ("PyCon Slovakia", 2027, "https://pycon.sk/"),
        )
        kept = drop_denied(df, "python.org", DENYLIST)
        assert kept["conference"].tolist() == ["PyCon Slovakia"]
        (record,) = (json.loads(line) for line in out.read_text(encoding="utf-8").splitlines())
        assert record["kind"] == "candidate"
        assert record["title"] == "PyConf 2026"
        assert record["payload"]["classification"] == "MAYBE"
        assert record["payload"]["source_id"] == "python.org"
        assert record["payload"]["flags"] == ["denylist-review: pyconf.org: domain registered after the claimed CfP"]
        assert normalise_record(record)["id"]

    def test_cfp_link_counts_too(self):
        df = rows(("Some Summit", 2026, "https://summit.example/"))
        df["cfp_link"] = ["https://forms.codehut.co.uk/cfp"]
        assert drop_denied(df, "python.org", DENYLIST).empty


class TestRowsWithoutLink:
    def test_left_out(self, capsys):
        df = rows(
            ("PyDay Chile Santiago", 2026.0, float("nan")),
            ("PyDay Chile Rancagua", 2026.0, ""),
            ("PyDay Chile Valparaiso", 2026.0, "https://pyday.cl/valparaiso"),
        )
        assert drop_rows_without_link(df)["conference"].tolist() == ["PyDay Chile Valparaiso"]
