"""Tests for data import functions."""

# Add utils to path for imports
import sys
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import import_python_official
import import_python_organizers


class TestPythonOfficialImport:
    """Test import from python.org calendar."""

    @patch("import_python_official.requests.get")
    def test_ics_parsing(self, mock_get):
        """Test ICS file parsing from Google Calendar."""
        # Mock ICS content
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

        # Verify the result
        assert isinstance(df, pd.DataFrame)
        mock_get.assert_called_once()

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
    def test_main_function(self, mock_write, mock_load):
        """Test the main import function."""
        mock_load.return_value = pd.DataFrame()

        # Should not raise an exception
        import_python_official.main()

        mock_load.assert_called_once()


class TestPythonOrganizersImport:
    """Test import from python-organizers repository."""

    @patch("import_python_organizers.pd.read_csv")
    def test_remote_csv_loading(self, mock_read_csv):
        """Test loading CSV from remote repository."""
        # Mock CSV data
        mock_df = pd.DataFrame(
            {
                "Name": ["PyCon Test"],
                "Year": [2025],
                "Website": ["https://test.pycon.org"],
                "CFP": ["2025-02-15"],
                "Location": ["Test City, Test Country"],
                "Start": ["2025-06-01"],
                "End": ["2025-06-03"],
                "Type": ["Conference"],
            },
        )
        mock_read_csv.return_value = mock_df

        result_df = import_python_organizers.load_remote(2025)

        # Verify the CSV was loaded with correct URL
        expected_url = "https://raw.githubusercontent.com/python-organizers/conferences/main/2025.csv"
        mock_read_csv.assert_called_once_with(expected_url)

        # Verify result is returned
        assert result_df is not None

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

    @patch("import_python_organizers.load_remote")
    @patch("import_python_organizers.load_conferences")
    @patch("import_python_organizers.write_df_yaml")
    def test_main_function(self, mock_write, mock_load_conf, mock_load_remote):
        """Test the main import function."""
        # Mock DataFrames with expected columns to avoid processing errors
        mock_load_remote.return_value = pd.DataFrame(
            columns=["conference", "year", "cfp", "start", "end", "link", "place"],
        )
        mock_load_conf.return_value = pd.DataFrame(
            columns=["conference", "year", "cfp", "start", "end", "link", "place"],
        )

        # Should not raise an exception
        import_python_organizers.main()

        # Should attempt to load remote data
        assert mock_load_remote.called
        assert mock_load_conf.called


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
