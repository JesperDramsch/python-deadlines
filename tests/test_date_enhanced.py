"""Enhanced tests for tidy_conf.date functionality to increase coverage."""

import sys
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.date import clean_dates
from tidy_conf.date import create_nice_date
from tidy_conf.date import suffix


class TestCleanDates:
    """Test clean_dates functionality with comprehensive coverage."""

    def test_clean_dates_string_start_end_dates(self):
        """Test cleaning of start and end dates when they are strings."""
        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}

        result = clean_dates(data)

        # Start and end should be converted to date objects
        assert isinstance(result["start"], date)
        assert isinstance(result["end"], date)
        assert result["start"] == date(2025, 6, 1)
        assert result["end"] == date(2025, 6, 3)

    def test_clean_dates_already_date_objects(self):
        """Test cleaning when start and end are already date objects."""
        data = {"start": date(2025, 6, 1), "end": date(2025, 6, 3), "cfp": "2025-02-15"}

        result = clean_dates(data)

        # Should remain as date objects
        assert isinstance(result["start"], date)
        assert isinstance(result["end"], date)
        assert result["start"] == date(2025, 6, 1)
        assert result["end"] == date(2025, 6, 3)

    def test_clean_dates_cfp_date_only(self):
        """Test CFP cleaning when only date is provided (no time)."""
        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}  # Date only

        result = clean_dates(data)

        # CFP should get time appended (23:59:00)
        assert result["cfp"] == "2025-02-15 23:59:00"

    def test_clean_dates_cfp_with_time(self):
        """Test CFP cleaning when time is already provided."""
        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15 12:30:00"}  # Already has time

        result = clean_dates(data)

        # CFP should remain unchanged
        assert result["cfp"] == "2025-02-15 12:30:00"

    def test_clean_dates_tba_words(self):
        """Test handling of TBA words in deadlines."""
        tba_words = ["tba", "tbd", "cancelled"]

        for tba_word in tba_words:
            data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": tba_word}

            result = clean_dates(data)

            # TBA words should remain unchanged
            assert result["cfp"] == tba_word

    def test_clean_dates_tba_case_insensitive(self):
        """Test that TBA word matching is case insensitive."""
        tba_variations = ["TBA", "Tba", "tBa", "TBD", "CANCELLED"]

        for tba_word in tba_variations:
            data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": tba_word}

            result = clean_dates(data)

            # Should remain unchanged regardless of case
            assert result["cfp"] == tba_word

    def test_clean_dates_datetime_object_cfp(self):
        """Test CFP cleaning when it's a datetime object."""
        cfp_datetime = datetime(2025, 2, 15, 12, 30, 0, tzinfo=timezone.utc)

        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": cfp_datetime}

        result = clean_dates(data)

        # Should convert datetime to string format
        assert result["cfp"] == "2025-02-15 12:30:00"

    def test_clean_dates_date_object_cfp(self):
        """Test CFP cleaning when it's a date object."""
        cfp_date = date(2025, 2, 15)

        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": cfp_date}

        result = clean_dates(data)

        # Date objects get converted to string, then time is added (23:59:00)
        assert result["cfp"] == "2025-02-15 23:59:00"

    def test_clean_dates_workshop_deadline(self):
        """Test workshop_deadline processing."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-01-15",  # Date only
        }

        result = clean_dates(data)

        # Workshop deadline should get time appended
        assert result["workshop_deadline"] == "2025-01-15 23:59:00"

    def test_clean_dates_tutorial_deadline(self):
        """Test tutorial_deadline processing."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "tutorial_deadline": "2025-01-20",  # Date only
        }

        result = clean_dates(data)

        # Tutorial deadline should get time appended
        assert result["tutorial_deadline"] == "2025-01-20 23:59:00"

    def test_clean_dates_deadline_same_as_cfp(self):
        """Test that deadlines identical to CFP are removed."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-02-15",  # Same as CFP
            "tutorial_deadline": "2025-01-20",  # Different from CFP
        }

        result = clean_dates(data)

        # Workshop deadline should be removed (same as CFP)
        assert "workshop_deadline" not in result

        # Tutorial deadline should remain (different from CFP)
        assert "tutorial_deadline" in result
        assert result["tutorial_deadline"] == "2025-01-20 23:59:00"

    def test_clean_dates_missing_deadline_keys(self):
        """Test handling when deadline keys are missing."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            # No workshop_deadline or tutorial_deadline
        }

        result = clean_dates(data)

        # Should not crash and should only have the provided keys
        assert "workshop_deadline" not in result
        assert "tutorial_deadline" not in result
        assert result["cfp"] == "2025-02-15 23:59:00"

    def test_clean_dates_invalid_date_format(self):
        """Test handling of invalid date formats."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "invalid-date-format",
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged due to ValueError handling
        assert result["workshop_deadline"] == "invalid-date-format"

    def test_clean_dates_midnight_time_conversion(self):
        """Test that midnight times get converted to 23:59."""
        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}  # Will become midnight when parsed

        result = clean_dates(data)

        # Should convert midnight (00:00) to 23:59
        assert result["cfp"] == "2025-02-15 23:59:00"

    def test_clean_dates_non_midnight_time_preservation(self):
        """Test that non-midnight times are preserved."""
        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15 14:30:00"}  # Non-midnight time

        result = clean_dates(data)

        # Should preserve the original time
        assert result["cfp"] == "2025-02-15 14:30:00"

    def test_clean_dates_all_deadline_types(self):
        """Test processing all deadline types together."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-01-15",
            "tutorial_deadline": "2025-01-20",
        }

        result = clean_dates(data)

        # All deadlines should be processed
        assert result["cfp"] == "2025-02-15 23:59:00"
        assert result["workshop_deadline"] == "2025-01-15 23:59:00"
        assert result["tutorial_deadline"] == "2025-01-20 23:59:00"

    def test_clean_dates_data_modification_in_place(self):
        """Test that the original data dict is modified in place."""
        original_data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}

        result = clean_dates(original_data)

        # Should return the same object (modified in place)
        assert result is original_data
        assert original_data["cfp"] == "2025-02-15 23:59:00"


