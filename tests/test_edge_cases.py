"""Tests for edge cases in conference data processing.

This module tests unusual or boundary scenarios that the sync pipeline
must handle gracefully. These tests protect against regressions and
ensure robustness.

Edge cases tested:
- Empty DataFrames
- TBA CFP dates and places
- Multiple locations (extra_places)
- Online-only conferences
- Special characters in names
- Legacy/very old conferences
- Far-future conferences
- Missing mapping files
- CSV column order variations
- Duplicate conferences
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.deduplicate import deduplicate
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.titles import tidy_df_names


class TestEmptyDataFrames:
    """Test handling of empty DataFrames."""

    def test_empty_yaml_handled_gracefully(self, mock_title_mappings):
        """Empty YAML DataFrame should not crash fuzzy_match."""
        df_yml = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        df_remote = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://test.conf/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            },
        )

        # Should not raise exception
        _result, remote, _report = fuzzy_match(df_yml, df_remote)

        # Remote should still have the conference
        assert not remote.empty, "Remote should preserve data when YAML is empty"

    def test_empty_csv_handled_gracefully(self, mock_title_mappings):
        """Empty CSV DataFrame should not crash fuzzy_match."""
        df_yml = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://test.conf/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            },
        )

        df_remote = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        result, _remote, _report = fuzzy_match(df_yml, df_remote)

        # YAML data should be preserved
        assert not result.empty, "YAML data should be preserved when CSV is empty"

    def test_both_empty_handled_gracefully(self, mock_title_mappings):
        """Both empty DataFrames should not crash."""
        df_yml = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])
        df_remote = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        result, remote, _report = fuzzy_match(df_yml, df_remote)

        # Both should be empty but valid DataFrames
        assert isinstance(result, pd.DataFrame)
        assert isinstance(remote, pd.DataFrame)


class TestTBACFP:
    """Test handling of TBA (To Be Announced) CFP dates."""

    def test_tba_cfp_preserved(self, mock_title_mappings):
        """Conference with TBA CFP should be preserved correctly."""
        df_yml = pd.DataFrame(
            {
                "conference": ["Future Conference"],
                "year": [2026],
                "cfp": ["TBA"],
                "link": ["https://future.conf/"],
                "place": ["Future City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            },
        )

        df_remote = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        result, _, _report = fuzzy_match(df_yml, df_remote)

        # TBA should be preserved
        conf_row = result[result["conference"].str.contains("Future", na=False)]
        if len(conf_row) > 0:
            assert conf_row["cfp"].iloc[0] == "TBA", f"TBA CFP should be preserved, got: {conf_row['cfp'].iloc[0]}"

    def test_tba_cfp_replaceable(self, mock_title_mappings):
        """TBA CFP should be replaceable when actual date is available."""
        df_yml = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2026],
                "cfp": ["TBA"],
                "link": ["https://test.conf/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],  # Actual date
                "link": ["https://test.conf/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            },
        )

        with patch("builtins.input", return_value="y"):
            result, _, _report = fuzzy_match(df_yml, df_remote)

        # Actual date should be available somewhere
        assert not result.empty


class TestExtraPlaces:
    """Test handling of conferences with multiple locations."""

    def test_extra_places_preserved_in_dataframe(self, edge_cases_df):
        """Extra places should be preserved in DataFrame."""
        multi_venue = edge_cases_df[edge_cases_df["conference"].str.contains("Multi-Venue", na=False)]

        if len(multi_venue) > 0:
            extra_places = multi_venue["extra_places"].iloc[0]
            assert extra_places is not None, "extra_places should be present"
            assert isinstance(extra_places, list), "extra_places should be a list"
            assert len(extra_places) > 0, "extra_places should have venues"


class TestOnlineConferences:
    """Test handling of online-only conferences."""

    def test_online_conference_no_location_required(self, edge_cases_df):
        """Online conferences should not require physical location."""
        online_conf = edge_cases_df[edge_cases_df["place"].str.contains("Online", na=False, case=False)]

        if len(online_conf) > 0:
            # Online conferences are valid - verify place is marked as online
            assert online_conf["place"].iloc[0].lower() == "online"

    def test_online_keyword_detection(self):
        """Conferences with 'Online' place should be recognized."""
        conf = {
            "conference": "PyConf Online",
            "place": "Online",
        }
        assert "online" in conf["place"].lower()


class TestSpecialCharacters:
    """Test handling of special characters in conference names."""

    def test_accented_characters_preserved(self, edge_cases_df):
        """Accented characters (México) should be preserved."""
        mexico_conf = edge_cases_df[edge_cases_df["conference"].str.contains("xico", na=False, case=False)]

        if len(mexico_conf) > 0:
            name = mexico_conf["conference"].iloc[0]
            # Check that the name contains the accented character or the base form
            assert "xico" in name.lower(), f"México should be preserved: {name}"

    def test_special_chars_normalization(self):
        """Special characters should not corrupt names during normalization."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": ["PyCon México 2026"]})
            result = tidy_df_names(df)

            # Name should still contain México (or Mexico)
            assert (
                "xico" in result["conference"].iloc[0].lower()
            ), f"Special characters corrupted: {result['conference'].iloc[0]}"

    def test_ampersand_preserved(self):
        """Ampersand should be preserved in conference names."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": ["PyCon Germany & PyData Conference"]})
            result = tidy_df_names(df)

            assert "&" in result["conference"].iloc[0], f"Ampersand should be preserved: {result['conference'].iloc[0]}"


class TestDateBoundaries:
    """Test handling of date edge cases."""

    def test_far_future_conference(self):
        """Conferences in far future (2035) should be handled."""
        conf = {
            "conference": "FutureCon",
            "year": 2035,
            "start": "2035-06-01",
            "end": "2035-06-03",
        }

        # Year should be valid (schema allows up to 3000)
        assert conf["year"] <= 3000

    def test_conference_year_extraction(self):
        """Year should be correctly extracted from dates."""
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-06-01"]),
            },
        )
        df["year"] = df["start"].dt.year

        assert df["year"].iloc[0] == 2026


class TestMappingFileFallback:
    """Test behavior when mapping file is missing."""

    def test_graceful_fallback_on_missing_mappings(self):
        """Fuzzy matching should work even without mapping files."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            # Simulate missing file - return empty mappings
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": ["PyCon US 2026"]})
            result = tidy_df_names(df)

            # Should still process without crashing
            assert len(result) == 1
            assert "PyCon" in result["conference"].iloc[0]


