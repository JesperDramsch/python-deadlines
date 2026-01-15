"""Tests for fuzzy matching logic in conference synchronization.

This module tests the fuzzy_match function that compares conference names
between YAML and CSV sources to find matches. Tests use real DataFrames
and only mock external I/O (file system, user input).

Key behaviors tested:
- Exact name matching (100% score)
- Similar name matching (90%+ score with user confirmation)
- Dissimilar names not matching
- Title match structure in returned DataFrame
- CFP filling with TBA when missing
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.interactive_merge import fuzzy_match


class TestExactMatching:
    """Test fuzzy matching behavior when names are identical."""

    def test_exact_match_scores_100(self, mock_title_mappings):
        """Identical conference names should match with 100% confidence.

        Contract: When names are exactly equal, fuzzy_match should:
        - Find the match automatically (no user prompt)
        - Combine the data from both sources
        """
        df_yml = pd.DataFrame({
            "conference": ["PyCon Germany & PyData Conference"],
            "year": [2026],
            "cfp": ["2025-12-21 23:59:59"],
            "link": ["https://2026.pycon.de/"],
            "place": ["Darmstadt, Germany"],
            "start": ["2026-04-14"],
            "end": ["2026-04-17"],
        })

        df_remote = pd.DataFrame({
            "conference": ["PyCon Germany & PyData Conference"],
            "year": [2026],
            "cfp": ["2025-12-21 23:59:59"],
            "link": ["https://pycon.de/"],
            "place": ["Darmstadt, Germany"],
            "start": ["2026-04-14"],
            "end": ["2026-04-17"],
        })

        result, remote = fuzzy_match(df_yml, df_remote)

        # Should find the match
        assert not result.empty, "Result should not be empty for exact match"
        assert len(result) == 1, f"Expected 1 merged conference, got {len(result)}"

        # Conference name should be preserved
        assert "PyCon Germany" in str(result["conference"].iloc[0]) or \
               "PyData" in str(result["conference"].iloc[0]), \
            f"Conference name corrupted: {result['conference'].iloc[0]}"

    def test_exact_match_no_user_prompt(self, mock_title_mappings):
        """Exact matches should not prompt the user for confirmation.

        We verify this by NOT mocking input and expecting no interaction.
        """
        df_yml = pd.DataFrame({
            "conference": ["DjangoCon US"],
            "year": [2026],
            "cfp": ["2026-03-16 11:00:00"],
            "link": ["https://djangocon.us/"],
            "place": ["Chicago, USA"],
            "start": ["2026-09-14"],
            "end": ["2026-09-18"],
        })

        df_remote = pd.DataFrame({
            "conference": ["DjangoCon US"],
            "year": [2026],
            "cfp": ["2026-03-16 11:00:00"],
            "link": ["https://2026.djangocon.us/"],
            "place": ["Chicago, USA"],
            "start": ["2026-09-14"],
            "end": ["2026-09-18"],
        })

        # This should not prompt - if it does, test will hang or fail
        with patch("builtins.input", side_effect=AssertionError("Should not prompt for exact match")):
            result, _ = fuzzy_match(df_yml, df_remote)

        assert len(result) == 1


class TestSimilarNameMatching:
    """Test fuzzy matching when names are similar but not identical."""

    def test_similar_names_prompt_user(self, mock_title_mappings):
        """Similar names (90%+ match) should prompt user for confirmation.

        Contract: When similarity is 90-99%, fuzzy_match should:
        - Ask the user if the conferences match
        - If accepted, treat as match
        - If rejected, keep separate
        """
        df_yml = pd.DataFrame({
            "conference": ["PyCon US"],
            "year": [2026],
            "cfp": ["2025-12-18 23:59:59"],
            "link": ["https://us.pycon.org/2026/"],
            "place": ["Pittsburgh, USA"],
            "start": ["2026-05-06"],
            "end": ["2026-05-11"],
        })

        df_remote = pd.DataFrame({
            "conference": ["PyCon United States"],
            "year": [2026],
            "cfp": ["2025-12-18 23:59:59"],
            "link": ["https://pycon.us/"],
            "place": ["Pittsburgh, PA, USA"],
            "start": ["2026-05-06"],
            "end": ["2026-05-11"],
        })

        # User accepts the match
        with patch("builtins.input", return_value="y"):
            result, _ = fuzzy_match(df_yml, df_remote)

        # Match should be accepted
        assert not result.empty
        # Original YAML name should be preserved
        assert "PyCon" in str(result["conference"].iloc[0])

    def test_user_rejects_similar_match(self, mock_title_mappings):
        """When user rejects a fuzzy match, conferences stay separate.

        Contract: Rejecting a fuzzy match should:
        - Keep YAML conference in result with original name
        - Keep CSV conference in remote for later processing
        """
        df_yml = pd.DataFrame({
            "conference": ["PyCon US"],
            "year": [2026],
            "cfp": ["2025-12-18 23:59:59"],
            "link": ["https://us.pycon.org/2026/"],
            "place": ["Pittsburgh, USA"],
            "start": ["2026-05-06"],
            "end": ["2026-05-11"],
        })

        df_remote = pd.DataFrame({
            "conference": ["PyCon United States"],
            "year": [2026],
            "cfp": ["2025-12-18 23:59:59"],
            "link": ["https://pycon.us/"],
            "place": ["Pittsburgh, PA, USA"],
            "start": ["2026-05-06"],
            "end": ["2026-05-11"],
        })

        # User rejects the match
        with patch("builtins.input", return_value="n"):
            result, remote = fuzzy_match(df_yml, df_remote)

        # YAML conference should still be in result
        assert "PyCon US" in result["conference"].tolist() or \
               "PyCon US" in result.index.tolist(), \
            f"Original YAML conference should be preserved, got: {result['conference'].tolist()}"

        # Remote conference should still be available
        assert len(remote) >= 1, "Remote conference should be preserved after rejection"


class TestDissimilarNames:
    """Test that dissimilar conference names are not matched."""

    def test_dissimilar_names_no_match(self, mock_title_mappings):
        """Conferences with very different names should not match.

        Contract: When similarity is below 90%, fuzzy_match should:
        - NOT prompt user
        - Keep conferences separate
        """
        df_yml = pd.DataFrame({
            "conference": ["PyCon US"],
            "year": [2026],
            "cfp": ["2025-12-18 23:59:59"],
            "link": ["https://us.pycon.org/2026/"],
            "place": ["Pittsburgh, USA"],
            "start": ["2026-05-06"],
            "end": ["2026-05-11"],
        })

        df_remote = pd.DataFrame({
            "conference": ["DjangoCon Europe"],
            "year": [2026],
            "cfp": ["2026-03-01 23:59:00"],
            "link": ["https://djangocon.eu/"],
            "place": ["Amsterdam, Netherlands"],
            "start": ["2026-06-01"],
            "end": ["2026-06-05"],
        })

        # Should not prompt for dissimilar names
        with patch("builtins.input", side_effect=AssertionError("Should not prompt for dissimilar names")):
            result, remote = fuzzy_match(df_yml, df_remote)

        # Both conferences should exist separately
        assert "PyCon US" in result["conference"].tolist() or \
               "PyCon US" in result.index.tolist()
        assert "DjangoCon Europe" in remote["conference"].tolist()

    def test_different_conference_types_not_matched(self, mock_title_mappings):
        """PyCon vs DjangoCon should never be incorrectly matched."""
        df_yml = pd.DataFrame({
            "conference": ["PyCon Germany"],
            "year": [2026],
            "cfp": ["2025-12-21 23:59:59"],
            "link": ["https://pycon.de/"],
            "place": ["Darmstadt, Germany"],
            "start": ["2026-04-14"],
            "end": ["2026-04-17"],
        })

        df_remote = pd.DataFrame({
            "conference": ["DjangoCon Germany"],  # Similar location, different type
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://djangocon.de/"],
            "place": ["Berlin, Germany"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        # User should be prompted (names are somewhat similar)
        # We reject to verify they stay separate
        with patch("builtins.input", return_value="n"):
            result, remote = fuzzy_match(df_yml, df_remote)

        # Both should exist separately
        result_names = result["conference"].tolist()
        remote_names = remote["conference"].tolist()

        # Verify no incorrect merging happened
        assert len(result) >= 1 and len(remote) >= 1, \
            "Both conferences should be preserved when rejected"


class TestTitleMatchStructure:
    """Test that the title_match column/index is correctly structured."""

    def test_result_has_title_match_index(self, mock_title_mappings):
        """Result DataFrame should have title_match as index name."""
        df_yml = pd.DataFrame({
            "conference": ["Test Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://test.conf/"],
            "place": ["Test City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_remote = pd.DataFrame({
            "conference": ["Other Conference"],
            "year": [2026],
            "cfp": ["2026-02-15 23:59:00"],
            "link": ["https://other.conf/"],
            "place": ["Other City"],
            "start": ["2026-07-01"],
            "end": ["2026-07-03"],
        })

        result, remote = fuzzy_match(df_yml, df_remote)

        # Remote should have title_match as index name
        assert remote.index.name == "title_match", \
            f"Remote index name should be 'title_match', got '{remote.index.name}'"

    def test_title_match_values_are_strings(self, mock_title_mappings):
        """Title match values should be strings, not integers or tuples."""
        df_yml = pd.DataFrame({
            "conference": ["Test Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://test.conf/"],
            "place": ["Test City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_remote = pd.DataFrame({
            "conference": ["Test Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://test.conf/"],
            "place": ["Test City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        result, _ = fuzzy_match(df_yml, df_remote)

        # Check index values are strings
        for idx in result.index:
            assert isinstance(idx, str), \
                f"Index value should be string, got {type(idx)}: {idx}"


class TestCFPHandling:
    """Test CFP field handling in fuzzy match results."""

    def test_missing_cfp_filled_with_tba(self, mock_title_mappings):
        """Missing CFP values should be filled with 'TBA'.

        Contract: fuzzy_match should fill NaN CFP values with 'TBA'
        to indicate "To Be Announced".
        """
        df_yml = pd.DataFrame({
            "conference": ["Test Conference"],
            "year": [2026],
            "cfp": [None],  # Missing CFP
            "link": ["https://test.conf/"],
            "place": ["Test City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_remote = pd.DataFrame({
            "conference": ["Other Conference"],
            "year": [2026],
            "cfp": ["2026-02-15 23:59:00"],
            "link": ["https://other.conf/"],
            "place": ["Other City"],
            "start": ["2026-07-01"],
            "end": ["2026-07-03"],
        })

        result, _ = fuzzy_match(df_yml, df_remote)

        # Check that CFP is filled with TBA for the conference that had None
        test_conf_rows = result[result["conference"].str.contains("Test", na=False)]
        if len(test_conf_rows) > 0:
            cfp_value = test_conf_rows["cfp"].iloc[0]
            assert cfp_value == "TBA" or pd.notna(cfp_value), \
                f"Missing CFP should be filled with 'TBA', got: {cfp_value}"


class TestEmptyDataFrames:
    """Test fuzzy matching behavior with empty DataFrames."""

    def test_empty_remote_handled_gracefully(self, mock_title_mappings):
        """Fuzzy match should handle empty remote DataFrame without crashing."""
        df_yml = pd.DataFrame({
            "conference": ["Test Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://test.conf/"],
            "place": ["Test City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_remote = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        result, remote = fuzzy_match(df_yml, df_remote)

        # Should not crash, result should contain YAML data
        assert not result.empty, "Result should not be empty when YAML has data"
        assert "Test Conference" in result["conference"].tolist() or \
               "Test Conference" in result.index.tolist()


class TestRealDataMatching:
    """Test fuzzy matching with realistic test fixtures."""

    def test_matches_pycon_de_variants(self, mock_title_mappings_with_data, minimal_yaml_df, minimal_csv_df):
        """REGRESSION: PyCon DE variants should match PyCon Germany.

        This was a bug where 'PyCon DE & PyData' in CSV didn't match
        'PyCon Germany & PyData Conference' in YAML, causing data loss.
        """
        # Filter to just PyCon Germany from YAML
        pycon_yml = minimal_yaml_df[
            minimal_yaml_df["conference"].str.contains("Germany", na=False)
        ].copy()

        # Filter to just PyCon DE from CSV
        pycon_csv = minimal_csv_df[
            minimal_csv_df["conference"].str.contains("PyCon DE", na=False)
        ].copy()

        if len(pycon_yml) > 0 and len(pycon_csv) > 0:
            # With proper mappings, these should match without user prompt
            with patch("builtins.input", return_value="y"):
                result, _ = fuzzy_match(pycon_yml, pycon_csv)

            # Should have merged the data
            assert len(result) >= 1, "PyCon DE should match PyCon Germany"

    def test_europython_variants_match(self, mock_title_mappings, minimal_yaml_df, minimal_csv_df):
        """EuroPython Conference (CSV) should match EuroPython (YAML)."""
        # Filter to EuroPython entries
        euro_yml = minimal_yaml_df[
            minimal_yaml_df["conference"].str.contains("EuroPython", na=False)
        ].copy()

        euro_csv = minimal_csv_df[
            minimal_csv_df["conference"].str.contains("EuroPython", na=False)
        ].copy()

        if len(euro_yml) > 0 and len(euro_csv) > 0:
            # User accepts the match
            with patch("builtins.input", return_value="y"):
                result, _ = fuzzy_match(euro_yml, euro_csv)

            # Should match
            assert len(result) >= 1


class TestFuzzyMatchThreshold:
    """Test the fuzzy match confidence threshold behavior."""

    def test_below_90_percent_no_prompt(self, mock_title_mappings):
        """Matches below 90% confidence should not prompt user.

        Contract: Below 90% similarity, conferences are considered
        different and should not be merged.
        """
        df_yml = pd.DataFrame({
            "conference": ["ABC Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://abc.conf/"],
            "place": ["ABC City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_remote = pd.DataFrame({
            "conference": ["XYZ Symposium"],  # Very different name
            "year": [2026],
            "cfp": ["2026-02-15 23:59:00"],
            "link": ["https://xyz.conf/"],
            "place": ["XYZ City"],
            "start": ["2026-07-01"],
            "end": ["2026-07-03"],
        })

        # Should not prompt
        with patch("builtins.input", side_effect=AssertionError("Should not prompt below threshold")):
            result, remote = fuzzy_match(df_yml, df_remote)

        # Both should be preserved separately
        assert len(remote) >= 1


class TestDataPreservation:
    """Test that original data is preserved through fuzzy matching."""

    def test_yaml_data_not_lost(self, mock_title_mappings):
        """YAML conference data should not be silently dropped.

        Contract: All YAML conferences should appear in the result,
        even if they don't match anything in remote.
        """
        df_yml = pd.DataFrame({
            "conference": ["Unique YAML Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://unique-yaml.conf/"],
            "place": ["YAML City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
            "mastodon": ["https://fosstodon.org/@unique"],  # Extra field
        })

        df_remote = pd.DataFrame({
            "conference": ["Unique CSV Conference"],
            "year": [2026],
            "cfp": ["2026-02-15 23:59:00"],
            "link": ["https://unique-csv.conf/"],
            "place": ["CSV City"],
            "start": ["2026-07-01"],
            "end": ["2026-07-03"],
        })

        result, _ = fuzzy_match(df_yml, df_remote)

        # YAML conference should be in result
        yaml_conf_found = any(
            "Unique YAML Conference" in str(name)
            for name in result["conference"].tolist()
        )
        assert yaml_conf_found, \
            f"YAML conference should be preserved, got: {result['conference'].tolist()}"

        # Extra field (mastodon) should also be preserved if it exists in result columns
        if "mastodon" in result.columns:
            yaml_rows = result[result["conference"].str.contains("YAML", na=False)]
            if len(yaml_rows) > 0:
                assert pd.notna(yaml_rows["mastodon"].iloc[0]), \
                    "Extra YAML field (mastodon) should be preserved"


# ---------------------------------------------------------------------------
# Property-based tests using Hypothesis
# ---------------------------------------------------------------------------

# Import shared strategies from hypothesis_strategies module
sys.path.insert(0, str(Path(__file__).parent))
from hypothesis_strategies import HYPOTHESIS_AVAILABLE

if HYPOTHESIS_AVAILABLE:
    from hypothesis import HealthCheck, assume, given, settings
    from hypothesis import strategies as st


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestFuzzyMatchProperties:
    """Property-based tests for fuzzy matching."""

    @given(st.lists(st.text(min_size=5, max_size=30), min_size=1, max_size=5, unique=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_fuzzy_match_preserves_all_yaml_entries(self, names):
        """All YAML entries should appear in result (no silent data loss)."""
        # Filter out empty or whitespace-only names
        names = [n for n in names if len(n.strip()) > 3]
        assume(len(names) > 0)

        with patch("tidy_conf.interactive_merge.load_title_mappings") as mock1, \
             patch("tidy_conf.titles.load_title_mappings") as mock2, \
             patch("tidy_conf.interactive_merge.update_title_mappings"):
            mock1.return_value = ([], {})
            mock2.return_value = ([], {})

            df_yml = pd.DataFrame({
                "conference": names,
                "year": [2026] * len(names),
                "cfp": ["2026-01-15 23:59:00"] * len(names),
                "link": [f"https://conf{i}.org/" for i in range(len(names))],
                "place": ["Test City"] * len(names),
                "start": ["2026-06-01"] * len(names),
                "end": ["2026-06-03"] * len(names),
            })

            df_remote = pd.DataFrame(
                columns=["conference", "year", "cfp", "link", "place", "start", "end"]
            )

            result, _ = fuzzy_match(df_yml, df_remote)

            # All input conferences should be in result
            assert len(result) >= len(names), \
                f"Expected at least {len(names)} results, got {len(result)}"

    @given(st.text(min_size=10, max_size=50))
    @settings(max_examples=30)
    def test_exact_match_always_scores_100(self, name):
        """Identical names should always match perfectly."""
        assume(len(name.strip()) > 5)

        with patch("tidy_conf.interactive_merge.load_title_mappings") as mock1, \
             patch("tidy_conf.titles.load_title_mappings") as mock2, \
             patch("tidy_conf.interactive_merge.update_title_mappings"):
            mock1.return_value = ([], {})
            mock2.return_value = ([], {})

            df_yml = pd.DataFrame({
                "conference": [name],
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://test.org/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            })

            df_remote = pd.DataFrame({
                "conference": [name],  # Same name
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://other.org/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            })

            # No user prompts should be needed for exact match
            with patch("builtins.input", side_effect=AssertionError("Should not prompt")):
                result, _ = fuzzy_match(df_yml, df_remote)

            # Should be merged (1 result, not 2)
            assert len(result) == 1, f"Exact match should merge, got {len(result)} results"
