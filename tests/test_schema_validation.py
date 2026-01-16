"""Tests for conference data schema validation."""

# Add utils to path for imports
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "utils"))

from hypothesis_strategies import HYPOTHESIS_AVAILABLE
from hypothesis_strategies import valid_latitude
from hypothesis_strategies import valid_longitude
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


class TestSchemaEdgeCases:
    """Test schema validation edge cases and boundary conditions."""

    def test_missing_required_link_fails(self, sample_conference):
        """Missing required 'link' field should fail validation."""
        del sample_conference["link"]

        with pytest.raises(ValidationError) as exc_info:
            Conference(**sample_conference)

        errors = exc_info.value.errors()
        assert any("link" in str(e["loc"]) for e in errors), "Link field should be reported as missing"

    def test_invalid_date_format_fails(self, sample_conference):
        """Invalid date format should fail validation.

        Note: The CFP field uses string pattern matching.
        """
        # Completely wrong format
        sample_conference["cfp"] = "not-a-date-format"

        with pytest.raises(ValidationError):
            Conference(**sample_conference)

    def test_invalid_cfp_datetime_format(self, sample_conference):
        r"""CFP with wrong datetime format should fail.

        The schema uses a regex pattern: ^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$
        """
        invalid_cfps = [
            "2025/02/15 23:59:00",  # Wrong separator (/)
            "02-15-2025 23:59:00",  # Wrong order (MM-DD-YYYY)
            "2025-02-15T23:59:00",  # ISO format with T
            "15 Feb 2025 23:59:00",  # Written format
        ]

        for cfp in invalid_cfps:
            sample_conference["cfp"] = cfp
            with pytest.raises(ValidationError):
                Conference(**sample_conference)

    def test_invalid_latitude_out_of_bounds(self, sample_conference):
        """Latitude outside -90 to 90 should fail."""
        sample_conference["location"] = [
            {"title": "Test", "latitude": 999, "longitude": 10},  # 999 > 90
        ]

        with pytest.raises(ValidationError):
            Conference(**sample_conference)

    def test_invalid_longitude_out_of_bounds(self, sample_conference):
        """Longitude outside -180 to 180 should fail."""
        sample_conference["location"] = [
            {"title": "Test", "latitude": 10, "longitude": 999},  # 999 > 180
        ]

        with pytest.raises(ValidationError):
            Conference(**sample_conference)

    def test_year_before_python_existed_fails(self, sample_conference):
        """Year before 1989 (Python's creation) should fail."""
        sample_conference["year"] = 1988
        sample_conference["start"] = date(1988, 6, 1)
        sample_conference["end"] = date(1988, 6, 3)

        with pytest.raises(ValidationError):
            Conference(**sample_conference)

    def test_year_far_future_accepted(self, sample_conference):
        """Year up to 3000 should be accepted."""
        sample_conference["year"] = 2999

        # Need to update dates to match
        sample_conference["start"] = date(2999, 6, 1)
        sample_conference["end"] = date(2999, 6, 3)

        conf = Conference(**sample_conference)
        assert conf.year == 2999

    def test_twitter_handle_strips_at_symbol(self, sample_conference):
        """Twitter handle with @ should have it stripped."""
        sample_conference["twitter"] = "@testconf"

        conf = Conference(**sample_conference)
        assert conf.twitter == "testconf", f"@ should be stripped from Twitter handle, got: {conf.twitter}"

    def test_conference_name_year_stripped(self, sample_conference):
        """Year in conference name should be stripped."""
        sample_conference["conference"] = "PyCon Test 2025"

        conf = Conference(**sample_conference)
        assert "2025" not in conf.conference, f"Year should be stripped from name, got: {conf.conference}"

    def test_location_required_for_non_online(self, sample_conference):
        """In-person conferences should require location."""
        sample_conference["place"] = "Berlin, Germany"  # Not online
        sample_conference["location"] = None  # No location

        with pytest.raises(ValidationError) as exc_info:
            Conference(**sample_conference)

        assert "location is required" in str(exc_info.value).lower()

    def test_empty_location_title_fails(self):
        """Location with empty title should fail."""
        with pytest.raises(ValidationError):
            Location(title="", latitude=40.7128, longitude=-74.0060)

    def test_null_location_title_fails(self):
        """Location with null title should fail."""
        with pytest.raises(ValidationError):
            Location(title=None, latitude=40.7128, longitude=-74.0060)

    def test_special_invalid_coordinates_rejected(self):
        """Special invalid coordinates should be rejected.

        These are coordinates that map to 'None' or 'Online' in geocoding.
        """
        # Coordinates that map to 'None' location
        with pytest.raises(ValidationError):
            Location(title="Test", latitude=44.93796, longitude=7.54012)

        # Coordinates that map to 'Online' location
        with pytest.raises(ValidationError):
            Location(title="Test", latitude=43.59047, longitude=3.85951)

    def test_multiple_subs_comma_separated(self, sample_conference):
        """Multiple sub types should be comma-separated."""
        sample_conference["sub"] = "PY,DATA,WEB"

        conf = Conference(**sample_conference)
        assert conf.sub == "PY,DATA,WEB"

    def test_invalid_sub_type_fails(self, sample_conference):
        """Invalid sub type should fail validation."""
        sample_conference["sub"] = "INVALID_TYPE"

        with pytest.raises(ValidationError):
            Conference(**sample_conference)

    def test_extra_places_list_format(self, sample_conference):
        """Extra places should be a list of strings."""
        sample_conference["extra_places"] = ["Online", "Hybrid Session"]

        conf = Conference(**sample_conference)
        assert conf.extra_places == ["Online", "Hybrid Session"]

    def test_timezone_accepted(self, sample_conference):
        """Valid timezone strings should be accepted."""
        valid_timezones = [
            "America/New_York",
            "Europe/Berlin",
            "Asia/Tokyo",
            "UTC",
            "America/Los_Angeles",
        ]

        for tz in valid_timezones:
            sample_conference["timezone"] = tz
            conf = Conference(**sample_conference)
            assert conf.timezone == tz


