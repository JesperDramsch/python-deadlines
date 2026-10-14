"""Tests for the daily canonical import.

utils/main.py runs every day: the python.org import, the sort, the
python-organizers import and the sort again. A review of that run found five
faults, each covered here:

- Country names were replaced inside every text field, so a Google Form id
  with "GB" in it changed, and "PyCon Korea" grew a "South" on each run.
- The sort did not fold an importer's copy of an archived edition into the
  stored entry when only the spelling of the country differed.
- An upcoming entry with two or more extra_places or location items stopped
  both importers.
- In January both importers dropped last year's editions that were still in
  conferences.yml.
- The coc field was never link-checked.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib import error as urllib_error

import pandas as pd
import pytest
import yaml
from freezegun import freeze_time

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "utils"))

import import_python_official
import import_python_organizers
import sort_yaml
from tidy_conf.deduplicate import deduplicate
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import merge_conferences
from tidy_conf.links import REDUNDANT_LINK_FIELDS
from tidy_conf.links import drop_redundant_link_fields
from tidy_conf.schema import get_schema

FORM = "https://docs.google.com/forms/d/e/1FAIpQLSfGBq7Wales/viewform"


def sheet_rows(*entries: dict) -> pd.DataFrame:
    """Remote rows with every schema column, as the organizers import builds them."""
    return pd.concat([pd.DataFrame(columns=get_schema().columns), pd.DataFrame(list(entries))], ignore_index=True)


def merge(df_yml: pd.DataFrame, df_remote: pd.DataFrame) -> pd.DataFrame:
    """Merge one year the way both importers do."""
    with patch("tidy_conf.interactive_merge.query_yes_no", side_effect=AssertionError("no question expected")):
        df_merged, df_remote, _report = fuzzy_match(df_yml, df_remote)
        df_merged = deduplicate(df_merged.drop(["conference"], axis=1))
        return merge_conferences(df_merged, deduplicate(df_remote)).set_index("conference")


def edition(conference: str, **fields) -> dict:
    """A 2026 edition with the required fields."""
    return {
        "conference": conference,
        "year": 2026,
        "link": f"https://{conference.lower().replace(' ', '')}.example/",
        "cfp": "TBA",
        "place": "Online",
        "start": "2026-08-13",
        "end": "2026-08-15",
        **fields,
    }


class TestCountryNamesStayInPlace:
    """Country names are normalised in the place field and nowhere else."""

    def test_yaml_only_row_comes_out_unchanged(self, mock_title_mappings):
        korea = edition(
            "PyCon South Korea",
            alt_name="PyCon Korea",
            cfp_link=FORM,
            note="Online in England and Wales",
            place="Seoul, South Korea",
        )
        result = merge(pd.DataFrame([korea]), sheet_rows(edition("EuroPython", place="Prague, Czechia")))
        row = result.loc["PyCon South Korea"]
        assert row["alt_name"] == "PyCon Korea"
        assert row["cfp_link"] == FORM
        assert row["note"] == "Online in England and Wales"
        assert row["place"] == "Seoul, South Korea"

    def test_matched_row_comes_out_unchanged(self, mock_title_mappings):
        korea = edition("PyCon South Korea", alt_name="PyCon Korea", cfp_link=FORM, place="Seoul, South Korea")
        result = merge(pd.DataFrame([korea]), sheet_rows(korea))
        assert result.loc["PyCon South Korea", "alt_name"] == "PyCon Korea"
        assert result.loc["PyCon South Korea", "cfp_link"] == FORM

    def test_place_is_still_normalised(self, mock_title_mappings):
        scipy = edition("SciPy", place="Tacoma, United States of America")
        result = merge(pd.DataFrame([scipy]), sheet_rows(edition("EuroPython", place="Prague, Czechia")))
        assert result.loc["SciPy", "place"] == "Tacoma, USA"


class TestListFields:
    """extra_places and location hold lists, which the merge must not test for truth."""

    EDITION = edition(
        "PyCon China",
        place="Shanghai, China",
        extra_places=["Beijing, China", "Online"],
        location=[
            {"title": "PyCon China 2026", "latitude": 31.2304, "longitude": 121.4737},
            {"title": "PyCon China 2026", "latitude": 39.9042, "longitude": 116.4074},
        ],
    )

    def test_yaml_lists_are_kept(self, mock_title_mappings):
        remote = {key: value for key, value in self.EDITION.items() if key not in ("extra_places", "location")}
        result = merge(pd.DataFrame([self.EDITION]), sheet_rows(remote))
        assert result.loc["PyCon China", "extra_places"] == self.EDITION["extra_places"]
        assert result.loc["PyCon China", "location"] == self.EDITION["location"]

    def test_yaml_list_wins_over_a_different_remote_list(self, mock_title_mappings):
        remote = {**self.EDITION, "extra_places": ["Online"], "location": self.EDITION["location"][:1]}
        result = merge(pd.DataFrame([self.EDITION]), sheet_rows(remote))
        assert result.loc["PyCon China", "extra_places"] == self.EDITION["extra_places"]
        assert result.loc["PyCon China", "location"] == self.EDITION["location"]

    @pytest.mark.parametrize("empty", [float("nan"), None, []])
    def test_remote_list_fills_an_empty_yaml_value(self, mock_title_mappings, empty):
        yml = {**self.EDITION, "extra_places": empty}
        result = merge(pd.DataFrame([yml]), sheet_rows(self.EDITION))
        assert result.loc["PyCon China", "extra_places"] == self.EDITION["extra_places"]


# An importer's copy of an archived edition, and the entry as stored
LONDON_COPY = {"conference": "PyData London", "year": 2026, "place": "London, UK", "cfp": "TBA"}
LONDON_STORED = {
    "conference": "PyData London",
    "year": 2026,
    "place": "London, United Kingdom",
    "cfp": "2026-02-22 23:59:00",
    "coc": "https://pydata.org/code-of-conduct/",
}


class TestMergeDuplicates:
    """The sort folds an importer's copy of an edition into the stored entry."""

    def test_country_spellings_fold(self):
        (entry,) = sort_yaml.merge_duplicates([dict(LONDON_COPY), dict(LONDON_STORED)])
        assert entry["place"] == "London, UK"
        assert entry["cfp"] == "2026-02-22 23:59:00"
        assert entry["coc"] == "https://pydata.org/code-of-conduct/"

    def test_other_places_do_not_fold(self):
        other = {**LONDON_STORED, "place": "Leeds, UK"}
        assert len(sort_yaml.merge_duplicates([dict(LONDON_COPY), other])) == 2

    def test_stored_places_are_not_rewritten(self):
        entries = [
            {"conference": "SciPy US", "year": 2021, "place": "Austin, US"},
            {"conference": "PyCon South Korea", "year": 2014, "place": "Seoul, Korea"},
        ]
        assert sort_yaml.merge_duplicates([dict(entry) for entry in entries]) == entries

    def test_sort_leaves_one_entry(self, tmp_path):
        """The importer's copy in conferences.yml and the archived entry become one.

        The sort is not run under freeze_time: yaml cannot write the dates
        freezegun makes. The edition is past either way.
        """
        data = tmp_path / "_data"
        data.mkdir()
        stored = {
            "conference": "PyData London",
            "year": 2026,
            "link": "https://pydata.org/london2026/",
            "cfp": "2026-02-22 23:59:00",
            "place": "London, United Kingdom",
            "start": date(2026, 6, 5),
            "end": date(2026, 6, 7),
            "sub": "DATA",
            "location": [{"title": "PyData London 2026", "latitude": 51.5074, "longitude": -0.1278}],
        }
        copy = {**stored, "place": "London, UK"}
        for name, entries in (("conferences", [copy]), ("archive", [stored]), ("legacy", [])):
            (data / f"{name}.yml").write_text(yaml.safe_dump(entries), encoding="utf-8")

        sort_yaml.sort_data(base=str(tmp_path), skip_links=True)

        entries = [
            entry
            for name in ("conferences", "archive", "legacy")
            for entry in yaml.safe_load((data / f"{name}.yml").read_text(encoding="utf-8")) or []
        ]
        assert [(entry["conference"], entry["year"]) for entry in entries] == [("PyData London", 2026)]


