"""Tests for the validation module in tidy_conf.

This module tests:
1. DataFrame validation
2. MergeReport tracking
3. MergeRecord creation
4. Data consistency checks
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.validation import ALL_KNOWN_COLUMNS
from tidy_conf.validation import OPTIONAL_COLUMNS
from tidy_conf.validation import REQUIRED_COLUMNS
from tidy_conf.validation import MergeRecord
from tidy_conf.validation import MergeReport
from tidy_conf.validation import ValidationError
from tidy_conf.validation import ensure_conference_strings
from tidy_conf.validation import log_dataframe_state
from tidy_conf.validation import validate_dataframe
from tidy_conf.validation import validate_merge_inputs


class TestValidationConstants:
    """Test validation constants are properly defined."""

    def test_required_columns_defined(self):
        """Test that required columns are defined."""
        assert len(REQUIRED_COLUMNS) > 0
        assert "conference" in REQUIRED_COLUMNS
        assert "year" in REQUIRED_COLUMNS
        assert "start" in REQUIRED_COLUMNS
        assert "end" in REQUIRED_COLUMNS

    def test_optional_columns_defined(self):
        """Test that optional columns are defined."""
        assert len(OPTIONAL_COLUMNS) > 0
        assert "link" in OPTIONAL_COLUMNS
        assert "cfp" in OPTIONAL_COLUMNS
        assert "place" in OPTIONAL_COLUMNS

    def test_all_known_columns_complete(self):
        """Test that ALL_KNOWN_COLUMNS includes both required and optional."""
        for col in REQUIRED_COLUMNS:
            assert col in ALL_KNOWN_COLUMNS
        for col in OPTIONAL_COLUMNS:
            assert col in ALL_KNOWN_COLUMNS


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_is_exception(self):
        """Test that ValidationError is an exception."""
        assert issubclass(ValidationError, Exception)

    def test_validation_error_can_be_raised(self):
        """Test that ValidationError can be raised with message."""
        with pytest.raises(ValidationError, match="Test error"):
            raise ValidationError("Test error")


class TestMergeRecord:
    """Test MergeRecord dataclass."""

    def test_merge_record_creation(self):
        """Test creating a basic MergeRecord."""
        record = MergeRecord(
            yaml_name="PyCon Test",
            remote_name="PyCon Test Conference",
            match_score=95,
            match_type="fuzzy",
            action="merged",
            year=2025,
        )
        assert record.yaml_name == "PyCon Test"
        assert record.remote_name == "PyCon Test Conference"
        assert record.match_score == 95
        assert record.match_type == "fuzzy"
        assert record.action == "merged"
        assert record.year == 2025

    def test_merge_record_default_values(self):
        """Test MergeRecord default values for optional fields."""
        record = MergeRecord(
            yaml_name="Test",
            remote_name="Test",
            match_score=100,
            match_type="exact",
            action="merged",
            year=2025,
        )
        assert record.before_values == {}
        assert record.after_values == {}
        assert record.conflict_resolutions == []

    def test_merge_record_with_conflict_data(self):
        """Test MergeRecord with conflict resolution data."""
        record = MergeRecord(
            yaml_name="PyCon US",
            remote_name="PyCon United States",
            match_score=88,
            match_type="fuzzy",
            action="merged",
            year=2025,
            before_values={"link": "https://old.com"},
            after_values={"link": "https://new.com"},
            conflict_resolutions=["link: used remote value"],
        )
        assert record.before_values == {"link": "https://old.com"}
        assert record.after_values == {"link": "https://new.com"}
        assert len(record.conflict_resolutions) == 1


class TestMergeReport:
    """Test MergeReport dataclass."""

    def test_merge_report_creation(self):
        """Test creating a basic MergeReport."""
        report = MergeReport()
        assert report.source_yaml_count == 0
        assert report.source_remote_count == 0
        assert report.exact_matches == 0
        assert report.fuzzy_matches == 0
        assert report.no_matches == 0

    def test_add_record_exact_match(self):
        """Test adding an exact match record."""
        report = MergeReport()
        record = MergeRecord(
            yaml_name="Test",
            remote_name="Test",
            match_score=100,
            match_type="exact",
            action="merged",
            year=2025,
        )
        report.add_record(record)
        assert report.exact_matches == 1
        assert len(report.records) == 1

    def test_add_record_fuzzy_match(self):
        """Test adding a fuzzy match record."""
        report = MergeReport()
        record = MergeRecord(
            yaml_name="PyCon US",
            remote_name="PyCon United States",
            match_score=90,
            match_type="fuzzy",
            action="merged",
            year=2025,
        )
        report.add_record(record)
        assert report.fuzzy_matches == 1

    def test_add_record_no_match(self):
        """Test adding a no-match record."""
        report = MergeReport()
        record = MergeRecord(
            yaml_name="PyCon Test",
            remote_name="DjangoCon",
            match_score=30,
            match_type="no_match",
            action="kept_yaml",
            year=2025,
        )
        report.add_record(record)
        assert report.no_matches == 1

    def test_add_record_excluded(self):
        """Test adding an excluded match record."""
        report = MergeReport()
        record = MergeRecord(
            yaml_name="PyCon Austria",
            remote_name="PyCon Australia",
            match_score=92,
            match_type="excluded",
            action="kept_yaml",
            year=2025,
        )
        report.add_record(record)
        assert report.excluded_matches == 1

    def test_add_record_dropped(self):
        """Test adding a dropped record tracks data loss."""
        report = MergeReport()
        record = MergeRecord(
            yaml_name="Lost Conference",
            remote_name="Lost Conference",
            match_score=100,
            match_type="exact",
            action="dropped",
            year=2025,
        )
        report.add_record(record)
        assert len(report.dropped_conferences) == 1
        assert report.dropped_conferences[0]["yaml_name"] == "Lost Conference"

    def test_add_warning(self):
        """Test adding warnings to report."""
        report = MergeReport()
        report.add_warning("Test warning message")
        assert len(report.warnings) == 1
        assert report.warnings[0] == "Test warning message"

    def test_add_error(self):
        """Test adding errors to report."""
        report = MergeReport()
        report.add_error("Test error message")
        assert len(report.errors) == 1
        assert report.errors[0] == "Test error message"

    def test_summary_generation(self):
        """Test that summary generates readable output."""
        report = MergeReport()
        report.source_yaml_count = 10
        report.source_remote_count = 15
        report.exact_matches = 8
        report.fuzzy_matches = 2
        report.total_output = 15

        summary = report.summary()
        assert "MERGE REPORT SUMMARY" in summary
        assert "10" in summary  # yaml count
        assert "15" in summary  # remote count
        assert "8" in summary  # exact matches

    def test_validate_no_data_loss_success(self):
        """Test data loss validation passes when no data lost."""
        report = MergeReport()
        report.source_yaml_count = 10
        report.source_remote_count = 12
        report.total_output = 15
        assert report.validate_no_data_loss() is True

    def test_validate_no_data_loss_failure(self):
        """Test data loss validation fails when data is lost."""
        report = MergeReport()
        report.source_yaml_count = 10
        report.source_remote_count = 12
        report.total_output = 5  # Less than expected
        assert report.validate_no_data_loss() is False
        assert len(report.errors) > 0


class TestValidateDataframe:
    """Test validate_dataframe function."""

    def test_validate_valid_dataframe(self):
        """Test validation of a valid DataFrame."""
        df = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_empty_dataframe(self):
        """Test validation of an empty DataFrame."""
        df = pd.DataFrame()
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is False
        assert any("empty" in e.lower() for e in errors)

    def test_validate_none_dataframe(self):
        """Test validation of None DataFrame."""
        is_valid, errors = validate_dataframe(None, "Test")
        assert is_valid is False
        assert any("None" in e for e in errors)

    def test_validate_missing_columns(self):
        """Test validation detects missing required columns."""
        df = pd.DataFrame(
            {
                "conference": ["Test"],
                # Missing: year, start, end
            },
        )
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is False
        assert any("Missing required columns" in e for e in errors)

    def test_validate_non_string_conference(self):
        """Test validation detects non-string conference names."""
        df = pd.DataFrame(
            {
                "conference": [123, 456],  # Numbers, not strings
                "year": [2025, 2025],
                "start": ["2025-06-01", "2025-07-01"],
                "end": ["2025-06-03", "2025-07-03"],
            },
        )
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is False
        assert any("not strings" in e for e in errors)

    def test_validate_empty_conference_names(self):
        """Test validation detects empty conference names."""
        df = pd.DataFrame(
            {
                "conference": ["", "   "],  # Empty strings
                "year": [2025, 2025],
                "start": ["2025-06-01", "2025-07-01"],
                "end": ["2025-06-03", "2025-07-03"],
            },
        )
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is False
        assert any("empty" in e.lower() for e in errors)

    def test_validate_invalid_year(self):
        """Test validation detects invalid year values."""
        df = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": ["not a year"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        is_valid, errors = validate_dataframe(df, "Test")
        assert is_valid is False
        assert any("invalid year" in e.lower() for e in errors)

    def test_validate_custom_required_columns(self):
        """Test validation with custom required columns."""
        df = pd.DataFrame(
            {
                "name": ["Test"],
                "date": ["2025-06-01"],
            },
        )
        is_valid, _errors = validate_dataframe(df, "Test", required_columns=["name", "date"])
        assert is_valid is True


class TestValidateMergeInputs:
    """Test validate_merge_inputs function."""

    def test_validate_both_valid(self):
        """Test validation when both DataFrames are valid."""
        df_yaml = pd.DataFrame(
            {
                "conference": ["PyCon Test"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        df_remote = pd.DataFrame(
            {
                "conference": ["DjangoCon Test"],
                "year": [2025],
                "start": ["2025-07-01"],
                "end": ["2025-07-03"],
            },
        )
        is_valid, report = validate_merge_inputs(df_yaml, df_remote)
        assert is_valid is True
        assert report.source_yaml_count == 1
        assert report.source_remote_count == 1

    def test_validate_yaml_invalid(self):
        """Test validation when YAML DataFrame is invalid."""
        df_yaml = pd.DataFrame()  # Empty
        df_remote = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        is_valid, report = validate_merge_inputs(df_yaml, df_remote)
        assert is_valid is False
        assert len(report.errors) > 0

    def test_validate_remote_invalid(self):
        """Test validation when remote DataFrame is invalid."""
        df_yaml = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        df_remote = pd.DataFrame()  # Empty
        is_valid, report = validate_merge_inputs(df_yaml, df_remote)
        assert is_valid is False
        assert len(report.errors) > 0

    def test_validate_with_existing_report(self):
        """Test validation updates existing report."""
        existing_report = MergeReport()
        existing_report.add_warning("Previous warning")

        df_yaml = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
            },
        )
        df_remote = pd.DataFrame(
            {
                "conference": ["Test2"],
                "year": [2025],
                "start": ["2025-07-01"],
                "end": ["2025-07-03"],
            },
        )

        is_valid, report = validate_merge_inputs(df_yaml, df_remote, existing_report)
        assert is_valid is True
        assert len(report.warnings) == 1  # Previous warning preserved


class TestEnsureConferenceStrings:
    """Test ensure_conference_strings function."""

    def test_already_strings(self):
        """Test function handles already-string conference names."""
        df = pd.DataFrame(
            {
                "conference": ["PyCon Test", "DjangoCon"],
                "year": [2025, 2025],
            },
        )
        result = ensure_conference_strings(df, "Test")
        assert result["conference"].tolist() == ["PyCon Test", "DjangoCon"]

    def test_converts_numbers(self):
        """Test function converts numeric conference names to strings."""
        df = pd.DataFrame(
            {
                "conference": [123, 456],
                "year": [2025, 2025],
            },
        )
        result = ensure_conference_strings(df, "Test")
        assert result["conference"].tolist() == ["123", "456"]

    def test_handles_none_values(self):
        """Test function handles None/NaN conference names."""
        df = pd.DataFrame(
            {
                "conference": [None, "Valid"],
                "year": [2025, 2025],
            },
        )
        result = ensure_conference_strings(df, "Test")
        # None should be replaced with placeholder
        assert "Unknown_Conference" in result.iloc[0]["conference"]
        assert result.iloc[1]["conference"] == "Valid"

    def test_handles_missing_column(self):
        """Test function handles DataFrame without conference column."""
        df = pd.DataFrame(
            {
                "year": [2025],
                "place": ["Test City"],
            },
        )
        result = ensure_conference_strings(df, "Test")
        # Should return unchanged
        assert "conference" not in result.columns

    def test_does_not_modify_original(self):
        """Test function returns copy, not modifying original."""
        df = pd.DataFrame(
            {
                "conference": [123],
                "year": [2025],
            },
        )
        original_value = df.iloc[0]["conference"]
        result = ensure_conference_strings(df, "Test")
        # Original should be unchanged
        assert df.iloc[0]["conference"] == original_value
        # Result should be string
        assert result.iloc[0]["conference"] == "123"


class TestLogDataframeState:
    """Test log_dataframe_state function."""

    def test_logs_without_error(self):
        """Test that log_dataframe_state doesn't raise errors."""
        df = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": [2025],
            },
        )
        # Should not raise any exceptions
        log_dataframe_state(df, "Test DataFrame")

    def test_logs_empty_dataframe(self):
        """Test logging an empty DataFrame."""
        df = pd.DataFrame()
        # Should not raise any exceptions
        log_dataframe_state(df, "Empty DataFrame")

    def test_logs_without_sample(self):
        """Test logging without sample data."""
        df = pd.DataFrame(
            {
                "conference": ["Test"],
                "year": [2025],
            },
        )
        log_dataframe_state(df, "Test", show_sample=False)
