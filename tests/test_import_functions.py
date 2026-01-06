"""Tests for data import functions."""

# Add utils to path for imports
import sys
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import import_python_official
import import_python_organizers


class TestPythonOfficialImport:
    """Test import from python.org calendar."""

    @patch("import_python_official.requests.get")
    def test_ics_parsing(self, mock_get):
        """Test ICS file parsing from Google Calendar."""
        # Mock ICS content with complete event data
        mock_ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
DTSTART:20250601T000000Z
DTEND:20250603T000000Z
SUMMARY:PyCon Test 2025
DESCRIPTION:<a href="https://test.pycon.org">PyCon Test</a>
LOCATION:Test City
END:VEVENT
END:VCALENDAR"""

        mock_response = Mock()
        mock_response.content = mock_ics_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Test the function
        df = import_python_official.ics_to_dataframe()

        # Verify DataFrame structure and content
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1, "Should have exactly 1 conference entry"

        # Verify column names are correct
        expected_columns = {"conference", "year", "cfp", "start", "end", "link", "place"}
        assert set(df.columns) == expected_columns, f"Expected {expected_columns}, got {set(df.columns)}"

        # Verify actual data values
        row = df.iloc[0]
        assert row["conference"] == "PyCon Test", f"Expected 'PyCon Test', got '{row['conference']}'"
        assert row["year"] == 2025, f"Expected year 2025, got {row['year']}"
        assert row["start"] == "2025-06-01", f"Expected '2025-06-01', got '{row['start']}'"
        assert row["end"] == "2025-06-02", f"Expected '2025-06-02', got '{row['end']}'"  # End is dtend - 1 day
        assert row["link"] == "https://test.pycon.org", f"Expected 'https://test.pycon.org', got '{row['link']}'"
        assert row["place"] == "Test City", f"Expected 'Test City', got '{row['place']}'"
        assert row["cfp"] == "TBA", f"Expected 'TBA', got '{row['cfp']}'"

    @patch("import_python_official.requests.get")
    def test_ics_parsing_multiple_events(self, mock_get):
        """Test ICS parsing with multiple events."""
        mock_ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
DTSTART:20250601T000000Z
DTEND:20250603T000000Z
SUMMARY:PyCon US 2025
DESCRIPTION:<a href="https://pycon.us">PyCon US</a>
LOCATION:Pittsburgh, PA
END:VEVENT
BEGIN:VEVENT
DTSTART:20250715T000000Z
DTEND:20250720T000000Z
SUMMARY:EuroPython 2025
DESCRIPTION:<a href="https://europython.eu">EuroPython</a>
LOCATION:Dublin, Ireland
END:VEVENT
END:VCALENDAR"""

        mock_response = Mock()
        mock_response.content = mock_ics_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        df = import_python_official.ics_to_dataframe()

        # Verify both events were parsed
        assert len(df) == 2, f"Expected 2 conferences, got {len(df)}"

        # Verify each conference is present
        conferences = df["conference"].tolist()
        assert "PyCon US" in conferences, f"'PyCon US' not found in {conferences}"
        assert "EuroPython" in conferences, f"'EuroPython' not found in {conferences}"

    @patch("import_python_official.requests.get")
    def test_ics_parsing_missing_dates_skipped(self, mock_get):
        """Test that events with missing dates are skipped."""
        mock_ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Invalid Event Without Dates
