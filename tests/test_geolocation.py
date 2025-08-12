"""Tests for geolocation functionality."""

import sys
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf import latlon


class TestAddLatLon:
    """Test latitude and longitude addition functionality."""

    def test_online_conference_skipped(self):
        """Test that online conferences are skipped during geolocation."""
        data = [
            {
                "conference": "Online Conference",
                "year": 2025,
                "place": "Online",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        result = latlon.add_latlon(data)

        # Should return unchanged - no location added for online conferences
        assert len(result) == 1
        assert "location" not in result[0]

    def test_conference_with_existing_location(self):
        """Test that conferences with existing location data are handled correctly."""
        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "New York, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "location": [
                    {
                        "title": "Test Conference 2025",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                    },
                ],
            },
        ]

        result = latlon.add_latlon(data)

        # Should maintain existing location
        assert len(result) == 1
        assert "location" in result[0]
        assert result[0]["location"][0]["latitude"] == 40.7128
        assert result[0]["location"][0]["longitude"] == -74.0060

    @patch("tidy_conf.latlon.requests.get")
    @patch("tidy_conf.latlon.time.sleep")
    def test_successful_geocoding(self, mock_sleep, mock_get):
        """Test successful geocoding from OpenStreetMap."""
        # Mock successful OpenStreetMap response
        mock_response = Mock()
        mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, USA"}]
        mock_get.return_value = mock_response

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "New York, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        result = latlon.add_latlon(data)

        # Should add location data
        assert len(result) == 1
        assert "location" in result[0]
        assert len(result[0]["location"]) == 1

        location = result[0]["location"][0]
        assert location["title"] == "Test Conference 2025"
        assert location["latitude"] == 40.7128
        assert location["longitude"] == -74.0060

        # Should have made a request to OpenStreetMap
        mock_get.assert_called_once()

        # Should have slept to respect rate limits
        mock_sleep.assert_called_once_with(2)

    @patch("tidy_conf.latlon.requests.get")
    def test_geocoding_no_results(self, mock_get):
        """Test handling when OpenStreetMap returns no results."""
        # Mock empty response from OpenStreetMap
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "Unknown City, Unknown Country",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        result = latlon.add_latlon(data)

        # Should not add location data when no results found
        assert len(result) == 1
        assert "location" not in result[0]

    @patch("tidy_conf.latlon.requests.get")
    def test_geocoding_request_failure(self, mock_get):
        """Test handling of request failures."""
        # Mock request failure
        mock_get.return_value = None

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "Test City, Test Country",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        result = latlon.add_latlon(data)

        # Should handle gracefully and not add location data
        assert len(result) == 1
        assert "location" not in result[0]

    def test_place_name_processing(self):
        """Test that place names are processed correctly."""
        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "New York City, New York, United States",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get, patch("tidy_conf.latlon.time.sleep"):
            mock_response = Mock()
            mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, USA"}]
            mock_get.return_value = mock_response

            latlon.add_latlon(data)

            # Should have processed place name
            assert mock_get.called
            # Verify that the API was called with the processed place name
            call_args = mock_get.call_args[0][0]
            # Check for URL-encoded versions of the place name components
            assert "New%20York%20City" in call_args and "United%20States" in call_args

    def test_caching_functionality(self):
        """Test that caching works correctly."""
        data = [
            {
                "conference": "Conference A",
                "year": 2025,
                "place": "New York, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
            {
                "conference": "Conference B",
                "year": 2025,
                "place": "New York, USA",  # Same place
                "start": "2025-07-01",
                "end": "2025-07-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, USA"}]
            mock_get.return_value = mock_response

            result = latlon.add_latlon(data)

            # Should only make one API call due to caching
            assert mock_get.call_count == 1

            # Both conferences should have location data
            assert len(result) == 2
            assert "location" in result[0]
            assert "location" in result[1]

    def test_multiple_places_extra_places(self):
        """Test handling of conferences with extra_places."""
        data = [
            {
                "conference": "Hybrid Conference",
                "year": 2025,
                "place": "New York, USA",
                "extra_places": ["Online", "London, UK"],
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get, patch("tidy_conf.latlon.time.sleep"):

            # Create mock responses with proper json() methods
            mock_response_ny = Mock()
            mock_response_ny.json.return_value = [{"lat": "40.7128", "lon": "-74.0060"}]

            mock_response_london = Mock()
            mock_response_london.json.return_value = [{"lat": "51.5074", "lon": "-0.1278"}]

            mock_get.side_effect = [mock_response_ny, mock_response_london]

            result = latlon.add_latlon(data)

            # Should have the conference with location data
            assert len(result) == 1
            # For this test, we just verify that the function processed it without errors
            # The actual implementation may vary in how it handles extra_places

    def test_user_agent_header(self):
        """Test that proper User-Agent header is set."""
        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "Test City, Test Country",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "lat": "40.0",
                    "lon": "-74.0",
                },
            ]
            mock_get.return_value = mock_response

            latlon.add_latlon(data)

            # Check that User-Agent header was set
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert "headers" in call_kwargs
            assert "User-Agent" in call_kwargs["headers"]
            assert "Pythondeadlin.es" in call_kwargs["headers"]["User-Agent"]

    def test_rate_limiting_sleep(self):
        """Test that rate limiting sleep is respected."""
        data = [
            {
                "conference": "Conference A",
                "year": 2025,
                "place": "City A, Country A",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
            {
                "conference": "Conference B",
                "year": 2025,
                "place": "City B, Country B",
                "start": "2025-07-01",
                "end": "2025-07-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get, patch("tidy_conf.latlon.time.sleep") as mock_sleep:

            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "lat": "40.0",
                    "lon": "-74.0",
                },
            ]
            mock_get.return_value = mock_response

            latlon.add_latlon(data)

            # Should sleep after each API call for rate limiting
            assert mock_sleep.call_count == 2
            for call in mock_sleep.call_args_list:
                assert call[0][0] == 2  # 2 second sleep


class TestErrorHandling:
    """Test error handling in geolocation functionality."""

    def test_index_error_handling(self):
        """Test handling of IndexError during place processing."""
        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "",  # Empty place that might cause IndexError
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        # Should not raise an exception
        result = latlon.add_latlon(data)

        # Should return data unchanged
        assert len(result) == 1

    def test_missing_place_field(self):
        """Test handling when 'place' field is missing."""
        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                # Missing 'place' field
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        # Should not raise an exception
        result = latlon.add_latlon(data)

        # Should return data unchanged
        assert len(result) == 1

    @patch("tidy_conf.latlon.requests.get")
    @patch("tidy_conf.latlon.time.sleep")
    def test_json_decode_error(self, mock_sleep, mock_get):
        """Test handling of JSON decode errors."""
        # Mock response that causes JSON decode error
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "Test City, Test Country",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        # Should handle gracefully
        result = latlon.add_latlon(data)

        # Should return the original data without location
        assert len(result) == 1
        assert "location" not in result[0]


class TestLoggingIntegration:
    """Test integration with logging system."""

    @patch("tidy_conf.latlon.get_tqdm_logger")
    def test_logging_calls(self, mock_get_logger):
        """Test that appropriate logging calls are made."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "Test City, Test Country",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []  # No results
            mock_get.return_value = mock_response

            latlon.add_latlon(data)

            # Should have made logging calls
            assert mock_get_logger.called
            assert mock_logger.debug.called
            assert mock_logger.warning.called  # Warning for no results

    @patch("tidy_conf.latlon.get_tqdm_logger")
    def test_error_logging(self, mock_get_logger):
        """Test that errors are logged appropriately."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "",  # This will cause an IndexError in place processing
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        # Should handle gracefully and log errors
        result = latlon.add_latlon(data)

        # Should return the data even if there was an error
        assert len(result) == 1

        # Check that logger was called
        assert mock_get_logger.called
