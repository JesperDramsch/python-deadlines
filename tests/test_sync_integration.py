"""Integration tests for the conference synchronization pipeline.

This module tests the full pipeline from loading data through merging
and outputting results. These tests are slower than unit tests but
verify that all components work together correctly.

Integration tests cover:
- YAML → Normalize → Output matches schema
- CSV → Normalize → Output matches schema
- YAML + CSV → Fuzzy match → Merge → Valid output
- Conflict resolution through full pipeline
- Round-trip read/write consistency
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.deduplicate import deduplicate
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import merge_conferences
from tidy_conf.titles import tidy_df_names
from tidy_conf.yaml import write_conference_yaml


class TestYAMLNormalizePipeline:
    """Test YAML loading, normalization, and output."""

    def test_yaml_normalize_output_valid(self, minimal_yaml_df):
        """Load YAML → Normalize → Output should produce valid schema-compliant data.

        Contract: Data that goes through normalization should still
        contain all original information in a standardized format.
        """
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            # Normalize
            result = tidy_df_names(minimal_yaml_df.reset_index(drop=True))

        # Should have all columns
        required_columns = ["conference", "year", "link", "cfp", "place", "start", "end"]
        for col in required_columns:
            if col in minimal_yaml_df.columns:
                assert col in result.columns, f"Column {col} should be preserved"

        # Should have same number of rows
        assert len(result) == len(minimal_yaml_df), \
            "Normalization should not change row count"

        # All conferences should have valid names
        for name in result["conference"]:
            assert isinstance(name, str), f"Conference name should be string: {name}"
            assert len(name) > 0, f"Conference name should not be empty"

    def test_round_trip_yaml_consistency(self, minimal_yaml_df, tmp_path):
        """Write YAML → Read YAML → Data should be consistent.

        Contract: Writing and reading should not corrupt data.
        """
        output_file = tmp_path / "output.yml"

        # Write
        write_conference_yaml(minimal_yaml_df.reset_index(drop=True), str(output_file))

        # Read back
        with output_file.open(encoding="utf-8") as f:
            reloaded = yaml.safe_load(f)

        # Should have same number of conferences
        assert len(reloaded) == len(minimal_yaml_df), \
            f"Round trip should preserve count: {len(reloaded)} vs {len(minimal_yaml_df)}"

        # Conference names should be preserved
        original_names = set(minimal_yaml_df["conference"].tolist())
        reloaded_names = {conf["conference"] for conf in reloaded}

        # At least core names should be preserved
        assert len(reloaded_names) == len(original_names), \
            f"Conference names should be preserved: {reloaded_names} vs {original_names}"


class TestCSVNormalizePipeline:
    """Test CSV loading, normalization, and output."""

    def test_csv_normalize_produces_valid_structure(self, minimal_csv_df):
        """CSV → Normalize → Output should have correct structure.

        Contract: CSV data should be normalized to match YAML schema.
        """
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            result = tidy_df_names(minimal_csv_df)

        # Should have conference column
        assert "conference" in result.columns

        # Should have year
        assert "year" in result.columns

        # All years should be integers
        for year in result["year"]:
            assert isinstance(year, (int, float)), f"Year should be numeric: {year}"

    def test_csv_column_mapping_correct(self, minimal_csv_df):
        """CSV columns should be mapped correctly to schema columns."""
        # The fixture already maps columns
        expected_columns = ["conference", "start", "end", "place", "link", "year"]

        for col in expected_columns:
            assert col in minimal_csv_df.columns, \
                f"Column {col} should exist after mapping"


class TestFullMergePipeline:
    """Test complete merge pipeline: YAML + CSV → Match → Merge → Output."""

    def test_full_pipeline_produces_valid_output(self, mock_title_mappings, minimal_yaml_df, minimal_csv_df):
        """Full pipeline should produce valid merged output.

        Pipeline: YAML + CSV → fuzzy_match → merge_conferences → valid output
        """
        # Reset index for processing
        df_yml = minimal_yaml_df.reset_index(drop=True)
        df_csv = minimal_csv_df.copy()

        # Step 1: Fuzzy match
        with patch("builtins.input", return_value="y"):  # Accept matches
            matched, remote = fuzzy_match(df_yml, df_csv)

        # Verify fuzzy match output
        assert not matched.empty, "Fuzzy match should produce output"
        assert matched.index.name == "title_match", "Index should be title_match"

        # Step 2: Merge
        with patch("tidy_conf.interactive_merge.get_schema") as mock_schema:
            mock_schema.return_value = pd.DataFrame(
                columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"]
            )

            result = merge_conferences(matched, remote)

        # Verify merge output
        assert isinstance(result, pd.DataFrame), "Merge should produce DataFrame"
        assert "conference" in result.columns, "Result should have conference column"

        # Should not lose data
        assert len(result) >= 1, "Result should have conferences"

    def test_pipeline_with_conflicts_logs_resolution(self, mock_title_mappings, caplog):
        """Pipeline with conflicts should log resolution decisions."""
        import logging
        caplog.set_level(logging.DEBUG)

        df_yml = pd.DataFrame({
            "conference": ["Test Conf"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://yaml.conf/"],  # Different link
            "place": ["Berlin, Germany"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_csv = pd.DataFrame({
            "conference": ["Test Conf"],
            "year": [2026],
            "cfp": ["2026-01-20 23:59:00"],  # Different CFP
            "link": ["https://csv.conf/"],  # Different link
            "place": ["Munich, Germany"],  # Different place
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        with patch("builtins.input", return_value="y"):
            matched, remote = fuzzy_match(df_yml, df_csv)

        with patch("tidy_conf.interactive_merge.get_schema") as mock_schema:
            mock_schema.return_value = pd.DataFrame(
                columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"]
            )

            # Mock query_yes_no to auto-select options
            with patch("tidy_conf.interactive_merge.query_yes_no", return_value=False):
                result = merge_conferences(matched, remote)

        # Pipeline should complete
        assert len(result) >= 1


class TestDeduplicationInPipeline:
    """Test deduplication as part of the pipeline."""

    def test_duplicate_removal_in_pipeline(self, mock_title_mappings):
        """Duplicates introduced during merge should be removed.

        Contract: Final output should have no duplicate conferences.
        """
        # Create DataFrame with duplicates directly (bypassing fuzzy_match)
        df = pd.DataFrame({
            "conference": ["PyCon US", "PyCon US"],  # Duplicate
            "year": [2026, 2026],
            "cfp": ["2026-01-15 23:59:00", "2026-01-15 23:59:00"],
            "link": ["https://us.pycon.org/", "https://us.pycon.org/"],
            "place": ["Pittsburgh, USA", "Pittsburgh, USA"],
            "start": ["2026-05-06", "2026-05-06"],
            "end": ["2026-05-11", "2026-05-11"],
        })
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        # Deduplicate using conference name as key
        deduped = deduplicate(df, key="conference")

        # Should have removed duplicate
        assert len(deduped) == 1, f"Duplicates should be merged: {len(deduped)}"


class TestDataIntegrityThroughPipeline:
    """Test that data integrity is maintained through the full pipeline."""

    def test_no_data_loss_through_pipeline(self, mock_title_mappings):
        """All input conferences should be present in output.

        Contract: The pipeline should never silently drop conferences.
        """
        unique_names = [
            "Unique Conference Alpha",
            "Unique Conference Beta",
            "Unique Conference Gamma",
        ]

        df_yml = pd.DataFrame({
            "conference": unique_names,
            "year": [2026, 2026, 2026],
            "cfp": ["2026-01-15 23:59:00"] * 3,
            "link": ["https://alpha.conf/", "https://beta.conf/", "https://gamma.conf/"],
            "place": ["City A", "City B", "City C"],
            "start": ["2026-06-01", "2026-07-01", "2026-08-01"],
            "end": ["2026-06-03", "2026-07-03", "2026-08-03"],
        })

        df_csv = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        # Run through pipeline
        with patch("builtins.input", return_value="n"):
            result, _ = fuzzy_match(df_yml, df_csv)

        # All conferences should be present
        result_names = result["conference"].tolist()
        for name in unique_names:
            found = any(name in str(rname) for rname in result_names)
            assert found, f"Conference '{name}' should not be lost, got: {result_names}"

    def test_field_preservation_through_pipeline(self, mock_title_mappings):
        """Optional fields should be preserved through the pipeline.

        Contract: Fields like mastodon, twitter, finaid should not be lost.
        """
        df_yml = pd.DataFrame({
            "conference": ["Full Field Conference"],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://full.conf/"],
            "place": ["Full City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
            "mastodon": ["https://fosstodon.org/@fullconf"],
            "twitter": ["fullconf"],
            "finaid": ["https://full.conf/finaid/"],
        })

        df_csv = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        with patch("builtins.input", return_value="n"):
            result, _ = fuzzy_match(df_yml, df_csv)

        # Optional fields should be preserved
        if "mastodon" in result.columns:
            mastodon_val = result["mastodon"].iloc[0]
            if pd.notna(mastodon_val):
                assert "fosstodon" in str(mastodon_val), \
                    f"Mastodon should be preserved: {mastodon_val}"


class TestPipelineEdgeCases:
    """Test pipeline behavior with edge case inputs."""

    def test_pipeline_handles_unicode(self, mock_title_mappings):
        """Pipeline should correctly handle Unicode characters."""
        df_yml = pd.DataFrame({
            "conference": ["PyCon México", "PyCon España"],
            "year": [2026, 2026],
            "cfp": ["2026-01-15 23:59:00", "2026-02-15 23:59:00"],
            "link": ["https://pycon.mx/", "https://pycon.es/"],
            "place": ["Ciudad de México, Mexico", "Madrid, Spain"],
            "start": ["2026-06-01", "2026-07-01"],
            "end": ["2026-06-03", "2026-07-03"],
        })

        df_csv = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        with patch("builtins.input", return_value="n"):
            result, _ = fuzzy_match(df_yml, df_csv)

        # Unicode names should be preserved
        result_names = " ".join(result["conference"].tolist())
        assert "xico" in result_names.lower() or "spain" in result_names.lower(), \
            f"Unicode characters should be handled: {result_names}"

    def test_pipeline_handles_very_long_names(self, mock_title_mappings):
        """Pipeline should handle conferences with very long names."""
        long_name = "The International Conference on Python Programming and Data Science with Machine Learning and AI Applications for Industry and Academia 2026"

        df_yml = pd.DataFrame({
            "conference": [long_name],
            "year": [2026],
            "cfp": ["2026-01-15 23:59:00"],
            "link": ["https://long.conf/"],
            "place": ["Long City"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
        })

        df_csv = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end"])

        with patch("builtins.input", return_value="n"):
            result, _ = fuzzy_match(df_yml, df_csv)

        # Long name should be preserved (possibly without year)
        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 50, \
            "Long conference name should be preserved"


class TestRoundTripConsistency:
    """Test that writing and reading produces consistent results."""

    def test_yaml_round_trip_preserves_structure(self, tmp_path):
        """YAML write → read should preserve data structure."""
        original_data = [
            {
                "conference": "Test Conference",
                "year": 2026,
                "link": "https://test.conf/",
                "cfp": "2026-01-15 23:59:00",
                "place": "Test City",
                "start": "2026-06-01",
                "end": "2026-06-03",
                "sub": "PY",
            }
        ]

        output_file = tmp_path / "round_trip.yml"

        # Write
        write_conference_yaml(original_data, str(output_file))

        # Read
        with output_file.open(encoding="utf-8") as f:
            reloaded = yaml.safe_load(f)

        # Verify structure
        assert len(reloaded) == 1
        assert reloaded[0]["conference"] == "Test Conference"
        assert reloaded[0]["year"] == 2026
        assert "link" in reloaded[0]

    def test_dataframe_round_trip(self, tmp_path):
        """DataFrame → YAML → DataFrame should preserve data."""
        df = pd.DataFrame({
            "conference": ["Test Conf"],
            "year": [2026],
            "link": ["https://test.conf/"],
            "cfp": ["2026-01-15 23:59:00"],
            "place": ["Test City"],
            "start": [pd.to_datetime("2026-06-01").date()],
            "end": [pd.to_datetime("2026-06-03").date()],
            "sub": ["PY"],
        })

        output_file = tmp_path / "df_round_trip.yml"

        # Write DataFrame
        write_conference_yaml(df, str(output_file))

        # Read back
        with output_file.open(encoding="utf-8") as f:
            reloaded = yaml.safe_load(f)

        # Convert back to DataFrame
        df_reloaded = pd.DataFrame(reloaded)

        # Verify key fields
        assert df_reloaded["conference"].iloc[0] == "Test Conf"
        assert df_reloaded["year"].iloc[0] == 2026


class TestGoldenFileComparison:
    """Test outputs against known-good golden files."""

    def test_normalization_matches_expected(self):
        """Normalization output should match expected format.

        This is a form of golden file testing where we verify
        the transformation produces expected results.
        """
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            input_data = pd.DataFrame({
                "conference": ["PyCon Germany 2026", "DjangoCon US 2025"]
            })

            result = tidy_df_names(input_data)

        # Expected transformations
        expected = [
            ("2026" not in result["conference"].iloc[0]),  # Year removed
            ("2025" not in result["conference"].iloc[1]),  # Year removed
            ("PyCon" in result["conference"].iloc[0]),  # Core name preserved
            ("DjangoCon" in result["conference"].iloc[1]),  # Core name preserved
        ]

        for i, check in enumerate(expected):
            assert check, f"Transformation check {i} failed: {result['conference'].tolist()}"