class TestSuffix:
    """Test suffix function for ordinal numbers."""

    def test_suffix_basic_numbers(self):
        """Test suffix for basic ordinal numbers."""
        test_cases = [
            (1, "st"),
            (2, "nd"),
            (3, "rd"),
            (4, "th"),
            (5, "th"),
            (6, "th"),
            (7, "th"),
            (8, "th"),
            (9, "th"),
            (10, "th"),
        ]

        for number, expected_suffix in test_cases:
            assert suffix(number) == expected_suffix

    def test_suffix_teens_special_case(self):
        """Test suffix for teen numbers (11, 12, 13) which are special cases."""
        teen_numbers = [11, 12, 13]

        for number in teen_numbers:
            assert suffix(number) == "th"

    def test_suffix_twenties_and_beyond(self):
        """Test suffix for numbers in twenties and beyond."""
        test_cases = [
            (21, "st"),  # 21st
            (22, "nd"),  # 22nd
            (23, "rd"),  # 23rd
            (24, "th"),  # 24th
            (31, "st"),  # 31st
            (32, "nd"),  # 32nd
            (33, "rd"),  # 33rd
            (101, "st"),  # 101st
            (102, "nd"),  # 102nd
            (103, "rd"),  # 103rd
            (111, "th"),  # 111th (special case)
            (112, "th"),  # 112th (special case)
            (113, "th"),  # 113th (special case)
            (121, "st"),  # 121st
            (122, "nd"),  # 122nd
            (123, "rd"),  # 123rd
        ]

        for number, expected_suffix in test_cases:
            assert suffix(number) == expected_suffix

    def test_suffix_large_numbers(self):
        """Test suffix for large numbers."""
        test_cases = [
            (1001, "st"),
            (1002, "nd"),
            (1003, "rd"),
            (1011, "th"),  # Special case
            (1021, "st"),
            (1111, "th"),  # Special case
            (1121, "st"),
        ]

        for number, expected_suffix in test_cases:
            assert suffix(number) == expected_suffix


