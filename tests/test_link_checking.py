"""Tests for link checking functionality."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import requests
import responses

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf import links


class TestLinkCheckingWithResponses:
    """Test link checking using responses library for cleaner HTTP mocking."""

    @responses.activate
    def test_successful_link_check_clean(self):
        """Test successful link checking with responses library."""
        test_url = "https://example.com/"  # Include trailing slash for normalized URL
        responses.add(
            responses.GET,
            test_url,
            status=200,
            headers={"Content-Type": "text/html"},
        )

        test_start = date(2025, 6, 1)
        result = links.check_link_availability(test_url, test_start)

        # URL should be returned (possibly with trailing slash normalization)
        assert result.rstrip("/") == test_url.rstrip("/")
        assert len(responses.calls) == 1

    @responses.activate
    def test_redirect_handling_clean(self):
        """Test redirect handling with responses library."""
        original_url = "https://example.com"
        redirected_url = "https://example.com/new-page"

        responses.add(
            responses.GET,
            original_url,
            status=301,
            headers={"Location": redirected_url},
        )
        responses.add(
            responses.GET,
            redirected_url,
            status=200,
            headers={"Content-Type": "text/html"},
        )

        test_start = date(2025, 6, 1)

        # The actual behavior depends on how requests handles redirects
        # By default requests follows redirects, so we should get the final URL
        result = links.check_link_availability(original_url, test_start)

        # Result should be the redirected URL
        assert redirected_url in result or original_url in result

    @responses.activate
    def test_404_triggers_archive_lookup(self):
        """Test that 404 triggers archive.org lookup."""
        test_url = "https://example.com/missing"
        archive_api_url = "https://archive.org/wayback/available"

        # First request returns 404
        responses.add(
            responses.GET,
            test_url,
            status=404,
        )

        # Archive.org API response - no archive found
        responses.add(
            responses.GET,
            archive_api_url,
            json={"archived_snapshots": {}},
            status=200,
        )

        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.get_cache") as mock_cache, patch(
            "tidy_conf.links.get_cache_location",
        ) as mock_cache_location:
            mock_cache.return_value = (set(), set())
            mock_cache_file = Mock()
            mock_file_handle = Mock()
            mock_file_handle.__enter__ = Mock(return_value=mock_file_handle)
            mock_file_handle.__exit__ = Mock(return_value=None)
            mock_cache_file.open.return_value = mock_file_handle
            mock_cache_location.return_value = (mock_cache_file, Mock())

            result = links.check_link_availability(test_url, test_start)

        # Should return original URL when no archive is found
        assert result == test_url

    @responses.activate
    def test_archive_found_returns_archive_url(self):
        """Test that archive URL is returned when found."""
        test_url = "https://example.com/old-page"
        archive_url = "https://web.archive.org/web/20240101/https://example.com/old-page"
        archive_api_url = "https://archive.org/wayback/available"

        # First request returns 404
        responses.add(
            responses.GET,
            test_url,
            status=404,
        )

        # Archive.org API returns a valid snapshot
        responses.add(
            responses.GET,
            archive_api_url,
            json={
                "archived_snapshots": {
                    "closest": {
                        "available": True,
                        "url": archive_url,
                    },
                },
            },
            status=200,
        )

        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_link_availability(test_url, test_start)

        # Should return the archive URL
        assert result == archive_url

    @responses.activate
    def test_timeout_handling(self):
        """Test handling of timeout errors."""
        test_url = "https://slow-server.com"

        # Simulate timeout
        responses.add(
            responses.GET,
            test_url,
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        test_start = date(2025, 6, 1)

        # Should handle timeout gracefully
        result = links.check_link_availability(test_url, test_start)

        # Should return original URL on timeout
        assert result == test_url

    @responses.activate
    def test_ssl_error_handling(self):
        """Test handling of SSL certificate errors."""
        test_url = "https://invalid-cert.com"

        # Simulate SSL error
        responses.add(
            responses.GET,
            test_url,
            body=requests.exceptions.SSLError("SSL certificate verify failed"),
        )

        test_start = date(2025, 6, 1)

        result = links.check_link_availability(test_url, test_start)

        # Should return original URL on SSL error
        assert result == test_url

    @responses.activate
    def test_multiple_links_batch(self):
        """Test checking multiple links."""
        # Use trailing slashes for normalized URLs
        urls = [
            "https://pycon.us/",
            "https://djangocon.us/",
            "https://europython.eu/",
        ]

        for url in urls:
            responses.add(
                responses.GET,
                url,
                status=200,
            )

        test_start = date(2025, 6, 1)

        results = [links.check_link_availability(url, test_start) for url in urls]

        # All should succeed - compare without trailing slashes for flexibility
        assert len(results) == 3
        for url, result in zip(urls, results, strict=False):
            assert result.rstrip("/") == url.rstrip("/")

    @responses.activate
    def test_archive_org_url_passthrough(self):
        """Test that archive.org URLs are returned unchanged."""
        archive_url = "https://web.archive.org/web/20240101/https://example.com"

        test_start = date(2025, 6, 1)

        # Should not make any HTTP requests
        result = links.check_link_availability(archive_url, test_start)

        assert result == archive_url
        assert len(responses.calls) == 0  # No HTTP calls made


class TestLinkAvailability:
    """Test link availability checking functionality."""

    @patch("tidy_conf.links.requests.get")
    def test_successful_link_check(self, mock_get):
        """Test successful link checking."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        test_url = "https://example.com"
        test_start = date(2025, 6, 1)

        result = links.check_link_availability(test_url, test_start)

        assert result == test_url
        mock_get.assert_called_once()

    @patch("tidy_conf.links.requests.get")
    def test_link_redirect_same_domain(self, mock_get):
        """Test handling of redirects within the same domain."""
        # Mock response with redirect
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/redirected"
        mock_get.return_value = mock_response

        test_url = "https://example.com"
        test_start = date(2025, 6, 1)

        result = links.check_link_availability(test_url, test_start)

        # Should return the redirected URL
        assert result == "https://example.com/redirected"

    @patch("tidy_conf.links.requests.get")
    def test_link_check_with_query_string_warning(self, mock_get):
        """Test warning for redirects that add query strings."""
        # Mock response with query string redirect
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/page?session=123"
        mock_get.return_value = mock_response

        test_url = "https://example.com/page"
        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.tqdm.write"):  # Suppress tqdm output
            result = links.check_link_availability(test_url, test_start)

        # Should return original URL due to query string warning
        assert result == test_url

    @patch("tidy_conf.links.requests.get")
    def test_link_check_404_error(self, mock_get):
        """Test handling of 404 errors."""
        # Mock 404 response for original URL
        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.url = "https://example.com/not-found"  # Set URL for urlparse

        # Mock archive.org response (no archive found)
        mock_archive_response = Mock()
        mock_archive_response.status_code = 200
        mock_archive_response.json.return_value = {"archived_snapshots": {}}

        # Set up side effects: first call returns 404, second returns empty archive response
        mock_get.side_effect = [mock_404_response, mock_archive_response]

        test_url = "https://example.com/not-found"
        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.tqdm.write"), patch("tidy_conf.links.attempt_archive_url"), patch(
            "tidy_conf.links.get_cache",
        ) as mock_get_cache, patch("tidy_conf.links.get_cache_location") as mock_cache_location, patch(
            "builtins.open",
            create=True,
        ):

            # Mock cache returns empty sets
            mock_get_cache.return_value = (set(), set())
            # Mock cache file paths with proper context manager support
            mock_cache_file = Mock()
            mock_file_handle = Mock()
            mock_file_handle.__enter__ = Mock(return_value=mock_file_handle)
            mock_file_handle.__exit__ = Mock(return_value=None)
            mock_cache_file.open.return_value = mock_file_handle
            mock_cache_location.return_value = (mock_cache_file, Mock())

            result = links.check_link_availability(test_url, test_start)

            # Should return original URL when no archive is found
            assert result == test_url

    @patch("tidy_conf.links.requests.get")
    def test_archived_link_found(self, mock_get):
        """Test finding an archived version of a link."""
        # Mock 404 response for original link
        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.url = "https://example.com"  # Set URL for urlparse

        # Mock successful archive.org response
        mock_archive_response = Mock()
        mock_archive_response.status_code = 200
        mock_archive_response.json.return_value = {
            "archived_snapshots": {
                "closest": {"available": True, "url": "https://web.archive.org/web/20250101000000/https://example.com"},
            },
        }

        mock_get.side_effect = [mock_404_response, mock_archive_response]

        test_url = "https://example.com"
        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_link_availability(test_url, test_start)

        # Should return archived URL
        assert result == "https://web.archive.org/web/20250101000000/https://example.com"

    def test_already_archived_url(self):
        """Test that already archived URLs are returned as-is."""
        archived_url = "https://web.archive.org/web/20250101000000/https://example.com"
        test_start = date(2025, 6, 1)

        result = links.check_link_availability(archived_url, test_start)

        assert result == archived_url

    @patch("tidy_conf.links.requests.get")
    def test_connection_error_handling(self, mock_get):
        """Test handling of connection errors."""
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        test_url = "https://example.com"
        test_start = date(2025, 6, 1)

        with patch("tidy_conf.links.requests.get") as mock_archive_get:
            # Mock archive.org response failure
            mock_archive_get.side_effect = requests.exceptions.ConnectionError("Archive connection failed")

            result = links.check_link_availability(test_url, test_start)

            # Should return original URL when both checks fail
            assert result == test_url


