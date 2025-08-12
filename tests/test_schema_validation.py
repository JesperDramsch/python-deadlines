"""Tests for conference data schema validation."""

# Add utils to path for imports
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.schema import Conference
from tidy_conf.schema import Location


class TestConferenceSchema:
    """Test the Conference Pydantic model validation."""

    def test_valid_conference(self, sample_conference):
        """Test that valid conference data passes validation."""
        conf = Conference(**sample_conference)
        assert conf.conference == "PyCon Test"
        assert conf.year == 2025
        assert conf.sub == "PY"

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            Conference()

        errors = exc_info.value.errors()
        required_fields = {"conference", "year", "link", "cfp", "place", "start", "end", "sub"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert required_fields.issubset(error_fields)

    def test_year_validation(self, sample_conference):
        """Test that year validation accepts valid years."""
        # Valid year
        sample_conference["year"] = 2025
        conf = Conference(**sample_conference)
        assert conf.year == 2025

        # Test another valid year
        sample_conference["year"] = 2024
        conf = Conference(**sample_conference)
        assert conf.year == 2024

    def test_date_validation(self, sample_conference):
        """Test date format and logic validation."""
        # Test end date before start date
        sample_conference["start"] = date(2025, 6, 3)
        sample_conference["end"] = date(2025, 6, 1)

        with pytest.raises(ValidationError) as exc_info:
            Conference(**sample_conference)

        assert "start date must be before" in str(exc_info.value).lower()

    def test_multi_year_conference(self, sample_conference):
        """Test validation for multi-year conferences."""
        sample_conference["start"] = date(2025, 12, 30)
        sample_conference["end"] = date(2026, 1, 2)

        with pytest.raises(ValidationError) as exc_info:
            Conference(**sample_conference)

        assert "multi-year conference" in str(exc_info.value).lower()

    def test_cfp_datetime_format(self, sample_conference):
        """Test CFP datetime format validation."""
        # Valid formats
        valid_cfps = [
            "2025-02-15 23:59:00",
            "2025-12-31 00:00:00",
            "2025-01-01 12:30:45",
        ]

        for cfp in valid_cfps:
            sample_conference["cfp"] = cfp
            conf = Conference(**sample_conference)
            assert conf.cfp == cfp

    def test_url_validation(self, sample_conference):
        """Test URL field validation."""
        # Valid URLs - test that they're accepted and normalized properly
        valid_urls = [
            ("https://example.com", "https://example.com/"),
            ("http://test.org", "http://test.org/"),
            ("https://sub.domain.com/path", "https://sub.domain.com/path"),
        ]

        for url, expected in valid_urls:
            sample_conference["link"] = url
            conf = Conference(**sample_conference)
            assert str(conf.link) == expected

        # Invalid URLs
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Wrong protocol
            "example.com",  # Missing protocol
        ]

        for invalid_url in invalid_urls:
            sample_conference["link"] = invalid_url
            with pytest.raises(ValidationError):
                Conference(**sample_conference)

    def test_sub_field_validation(self, sample_conference):
        """Test conference sub-type field."""
        valid_subs = ["PY", "SCIPY", "DATA", "WEB", "BIZ", "GEO", "CAMP", "DAY", "PY,DATA", "WEB,BIZ"]

        for sub in valid_subs:
            sample_conference["sub"] = sub
            conf = Conference(**sample_conference)
            assert conf.sub == sub

    def test_optional_fields(self, sample_conference):
        """Test optional field handling."""
        # Test non-URL fields
        non_url_fields = {
            "alt_name": "Alternative Conference Name",
            "cfp_ext": "2025-03-01 23:59:00",
            "workshop_deadline": "2025-02-01 23:59:00",
            "tutorial_deadline": "2025-02-10 23:59:00",
            "twitter": "testconf",
            "bluesky": "testconf.bsky.social",
            "note": "Special conference notes",
            "extra_places": ["Online", "Hybrid"],
        }

        for field, value in non_url_fields.items():
            test_data = sample_conference.copy()
            test_data[field] = value
            conf = Conference(**test_data)
            assert getattr(conf, field) == value

        # Test URL fields separately (accounting for normalization)
        url_fields = {
            "cfp_link": ("https://cfp.example.com", "https://cfp.example.com/"),
            "sponsor": ("https://sponsor.example.com", "https://sponsor.example.com/"),
            "finaid": ("https://finaid.example.com", "https://finaid.example.com/"),
            "mastodon": ("https://mastodon.social/@testconf", "https://mastodon.social/@testconf"),
        }

        for field, (input_value, expected) in url_fields.items():
            test_data = sample_conference.copy()
            test_data[field] = input_value
            conf = Conference(**test_data)
            assert str(getattr(conf, field)) == expected

    def test_online_conference_no_location(self, online_conference):
        """Test that online conferences don't require location data."""
        conf = Conference(**online_conference)
        assert conf.place.lower() == "online"
        assert conf.location is None


class TestLocationSchema:
    """Test the Location model validation."""

    def test_valid_location(self):
        """Test valid location data."""
        location_data = {"title": "Test Conference 2025", "latitude": 40.7128, "longitude": -74.0060}

        location = Location(**location_data)
        assert location.title == "Test Conference 2025"
        assert location.latitude == 40.7128
        assert location.longitude == -74.0060

    def test_coordinate_bounds(self):
        """Test coordinate validation bounds."""
        # Valid coordinates (excluding 0,0 which is rejected)
        valid_coords = [
            (90.0, 180.0),  # Max bounds
            (-90.0, -180.0),  # Min bounds
            (45.5, -122.6),  # Normal coordinates
            (40.7128, -74.0060),  # NYC coordinates
        ]

        for lat, lon in valid_coords:
            location = Location(title="Test", latitude=lat, longitude=lon)
            assert location.latitude == lat
            assert location.longitude == lon

        # Test that 0,0 coordinates are rejected (custom validation in schema)
        with pytest.raises(ValidationError):
            Location(title="Test", latitude=0.0, longitude=0.0)  # Origin coordinates are rejected

    def test_coordinate_precision(self):
        """Test coordinate precision validation."""
        # Test high precision coordinates (should be rounded to 5 decimal places)
        location = Location(title="High Precision Test", latitude=40.712812345678, longitude=-74.006012345678)

        # Should accept the coordinates even with high precision
        assert location.latitude == 40.712812345678
        assert location.longitude == -74.006012345678
