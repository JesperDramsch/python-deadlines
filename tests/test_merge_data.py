"""Tests for merge_data: the three-way merge of the conference data files during a stopped git merge."""

import datetime as dt
import os
import re
import shutil
import sys
import types
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import merge_data
import sort_yaml
from merge_data import DATA_FILES
from merge_data import MISSING
from merge_data import NO_ENTRY
from merge_data import Conflict
from merge_data import DataError
from merge_data import index_entries
from merge_data import merge_entries
from merge_data import same_value
from merge_data import show
from tidy_conf.yaml import write_conference_yaml

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
CONFERENCES, ARCHIVE, LEGACY = DATA_FILES
FINAID = "https://amsterdam.pydata.org/finaid/"


def entry(conference="PyData Amsterdam", year=2026, **fields):
    """Return a valid conference entry, with fields replaced or added."""
    data = {
        "conference": conference,
        "year": year,
        "link": "https://amsterdam.pydata.org/",
        "cfp": f"{year}-05-11 23:59:00",
        "timezone": "Europe/Amsterdam",
        "place": "Amsterdam, Netherlands",
        "start": date(year, 9, 23),
        "end": date(year, 9, 25),
        "sub": "DATA",
        "location": [{"title": f"{conference} {year}", "latitude": 52.3833, "longitude": 4.9204}],
    }
    data.update(fields)
    return data


def without(data, *names):
    """Return a copy of an entry without the named fields."""
    return {key: value for key, value in data.items() if key not in names}


class TestSameValue:
    def test_dates_compare_as_dates(self):
        assert same_value(date(2026, 9, 23), date(2026, 9, 23))
        assert not same_value(date(2026, 9, 23), date(2026, 9, 24))

    def test_types_must_match(self):
        assert not same_value(1, True)
        assert not same_value(2026, "2026")
        assert not same_value(date(2026, 9, 23), datetime(2026, 9, 23, tzinfo=timezone.utc))

    def test_lists_compare_in_order(self):
        assert same_value(["Online"], ["Online"])
        assert not same_value(["Online", "Berlin"], ["Berlin", "Online"])
        assert not same_value(["Online"], ["Online", "Berlin"])

    def test_mappings_compare_without_key_order(self):
        assert same_value({"latitude": 1.5, "longitude": 2.5}, {"longitude": 2.5, "latitude": 1.5})
        assert not same_value({"latitude": 1.5}, {"latitude": 1.5, "longitude": 2.5})

    def test_nested_values(self):
        first = [{"title": "PyData Amsterdam 2026", "latitude": 52.3833, "longitude": 4.9204}]
        assert same_value(first, [dict(reversed(first[0].items()))])
        assert not same_value(first, [{**first[0], "latitude": 52.0}])


class TestIndexEntries:
    def test_keys_on_conference_and_year(self):
        index = index_entries([entry(year=2025), entry(year=2026)], "ours")
        assert list(index) == [("PyData Amsterdam", 2025), ("PyData Amsterdam", 2026)]

    def test_repeated_key_is_an_error(self):
        with pytest.raises(DataError, match="ours: PyData Amsterdam 2026 appears more than once"):
            index_entries([entry(), entry(cfp="TBA")], "ours")

    def test_entry_must_be_a_mapping(self):
        with pytest.raises(DataError, match="not a mapping"):
            index_entries(["PyData Amsterdam"], "base")

    def test_entry_needs_conference_and_year(self):
        with pytest.raises(DataError, match="no conference or no year"):
            index_entries([without(entry(), "year")], "theirs")