# A December edition that the sort archives only in mid January, an upcoming
# edition with list fields, and an archived edition of the same year.
DECEMBER = {
    "conference": "PyData Global",
    "year": 2026,
    "link": "https://pydata.org/global2026/",
    "cfp": "2026-08-31 23:59:00",
    "place": "Online",
    "start": date(2026, 12, 8),
    "end": date(2026, 12, 10),
    "sub": "DATA",
}
CHINA = {
    "conference": "PyCon China",
    "year": 2027,
    "link": "https://cn.pycon.org/2027/",
    "cfp": "2027-03-31 23:59:00",
    "place": "Shanghai, China",
    "extra_places": ["Beijing, China", "Online"],
    "start": date(2027, 6, 12),
    "end": date(2027, 6, 13),
    "sub": "PY",
    "location": [
        {"title": "PyCon China 2027", "latitude": 31.2304, "longitude": 121.4737},
        {"title": "PyCon China 2027", "latitude": 39.9042, "longitude": 116.4074},
    ],
}
ARCHIVED = {
    "conference": "EuroPython",
    "year": 2026,
    "link": "https://ep2026.europython.eu/",
    "cfp": "2026-02-08 23:59:00",
    "place": "Prague, Czechia",
    "start": date(2026, 7, 13),
    "end": date(2026, 7, 19),
    "sub": "PY",
}


def load_from(base: Path):
    """Stand in for load_conferences, reading the data files under base."""

    def load() -> pd.DataFrame:
        frames = [pd.DataFrame(columns=get_schema().columns)]
        for name in ("conferences", "archive", "legacy"):
            entries = yaml.safe_load(Path(base, "_data", f"{name}.yml").read_text(encoding="utf-8")) or []
            frames.append(pd.DataFrame.from_dict(entries))
        return pd.concat(frames, ignore_index=True).set_index("conference", drop=False)

    return load


