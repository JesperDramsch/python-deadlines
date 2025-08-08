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
        """Test that year must be >= 1989 (Python's birth year)."""
        # Valid year
        sample_conference["year"] = 2025
        conf = Conference(**sample_conference)
        assert conf.year == 2025

        # Invalid year - before Python
        sample_conference["year"] = 1988
        with pytest.raises(ValidationError) as exc_info:
            Conference(**sample_conference)

        assert "ge=1989" in str(exc_info.value)

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
        # Valid format
        sample_conference["cfp"] = "2025-02-15 23:59:00"
        conf = Conference(**sample_conference)
        assert conf.cfp == "2025-02-15 23:59:00"

        # Invalid format
        invalid_formats = [
            "2025-02-15",  # Missing time
            "02/15/2025 23:59:00",  # Wrong date format
            "2025-2-15 23:59:00",  # Single digit month
            "TBA",  # Text instead of date
        ]

        for invalid_cfp in invalid_formats:
            sample_conference["cfp"] = invalid_cfp
            with pytest.raises(ValidationError):
                Conference(**sample_conference)

    def test_url_validation(self, sample_conference):
        """Test URL field validation."""
        # Valid URLs
        valid_urls = ["https://example.com", "http://test.org", "https://sub.domain.com/path"]

        for url in valid_urls:
            sample_conference["link"] = url
            conf = Conference(**sample_conference)
            assert str(conf.link) == url

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
        valid_subs = ["PY", "SCIPY", "DATA", "WEB", "BIZ", "GEO", "CAMP", "DAY"]

        for sub in valid_subs:
            sample_conference["sub"] = sub
            conf = Conference(**sample_conference)
            assert conf.sub == sub

    def test_optional_fields(self, sample_conference):
        """Test optional field handling."""
        optional_fields = {
            "alt_name": "Alternative Conference Name",
            "cfp_link": "https://cfp.example.com",
            "cfp_ext": "2025-03-01 23:59:00",
            "workshop_deadline": "2025-02-01 23:59:00",
            "tutorial_deadline": "2025-02-10 23:59:00",
            "sponsor": "https://sponsor.example.com",
            "finaid": "https://finaid.example.com",
            "twitter": "testconf",
            "mastodon": "https://mastodon.social/@testconf",
            "bluesky": "testconf.bsky.social",
            "note": "Special conference notes",
            "extra_places": ["Online", "Hybrid"],
        }

        for field, value in optional_fields.items():
            test_data = sample_conference.copy()
            test_data[field] = value
            conf = Conference(**test_data)
            assert getattr(conf, field) == value


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
        # Valid coordinates
        valid_coords = [
            (90.0, 180.0),  # Max bounds
            (-90.0, -180.0),  # Min bounds
            (0.0, 0.0),  # Origin
            (45.5, -122.6),  # Normal coordinates
        ]

        for lat, lon in valid_coords:
            location = Location(title="Test", latitude=lat, longitude=lon)
            assert location.latitude == lat
            assert location.longitude == lon

        # Invalid coordinates
        invalid_coords = [
            (91.0, 0.0),  # Latitude too high
            (-91.0, 0.0),  # Latitude too low
            (0.0, 181.0),  # Longitude too high
            (0.0, -181.0),  # Longitude too low
        ]

        for lat, lon in invalid_coords:
            with pytest.raises(ValidationError):
                Location(title="Test", latitude=lat, longitude=lon)

    def test_coordinate_precision(self):
        """Test coordinate precision validation."""
        # Test high precision coordinates (should be rounded to 5 decimal places)
        location = Location(title="High Precision Test", latitude=40.712812345678, longitude=-74.006012345678)

        # Should accept the coordinates even with high precision
        assert location.latitude == 40.712812345678
        assert location.longitude == -74.006012345678