class TestMergeFields:
    def test_unchanged_entry_is_kept(self):
        result = merge_entries([entry()], [entry()], [entry()])
        assert result.entries == [entry()]
        assert result.conflicts == []

    def test_change_on_ours_is_taken(self):
        result = merge_entries([entry()], [entry(cfp_ext="2026-05-25 23:59:00")], [entry()])
        assert result.entries == [entry(cfp_ext="2026-05-25 23:59:00")]
        assert (result.fields_from_ours, result.fields_from_theirs) == (1, 0)

    def test_change_on_theirs_is_taken(self):
        result = merge_entries([entry()], [entry()], [entry(cfp="2026-05-18 23:59:00")])
        assert result.entries == [entry(cfp="2026-05-18 23:59:00")]
        assert (result.fields_from_ours, result.fields_from_theirs) == (0, 1)

    def test_changes_to_different_fields_combine(self):
        result = merge_entries([entry()], [entry(finaid=FINAID)], [entry(cfp="2026-05-18 23:59:00")])
        assert result.entries == [entry(finaid=FINAID, cfp="2026-05-18 23:59:00")]
        assert result.conflicts == []

    def test_same_change_on_both_sides_is_kept(self):
        changed = entry(cfp="2026-05-18 23:59:00")
        result = merge_entries([entry()], [changed], [changed])
        assert result.entries == [changed]
        assert result.conflicts == []

    def test_different_changes_to_one_field_conflict(self):
        result = merge_entries(
            [entry()],
            [entry(cfp="2026-05-18 23:59:00")],
            [entry(cfp="2026-05-25 23:59:00")],
        )
        assert result.conflicts == [
            Conflict(
                ("PyData Amsterdam", 2026),
                "cfp",
                "2026-05-11 23:59:00",
                "2026-05-18 23:59:00",
                "2026-05-25 23:59:00",
            ),
        ]

    def test_field_deleted_on_one_side_is_deleted(self):
        base = entry(twitter="pydataams")
        result = merge_entries([base], [base], [without(base, "twitter")])
        assert result.entries == [entry()]
        assert result.fields_from_theirs == 1

    def test_field_deleted_on_one_side_and_changed_on_the_other_conflicts(self):
        base = entry(twitter="pydataams")
        result = merge_entries([base], [without(base, "twitter")], [entry(twitter="pydata_ams")])
        assert result.conflicts == [
            Conflict(("PyData Amsterdam", 2026), "twitter", "pydataams", MISSING, "pydata_ams"),
        ]

    def test_field_deleted_on_both_sides_is_deleted(self):
        base = entry(twitter="pydataams")
        result = merge_entries([base], [without(base, "twitter")], [without(base, "twitter")])
        assert result.entries == [entry()]

    def test_field_added_on_one_side_is_kept(self):
        result = merge_entries([entry()], [entry()], [entry(bluesky="pydata.bsky.social")])
        assert result.entries == [entry(bluesky="pydata.bsky.social")]

    def test_field_added_differently_on_both_sides_conflicts(self):
        result = merge_entries([entry()], [entry(bluesky="a.bsky.social")], [entry(bluesky="b.bsky.social")])
        assert result.conflicts == [
            Conflict(("PyData Amsterdam", 2026), "bluesky", MISSING, "a.bsky.social", "b.bsky.social"),
        ]

    def test_dates_lists_and_mappings_merge_as_values(self):
        location = [{"title": "PyData Amsterdam 2026", "latitude": 52.37, "longitude": 4.89}]
        ours = entry(extra_places=["Online"])
        theirs = entry(end=date(2026, 9, 26), location=location)
        result = merge_entries([entry()], [ours], [theirs])
        assert result.entries == [entry(extra_places=["Online"], end=date(2026, 9, 26), location=location)]

    def test_mapping_key_order_is_not_a_change(self):
        reordered = dict(reversed(list(entry().items())))
        result = merge_entries([entry()], [reordered], [entry(cfp="2026-05-18 23:59:00")])
        assert result.conflicts == []
        assert result.entries == [entry(cfp="2026-05-18 23:59:00")]
        assert result.fields_from_ours == 0