class TestCaching:
    """Test caching functionality."""

    def test_get_cache_location(self):
        """Test cache location paths."""
        cache_file, cache_file_archived = links.get_cache_location()

        assert isinstance(cache_file, Path)
        assert isinstance(cache_file_archived, Path)
        assert cache_file.name == "no_archive.txt"
        assert cache_file_archived.name == "archived_links.txt"

    @patch("tidy_conf.links.Path.read_text")
    @patch("tidy_conf.links.Path.touch")
    def test_get_cache(self, mock_touch, mock_read_text):
        """Test cache loading."""
        mock_read_text.side_effect = ["https://example.com\n", "https://archived.com\n"]

        cache, cache_archived = links.get_cache()

        assert isinstance(cache, set)
        assert isinstance(cache_archived, set)
        assert "https://example.com" in cache
        assert "https://archived.com" in cache_archived

    @patch("tidy_conf.links.get_cache")
    def test_cached_link_no_archive(self, mock_get_cache):
        """Test behavior with cached link marked as no archive."""
        # Mock cache with the URL already marked as no archive
        mock_get_cache.return_value = ({"https://example.com"}, set())

        test_url = "https://example.com"
        test_start = date(2025, 6, 1)

        result = links.check_link_availability(test_url, test_start)

        # Should return original URL without making HTTP requests
        assert result == test_url