class TestCreateNiceDate:
    """Test create_nice_date functionality."""

    def test_create_nice_date_same_day(self):
        """Test nice date creation when start and end are the same day."""
        data = {"start": "2025-06-01", "end": "2025-06-01"}

        result = create_nice_date(data)

        # Should create a single date format
        assert result["date"] == "June 1st, 2025"

    def test_create_nice_date_same_month(self):
        """Test nice date creation when start and end are in the same month."""
        data = {"start": "2025-06-01", "end": "2025-06-15"}

        result = create_nice_date(data)

        # Should show month once with date range
        assert result["date"] == "June 1 - 15, 2025"

    def test_create_nice_date_same_year_different_months(self):
        """Test nice date creation for different months in same year."""
        data = {"start": "2025-06-01", "end": "2025-07-15"}

        result = create_nice_date(data)

        # Should show both months with year once
        assert result["date"] == "June 1 - July 15, 2025"

    def test_create_nice_date_different_years(self):
        """Test nice date creation spanning different years."""
        data = {"start": "2025-12-15", "end": "2026-01-05"}

        result = create_nice_date(data)

        # Should show full dates for both
        assert result["date"] == "December 15, 2025 - January 5, 2026"

    def test_create_nice_date_ordinal_suffixes(self):
        """Test that ordinal suffixes are correctly applied."""
        test_cases = [
            ("2025-06-01", "2025-06-01", "June 1st, 2025"),
            ("2025-06-02", "2025-06-02", "June 2nd, 2025"),
            ("2025-06-03", "2025-06-03", "June 3rd, 2025"),
            ("2025-06-04", "2025-06-04", "June 4th, 2025"),
            ("2025-06-11", "2025-06-11", "June 11th, 2025"),  # Teen special case
            ("2025-06-21", "2025-06-21", "June 21st, 2025"),
            ("2025-06-22", "2025-06-22", "June 22nd, 2025"),
            ("2025-06-23", "2025-06-23", "June 23rd, 2025"),
        ]

        for start_date, end_date, expected in test_cases:
            data = {"start": start_date, "end": end_date}

            result = create_nice_date(data)
            assert result["date"] == expected

    def test_create_nice_date_removes_leading_zeros(self):
        """Test that leading zeros are removed from dates."""
        data = {"start": "2025-06-01", "end": "2025-06-09"}  # Day 01 should become 1  # Day 09 should become 9

        result = create_nice_date(data)

        # Should not have leading zeros
        assert result["date"] == "June 1 - 9, 2025"
        assert " 01" not in result["date"]
        assert " 09" not in result["date"]

    def test_create_nice_date_already_date_objects(self):
        """Test nice date creation when dates are already date objects."""
        data = {"start": date(2025, 6, 1), "end": date(2025, 6, 15)}

        result = create_nice_date(data)

        # Should handle date objects correctly
        assert result["date"] == "June 1 - 15, 2025"

    def test_create_nice_date_mixed_date_types(self):
        """Test nice date creation with mixed date types."""
        data = {"start": "2025-06-01", "end": date(2025, 6, 15)}  # String  # Date object

        # Should handle mixed types gracefully now
        result = create_nice_date(data)

        # Should create proper date format
        assert "date" in result
        assert "June 1 - 15, 2025" in result["date"]

    def test_create_nice_date_edge_cases_months(self):
        """Test nice date creation for edge case months."""
        test_cases = [
            ("2025-01-01", "2025-01-31", "January"),  # January
            ("2025-02-01", "2025-02-28", "February"),  # February
            ("2025-12-01", "2025-12-31", "December"),  # December
        ]

        for start_date, end_date, expected_month in test_cases:
            data = {"start": start_date, "end": end_date}

            result = create_nice_date(data)
            assert expected_month in result["date"]

    def test_create_nice_date_data_modification(self):
        """Test that create_nice_date modifies the original data dict."""
        original_data = {"start": "2025-06-01", "end": "2025-06-15", "conference": "Test Conference"}

        result = create_nice_date(original_data)

        # Should return the same object (modified in place)
        assert result is original_data
        assert "date" in original_data
        assert original_data["date"] == "June 1 - 15, 2025"

    def test_create_nice_date_preserves_other_data(self):
        """Test that create_nice_date preserves other data in the dict."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-15",
            "conference": "Test Conference",
            "year": 2025,
            "cfp": "2025-02-15",
        }

        result = create_nice_date(data)

        # Should preserve all other data
        assert result["conference"] == "Test Conference"
        assert result["year"] == 2025
        assert result["cfp"] == "2025-02-15"
        assert result["date"] == "June 1 - 15, 2025"


class TestIntegrationAndEdgeCases:
    """Test integration scenarios and edge cases."""

    def test_full_date_processing_workflow(self):
        """Test complete date processing workflow."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-15",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-01-15",
            "tutorial_deadline": "2025-02-15",  # Same as CFP
        }

        # Clean dates first
        cleaned = clean_dates(data)

        # Then create nice date
        result = create_nice_date(cleaned)

        # Should have processed everything correctly
        assert isinstance(result["start"], date)
        assert isinstance(result["end"], date)
        assert result["cfp"] == "2025-02-15 23:59:00"
        assert result["workshop_deadline"] == "2025-01-15 23:59:00"
        assert "tutorial_deadline" not in result  # Removed because same as CFP
        assert result["date"] == "June 1 - 15, 2025"

    def test_error_handling_invalid_dates(self):
        """Test error handling with invalid date formats."""
        data = {"start": "invalid-start-date", "end": "invalid-end-date", "cfp": "2025-02-15"}

        # clean_dates should handle invalid formats gracefully
        with pytest.raises(ValueError, match=r"time data .* does not match format"):
            clean_dates(data)

    def test_timezone_awareness_preservation(self):
        """Test that timezone information is properly handled."""
        utc_datetime = datetime(2025, 2, 15, 12, 30, 0, tzinfo=timezone.utc)

        data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": utc_datetime}

        result = clean_dates(data)

        # Should preserve the time information
        assert result["cfp"] == "2025-02-15 12:30:00"

    def test_boundary_date_handling(self):
        """Test handling of boundary dates and times."""
        data = {
            "start": "2025-01-01",  # Start of year
            "end": "2025-12-31",  # End of year
            "cfp": "2025-02-28",  # End of February (non-leap year)
        }

        cleaned = clean_dates(data)
        nice_date = create_nice_date(cleaned)

        assert cleaned["cfp"] == "2025-02-28 23:59:00"
        assert nice_date["date"] == "January 1 - December 31, 2025"

    def test_data_immutability_concerns(self):
        """Test that functions properly handle data modification."""
        original_data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "immutable_field": "should_not_change",
        }

        # Make a copy to compare
        import copy

        data_copy = copy.deepcopy(original_data)

        # Process the data
        result = clean_dates(data_copy)

        # Original should be unchanged, copy should be modified
        assert original_data["cfp"] == "2025-02-15"
        assert result["cfp"] == "2025-02-15 23:59:00"
        assert result["immutable_field"] == "should_not_change"

    def test_memory_efficiency_large_datasets(self):
        """Test memory efficiency with repeated function calls."""
        # Simulate processing many conferences
        base_data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}

        results = []
        for i in range(100):
            data = base_data.copy()
            data["conference"] = f"Conference {i}"

            cleaned = clean_dates(data)
            nice_date = create_nice_date(cleaned)
            results.append(nice_date)

        # Should handle many operations without issues
        assert len(results) == 100
        assert all("date" in result for result in results)
        assert all(result["cfp"] == "2025-02-15 23:59:00" for result in results)