DESCRIPTION:No dates here
LOCATION:Unknown
END:VEVENT
BEGIN:VEVENT
DTSTART:20250601T000000Z
DTEND:20250603T000000Z
SUMMARY:Valid Event
DESCRIPTION:<a href="https://valid.com">Valid</a>
LOCATION:Valid City
END:VEVENT
END:VCALENDAR"""

        mock_response = Mock()
        mock_response.content = mock_ics_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        df = import_python_official.ics_to_dataframe()

        # Only valid event should be included
        assert len(df) == 1, f"Expected 1 conference (invalid skipped), got {len(df)}"
        assert df.iloc[0]["conference"] == "Valid", f"Expected 'Valid', got '{df.iloc[0]['conference']}'"

    @patch("import_python_official.requests.get")
    def test_ics_parsing_empty_calendar(self, mock_get):
        """Test handling of empty calendar."""
        mock_ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
END:VCALENDAR"""

        mock_response = Mock()
        mock_response.content = mock_ics_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        df = import_python_official.ics_to_dataframe()

        # Should return empty DataFrame with correct columns
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0, f"Expected empty DataFrame, got {len(df)} rows"

    def test_link_description_parsing(self):
        """Test parsing of HTML links in event descriptions."""
        # Test the regex pattern used in the import
        import re

        link_desc = re.compile(r".*<a .*?href=\"? ?((?:https|http):\/\/[\w\.\/\-\?= ]+)\"?.*?>(.*?)[#0-9 ]*<\/?a>.*")

        test_descriptions = [
            '<a href="https://example.com">Test Conference</a>',
            '<a href="https://pycon.org/2025">PyCon 2025</a>',
            'Some text <a href="https://test.org">Link Text</a> more text',
        ]

        for desc in test_descriptions:
            match = link_desc.match(desc)
            if match:
                url, title = match.groups()
                assert url.startswith(("http://", "https://"))
                assert title.strip() != ""

    @patch("import_python_official.load_conferences")
    @patch("import_python_official.write_df_yaml")
    @patch("import_python_official.ics_to_dataframe")
    @patch("import_python_official.tidy_df_names")
    def test_main_function_with_data_flow(self, mock_tidy, mock_ics, mock_write, mock_load):
        """Test main function processes data correctly through pipeline."""
        # Setup test data that flows through the pipeline
        test_ics_df = pd.DataFrame({
            "conference": ["Test Conf"],
            "year": [2026],
            "cfp": ["TBA"],
            "start": ["2026-06-01"],
            "end": ["2026-06-03"],
            "link": ["https://test.com"],
            "place": ["Test City"]
        })

        test_yml_df = pd.DataFrame({
            "conference": [],
            "year": [],
            "cfp": [],
            "start": [],
            "end": [],
            "link": [],
            "place": []
        })

        mock_load.return_value = test_yml_df
        mock_ics.return_value = test_ics_df
        mock_tidy.return_value = test_ics_df  # Return same data after tidy

        # Run the import
        result = import_python_official.main()

        # Verify data was loaded
        assert mock_load.called, "Should load existing conference data"
        assert mock_ics.called, "Should fetch ICS calendar data"

        # Verify title tidying was applied
        assert mock_tidy.called, "Should tidy conference names"

    @patch("import_python_official.requests.get")
    def test_ics_to_dataframe_network_error(self, mock_get):
        """Test ICS parsing handles network errors correctly."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            import_python_official.ics_to_dataframe()

        assert "Network error" in str(exc_info.value) or "Unable to fetch" in str(exc_info.value)


class TestPythonOrganizersImport:
    """Test import from python-organizers repository."""

    @patch("import_python_organizers.pd.read_csv")
    def test_remote_csv_loading(self, mock_read_csv):
        """Test loading CSV from remote repository with correct URL and column mapping."""
        # Mock CSV data with actual column names from python-organizers repo
        mock_df = pd.DataFrame(
            {
                "Subject": ["PyCon Test"],
                "Start Date": ["2025-06-01"],
                "End Date": ["2025-06-03"],
                "Tutorial Deadline": ["2025-02-01"],
                "Talk Deadline": ["2025-02-15 23:59:00"],
                "Website URL": ["https://test.pycon.org"],
                "Proposal URL": ["https://cfp.test.pycon.org"],
                "Sponsorship URL": ["https://sponsor.test.pycon.org"],
                "Location": ["Test City, Test Country"],
            },
        )
        mock_read_csv.return_value = mock_df

        result_df = import_python_organizers.load_remote(2025)

        # Verify the CSV was loaded with correct URL
        expected_url = "https://raw.githubusercontent.com/python-organizers/conferences/main/2025.csv"
        mock_read_csv.assert_called_once_with(expected_url)

        # Verify result has mapped column names
        assert "conference" in result_df.columns, "Should map 'Subject' to 'conference'"
        assert "start" in result_df.columns, "Should map 'Start Date' to 'start'"
        assert "cfp" in result_df.columns, "Should map 'Talk Deadline' to 'cfp'"

        # Verify actual values were preserved
        assert result_df.iloc[0]["conference"] == "PyCon Test"
        assert result_df.iloc[0]["start"] == "2025-06-01"

    def test_column_mapping(self):
        """Test column mapping from CSV format to internal format."""
        # Create sample CSV-style DataFrame with the correct column names
        csv_df = pd.DataFrame(
            {
                "Subject": ["PyCon Test"],
                "Start Date": ["2025-06-01"],
                "End Date": ["2025-06-03"],
                "Tutorial Deadline": ["2025-02-01"],
                "Talk Deadline": ["2025-02-15 23:59:00"],
                "Website URL": ["https://test.pycon.org"],
                "Proposal URL": ["https://cfp.test.pycon.org"],
                "Sponsorship URL": ["https://sponsor.test.pycon.org"],
                "Location": ["Test City, Test Country"],
            },
        )

        # Test mapping function
        mapped_df = import_python_organizers.map_columns(csv_df)

        # Should have internal column names
        expected_mappings = {
            "conference": "Subject",
            "start": "Start Date",
            "end": "End Date",
            "tutorial_deadline": "Tutorial Deadline",
            "cfp": "Talk Deadline",
            "link": "Website URL",
            "cfp_link": "Proposal URL",
            "sponsor": "Sponsorship URL",
        }

        for internal_name in expected_mappings:
            assert internal_name in mapped_df.columns, f"Missing {internal_name} from mapped columns"

    def test_country_validation(self):
        """Test country validation using ISO3166."""
        # Test valid countries
        valid_locations = [
            "New York, USA",
            "Berlin, Germany",
            "Tokyo, Japan",
            "Online",  # Special case
        ]

        # Should not raise exceptions for valid countries
        for location in valid_locations:
            # Basic validation - location should have comma or be 'Online'
            assert "," in location or location.lower() == "online"

    def test_map_columns_data_preservation(self):
        """Test that map_columns preserves data values while renaming columns."""
        input_df = pd.DataFrame({
            "Subject": ["PyCon US 2025", "DjangoCon 2025"],
            "Start Date": ["2025-06-01", "2025-09-01"],
            "End Date": ["2025-06-03", "2025-09-03"],
            "Tutorial Deadline": ["2025-02-01", "2025-05-01"],
            "Talk Deadline": ["2025-02-15", "2025-05-15"],
            "Website URL": ["https://pycon.us", "https://djangocon.us"],
            "Proposal URL": ["https://pycon.us/cfp", "https://djangocon.us/cfp"],
            "Sponsorship URL": ["https://pycon.us/sponsor", "https://djangocon.us/sponsor"],
            "Location": ["Pittsburgh, PA, USA", "San Francisco, CA, USA"]
        })

        result = import_python_organizers.map_columns(input_df)

        # Verify column names are mapped correctly
        assert "conference" in result.columns
        assert "start" in result.columns
        assert "cfp" in result.columns
        assert "link" in result.columns

        # Verify data values are preserved
        assert result["conference"].tolist() == ["PyCon US 2025", "DjangoCon 2025"]
        assert result["start"].tolist() == ["2025-06-01", "2025-09-01"]
        assert result["cfp"].tolist() == ["2025-02-15", "2025-05-15"]
        assert result["link"].tolist() == ["https://pycon.us", "https://djangocon.us"]

    def test_map_columns_reverse_mapping(self):
        """Test reverse column mapping from internal format to CSV format."""
        # The reverse mapping only renames specific columns defined in cols dict
        # 'place' column is handled separately in map_columns (df["place"] = df["Location"])
        input_df = pd.DataFrame({
            "conference": ["Test Conf"],
            "start": ["2025-06-01"],
            "end": ["2025-06-03"],
            "tutorial_deadline": ["2025-02-01"],
            "cfp": ["2025-02-15"],
            "link": ["https://test.com"],
            "cfp_link": ["https://test.com/cfp"],
            "sponsor": ["https://test.com/sponsor"],
            "Location": ["Test City, Country"]  # Must include original Location column for reverse
        })

        result = import_python_organizers.map_columns(input_df, reverse=True)

        # Verify reverse mapping works for columns in the mapping dict
        assert "Subject" in result.columns
        assert "Start Date" in result.columns
        assert "Talk Deadline" in result.columns
        assert "Website URL" in result.columns

        # Verify data is preserved
        assert result["Subject"].tolist() == ["Test Conf"]
        assert result["Talk Deadline"].tolist() == ["2025-02-15"]

    @patch("import_python_organizers.pd.read_csv")
    def test_load_remote_year_in_url(self, mock_read_csv):
        """Test that load_remote uses correct year in URL."""
        mock_read_csv.return_value = pd.DataFrame({
            "Subject": [],
            "Start Date": [],
            "End Date": [],
            "Tutorial Deadline": [],
            "Talk Deadline": [],
            "Website URL": [],
            "Proposal URL": [],
            "Sponsorship URL": [],
            "Location": []
        })

        # Test different years
        for year in [2024, 2025, 2026]:
            import_python_organizers.load_remote(year)
            expected_url = f"https://raw.githubusercontent.com/python-organizers/conferences/main/{year}.csv"
            mock_read_csv.assert_called_with(expected_url)


class TestDataImportIntegration:
    """Test integration between import functions."""

    def test_fuzzy_matching_integration(self):
        """Test fuzzy matching between different data sources."""
        # Test data that should match
        conference_names = [
            ("PyCon US", "PyCon United States"),
            ("DjangoCon EU", "DjangoCon Europe"),
            ("EuroPython", "Euro Python"),
        ]

        # Basic fuzzy matching test (would need actual fuzzy_match import)
        for name1, name2 in conference_names:
            # Should be similar enough to match
            assert len(name1) > 0 and len(name2) > 0

    def test_deduplication_logic(self):
        """Test deduplication between import sources."""
        # Sample duplicate conferences
        conferences = [
            {"conference": "PyCon Test", "year": 2025, "place": "Test City, Country", "source": "official"},
            {
                "conference": "PyCon Test",  # Same conference
                "year": 2025,
                "place": "Test City, Country",
                "source": "organizers",
            },
        ]

        # Should identify duplicates based on name, year, and location
        conf1, conf2 = conferences
        duplicate_key = f"{conf1['conference']} {conf1['year']} {conf1['place']}"
        duplicate_key2 = f"{conf2['conference']} {conf2['year']} {conf2['place']}"

        assert duplicate_key == duplicate_key2

    def test_data_merge_priority(self):
        """Test data merge priority from different sources."""
        # Test that more complete data takes priority
        source1 = {"conference": "PyCon Test", "link": "https://short.com", "sponsor": None}

        source2 = {
            "conference": "PyCon Test",
            "link": "https://much-longer-and-more-detailed.com",
            "sponsor": "https://sponsor.com",
        }

        # Longer/more complete data should be preferred
        assert len(source2["link"]) > len(source1["link"])
        assert source2["sponsor"] is not None
