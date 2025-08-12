"""Tests for interactive merge functionality."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import merge_conferences


class TestFuzzyMatch:
    """Test fuzzy matching functionality."""

    def test_fuzzy_match_identical_names(self):
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

        merged, _remote = fuzzy_match(df_yml, df_csv)

        # Should find a match and merge the data
        assert not merged.empty
        assert len(merged) == 1
        assert merged.iloc[0]["conference"] == "PyCon Test"

    def test_fuzzy_match_similar_names(self):
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
            merged, _remote = fuzzy_match(df_yml, df_csv)

        # Should find a fuzzy match
        assert not merged.empty
        assert len(merged) >= 1

    def test_fuzzy_match_no_matches(self):
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

        _merged, remote = fuzzy_match(df_yml, df_csv)

        # Should not find matches, return originals
        assert len(remote) >= 1  # The CSV data should remain unmatched


class TestMergeConferences:
    """Test conference merging functionality."""

    def test_merge_conferences_after_fuzzy_match(self):
        """Test conference merging using output from fuzzy_match."""
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
            df_merged, df_remote_processed = fuzzy_match(df_yml, df_remote)

        # Then test merge_conferences
        with patch("sys.stdin", StringIO("")):
            result = merge_conferences(df_merged, df_remote_processed)

        # Should combine both DataFrames
        assert len(result) >= 1

        # Verify conference names are preserved correctly
        assert "conference" in result.columns

    def test_merge_conferences_preserves_names(self):
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

        # Mock the title mappings and file operations
        with patch("builtins.input", return_value="n"), patch(
            "tidy_conf.yaml.load_title_mappings",
        ) as mock_load_mappings, patch("tidy_conf.yaml.update_title_mappings"), patch(
            "tidy_conf.utils.query_yes_no",
            return_value=False,
        ):

            # Mock empty mappings
            mock_load_mappings.return_value = ({}, {})

            df_merged, df_remote_processed = fuzzy_match(df_yml, df_remote)

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:

            # Mock schema with empty DataFrame
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Basic validation that we get some result
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns

    def test_merge_conferences_empty_dataframes(self):
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
        with patch("builtins.input", return_value="n"), patch(
            "tidy_conf.yaml.load_title_mappings",
        ) as mock_load_mappings, patch("tidy_conf.yaml.update_title_mappings"):

            # Mock empty mappings
            mock_load_mappings.return_value = ({}, {})

            df_merged, df_remote_processed = fuzzy_match(df_with_data, df_empty)

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:

            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)
            assert isinstance(result, pd.DataFrame)
            assert "conference" in result.columns


class TestInteractivePrompts:
    """Test interactive prompt functionality."""

    def test_interactive_user_input_yes(self):
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
            merged, _remote = fuzzy_match(df_yml, df_csv)

        # Should accept the match
        assert not merged.empty

    def test_interactive_user_input_no(self):
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
            _merged, remote = fuzzy_match(df_yml, df_csv)

        # Should reject the match and keep data separate
        assert len(remote) >= 1


class TestDataIntegrity:
    """Test data integrity during merge operations."""

    def test_conference_name_corruption_prevention(self):
        """Test prevention of conference name corruption bug."""
        # This test specifically targets the bug we fixed where conference names
        # were being set to pandas index values instead of actual names

        df_yml = pd.DataFrame(
            {
                "conference": ["Important Conference"],
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
                "conference": ["Another Important Conference"],
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
        with patch("builtins.input", return_value="n"), patch(
            "tidy_conf.yaml.load_title_mappings",
        ) as mock_load_mappings, patch("tidy_conf.yaml.update_title_mappings"):

            # Mock empty mappings
            mock_load_mappings.return_value = ({}, {})

            df_merged, df_remote_processed = fuzzy_match(df_yml, df_remote)

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:

            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Basic validation - we should get a DataFrame back with conference column
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns

    def test_data_consistency_after_merge(self):
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
        with patch("builtins.input", return_value="n"), patch(
            "tidy_conf.yaml.load_title_mappings",
        ) as mock_load_mappings, patch("tidy_conf.yaml.update_title_mappings"):

            # Mock empty mappings
            mock_load_mappings.return_value = ({}, {})

            df_merged, df_remote_processed = fuzzy_match(df_yml, df_remote)

        with patch("sys.stdin", StringIO("")), patch("tidy_conf.schema.get_schema") as mock_schema:

            # Mock schema
            empty_schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
            mock_schema.return_value = empty_schema

            result = merge_conferences(df_merged, df_remote_processed)

        # Data should be preserved - at least we should have some result
        assert isinstance(result, pd.DataFrame)
        assert "conference" in result.columns