class TestArchiveAttempt:
    """Test archive attempt functionality."""

    @patch("tidy_conf.links.requests.get")
    def test_successful_archive_attempt(self, mock_get):
        """Test successful archive attempt."""
        # Mock successful archive response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        test_url = "https://example.com"

        with patch("tidy_conf.links.get_cache_location") as mock_cache_location, patch(
            "tidy_conf.links.get_cache",
        ) as mock_get_cache, patch("builtins.open", create=True) as mock_open:

            # Mock cache file paths with proper context manager support
            mock_cache_file = Mock()
            mock_cache_archived = Mock()
            mock_file_handle = Mock()
            mock_file_handle.__enter__ = Mock(return_value=mock_file_handle)
            mock_file_handle.__exit__ = Mock(return_value=None)
            mock_cache_archived.open.return_value = mock_file_handle
            mock_cache_location.return_value = (mock_cache_file, mock_cache_archived)
            # Mock cache returns empty sets
            mock_get_cache.return_value = (set(), set())

            # Mock file operations
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            links.attempt_archive_url(test_url)

            # Should make a request to web.archive.org/save/
            mock_get.assert_called_once()
            call_args = mock_get.call_args[0][0]
            assert "web.archive.org/save/" in call_args
            assert test_url in call_args

    @patch("tidy_conf.links.requests.get")
    def test_archive_attempt_failure(self, mock_get):
        """Test archive attempt failure."""
        # Mock failed archive response
        mock_get.side_effect = requests.exceptions.RequestException("Archive failed")

        test_url = "https://example.com"

        # Should not raise exception, just handle gracefully
        links.attempt_archive_url(test_url)

    @patch("tidy_conf.links.get_cache")
    def test_already_archived_url_skip(self, mock_get_cache):
        """Test skipping archive attempt for already archived URLs."""
        # Mock cache showing URL is already archived
        mock_get_cache.return_value = (set(), {"https://example.com"})

        test_url = "https://example.com"

        with patch("tidy_conf.links.requests.get") as mock_get:
            links.attempt_archive_url(test_url)

            # Should not make any HTTP requests
            mock_get.assert_not_called()


class TestDateLogic:
    """Test date-based logic in link checking."""

    @patch("tidy_conf.links.requests.get")
    def test_old_conference_archive_check(self, mock_get):
        """Test that old conferences get archived automatically."""
        # Mock archive.org response (no archive found for old conference)
        mock_archive_response = Mock()
        mock_archive_response.status_code = 200
        mock_archive_response.json.return_value = {"archived_snapshots": {}}
        mock_get.return_value = mock_archive_response

        # Very old date (more than 5 years ago)
        old_start = date(2019, 6, 1)
        test_url = "https://example.com"

        with patch("tidy_conf.links.attempt_archive_url") as mock_archive, patch(
            "tidy_conf.links.get_cache",
        ) as mock_get_cache, patch("tidy_conf.links.get_cache_location") as mock_cache_location, patch(
            "builtins.open",
            create=True,
        ):

            # Mock cache returns to avoid cache hits
            mock_get_cache.return_value = (set(), set())
            # Mock cache file paths with proper context manager support
            mock_cache_file = Mock()
            mock_file_handle = Mock()
            mock_file_handle.__enter__ = Mock(return_value=mock_file_handle)
            mock_file_handle.__exit__ = Mock(return_value=None)
            mock_cache_file.open.return_value = mock_file_handle
            mock_cache_location.return_value = (mock_cache_file, Mock())

            result = links.check_link_availability(test_url, old_start)

            # Should attempt to archive old conferences
            mock_archive.assert_called_once_with(test_url, set())
            assert result == test_url

    @patch("tidy_conf.links.requests.get")
    def test_recent_conference_no_archive(self, mock_get):
        """Test that recent conferences don't get auto-archived."""
        # Mock successful link response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        # Recent date
        recent_start = date(2025, 6, 1)
        test_url = "https://example.com"

        with patch("tidy_conf.links.attempt_archive_url") as mock_archive:
            result = links.check_link_availability(test_url, recent_start)

            # Should not attempt to archive recent conferences
            assert not mock_archive.called
            assert result == test_url