class TestMergeEntries:
    def test_entries_key_across_files_so_a_move_does_not_matter(self):
        """The reported case: an edit on one side, then both sides sort the entry into archive.yml."""
        europython = entry("EuroPython", 2026, link="https://ep2026.europython.eu/")
        old = entry(year=2025)
        # Each side lists conferences.yml, then archive.yml.
        base = [entry(), europython, old]
        ours = [europython, entry(finaid=FINAID), old]
        theirs = [europython, entry(), old]
        result = merge_entries(base, ours, theirs)
        assert result.conflicts == []
        assert result.entries == [europython, entry(finaid=FINAID), old]

    def test_same_conference_in_two_years_are_two_entries(self):
        result = merge_entries([], [entry(year=2025)], [entry(year=2026)])
        assert result.entries == [entry(year=2025), entry(year=2026)]

    def test_entry_added_on_one_side_is_kept(self):
        new = entry("EuroPython", 2027)
        result = merge_entries([entry()], [entry()], [entry(), new])
        assert result.entries == [entry(), new]
        assert (result.added_ours, result.added_theirs) == (0, 1)

    def test_entry_added_on_both_sides_the_same_is_kept_once(self):
        new = entry("EuroPython", 2027)
        result = merge_entries([], [new], [new])
        assert result.entries == [new]
        assert result.conflicts == []

    def test_entry_added_on_both_sides_differently_conflicts_on_each_difference(self):
        ours = entry("EuroPython", 2027, cfp="TBA")
        theirs = entry("EuroPython", 2027, cfp="2027-02-01 23:59:00", twitter="europython")
        result = merge_entries([], [ours], [theirs])
        assert result.entries == []
        assert result.conflicts == [
            Conflict(("EuroPython", 2027), "cfp", NO_ENTRY, "TBA", "2027-02-01 23:59:00"),
            Conflict(("EuroPython", 2027), "twitter", NO_ENTRY, MISSING, "europython"),
        ]

    def test_entry_deleted_on_ours_and_unchanged_on_theirs_is_deleted(self):
        result = merge_entries([entry(), entry(year=2025)], [entry()], [entry(), entry(year=2025)])
        assert result.entries == [entry()]
        assert (result.deleted_ours, result.deleted_theirs) == (1, 0)

    def test_entry_deleted_on_theirs_and_unchanged_on_ours_is_deleted(self):
        result = merge_entries([entry(), entry(year=2025)], [entry(), entry(year=2025)], [entry()])
        assert result.entries == [entry()]
        assert (result.deleted_ours, result.deleted_theirs) == (0, 1)

    def test_entry_deleted_on_both_sides_is_deleted(self):
        result = merge_entries([entry(), entry(year=2025)], [entry()], [entry()])
        assert result.entries == [entry()]
        assert result.conflicts == []

    def test_entry_deleted_on_ours_and_changed_on_theirs_conflicts(self):
        result = merge_entries([entry()], [], [entry(cfp="2026-05-18 23:59:00")])
        assert result.entries == []
        assert result.conflicts == [
            Conflict(("PyData Amsterdam", 2026), "cfp", "2026-05-11 23:59:00", NO_ENTRY, "2026-05-18 23:59:00"),
        ]

    def test_entry_deleted_on_theirs_and_changed_on_ours_conflicts(self):
        result = merge_entries([entry()], [without(entry(), "timezone")], [])
        assert result.conflicts == [
            Conflict(("PyData Amsterdam", 2026), "timezone", "Europe/Amsterdam", MISSING, NO_ENTRY),
        ]

    def test_place_repeated_within_a_pair_on_one_side_is_an_error(self):
        with pytest.raises(
            DataError,
            match=re.escape("theirs: PyData Amsterdam 2026 (Amsterdam, Netherlands) appears more than once"),
        ):
            merge_entries([entry()], [entry()], [entry(), entry()])

    def test_places_that_differ_only_in_the_country_spelling_are_repeated(self):
        """The sort folds these two into one entry, so the merge must not keep both."""
        with pytest.raises(
            DataError,
            match=re.escape("ours: PyData Amsterdam 2026 (London, UK) appears more than once"),
        ):
            merge_entries([], [entry(place="London, United Kingdom"), entry(place="London, UK")], [])

    def test_pair_the_base_repeats_with_the_same_place_is_an_error(self):
        with pytest.raises(
            DataError,
            match=re.escape("base: PyData Amsterdam 2026 (Amsterdam, Netherlands) appears more than once"),
        ):
            merge_entries([entry(), entry()], [entry()], [entry()])