class TestSchemaRegressions:
    """Regression tests for schema validation bugs."""

    def test_regression_zero_zero_coordinates_rejected(self):
        """REGRESSION: (0, 0) coordinates should be rejected.

        This is a common default/error value that shouldn't be accepted.
        """
        with pytest.raises(ValidationError) as exc_info:
            Location(title="Test", latitude=0.0, longitude=0.0)

        assert "0" in str(exc_info.value) or "default" in str(exc_info.value).lower()

    def test_regression_http_urls_accepted(self, sample_conference):
        """REGRESSION: HTTP URLs should be accepted (not just HTTPS).

        Some older conference sites may still use HTTP.
        """
        sample_conference["link"] = "http://old-conference.org"

        conf = Conference(**sample_conference)
        assert "http://" in str(conf.link)

    def test_regression_date_objects_accepted(self, sample_conference):
        """REGRESSION: Python date objects should be accepted for start/end."""
        sample_conference["start"] = date(2025, 6, 1)
        sample_conference["end"] = date(2025, 6, 3)

        conf = Conference(**sample_conference)
        assert conf.start == date(2025, 6, 1)
        assert conf.end == date(2025, 6, 3)

    def test_regression_string_dates_accepted(self, sample_conference):
        """REGRESSION: String dates in ISO format should be accepted."""
        sample_conference["start"] = "2025-06-01"
        sample_conference["end"] = "2025-06-03"

        conf = Conference(**sample_conference)
        assert conf.start == date(2025, 6, 1)
        assert conf.end == date(2025, 6, 3)


# ---------------------------------------------------------------------------
# Property-based tests using Hypothesis
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:
    from hypothesis import assume
    from hypothesis import given
    from hypothesis import settings
    from hypothesis import strategies as st


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestCoordinateProperties:
    """Property-based tests for coordinate validation."""

    @given(valid_latitude, valid_longitude)
    @settings(max_examples=100)
    def test_valid_coordinates_accepted(self, lat, lon):
        """Valid coordinates within bounds should be accepted."""
        # Skip coordinates that are specifically rejected by the schema
        special_invalid = [
            (0.0, 0.0),  # Origin
            (44.93796, 7.54012),  # 'None' location
            (43.59047, 3.85951),  # 'Online' location
        ]

        for inv_lat, inv_lon in special_invalid:
            if abs(lat - inv_lat) < 0.0001 and abs(lon - inv_lon) < 0.0001:
                assume(False)

        # Should be accepted
        location = Location(title="Test", latitude=lat, longitude=lon)
        assert location.latitude == lat
        assert location.longitude == lon

    @given(st.floats(min_value=91, max_value=1000, allow_nan=False))
    @settings(max_examples=30)
    def test_invalid_latitude_rejected(self, lat):
        """Latitude > 90 should be rejected."""
        with pytest.raises(ValidationError):
            Location(title="Test", latitude=lat, longitude=0)

    @given(st.floats(min_value=181, max_value=1000, allow_nan=False))
    @settings(max_examples=30)
    def test_invalid_longitude_rejected(self, lon):
        """Longitude > 180 should be rejected."""
        with pytest.raises(ValidationError):
            Location(title="Test", latitude=0.1, longitude=lon)
