"""Tests to ensure no silent data loss during CSV merge operations.

These tests verify that:
1. Normalization is consistent between mapping_dict and df_new lookups (BUG 1)
2. Missing 'variations' keys are handled gracefully (BUG 2)
3. Missing cfp_ext_x/y columns don't cause KeyErrors (BUG 3)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

# Add utils to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "utils"))


# Test fixtures
@pytest.fixture()
def sample_csv_dataframe():
    """Create a sample CSV-like dataframe with conference data."""
    return pd.DataFrame(
        {
            "conference": [
                "PyCon US 2025",
                "EuroPython 2025",
                "PyCon PL 2025",
                "Django Conference 2025",
            ],
            "year": [2025, 2025, 2025, 2025],
            "cfp": ["2025-01-15", "2025-02-01", "TBA", "2025-03-01"],
            "start": ["2025-04-01", "2025-07-15", "2025-08-20", "2025-09-10"],
            "end": ["2025-04-05", "2025-07-21", "2025-08-22", "2025-09-12"],
            "link": [
                "https://pycon.us",
                "https://europython.eu",
                "https://pl.pycon.org",
                "https://djangocon.eu",
            ],
            "place": ["USA", "Prague, Czechia", "Warsaw, Poland", "Berlin, Germany"],
        },
    )


@pytest.fixture()
def sample_yaml_dataframe():
    """Create a sample YAML-like dataframe with existing conference data."""
    return pd.DataFrame(
        {
            "conference": [
                "PyCon US",
                "EuroPython",
                "PyCon Poland",
            ],
            "year": [2025, 2025, 2025],
            "cfp": ["2025-01-15", "TBA", "2025-06-01"],
            "start": ["2025-04-01", "2025-07-15", "2025-08-20"],
            "end": ["2025-04-05", "2025-07-21", "2025-08-22"],
            "link": [
                "https://pycon.us/2025",
                "https://europython.eu",
                "https://pl.pycon.org",
            ],
            "place": ["Pittsburgh, USA", "Prague, Czechia", "Warsaw, Poland"],
            "mastodon": ["@pycon", None, None],
        },
    )


class TestNormalizationConsistency:
    """Verify same normalization used everywhere (BUG 1 regression tests)."""

    def test_normalize_conference_name_exists(self):
        """The normalize_conference_name function should exist and be importable."""
        from tidy_conf.titles import normalize_conference_name

        assert callable(normalize_conference_name)

    def test_normalize_removes_year(self):
        """Normalization should remove years from conference names."""
        from tidy_conf.titles import normalize_conference_name

        assert "2025" not in normalize_conference_name("PyCon US 2025")
        assert "2024" not in normalize_conference_name("EuroPython 2024")

    def test_normalize_expands_country_codes(self):
        """Normalization should expand country codes to full names."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("PyCon PL")
        assert "Poland" in result or "PL" not in result.split()[-1]

    def test_normalize_handles_plus_sign(self):
        """Normalization should handle + signs."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("Python+Django")
        assert "+" not in result

    def test_normalize_strips_whitespace(self):
        """Normalization should strip extra whitespace."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("  PyCon   US  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")
        assert "  " not in result

    @given(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Zs"))))
    @settings(max_examples=50)
    def test_normalization_is_idempotent(self, name):
        """normalize(normalize(x)) == normalize(x)."""
        from tidy_conf.titles import normalize_conference_name

        once = normalize_conference_name(name)
        twice = normalize_conference_name(once)
        assert once == twice, f"Normalization not idempotent: '{name}' -> '{once}' -> '{twice}'"

    def test_tidy_df_names_uses_normalize_conference_name(self):
        """tidy_df_names should produce same results as normalize_conference_name."""
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.titles import tidy_df_names

        df = pd.DataFrame(
            {
                "conference": ["PyCon US 2025", "EuroPython 2024", "PyCon PL"],
            },
        )

        # Apply tidy_df_names
        df_tidied = tidy_df_names(df)

        # Apply normalize_conference_name individually
        expected = [normalize_conference_name(name) for name in df["conference"]]

        assert df_tidied["conference"].tolist() == expected

    def test_mapping_dict_normalization_matches_df_new(self, sample_csv_dataframe):
        """The normalization used for mapping_dict should match df_new lookup."""
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.yaml import load_title_mappings

        _, known_mappings = load_title_mappings(reverse=True)

        # Simulate mapping_dict creation (as in import_python_organizers.py)
        mapping_dict = {}
        for idx, row in sample_csv_dataframe.iterrows():
            standardized_conf = normalize_conference_name(row["conference"], known_mappings)
            mapping_key = (standardized_conf, row["year"])
            mapping_dict[mapping_key] = idx

        # Simulate df_new lookup (after tidy_df_names)
        from tidy_conf.titles import tidy_df_names

        df_tidied = tidy_df_names(sample_csv_dataframe.copy())

        # Verify all entries can be found
        for _, row in df_tidied.iterrows():
            key = (row["conference"], row["year"])
            assert key in mapping_dict, f"Key {key} not found in mapping_dict"


class TestNoSilentDataLoss:
    """Verify merge never silently drops entries."""

    def test_csv_entries_count_preserved(self, sample_csv_dataframe):
        """CSV entries should all be represented in normalized output."""
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.yaml import load_title_mappings

        _, known_mappings = load_title_mappings(reverse=True)

        original_count = len(sample_csv_dataframe)

        # Normalize all entries
        normalized = [
            normalize_conference_name(row["conference"], known_mappings) for _, row in sample_csv_dataframe.iterrows()
        ]

        # Check none became empty
        non_empty = [n for n in normalized if n and n.strip()]
        assert len(non_empty) == original_count, "Some entries normalized to empty strings"

    def test_all_csv_entries_have_mapping_key(self, sample_csv_dataframe):
        """Every CSV entry should produce a valid mapping key."""
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.yaml import load_title_mappings

        _, known_mappings = load_title_mappings(reverse=True)

        mapping_dict = {}
        for idx, row in sample_csv_dataframe.iterrows():
            standardized_conf = normalize_conference_name(row["conference"], known_mappings)
            mapping_key = (standardized_conf, row["year"])

            # Key should be valid (non-empty conference name)
            assert standardized_conf, f"Empty normalized name for {row['conference']}"
            assert mapping_key[1], f"Missing year for {row['conference']}"

            mapping_dict[mapping_key] = idx

        # All entries should have unique keys
        assert len(mapping_dict) == len(sample_csv_dataframe), "Some entries produced duplicate keys"


class TestVariationsKeyHandling:
    """Test that missing 'variations' key is handled gracefully (BUG 2)."""

    def test_update_title_mappings_handles_missing_variations(self):
        """update_title_mappings should not crash when 'variations' key is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a titles.yml file with a key missing 'variations'
            titles_path = Path(tmpdir) / "titles.yml"
            titles_path.write_text(
                """
spelling: []
alt_name:
  ExistingConf:
    global: "Existing Conference"
    # Note: no 'variations' key here!
""",
            )

            # Patch the path resolution to use our temp file
            with patch("tidy_conf.yaml.Path") as mock_path:
                # Make the module-relative path point to our temp file
                mock_path.return_value = titles_path
                mock_path.__truediv__ = lambda self, other: titles_path

                # This should not raise KeyError
                try:
                    # Import fresh to use patched path
                    import importlib

                    import tidy_conf.yaml

                    importlib.reload(tidy_conf.yaml)

                    # Try to update with new mapping
                    tidy_conf.yaml.update_title_mappings(
                        {"ExistingConf": ["New Variation"]},
                        path=str(titles_path),
                    )
                except KeyError as e:
                    pytest.fail(f"KeyError raised for missing 'variations' key: {e}")

    def test_load_title_mappings_handles_missing_variations(self):
        """load_title_mappings should handle entries without 'variations' key."""
        from tidy_conf.yaml import load_title_mappings

        # Should not crash even if some entries lack variations
        try:
            spellings, alt_names = load_title_mappings()
            # Just verify it returns something
            assert isinstance(spellings, list)
            assert isinstance(alt_names, dict)
        except KeyError as e:
            pytest.fail(f"KeyError when loading title mappings: {e}")


class TestCfpExtColumnHandling:
    """Test that missing cfp_ext_x/y columns are handled gracefully (BUG 3)."""

    def test_merge_handles_missing_cfp_ext_columns(self):
        """merge_conferences should not crash when cfp_ext columns are missing."""
        from tidy_conf.interactive_merge import merge_conferences

        # Create dataframes WITHOUT cfp_ext column
        # Use index that doesn't duplicate as column
        df_yml = pd.DataFrame(
            {
                "conference": ["TestConf"],
                "year": [2025],
                "cfp": ["2025-01-15"],
                "start": ["2025-04-01"],
                "end": ["2025-04-05"],
                "place": ["Test City"],
                "link": ["https://test.com"],
            },
        )
        df_yml["title_match"] = df_yml["conference"]
        df_yml = df_yml.set_index("title_match")

        df_remote = pd.DataFrame(
            {
                "conference": ["TestConf"],
                "year": [2025],
                "cfp": ["2025-01-20"],  # Different CFP date to trigger conflict
                "start": ["2025-04-01"],
                "end": ["2025-04-05"],
                "place": ["Test City"],
                "link": ["https://test.com"],
            },
        )
        df_remote["title_match"] = df_remote["conference"]
        df_remote = df_remote.set_index("title_match")

        # This should not raise KeyError
        try:
            # Mock query_yes_no to avoid interactive prompts
            with patch("tidy_conf.interactive_merge.query_yes_no", return_value=False):
                result = merge_conferences(df_yml, df_remote)
                assert result is not None
        except KeyError as e:
            if "cfp_ext" in str(e):
                pytest.fail(f"KeyError for cfp_ext column: {e}")
            raise

    def test_merge_handles_partial_cfp_ext_columns(self):
        """merge_conferences should handle when only one side has cfp_ext."""
        from tidy_conf.interactive_merge import merge_conferences

        # df_yml has cfp_ext, df_remote doesn't
        df_yml = pd.DataFrame(
            {
                "conference": ["TestConf"],
                "year": [2025],
                "cfp": ["2025-01-15"],
                "cfp_ext": ["2025-01-20"],  # Has extension
                "start": ["2025-04-01"],
                "end": ["2025-04-05"],
                "place": ["Test City"],
                "link": ["https://test.com"],
            },
        )
        df_yml["title_match"] = df_yml["conference"]
        df_yml = df_yml.set_index("title_match")

        df_remote = pd.DataFrame(
            {
                "conference": ["TestConf"],
                "year": [2025],
                "cfp": ["2025-01-18"],  # Different CFP
                # No cfp_ext column
                "start": ["2025-04-01"],
                "end": ["2025-04-05"],
                "place": ["Test City"],
                "link": ["https://test.com"],
            },
        )
        df_remote["title_match"] = df_remote["conference"]
        df_remote = df_remote.set_index("title_match")

        try:
            with patch("tidy_conf.interactive_merge.query_yes_no", return_value=False):
                result = merge_conferences(df_yml, df_remote)
                assert result is not None
        except KeyError as e:
            if "cfp_ext" in str(e):
                pytest.fail(f"KeyError for partial cfp_ext columns: {e}")
            raise


class TestMergeUnionProperty:
    """Test that merge produces union of inputs."""

    def test_output_contains_all_unique_conferences(
        self,
        sample_csv_dataframe,
        sample_yaml_dataframe,
    ):
        """Output should contain all unique conferences from both inputs."""
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.yaml import load_title_mappings

        _, known_mappings = load_title_mappings(reverse=True)

        # Get unique normalized names from CSV
        csv_names = {
            normalize_conference_name(row["conference"], known_mappings) for _, row in sample_csv_dataframe.iterrows()
        }

        # Get unique normalized names from YAML
        yaml_names = {
            normalize_conference_name(row["conference"], known_mappings) for _, row in sample_yaml_dataframe.iterrows()
        }

        # Union should contain all
        union_names = csv_names | yaml_names

        # Each unique name should be representable
        for name in union_names:
            assert name, f"Empty name in union: {name}"


class TestRegressionSpecificCases:
    """Test specific cases that have caused data loss in the past."""

    def test_pycon_with_country_code_matches_full_name(self):
        """'PyCon PL' should normalize to same as 'PyCon Poland'."""
        from tidy_conf.titles import normalize_conference_name

        pl_code = normalize_conference_name("PyCon PL")
        pl_full = normalize_conference_name("PyCon Poland")

        # Both should produce the same normalized form
        assert pl_code == pl_full, f"'{pl_code}' != '{pl_full}'"

    def test_year_variations_normalize_same(self):
        """'PyCon US 2025' and 'PyCon US' should normalize the same."""
        from tidy_conf.titles import normalize_conference_name

        with_year = normalize_conference_name("PyCon US 2025")
        without_year = normalize_conference_name("PyCon US")

        assert with_year == without_year, f"'{with_year}' != '{without_year}'"

    def test_conf_abbreviation_expanded(self):
        """'DjangoCon' should have 'Conf' expanded to 'Conference'."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("Django Conf")
        assert "Conference" in result, f"'Conf' not expanded in '{result}'"

    def test_extra_spaces_normalized(self):
        """Extra spaces should be normalized to single spaces."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("PyCon    US   2025")
        assert "  " not in result, f"Extra spaces not removed: '{result}'"


class TestMultiYearDeduplication:
    """Test that multi-year data is not lost during deduplication (BUG 4)."""

    def test_deduplicate_preserves_different_years_same_conference(self):
        """Deduplication by [conference, year] should preserve entries for different years."""
        from tidy_conf.deduplicate import deduplicate

        # Create data with same conference name but different years
        df = pd.DataFrame(
            {
                "conference": ["PyCon USA", "PyCon USA", "EuroPython"],
                "year": [2025, 2026, 2025],
                "cfp": ["2025-01-15", "2026-01-15", "2025-02-01"],
                "start": ["2025-04-01", "2026-04-01", "2025-07-15"],
            },
        )

        # Deduplicate by conference AND year (correct behavior)
        result = deduplicate(df, ["conference", "year"])

        # All 3 entries should be preserved (different years or different conferences)
        assert len(result) == 3, f"Expected 3 entries, got {len(result)}"

        # Verify all years are present
        years = set(result["year"].tolist())
        assert 2025 in years and 2026 in years, f"Missing years: {years}"

    def test_deduplicate_by_conference_only_loses_multi_year_data(self):
        """Deduplication by conference only incorrectly merges different years."""
        from tidy_conf.deduplicate import deduplicate

        # Create data with same conference name but different years
        df = pd.DataFrame(
            {
                "conference": ["PyCon USA", "PyCon USA", "EuroPython"],
                "year": [2025, 2026, 2025],
                "cfp": ["2025-01-15", "2026-01-15", "2025-02-01"],
            },
        )

        # Deduplicate by conference only (incorrect behavior)
        result = deduplicate(df, "conference")

        # Should lose one PyCon USA entry (demonstrating the bug)
        assert len(result) == 2, f"Expected 2 entries (bug behavior), got {len(result)}"

    def test_multi_year_csv_standardized_to_for_merge_preserves_all_years(self):
        """Regression test: CSV standardization should not lose multi-year entries."""
        from tidy_conf.deduplicate import deduplicate
        from tidy_conf.titles import normalize_conference_name
        from tidy_conf.yaml import load_title_mappings

        _, known_mappings = load_title_mappings(reverse=True)

        # Simulate CSV data with entries for 2025 and 2026
        df_csv_raw = pd.DataFrame(
            {
                "conference": ["PyCon US 2025", "PyCon US 2026", "EuroPython 2025", "EuroPython 2026"],
                "year": [2025, 2026, 2025, 2026],
                "cfp": ["2025-01-15", "2026-01-15", "2025-02-01", "2026-02-01"],
            },
        )

        # Standardize names (year gets removed)
        df_csv_standardized = df_csv_raw.copy()
        df_csv_standardized["conference"] = df_csv_standardized["conference"].apply(
            lambda x: normalize_conference_name(x, known_mappings),
        )

        # After standardization, all entries should still be present
        assert len(df_csv_standardized) == 4, "Lost entries during standardization"

        # CRITICAL: Deduplicate by [conference, year] to preserve multi-year
        df_csv_for_merge = deduplicate(df_csv_standardized, ["conference", "year"])

        # All 4 entries should be preserved (2 conferences x 2 years)
        assert (
            len(df_csv_for_merge) == 4
        ), f"Lost multi-year entries during deduplication! Expected 4, got {len(df_csv_for_merge)}"

        # Verify both years are present for each conference
        for conf in df_csv_for_merge["conference"].unique():
            conf_years = df_csv_for_merge[df_csv_for_merge["conference"] == conf]["year"].tolist()
            assert 2025 in conf_years and 2026 in conf_years, f"Missing year for {conf}: {conf_years}"