class TestRepeatedPairs:
    """Editions held in several cities share (conference, year), such as PyCon China 2023."""

    beijing = entry("PyCon China", 2023, place="Beijing, China", start=date(2023, 12, 2), end=date(2023, 12, 2))
    chengdu = entry("PyCon China", 2023, place="Chengdu, China", start=date(2023, 12, 17), end=date(2023, 12, 17))

    def test_a_pair_only_ours_repeats_is_told_apart_by_place(self):
        ours = [{**self.beijing, "twitter": "pyconchina"}, self.chengdu]
        theirs = [{**self.beijing, "cfp": "2023-11-01 23:59:00"}]
        result = merge_entries([self.beijing], ours, theirs)
        assert result.conflicts == []
        assert result.entries == [{**self.beijing, "twitter": "pyconchina", "cfp": "2023-11-01 23:59:00"}, self.chengdu]
        assert (result.added_ours, result.added_theirs) == (1, 0)

    def test_a_pair_only_theirs_repeats_is_told_apart_by_place(self):
        ours = [{**self.beijing, "twitter": "pyconchina"}]
        theirs = [self.beijing, self.chengdu]
        result = merge_entries([self.beijing], ours, theirs)
        assert result.conflicts == []
        assert result.entries == [{**self.beijing, "twitter": "pyconchina"}, self.chengdu]
        assert (result.added_ours, result.added_theirs) == (0, 1)

    def test_places_are_keyed_with_the_country_normalised(self):
        """One side writes "London, UK" where the others have "London, United Kingdom": the same edition."""
        london = entry(place="London, United Kingdom")
        paris = entry(place="Paris, France")
        result = merge_entries(
            [london],
            [{**london, "place": "London, UK"}, paris],
            [{**london, "cfp": "2026-05-18 23:59:00"}],
        )
        assert result.conflicts == []
        assert result.entries == [{**london, "place": "London, UK", "cfp": "2026-05-18 23:59:00"}, paris]

    def test_conflict_names_the_normalised_place(self):
        london = entry(place="London, United Kingdom")
        result = merge_entries(
            [london, entry(place="Paris, France")],
            [{**london, "cfp": "2026-05-18 23:59:00"}, entry(place="Paris, France")],
            [{**london, "cfp": "2026-05-25 23:59:00"}, entry(place="Paris, France")],
        )
        assert [conflict.key for conflict in result.conflicts] == [("PyData Amsterdam", 2026, "London, UK")]

    def test_entries_are_told_apart_by_place(self):
        ours = [{**self.beijing, "twitter": "pyconchina"}, self.chengdu]
        theirs = [self.beijing, {**self.chengdu, "cfp": "2023-11-01 23:59:00"}]
        result = merge_entries([self.beijing, self.chengdu], ours, theirs)
        assert result.conflicts == []
        assert result.entries == [
            {**self.beijing, "twitter": "pyconchina"},
            {**self.chengdu, "cfp": "2023-11-01 23:59:00"},
        ]

    def test_a_place_change_is_a_deletion_and_an_addition(self):
        moved = {**self.chengdu, "place": "Chengdu, Sichuan, China"}
        result = merge_entries([self.beijing, self.chengdu], [self.beijing, moved], [self.beijing, self.chengdu])
        assert result.conflicts == []
        assert result.entries == [self.beijing, moved]
        assert (result.added_ours, result.deleted_ours) == (1, 1)

    def test_conflict_names_the_place(self):
        result = merge_entries(
            [self.beijing, self.chengdu],
            [self.beijing, {**self.chengdu, "cfp": "2023-11-01 23:59:00"}],
            [self.beijing, {**self.chengdu, "cfp": "2023-11-08 23:59:00"}],
        )
        assert [conflict.describe() for conflict in result.conflicts] == [
            'PyCon China 2023 (Chengdu, China), field cfp: base "2023-05-11 23:59:00", '
            'ours "2023-11-01 23:59:00", theirs "2023-11-08 23:59:00"',
        ]

    def test_index_entries_keys_those_pairs_by_place(self):
        index = index_entries([self.beijing, self.chengdu, entry()], "base", {("PyCon China", 2023)})
        assert list(index) == [
            ("PyCon China", 2023, "Beijing, China"),
            ("PyCon China", 2023, "Chengdu, China"),
            ("PyData Amsterdam", 2026),
        ]

    def test_the_repository_data_merges_with_itself(self):
        entries = [item for path in DATA_FILES for item in load(ROOT / path)]
        result = merge_entries(entries, entries, entries)
        assert result.conflicts == []
        assert len(result.entries) == len(entries)

    def test_merge_does_not_change_its_inputs(self):
        base, ours, theirs = [entry()], [entry(cfp="TBA")], [entry(twitter="pydataams")]
        merge_entries(base, ours, theirs)
        assert (base, ours, theirs) == ([entry()], [entry(cfp="TBA")], [entry(twitter="pydataams")])

    def test_summary_counts_both_sides(self):
        result = merge_entries(
            [entry(), entry(year=2025)],
            [entry(cfp="TBA"), entry("EuroPython", 2027)],
            [entry(twitter="pydataams"), entry(year=2025)],
        )
        assert result.summary() == (
            "merged 2 entries: 1 field from HEAD and 1 from MERGE_HEAD, "
            "1 entry added on HEAD and 0 on MERGE_HEAD, 1 deleted on HEAD and 0 on MERGE_HEAD"
        )