class TestDateEdgeCases:
    """Test edge cases for date handling as identified in the audit.

    Section 5 of the audit identified these missing tests:
    - Malformed date strings (e.g., "2025-13-45")
    - Timezone edge cases (deadline at midnight in AoE vs UTC)
    - Leap year handling
    - Year boundary transitions
    """

    def test_malformed_date_invalid_month(self):
        """Test handling of invalid month (13) in date string."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-13-15",  # Invalid: month 13 doesn't exist
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged (ValueError is caught and continues)
        assert result["workshop_deadline"] == "2025-13-15"

    def test_malformed_date_invalid_day(self):
        """Test handling of invalid day (45) in date string."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-06-45",  # Invalid: day 45 doesn't exist
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged
        assert result["workshop_deadline"] == "2025-06-45"

    def test_malformed_date_february_30(self):
        """Test handling of impossible date: February 30."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-02-30",  # Invalid: Feb 30 doesn't exist
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged
        assert result["workshop_deadline"] == "2025-02-30"

    def test_leap_year_february_29_valid(self):
        """Test CFP on Feb 29 of leap year (2024 is a leap year)."""
        data = {
            "start": "2024-06-01",
            "end": "2024-06-03",
            "cfp": "2024-02-29",  # Valid: 2024 is a leap year
        }

        result = clean_dates(data)

        # Should process correctly and add time
        assert result["cfp"] == "2024-02-29 23:59:00"

    def test_non_leap_year_february_29_invalid(self):
        """Test CFP on Feb 29 of non-leap year (2025 is not a leap year)."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-02-29",  # Invalid: 2025 is not a leap year
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged
        assert result["workshop_deadline"] == "2025-02-29"

    def test_leap_year_february_29_nice_date(self):
        """Test nice date creation for Feb 29 on leap year."""
        data = {
            "start": "2024-02-29",  # Leap year day
            "end": "2024-02-29",
        }

        result = create_nice_date(data)

        assert result["date"] == "February 29th, 2024"

    def test_year_boundary_transition_december_to_january(self):
        """Test conference spanning year boundary (Dec to Jan)."""
        data = {
            "start": "2025-12-28",
            "end": "2026-01-03",
            "cfp": "2025-10-15",
        }

        cleaned = clean_dates(data)
        nice_date = create_nice_date(cleaned)

        # Should handle year transition in nice date
        assert nice_date["date"] == "December 28, 2025 - January 3, 2026"

    def test_year_boundary_cfp_deadline(self):
        """Test CFP deadline on Dec 31 (year boundary)."""
        data = {
            "start": "2026-03-01",
            "end": "2026-03-05",
            "cfp": "2025-12-31",  # Deadline on year boundary
        }

        result = clean_dates(data)

        # Should process correctly
        assert result["cfp"] == "2025-12-31 23:59:00"

    def test_year_boundary_new_years_day_cfp(self):
        """Test CFP deadline on Jan 1 (start of new year)."""
        data = {
            "start": "2026-03-01",
            "end": "2026-03-05",
            "cfp": "2026-01-01",  # First day of year
        }

        result = clean_dates(data)

        assert result["cfp"] == "2026-01-01 23:59:00"

    def test_century_leap_year_2000(self):
        """Test that year 2000 leap year rules work (divisible by 400)."""
        # 2000 was a leap year (divisible by 400)
        data = {
            "start": "2000-02-29",
            "end": "2000-02-29",
        }

        result = create_nice_date(data)

        assert result["date"] == "February 29th, 2000"

    def test_century_non_leap_year_1900(self):
        """Test that year 1900 non-leap year rules work (divisible by 100 but not 400)."""
        # 1900 was NOT a leap year (divisible by 100 but not 400)
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15",
            "workshop_deadline": "1900-02-29",  # Invalid: 1900 was not a leap year
        }

        result = clean_dates(data)

        # Invalid date should be left unchanged
        assert result["workshop_deadline"] == "1900-02-29"

    def test_midnight_boundary_explicit_midnight(self):
        """Test CFP with explicit midnight time (00:00:00).

        When a datetime string includes an explicit time component,
        it is preserved as-is. The 23:59 conversion only applies to
        date-only strings that are parsed without a time component.
        """
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15 00:00:00",  # Explicit midnight
        }

        result = clean_dates(data)

        # Explicit times are preserved as-is (conversion only for date-only strings)
        assert result["cfp"] == "2025-02-15 00:00:00"

    def test_one_minute_before_midnight(self):
        """Test CFP with 23:59:00 time (one minute before midnight)."""
        data = {
            "start": "2025-06-01",
            "end": "2025-06-03",
            "cfp": "2025-02-15 23:59:00",
        }

        result = clean_dates(data)

        # Should remain unchanged
        assert result["cfp"] == "2025-02-15 23:59:00"

    def test_conference_single_day_event(self):
        """Test single-day conference (start == end)."""
        data = {
            "start": "2025-06-15",
            "end": "2025-06-15",
            "cfp": "2025-02-15",
        }

        cleaned = clean_dates(data)
        nice_date = create_nice_date(cleaned)

        # Single day should show ordinal suffix
        assert nice_date["date"] == "June 15th, 2025"

    def test_multi_year_conference(self):
        """Test conference spanning multiple years (unusual but possible)."""
        data = {
            "start": "2025-11-15",
            "end": "2026-02-15",  # 3 months span across year
            "cfp": "2025-08-01",
        }

        cleaned = clean_dates(data)
        nice_date = create_nice_date(cleaned)

        assert nice_date["date"] == "November 15, 2025 - February 15, 2026"

    def test_future_year_dates(self):
        """Test handling of far future dates."""
        data = {
            "start": "2099-12-01",
            "end": "2099-12-05",
            "cfp": "2099-06-15",
        }

        cleaned = clean_dates(data)
        nice_date = create_nice_date(cleaned)

        assert cleaned["cfp"] == "2099-06-15 23:59:00"
        assert "2099" in nice_date["date"]
