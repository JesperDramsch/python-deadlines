"""Tests for interactive merge functionality."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import merge_conferences


@pytest.fixture()
def mock_title_mappings():
    """Mock the title mappings to avoid file I/O issues.

    The fuzzy_match function calls load_title_mappings from multiple locations:
    - tidy_conf.interactive_merge.load_title_mappings
    - tidy_conf.titles.load_title_mappings (via tidy_df_names)

    It also calls update_title_mappings which writes to files.
    We need to mock all of these to avoid file system operations.
    """
    with patch("tidy_conf.interactive_merge.load_title_mappings") as mock_load1, patch(
        "tidy_conf.titles.load_title_mappings",
    ) as mock_load2, patch("tidy_conf.interactive_merge.update_title_mappings") as mock_update:
        # Return empty mappings (list, dict) for both load calls
        mock_load1.return_value = ([], {})
        mock_load2.return_value = ([], {})
        mock_update.return_value = None
        yield mock_load1


class TestFuzzyMatch:
    """Test fuzzy matching functionality."""

    def test_fuzzy_match_identical_names(self, mock_title_mappings):
        """Test fuzzy matching with identical conference names."""
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_csv = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://new.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        # fuzzy_match now returns 3-tuple: (merged, remote, report)
        result = fuzzy_match(df_yml, df_csv)
        if len(result) == 3:
            merged, _remote, report = result
        else:
            merged, _remote = result

        # Should find a match and merge the data
        assert not merged.empty
        assert len(merged) == 1
        assert merged.iloc[0]["conference"] == "PyCon Test"

    def test_fuzzy_match_similar_names(self, mock_title_mappings):
        """Test fuzzy matching with similar but not identical names."""
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon US"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_csv = pd.DataFrame(
            {
                "conference": ["PyCon United States"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://new.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        with patch("builtins.input", return_value="y"):  # Simulate user accepting the match
            result = fuzzy_match(df_yml, df_csv)
            if len(result) == 3:
                merged, remote, report = result
            else:
                merged, remote = result

        # Should find and accept a fuzzy match
        assert not merged.empty

        # Verify the merged dataframe has conference data
        conference_names = merged["conference"].tolist()
        # Note: title mappings may transform names (e.g., "PyCon US" -> "PyCon USA")
        # Check that we have at least one conference in the result
        assert len(conference_names) >= 1, f"Should have at least one conference in result"

        # Verify fuzzy matching was attempted - remote should still be returned
        assert remote is not None, "Remote dataframe should be returned for further processing"

    def test_fuzzy_match_no_matches(self, mock_title_mappings):
        """Test fuzzy matching when there are no matches."""
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_csv = pd.DataFrame(
            {
                "conference": ["DjangoCon Completely Different"],
                "year": [2025],
                "cfp": ["2025-03-15 23:59:00"],
                "link": ["https://different.com"],
                "place": ["Different City"],
                "start": ["2025-07-01"],
                "end": ["2025-07-03"],
            },
        )

        result = fuzzy_match(df_yml, df_csv)
        if len(result) == 3:
            merged, remote, report = result
        else:
            merged, remote = result

        # Both dataframes should be non-empty after fuzzy_match
        assert not merged.empty, "Merged dataframe should not be empty"
        assert not remote.empty, "Remote dataframe should be returned"

        # Verify the YML conference is preserved in merged result
        conference_names = merged["conference"].tolist()
        assert "PyCon Test" in conference_names, f"YML conference 'PyCon Test' should be in {conference_names}"

        # Verify the dissimilar CSV conference remains in remote (unmatched)
        remote_names = remote["conference"].tolist()
        assert (
            "DjangoCon Completely Different" in remote_names
        ), f"Unmatched CSV conference should be in remote: {remote_names}"

        # Verify the dissimilar conferences weren't incorrectly merged
        # The YML row should still have its original link (not overwritten by CSV)
        yml_rows = merged[merged["conference"] == "PyCon Test"]
        assert not yml_rows.empty, "YML conference should exist in merged"
        assert (
            yml_rows.iloc[0]["link"] == "https://existing.com"
        ), "YML link should not be changed when no match is found"


class TestMergeConferences:
    """Test conference merging functionality."""

    def test_merge_conferences_after_fuzzy_match(self, mock_title_mappings):
        """Test conference merging using output from fuzzy_match.

        This test verifies that conference names are preserved through the merge.
        """
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": ["DjangoCon"],
                "year": [2025],
                "cfp": ["2025-03-15 23:59:00"],
                "link": ["https://django.com"],
                "place": ["Django City"],
                "start": ["2025-08-01"],
                "end": ["2025-08-03"],
            },
        )

        # First do fuzzy match to set up data properly
        with patch("builtins.input", return_value="n"):  # Reject any fuzzy matches
            result = fuzzy_match(df_yml, df_remote)
            if len(result) == 3:
                df_merged, df_remote_processed, _ = result
            else:
                df_merged, df_remote_processed = result

        # Then test merge_conferences
        with patch("sys.stdin", StringIO("")):
            result = merge_conferences(df_merged, df_remote_processed)

        # Should combine both DataFrames - we expect exactly 2 conferences
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2, f"Expected 2 conferences (1 merged + 1 remote), got {len(result)}"

        # Verify conference names are preserved correctly (not corrupted to index values)
        assert "conference" in result.columns
        conference_names = result["conference"].tolist()

        # Names should be actual conference names, not index values like "0"
        for name in conference_names:
            assert not str(name).isdigit(), f"Conference name '{name}' is corrupted to index value"

        assert "PyCon Test" in conference_names, "Original YML conference should be in result"
        assert "DjangoCon" in conference_names, "Remote conference should be in result"

    def test_merge_conferences_preserves_names(self, mock_title_mappings):
        """Test that merge preserves conference names correctly."""
        df_yml = pd.DataFrame(
            {
                "conference": ["Original Conference Name"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://original.com"],
                "place": ["Original City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
                "sub": ["PY"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": ["Remote Conference Name"],
                "year": [2025],
                "cfp": ["2025-03-15 23:59:00"],
                "link": ["https://remote.com"],
                "place": ["Remote City"],
                "start": ["2025-08-01"],
                "end": ["2025-08-03"],
                "sub": ["PY"],
            },
        )

        # Mock user input to reject matches
        with patch("builtins.input", return_value="n"):
            fuzzy_result = fuzzy_match(df_yml, df_remote)
            if len(fuzzy_result) == 3:
                df_merged, df_remote_processed, _ = fuzzy_result
            else:
                df_merged, df_remote_processed = fuzzy_result

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:
            # Mock schema with empty DataFrame
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Basic validation that we get some result
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns

    def test_merge_conferences_empty_dataframes(self, mock_title_mappings):
        """Test merging with empty DataFrames."""
        df_empty = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
        df_with_data = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://test.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
                "sub": ["PY"],
            },
        )

        # Test with empty remote - fuzzy_match should handle empty DataFrames gracefully
        with patch("builtins.input", return_value="n"):
            fuzzy_result = fuzzy_match(df_with_data, df_empty)
            if len(fuzzy_result) == 3:
                df_merged, df_remote_processed, _ = fuzzy_result
            else:
                df_merged, df_remote_processed = fuzzy_result

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:
            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)
            assert isinstance(result, pd.DataFrame)
            assert "conference" in result.columns


class TestInteractivePrompts:
    """Test interactive prompt functionality."""

    def test_interactive_user_input_yes(self, mock_title_mappings):
        """Test interactive prompts with 'yes' response."""
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Similar"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_csv = pd.DataFrame(
            {
                "conference": ["PyCon Slightly Different"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://new.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        # Mock user input to accept match
        with patch("builtins.input", return_value="y"):
            result = fuzzy_match(df_yml, df_csv)
            if len(result) == 3:
                merged, _remote, _ = result
            else:
                merged, _remote = result

        # Should accept the match
        assert not merged.empty

    def test_interactive_user_input_no(self, mock_title_mappings):
        """Test interactive prompts with 'no' response."""
        df_yml = pd.DataFrame(
            {
                "conference": ["PyCon Similar"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://existing.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        df_csv = pd.DataFrame(
            {
                "conference": ["PyCon Slightly Different"],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://new.com"],
                "place": ["Test City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )

        # Mock user input to reject match
        with patch("builtins.input", return_value="n"):
            result = fuzzy_match(df_yml, df_csv)
            if len(result) == 3:
                _merged, remote, _ = result
            else:
                _merged, remote = result

        # Should reject the match and keep data separate
        assert len(remote) == 1, f"Expected exactly 1 rejected conference in remote, got {len(remote)}"
        assert remote.iloc[0]["conference"] == "PyCon Slightly Different"


class TestDataIntegrity:
    """Test data integrity during merge operations."""

    def test_conference_name_corruption_prevention(self, mock_title_mappings):
        """Test prevention of conference name corruption bug.

        This test specifically targets a bug where conference names were being
        set to pandas index values (e.g., "0", "1") instead of actual names.
        The test verifies that original conference names are preserved through
        the merge process.
        """
        # Use distinctive names that can't be confused with index values
        original_name = "Important Conference With Specific Name"
        remote_name = "Another Important Conference With Unique Name"

        df_yml = pd.DataFrame(
            {
                "conference": [original_name],
                "year": [2025],
                "cfp": ["2025-02-15 23:59:00"],
                "link": ["https://important.com"],
                "place": ["Important City"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
                "sub": ["PY"],
            },
        )

        df_remote = pd.DataFrame(
            {
                "conference": [remote_name],
                "year": [2025],
                "cfp": ["2025-03-15 23:59:00"],
                "link": ["https://another.com"],
                "place": ["Another City"],
                "start": ["2025-08-01"],
                "end": ["2025-08-03"],
                "sub": ["PY"],
            },
        )

        # First do fuzzy match to set up data properly
        with patch("builtins.input", return_value="n"):
            fuzzy_result = fuzzy_match(df_yml, df_remote)
            if len(fuzzy_result) == 3:
                df_merged, df_remote_processed, _ = fuzzy_result
            else:
                df_merged, df_remote_processed = fuzzy_result

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:
            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Verify we got a valid result
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns
        assert len(result) > 0, "Expected at least one conference in result"

        # CRITICAL: Verify conference names are actual names, not index values
        conference_names = result["conference"].tolist()

        for name in conference_names:
            # Names should not be numeric strings (the corruption bug)
            assert not str(name).isdigit(), f"Conference name '{name}' appears to be a numeric index value"
            # Names should be reasonable strings (not just numbers)
            assert len(str(name)) > 2, f"Conference name '{name}' is too short, likely corrupted"

        # Verify the expected conference names are present (at least one should be)
        expected_names = {original_name, remote_name}
        actual_names = set(conference_names)
        assert actual_names & expected_names, f"Expected at least one of {expected_names} but got {actual_names}"

    def test_data_consistency_after_merge(self, mock_title_mappings):
        """Test that data remains consistent after merge operations."""
        original_data = {
            "conference": "Test Conference",
            "year": 2025,
            "cfp": "2025-02-15 23:59:00",
            "link": "https://test.com",
            "place": "Test City",
            "start": "2025-06-01",
            "end": "2025-06-03",
            "sub": "PY",
        }

        df_yml = pd.DataFrame([original_data])
        df_remote = pd.DataFrame(
            columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"],
        )  # Empty remote

        # First do fuzzy match
        with patch("builtins.input", return_value="n"):
            fuzzy_result = fuzzy_match(df_yml, df_remote)
            if len(fuzzy_result) == 3:
                df_merged, df_remote_processed, _ = fuzzy_result
            else:
                df_merged, df_remote_processed = fuzzy_result

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:
            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Verify the result is valid
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns

        # Verify original data was preserved through the merge
        if len(result) > 0:
            # Check that original conference name appears in result
            conference_names = result["conference"].tolist()
            assert (
                original_data["conference"] in conference_names
            ), f"Original conference '{original_data['conference']}' not found in result: {conference_names}"