def run_official(base: Path) -> None:
    """Run the python.org import on the data under base, with one calendar event."""
    ics = pd.DataFrame(
        [["PyCon China", 2027, "TBA", "2027-06-12", "2027-06-13", "https://cn.pycon.org/2027/", "Shanghai, China"]],
        columns=["conference", "year", "cfp", "start", "end", "link", "place"],
    )
    with (
        patch.object(import_python_official, "load_conferences", side_effect=load_from(base)),
        patch.object(import_python_official, "ics_to_dataframe", return_value=ics),
    ):
        assert import_python_official.main(base=str(base))


def run_organizers(base: Path) -> None:
    """Run the python-organizers import on the data under base, with one sheet row."""
    sheet = pd.DataFrame(
        [
            {
                "Subject": "PyCon China 2027",
                "Start Date": "2027-06-12",
                "End Date": "2027-06-13",
                "Location": "Shanghai, China",
                "Country": "CHN",
                "Venue": float("nan"),
                "Tutorial Deadline": float("nan"),
                "Talk Deadline": "2027-03-31",
                "Website URL": "https://cn.pycon.org/2027/",
                "Proposal URL": float("nan"),
                "Sponsorship URL": float("nan"),
            },
        ],
    )

    def load_remote(year: int) -> pd.DataFrame:
        if year != 2027:
            raise urllib_error.HTTPError(f"https://example.invalid/{year}.csv", 404, "Not Found", None, None)
        return import_python_organizers.map_columns(sheet.copy())

    Path(base, "utils", "conferences").mkdir(parents=True)
    with (
        patch.object(import_python_organizers, "load_conferences", side_effect=load_from(base)),
        patch.object(import_python_organizers, "load_remote", side_effect=load_remote),
    ):
        import_python_organizers.main(base=str(base))


@pytest.fixture()
def data_files(tmp_path, monkeypatch, mock_title_mappings):
    """Data files on 2027-01-05, before the sort has archived December's editions."""
    monkeypatch.delenv("DESK_QUEUE_OUT", raising=False)
    data = tmp_path / "_data"
    data.mkdir()
    for name, entries in (("conferences", [CHINA, DECEMBER]), ("archive", [ARCHIVED]), ("legacy", [])):
        (data / f"{name}.yml").write_text(yaml.safe_dump(entries), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("run_import", [run_official, run_organizers], ids=["python.org", "python-organizers"])
class TestImportInJanuary:
    """Both importers rebuild conferences.yml from the editions of this year on."""

    @freeze_time("2027-01-05")
    def test_last_years_editions_are_kept(self, data_files, run_import):
        run_import(data_files)
        written = yaml.safe_load((data_files / "_data" / "conferences.yml").read_text(encoding="utf-8"))
        assert DECEMBER in written
        assert {(entry["conference"], entry["year"]) for entry in written} == {
            ("PyCon China", 2027),
            ("PyData Global", 2026),
        }

    @freeze_time("2027-01-05")
    def test_list_fields_survive(self, data_files, run_import):
        run_import(data_files)
        written = yaml.safe_load((data_files / "_data" / "conferences.yml").read_text(encoding="utf-8"))
        (china,) = (entry for entry in written if entry["conference"] == "PyCon China")
        assert china["extra_places"] == CHINA["extra_places"]
        assert china["location"] == CHINA["location"]


class TestCodeOfConductLinks:
    """coc is a sub-page link like cfp_link, sponsor and finaid."""

    @patch("sort_yaml.get_cache", return_value=(set(), set()))
    @patch("sort_yaml.check_link_availability", side_effect=lambda url, *_args, **_kwargs: url)
    def test_check_links_checks_coc(self, mock_check_link, mock_get_cache):
        data = [
            {
                "conference": "PyCon Testland",
                "year": 2026,
                "link": "https://2026.pycon.test/",
                "cfp_link": "https://2026.pycon.test/cfp/",
                "sponsor": "https://2026.pycon.test/sponsors/",
                "finaid": "https://2026.pycon.test/finaid/",
                "coc": "https://2026.pycon.test/coc/",
                "start": date(2026, 6, 1),
            },
        ]
        sort_yaml.check_links(data)
        fields = [call.kwargs["field"] for call in mock_check_link.call_args_list]
        assert fields == ["link", "cfp_link", "sponsor", "finaid", "coc"]

    def test_coc_is_a_redundant_link_field(self):
        assert REDUNDANT_LINK_FIELDS == ("cfp_link", "sponsor", "finaid", "coc")

    @pytest.mark.parametrize("coc", ["https://2027.pycon.de/", "https://pycon.de/"])
    def test_homepage_coc_is_dropped(self, coc):
        (entry,) = drop_redundant_link_fields(
            [
                {"conference": "PyCon DE", "year": 2027, "link": "https://2027.pycon.de/", "coc": coc},
            ],
        )
        assert "coc" not in entry

    def test_coc_page_is_kept(self):
        coc = "https://2027.pycon.de/code-of-conduct/"
        (entry,) = drop_redundant_link_fields(
            [
                {"conference": "PyCon DE", "year": 2027, "link": "https://2027.pycon.de/", "coc": coc},
            ],
        )
        assert entry["coc"] == coc