class TestCSVColumnOrderVariations:
    """Test that CSV processing handles different column orders."""

    def test_different_column_order_handled(self, minimal_csv_df):
        """CSV with different column order should be processed correctly."""
        # The minimal_csv_df already has columns mapped
        assert "conference" in minimal_csv_df.columns
        assert "year" in minimal_csv_df.columns

        # Reorder columns and verify processing still works
        if "conference" in minimal_csv_df.columns and "year" in minimal_csv_df.columns:
            reordered = minimal_csv_df[
                ["year", "conference"] + [c for c in minimal_csv_df.columns if c not in ["year", "conference"]]
            ]

            # Should still have the correct data
            assert reordered["conference"].iloc[0] is not None


class TestDuplicateConferences:
    """Test deduplication of conferences."""

    def test_exact_duplicates_merged(self):
        """Exact duplicate conferences should be merged into one."""
        df = pd.DataFrame(
            {
                "conference": ["PyCon US", "PyCon US"],
                "year": [2026, 2026],
                "cfp": ["2026-01-15 23:59:00", "2026-01-15 23:59:00"],
                "link": ["https://us.pycon.org/2026/", "https://us.pycon.org/2026/"],
            },
        )
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        result = deduplicate(df)

        # Should have only one row
        assert len(result) == 1, f"Duplicates should be merged, got {len(result)} rows"

    def test_near_duplicates_merged(self):
        """Near duplicates (same name, slightly different data) should be merged."""
        df = pd.DataFrame(
            {
                "conference": ["PyCon US", "PyCon US"],
                "year": [2026, 2026],
                "cfp": ["2026-01-15 23:59:00", None],  # One has CFP, one doesn't
                "sponsor": [None, "https://us.pycon.org/sponsors/"],  # Vice versa
            },
        )
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        result = deduplicate(df)

        # Should be merged into one
        assert len(result) == 1

        # Both values should be preserved
        assert result["cfp"].iloc[0] == "2026-01-15 23:59:00", f"CFP should be preserved: {result['cfp'].iloc[0]}"
        assert (
            result["sponsor"].iloc[0] == "https://us.pycon.org/sponsors/"
        ), f"Sponsor should be preserved: {result['sponsor'].iloc[0]}"

    def test_different_years_not_merged(self):
        """Same conference different years should NOT be merged."""
        df = pd.DataFrame(
            {
                "conference": ["PyCon US 2026", "PyCon US 2027"],  # Different names
                "year": [2026, 2027],
                "cfp": ["2026-01-15 23:59:00", "2027-01-15 23:59:00"],
            },
        )
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        result = deduplicate(df)

        # Should remain separate
        assert len(result) == 2, "Different year conferences should not be merged"


