"""Tests for CSV processing functionality and fixes."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import import_python_organizers


class TestCSVSortingFixes:
    """Test CSV sorting functionality fixes."""

    def test_csv_sorting_compliance_python_organizers(self):
        """Test that CSV is sorted according to python-organizers expectations."""
        # Create test data with internal column names, then add required CSV columns
        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B", "Conference C", "Conference D"],
                "start": ["2025-06-15", "2025-06-01", "2025-06-01", "2025-06-15"],
                "end": ["2025-06-17", "2025-06-03", "2025-06-05", "2025-06-17"],
                "Location": ["City A", "City B", "City C", "City D"],  # Note: Location, not place
                "tutorial_deadline": ["2025-03-01", "2025-02-01", "2025-02-15", "2025-03-15"],
                "cfp": ["2025-04-01", "2025-03-01", "2025-03-15", "2025-04-15"],
                "link": ["https://a.com", "https://b.com", "https://c.com", "https://d.com"],
                "cfp_link": ["https://cfp-a.com", "https://cfp-b.com", "https://cfp-c.com", "https://cfp-d.com"],
                "sponsor": [
                    "https://sponsor-a.com",
                    "https://sponsor-b.com",
                    "https://sponsor-c.com",
                    "https://sponsor-d.com",
                ],
                "year": [2025, 2025, 2025, 2025],
                # Add required columns for write_csv
                "Country": ["USA", "UK", "Canada", "Germany"],
                "Venue": ["Convention Center A", "Convention Center B", "Convention Center C", "Convention Center D"],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Call write_csv function
            import_python_organizers.write_csv(test_data, 2025, temp_path)

            # Read back the written CSV to verify sorting
            csv_file = temp_path / "2025.csv"
            assert csv_file.exists()

            result_df = pd.read_csv(csv_file)

            # Verify the CSV is sorted by Start Date, End Date, Subject
            # Expected order should be: B (06-01,06-03), C (06-01,06-05), A (06-15,06-17), D (06-15,06-17)
            expected_subjects = ["Conference B", "Conference C", "Conference A", "Conference D"]
            actual_subjects = result_df["Subject"].tolist()

            assert (
                actual_subjects == expected_subjects
            ), f"CSV not sorted correctly. Expected: {expected_subjects}, Got: {actual_subjects}"

    def test_csv_column_structure(self):
        """Test that CSV has the expected column structure."""
        test_data = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
                "Location": ["Test City"],
                "Country": ["USA"],
                "Venue": ["Test Venue"],
                "tutorial_deadline": ["2025-03-01"],
                "cfp": ["2025-04-01"],
                "link": ["https://test.com"],
                "cfp_link": ["https://cfp-test.com"],
                "sponsor": ["https://sponsor-test.com"],
                "year": [2025],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            import_python_organizers.write_csv(test_data, 2025, temp_path)

            csv_file = temp_path / "2025.csv"
            result_df = pd.read_csv(csv_file)

            # Verify expected columns are present in correct order
            expected_columns = [
                "Subject",
                "Start Date",
                "End Date",
                "Location",
                "Country",
                "Venue",
                "Tutorial Deadline",
                "Talk Deadline",
                "Website URL",
                "Proposal URL",
                "Sponsorship URL",
            ]

            assert list(result_df.columns) == expected_columns

    def test_conference_name_validation_in_csv_processing(self):
        """Test that CSV processing validates conference names correctly."""
        # This tests the fix for conference name corruption
        test_data = pd.DataFrame(
            {
                "conference": ["Valid Conference", None, "", "Another Valid Conference"],
                "year": [2025, 2025, 2025, 2025],
                "start": ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"],
                "end": ["2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06"],
                "Location": ["City A", "City B", "City C", "City D"],
                "Country": ["USA", "UK", "Canada", "Germany"],
                "Venue": ["Venue A", "Venue B", "Venue C", "Venue D"],
                "tutorial_deadline": ["", "", "", ""],
                "cfp": ["", "", "", ""],
                "link": ["https://a.com", "https://b.com", "https://c.com", "https://d.com"],
                "cfp_link": ["", "", "", ""],
                "sponsor": ["", "", "", ""],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # This should not crash and should handle invalid conference names
            import_python_organizers.write_csv(test_data, 2025, temp_path)

            csv_file = temp_path / "2025.csv"
            assert csv_file.exists()

            result_df = pd.read_csv(csv_file)

            # Verify that all Subject entries are strings (not NaN, not empty)
            for subject in result_df["Subject"]:
                assert isinstance(subject, str)
                assert subject.strip() != ""


class TestDataValidation:
    """Test data validation during CSV processing."""

    def test_cfp_deadline_processing(self):
        """Test CFP deadline processing and cleanup."""
        test_data = pd.DataFrame(
            {
                "cfp": ["2025-02-15 23:59:00", "TBA", "None", "2025-03-15 23:59:00"],
                "tutorial_deadline": ["2025-02-01", "TBA", "", "2025-03-01"],
                "conference": ["Conf A", "Conf B", "Conf C", "Conf D"],
                "year": [2025, 2025, 2025, 2025],
                "start": ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"],
                "end": ["2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06"],
                "Location": ["City A", "City B", "City C", "City D"],
                "Country": ["USA", "UK", "Canada", "Germany"],
                "Venue": ["Venue A", "Venue B", "Venue C", "Venue D"],
                "link": ["https://a.com", "https://b.com", "https://c.com", "https://d.com"],
                "cfp_link": ["", "", "", ""],
                "sponsor": ["", "", "", ""],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            import_python_organizers.write_csv(test_data, 2025, temp_path)

            csv_file = temp_path / "2025.csv"

            # Read CSV with proper settings to preserve empty strings
            result_df = pd.read_csv(csv_file, keep_default_na=False, na_values=[])

            # Check that TBA and None values were processed correctly
            talk_deadlines = result_df["Talk Deadline"].tolist()
            assert "2025-02-15" in talk_deadlines
            assert "2025-03-15" in talk_deadlines
            # TBA and None should be converted to empty strings
            assert "" in talk_deadlines

    def test_country_code_assignment(self):
        """Test country code assignment from location."""
        test_data = pd.DataFrame(
            {
                "conference": ["Conf A", "Conf B", "Conf C"],
                "Location": ["New York, USA", "London, United Kingdom", "Invalid Location"],
                "year": [2025, 2025, 2025],
                "start": ["2025-06-01", "2025-06-02", "2025-06-03"],
                "end": ["2025-06-03", "2025-06-04", "2025-06-05"],
                "Country": ["", "", ""],
                "Venue": ["Venue A", "Venue B", "Venue C"],
                "tutorial_deadline": ["", "", ""],
                "cfp": ["", "", ""],
                "link": ["https://a.com", "https://b.com", "https://c.com"],
                "cfp_link": ["", "", ""],
                "sponsor": ["", "", ""],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            import_python_organizers.write_csv(test_data, 2025, temp_path)

            csv_file = temp_path / "2025.csv"
            result_df = pd.read_csv(csv_file, keep_default_na=False, na_values=[])

            # Check that country codes were assigned where possible
            countries = result_df["Country"].tolist()
            # Should handle country assignment or gracefully fail
            assert len(countries) == 3
            for country in countries:
                # Should be a string (even if empty)
                assert isinstance(country, str)


class TestErrorHandling:
    """Test error handling in CSV processing."""

    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        empty_df = pd.DataFrame(
            columns=[
                "conference",
                "year",
                "start",
                "end",
                "Location",
                "Country",
                "Venue",
                "tutorial_deadline",
                "cfp",
                "link",
                "cfp_link",
                "sponsor",
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Should not crash with empty DataFrame
            import_python_organizers.write_csv(empty_df, 2025, temp_path)

            csv_file = temp_path / "2025.csv"
            # File should still be created, even if empty
            assert csv_file.exists()

    def test_malformed_data_handling(self):
        """Test handling of malformed data."""
        malformed_data = pd.DataFrame(
            {
                "conference": [123, None, "Valid Conference"],  # Mixed types
                "year": ["invalid", 2025, 2025],  # Invalid year
                "start": ["invalid-date", "2025-06-02", "2025-06-03"],
                "end": ["2025-06-03", "invalid-date", "2025-06-05"],
                "Location": [None, "", "Valid City"],
                "Country": ["", "", ""],
                "Venue": ["", "", ""],
                "tutorial_deadline": ["", "", ""],
                "cfp": ["", "", ""],
                "link": ["", "", ""],
                "cfp_link": ["", "", ""],
                "sponsor": ["", "", ""],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Should handle malformed data gracefully
            import_python_organizers.write_csv(malformed_data, 2025, temp_path)

            csv_file = temp_path / "2025.csv"
            assert csv_file.exists()

            result_df = pd.read_csv(csv_file, keep_default_na=False, na_values=[])
            # Should have converted everything to strings
            for col in result_df.columns:
                for val in result_df[col]:
                    assert isinstance(val, str)


class TestIntegrationWithLogging:
    """Test integration with the new logging system."""

    @patch("logging_config.get_tqdm_logger")
    def test_logging_integration_in_csv_write(self, mock_logger):
        """Test that CSV processing integrates with tqdm logging."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        test_data = pd.DataFrame(
            {
                "conference": ["Test Conference"],
                "year": [2025],
                "start": ["2025-06-01"],
                "end": ["2025-06-03"],
                "Location": ["Test City"],
                "Country": ["USA"],
                "Venue": ["Test Venue"],
                "tutorial_deadline": [""],
                "cfp": [""],
                "link": ["https://test.com"],
                "cfp_link": [""],
                "sponsor": [""],
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            import_python_organizers.write_csv(test_data, 2025, temp_path)

            # Verify logging was called
            assert mock_logger.called
            assert mock_logger_instance.info.called

            # Check that specific logging messages were recorded
            log_calls = [call.args[0] for call in mock_logger_instance.info.call_args_list]
            assert any("Starting write_csv" in msg for msg in log_calls)
            assert any("Successfully wrote" in msg for msg in log_calls)