class TestConflictReport:
    def test_describe_names_key_field_and_values(self):
        conflict = Conflict(("PyData Amsterdam", 2026), "end", date(2026, 9, 25), date(2026, 9, 26), MISSING)
        assert conflict.describe() == (
            'PyData Amsterdam 2026, field end: base "2026-09-25", ours "2026-09-26", theirs (missing)'
        )

    def test_count_writes_the_noun_in_the_right_form(self):
        assert merge_data.count(1, "field") == "1 field"
        assert merge_data.count(0, "field") == "0 fields"
        assert merge_data.count(2, "entry", "entries") == "2 entries"

    def test_show_formats_sentinels_and_values(self):
        assert show(NO_ENTRY) == "(no entry)"
        assert show("PyCon México") == '"PyCon México"'
        assert show(["Online"]) == '["Online"]'


# The command line, in temporary git repositories.

needs_git = pytest.mark.skipif(GIT is None, reason="git builds the test repositories")


def git(*args, check=True):
    """Run git in the current directory."""
    return merge_data.git(*args, cwd=Path.cwd(), check=check)


def write(path, entries):
    write_conference_yaml(entries, path)


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []


def snapshot():
    return {path: Path(path).read_bytes() if Path(path).exists() else None for path in DATA_FILES}


def commit(message):
    git("add", "-A")
    git("commit", "-q", "-m", message)


def frozen_on(day):
    """Stop the sort's clock at midnight UTC on the given day.

    freezegun cannot be used here: its date objects reach the YAML writer, which cannot represent them.
    """
    moment = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)

    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

    clock = types.SimpleNamespace(datetime=FrozenDatetime, date=dt.date, timedelta=dt.timedelta)
    return patch.object(sort_yaml, "datetime", clock)


def sort_on(day):
    """Run the repository's sort as it would run on the given day."""
    with frozen_on(day):
        merge_data.sort_data(skip_links=True)