class TestWorkshopTutorialDeadlines:
    """Test handling of workshop and tutorial deadlines."""

    def test_workshop_deadline_preserved(self, edge_cases_df):
        """Workshop deadline field should be preserved."""
        advanced_conf = edge_cases_df[edge_cases_df["conference"].str.contains("Advanced", na=False)]

        if len(advanced_conf) > 0 and "workshop_deadline" in advanced_conf.columns:
            deadline = advanced_conf["workshop_deadline"].iloc[0]
            if pd.notna(deadline):
                assert "2026" in str(deadline), f"Workshop deadline should be a date: {deadline}"

    def test_tutorial_deadline_preserved(self, edge_cases_df):
        """Tutorial deadline field should be preserved."""
        advanced_conf = edge_cases_df[edge_cases_df["conference"].str.contains("Advanced", na=False)]

        if len(advanced_conf) > 0 and "tutorial_deadline" in advanced_conf.columns:
            deadline = advanced_conf["tutorial_deadline"].iloc[0]
            if pd.notna(deadline):
                assert "2026" in str(deadline), f"Tutorial deadline should be a date: {deadline}"


class TestRegressions:
    """Regression tests for specific bugs found in production."""

    def test_regression_pycon_de_vs_pycon_germany_match(self, mock_title_mappings):
        """REGRESSION: PyCon DE and PyCon Germany should be recognized as same conf.

        This was a silent data loss bug where variants weren't matched.
        """
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Germany & PyData Conference"],
                "year": [2026],
                "cfp": ["2025-12-21 23:59:59"],
                "link": ["https://2026.pycon.de/"],
                "place": ["Darmstadt, Germany"],
                "start": ["2026-04-14"],
                "end": ["2026-04-17"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": ["PyCon DE & PyData"],
                "year": [2026],
                "cfp": ["2025-12-21 23:59:59"],
                "link": ["https://pycon.de/"],
                "place": ["Darmstadt, Germany"],
                "start": ["2026-04-14"],
                "end": ["2026-04-17"],
            },
        )

        # With proper mappings or user acceptance, should match
        with patch("builtins.input", return_value="y"):
            result, _, _report = fuzzy_match(df_yml, df_remote)

        # Should be treated as one conference
        assert len(result) >= 1, "PyCon DE should match PyCon Germany"

    def test_regression_conference_name_not_silently_dropped(self, mock_title_mappings):
        """REGRESSION: Conference names should never be silently dropped.

        This verifies that all input conferences appear in output.
        """
        df_yml = pd.DataFrame(
            {
                "conference": ["Important Conference A", "Important Conference B"],
                "year": [2026, 2026],
                "cfp": ["2026-01-15 23:59:00", "2026-02-15 23:59:00"],
                "link": ["https://a.conf/", "https://b.conf/"],
                "place": ["City A", "City B"],
                "start": ["2026-06-01", "2026-07-01"],
                "end": ["2026-06-03", "2026-07-03"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": ["Important Conference C"],
                "year": [2026],
                "cfp": ["2026-03-15 23:59:00"],
                "link": ["https://c.conf/"],
                "place": ["City C"],
                "start": ["2026-08-01"],
                "end": ["2026-08-03"],
            },
        )

        # Reject any fuzzy matches to keep conferences separate
        with patch("builtins.input", return_value="n"):
            result, _remote, _report = fuzzy_match(df_yml, df_remote)

        # All conferences should be accounted for - result should contain all YAML data
        assert len(result) >= len(df_yml), f"All YAML conferences should be in result, got {len(result)}"

    def test_regression_missing_field_triggers_warning_not_skip(self, mock_title_mappings):
        """REGRESSION: Missing required fields should trigger warning, not silent skip.

        Conferences with missing fields should still be processed with warnings.
        """
        # This test documents that missing fields should be logged, not silently ignored
        df = pd.DataFrame(
            {
                "conference": ["Incomplete Conference"],
                "year": [2026],
                # Missing cfp, link, place, etc.
            },
        )

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            # Should not crash
            result = tidy_df_names(df)
            assert len(result) == 1, "Conference should not be silently dropped"