def conflicted():
    return merge_data.conflicted_paths(Path.cwd())


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Create an empty git repository on main as the working directory, with the files the schema check reads."""
    root = tmp_path / "repo"
    (root / "_data").mkdir(parents=True)
    (root / "utils").mkdir()
    shutil.copy(ROOT / "_data" / "types.yml", root / "_data" / "types.yml")
    shutil.copy(ROOT / "utils" / "schema.yml", root / "utils" / "schema.yml")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")
    monkeypatch.chdir(root)

    def no_network(*args, **kwargs):
        raise AssertionError("the merge must not geocode or fetch anything in tests")

    monkeypatch.setattr(requests, "get", no_network)
    git("init", "-q", "-b", "main")
    return root


def start_conflict(base, ours, theirs):
    """Commit base on main, ours on the rolling branch and theirs on main, then merge main into the rolling branch.

    Each of base, ours and theirs maps data file paths to their entries. Returns the merge's exit code.
    """
    for path, entries in base.items():
        write(path, entries)
    commit("base")
    git("checkout", "-q", "-b", "auto/conference-updates")
    for path, entries in ours.items():
        write(path, entries)
    commit("ours")
    git("checkout", "-q", "main")
    for path, entries in theirs.items():
        write(path, entries)
    commit("theirs")
    git("checkout", "-q", "auto/conference-updates")
    return git("merge", "--no-edit", "main", check=False).returncode


@needs_git
class TestSortConflictEndToEnd:
    def test_resolves_the_conflict_both_sorts_cause(self, repo, capsys):
        """The rolling branch adds finaid, both sides then sort the entry into archive.yml, and git conflicts."""
        europython = without(
            entry("EuroPython", 2027, link="https://ep2027.europython.eu/", cfp="2027-02-01 23:59:00", sub="PY"),
            "location",
            "timezone",
        )
        europython["place"] = "Online"
        write(CONFERENCES, [entry(), europython])
        write(ARCHIVE, [entry(year=2025)])
        write(LEGACY, [])
        sort_on("2026-10-14")
        commit("base")

        git("checkout", "-q", "-b", "auto/conference-updates")
        data = load(CONFERENCES)
        next(e for e in data if e["conference"] == "PyData Amsterdam")["finaid"] = FINAID
        write(CONFERENCES, data)
        commit("PyData Amsterdam 2026: finaid")
        sort_on("2026-11-15")
        commit("Sort on the rolling branch")

        git("checkout", "-q", "main")
        data = load(CONFERENCES)
        next(e for e in data if e["conference"] == "EuroPython")["cfp_ext"] = "2027-02-15 23:59:00"
        write(CONFERENCES, data)
        sort_on("2026-11-15")
        commit("EuroPython 2027: cfp_ext, then sort on main")

        git("checkout", "-q", "auto/conference-updates")
        assert git("merge", "--no-edit", "main", check=False).returncode != 0
        assert ARCHIVE in conflicted()

        with frozen_on("2026-11-15"):
            assert merge_data.main([]) == 0

        assert conflicted() == []
        # Everything is staged. Only conferences.yml differs from HEAD, whose archive.yml already has the finaid.
        assert git("diff", "--name-only").stdout == ""
        assert git("diff", "--cached", "--name-only").stdout.split() == [CONFERENCES]
        git("commit", "-q", "--no-edit")
        assert len(git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()) == 3

        archive, conferences = load(ARCHIVE), load(CONFERENCES)
        amsterdam = next(e for e in archive if (e["conference"], e["year"]) == ("PyData Amsterdam", 2026))
        assert amsterdam["finaid"] == FINAID
        assert next(e for e in conferences if e["conference"] == "EuroPython")["cfp_ext"] == "2027-02-15 23:59:00"
        keys = sorted((e["conference"], e["year"]) for path in DATA_FILES for e in load(path))
        assert keys == [("EuroPython", 2027), ("PyData Amsterdam", 2025), ("PyData Amsterdam", 2026)]
        assert "merged 3 entries: 1 field from HEAD and 1 from MERGE_HEAD" in capsys.readouterr().out

    def test_a_data_file_missing_on_one_side_counts_as_empty(self, repo):
        code = start_conflict(
            {CONFERENCES: [entry()]},
            {ARCHIVE: [entry(year=2025)]},
            {ARCHIVE: [entry(year=2024)]},
        )
        assert code != 0
        assert conflicted() == [ARCHIVE]

        with frozen_on("2026-10-14"):
            assert merge_data.main([]) == 0

        assert conflicted() == []
        assert [(e["conference"], e["year"]) for e in load(ARCHIVE)] == [
            ("PyData Amsterdam", 2025),
            ("PyData Amsterdam", 2024),
        ]
        assert [(e["conference"], e["year"]) for e in load(CONFERENCES)] == [("PyData Amsterdam", 2026)]

    def test_a_second_city_added_on_main_merges_by_place(self, repo):
        """Main respells the country and adds a second city for the edition; the rolling branch adds finaid."""
        london = entry(place="London, United Kingdom")
        paris = entry(
            place="Paris, France",
            link="https://paris.pydata.org/",
            location=[{"title": "PyData Amsterdam 2026", "latitude": 48.8566, "longitude": 2.3522}],
        )
        code = start_conflict(
            {CONFERENCES: [london]},
            {CONFERENCES: [{**london, "finaid": FINAID}]},
            {CONFERENCES: [{**london, "place": "London, UK", "twitter": "pydataams"}, paris]},
        )
        assert code != 0
        assert conflicted() == [CONFERENCES]

        with frozen_on("2026-10-14"):
            assert merge_data.main([]) == 0

        assert conflicted() == []
        assert {e["place"]: e for e in load(CONFERENCES)} == {
            "London, UK": {**london, "place": "London, UK", "finaid": FINAID, "twitter": "pydataams"},
            "Paris, France": paris,
        }


class TestCheckAfterTheSort:
    """write_and_sort compares the keys before and after the sort, places of a repeated pair normalised."""

    london = entry(place="London, UK")
    paris = entry(place="Paris, France")

    @pytest.fixture()
    def root(self, tmp_path):
        """A repository root whose data files hold one entry each, to check what a failure restores."""
        (tmp_path / "_data").mkdir()
        for year, path in zip((2026, 2025, 2019), DATA_FILES, strict=True):
            write(str(tmp_path / path), [entry(year=year)])
        return tmp_path

    def test_a_country_the_sort_spells_differently_is_the_same_entry(self, root, monkeypatch):
        def respelling_sort(base, **kwargs):
            write(str(Path(base, CONFERENCES)), [{**self.london, "place": "London, United Kingdom"}, self.paris])

        monkeypatch.setattr(merge_data, "sort_data", respelling_sort)

        merge_data.write_and_sort([self.london, self.paris], root)

        assert [e["place"] for e in load(root / CONFERENCES)] == ["London, United Kingdom", "Paris, France"]

    def test_an_entry_the_sort_folds_into_another_is_lost(self, root, monkeypatch):
        before = {path: (root / path).read_bytes() for path in DATA_FILES}

        def folding_sort(base, **kwargs):
            write(str(Path(base, CONFERENCES)), [self.london])

        monkeypatch.setattr(merge_data, "sort_data", folding_sort)

        with pytest.raises(DataError, match=re.escape("lost: PyData Amsterdam 2026 (Paris, France); gained: none")):
            merge_data.write_and_sort([self.london, self.paris], root)

        assert {path: (root / path).read_bytes() for path in DATA_FILES} == before


@needs_git
class TestCommandLineRefusals:
    @pytest.fixture()
    def resolvable(self, repo):
        """Stop a merge on a conflict that merges field by field: ours adds finaid, theirs a twitter handle."""
        code = start_conflict(
            {CONFERENCES: [entry()]},
            {CONFERENCES: [entry(finaid=FINAID)]},
            {CONFERENCES: [entry(twitter="pydataams")]},
        )
        assert code != 0
        assert conflicted() == [CONFERENCES]
        return snapshot()

    def test_resolvable_conflict_merges_both_changes(self, resolvable):
        with frozen_on("2026-10-14"):
            assert merge_data.main([]) == 0
        assert conflicted() == []
        assert load(CONFERENCES) == [entry(finaid=FINAID, twitter="pydataams")]
        assert load(ARCHIVE) == []
        assert load(LEGACY) == []

    def test_field_changed_on_both_sides_stops_and_writes_nothing(self, repo, capsys):
        code = start_conflict(
            {CONFERENCES: [entry()]},
            {CONFERENCES: [entry(cfp="2026-05-18 23:59:00")]},
            {CONFERENCES: [entry(cfp="2026-05-25 23:59:00")]},
        )
        assert code != 0
        before = snapshot()

        assert merge_data.main([]) == 1

        assert snapshot() == before
        assert conflicted() == [CONFERENCES]
        err = capsys.readouterr().err
        assert "1 conflict to resolve by hand, nothing written" in err
        assert (
            'PyData Amsterdam 2026, field cfp: base "2026-05-11 23:59:00", '
            'ours "2026-05-18 23:59:00", theirs "2026-05-25 23:59:00"'
        ) in err

    def test_conflict_outside_the_data_files_exits_2(self, repo, capsys):
        Path("README.md").write_text("base\n", encoding="utf-8")
        write(CONFERENCES, [entry()])
        commit("base")
        git("checkout", "-q", "-b", "auto/conference-updates")
        Path("README.md").write_text("ours\n", encoding="utf-8")
        write(CONFERENCES, [entry(finaid=FINAID)])
        commit("ours")
        git("checkout", "-q", "main")
        Path("README.md").write_text("theirs\n", encoding="utf-8")
        write(CONFERENCES, [entry(twitter="pydataams")])
        commit("theirs")
        git("checkout", "-q", "auto/conference-updates")
        assert git("merge", "--no-edit", "main", check=False).returncode != 0
        assert sorted(conflicted()) == sorted(["README.md", CONFERENCES])
        before = snapshot()

        assert merge_data.main([]) == 2

        assert snapshot() == before
        err = capsys.readouterr().err
        assert "conflicts outside the data files" in err
        assert "  README.md" in err
        assert CONFERENCES not in err

    def test_no_merge_in_progress_exits_2(self, repo, capsys):
        write(CONFERENCES, [entry()])
        commit("base")
        assert merge_data.main([]) == 2
        assert "no merge in progress" in capsys.readouterr().err

    def test_repeated_key_exits_1(self, repo, capsys):
        code = start_conflict(
            {CONFERENCES: [entry()], ARCHIVE: []},
            {CONFERENCES: [entry(finaid=FINAID)]},
            {CONFERENCES: [entry(twitter="pydataams")], ARCHIVE: [entry()]},
        )
        assert code != 0
        before = snapshot()

        assert merge_data.main([]) == 1

        assert snapshot() == before
        assert (
            "theirs: PyData Amsterdam 2026 (Amsterdam, Netherlands) appears more than once" in capsys.readouterr().err
        )

    def test_failed_sort_restores_the_files(self, resolvable, monkeypatch, capsys):
        def failing_sort(**kwargs):
            Path(CONFERENCES).write_text("half written\n", encoding="utf-8")
            raise ValueError("1 conferences failed validation; refusing to write data files")

        monkeypatch.setattr(merge_data, "sort_data", failing_sort)

        assert merge_data.main([]) == 1

        assert snapshot() == resolvable
        assert conflicted() == [CONFERENCES]
        assert "failed validation" in capsys.readouterr().err

    def test_lost_entry_after_the_sort_restores_the_files(self, resolvable, monkeypatch, capsys):
        def lossy_sort(**kwargs):
            write(CONFERENCES, [])

        monkeypatch.setattr(merge_data, "sort_data", lossy_sort)

        assert merge_data.main([]) == 1

        assert snapshot() == resolvable
        assert conflicted() == [CONFERENCES]
        assert "lost: PyData Amsterdam 2026" in capsys.readouterr().err
