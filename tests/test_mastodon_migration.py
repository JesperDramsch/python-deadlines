"""Tests for Mastodon account migration detection functionality."""

import sys
from pathlib import Path
from unittest.mock import patch

import responses

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf import links


class TestParseMastodonUrl:
    """Test Mastodon URL parsing."""

    def test_parse_standard_url(self):
        """Test parsing a standard Mastodon URL."""
        url = "https://fosstodon.org/@pycon"
        result = links.parse_mastodon_url(url)
        assert result == ("fosstodon.org", "pycon")

    def test_parse_url_without_at_prefix(self):
        """Test parsing URL with path starting with @."""
        url = "https://mastodon.social/@SciPyConf"
        result = links.parse_mastodon_url(url)
        assert result == ("mastodon.social", "SciPyConf")

    def test_parse_url_with_trailing_slash(self):
        """Test that trailing slashes cause parse failure (not standard format)."""
        url = "https://fosstodon.org/@pycon/"
        result = links.parse_mastodon_url(url)
        # Trailing slash doesn't match the pattern
        assert result is None

    def test_parse_invalid_url_no_username(self):
        """Test parsing URL without username."""
        url = "https://fosstodon.org/"
        result = links.parse_mastodon_url(url)
        assert result is None

    def test_parse_invalid_url_no_at_symbol(self):
        """Test parsing URL without @ symbol."""
        url = "https://fosstodon.org/pycon"
        result = links.parse_mastodon_url(url)
        assert result is None

    def test_parse_empty_url(self):
        """Test parsing empty URL."""
        result = links.parse_mastodon_url("")
        assert result is None

    def test_parse_invalid_url(self):
        """Test parsing malformed URL."""
        result = links.parse_mastodon_url("not-a-url")
        assert result is None


class TestCheckMastodonMigration:
    """Test Mastodon migration checking with mocked HTTP responses."""

    @responses.activate
    def test_no_migration(self):
        """Test account with no migration."""
        url = "https://fosstodon.org/@pycon"
        api_url = "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon"

        responses.add(
            responses.GET,
            api_url,
            json={
                "id": "123",
                "username": "pycon",
                "acct": "pycon",
                "url": "https://fosstodon.org/@pycon",
            },
            status=200,
        )

        result = links.check_mastodon_migration(url)
        assert result is None

    @responses.activate
    def test_single_migration(self):
        """Test account that has migrated once."""
        original_url = "https://old-instance.social/@pycon"
        new_url = "https://new-instance.social/@pycon"

        # First API call - account has moved
        responses.add(
            responses.GET,
            "https://old-instance.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "123",
                "username": "pycon",
                "acct": "pycon",
                "url": original_url,
                "moved": {
                    "id": "456",
                    "username": "pycon",
                    "acct": "pycon@new-instance.social",
                    "url": new_url,
                },
            },
            status=200,
        )

        # Second API call - verify new account exists and hasn't moved
        responses.add(
            responses.GET,
            "https://new-instance.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "456",
                "username": "pycon",
                "acct": "pycon",
                "url": new_url,
            },
            status=200,
        )

        with patch("tidy_conf.links.time.sleep"):  # Skip rate limit delay in tests
            result = links.check_mastodon_migration(original_url)

        assert result == new_url

    @responses.activate
    def test_chain_migration(self):
        """Test account that has migrated multiple times (A→B→C)."""
        url_a = "https://instance-a.social/@pycon"
        url_b = "https://instance-b.social/@pycon"
        url_c = "https://instance-c.social/@pycon"

        # First API call - A moved to B
        responses.add(
            responses.GET,
            "https://instance-a.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "1",
                "username": "pycon",
                "url": url_a,
                "moved": {"id": "2", "username": "pycon", "url": url_b},
            },
            status=200,
        )

        # Second API call - B moved to C
        responses.add(
            responses.GET,
            "https://instance-b.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "2",
                "username": "pycon",
                "url": url_b,
                "moved": {"id": "3", "username": "pycon", "url": url_c},
            },
            status=200,
        )

        # Third API call - C is the final destination
        responses.add(
            responses.GET,
            "https://instance-c.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "3",
                "username": "pycon",
                "url": url_c,
            },
            status=200,
        )

        with patch("tidy_conf.links.time.sleep"):
            result = links.check_mastodon_migration(url_a)

        assert result == url_c

    @responses.activate
    def test_circular_migration_detection(self):
        """Test detection of circular migration (A→B→A)."""
        url_a = "https://instance-a.social/@pycon"
        url_b = "https://instance-b.social/@pycon"

        # First API call - A moved to B
        responses.add(
            responses.GET,
            "https://instance-a.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "1",
                "username": "pycon",
                "url": url_a,
                "moved": {"id": "2", "username": "pycon", "url": url_b},
            },
            status=200,
        )

        # Second API call - B moved back to A (circular)
        responses.add(
            responses.GET,
            "https://instance-b.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "2",
                "username": "pycon",
                "url": url_b,
                "moved": {"id": "1", "username": "pycon", "url": url_a},
            },
            status=200,
        )

        with patch("tidy_conf.links.time.sleep"), patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url_a)

        # Should return B (last valid before cycle detected)
        assert result == url_b

    @responses.activate
    def test_max_depth_limit(self):
        """Test that max depth limit prevents infinite loops."""
        # Create a chain of 10 migrations
        base_url = "https://instance-{}.social/@pycon"

        for i in range(10):
            current_url = base_url.format(i)
            next_url = base_url.format(i + 1)
            responses.add(
                responses.GET,
                f"https://instance-{i}.social/api/v1/accounts/lookup?acct=pycon",
                json={
                    "id": str(i),
                    "username": "pycon",
                    "url": current_url,
                    "moved": {"id": str(i + 1), "username": "pycon", "url": next_url},
                },
                status=200,
            )

        with patch("tidy_conf.links.time.sleep"):
            # With max_depth=5 (default), should stop after 5 hops
            result = links.check_mastodon_migration(base_url.format(0), max_depth=5)

        # Should return the URL at depth 5
        assert result == base_url.format(5)

    @responses.activate
    def test_account_not_found_404(self):
        """Test handling of 404 (account not found)."""
        url = "https://fosstodon.org/@deleted_account"

        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=deleted_account",
            status=404,
        )

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url)

        assert result is None

    @responses.activate
    def test_rate_limited_429(self):
        """Test handling of rate limiting."""
        url = "https://fosstodon.org/@pycon"

        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon",
            status=429,
        )

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url)

        assert result is None

    @responses.activate
    def test_server_error_500(self):
        """Test handling of server errors."""
        url = "https://fosstodon.org/@pycon"

        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon",
            status=500,
        )

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url)

        assert result is None

    @responses.activate
    def test_connection_error(self):
        """Test handling of connection errors."""
        import requests as req

        url = "https://offline-instance.social/@pycon"

        responses.add(
            responses.GET,
            "https://offline-instance.social/api/v1/accounts/lookup?acct=pycon",
            body=req.exceptions.ConnectionError("Connection refused"),
        )

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url)

        assert result is None

    def test_invalid_url_format(self):
        """Test handling of invalid Mastodon URL format."""
        url = "https://not-a-mastodon-url.com/user/pycon"

        with patch("tidy_conf.links.tqdm.write"):
            result = links.check_mastodon_migration(url)

        assert result is None

    @responses.activate
    def test_moved_field_empty(self):
        """Test handling of empty moved field."""
        url = "https://fosstodon.org/@pycon"

        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "123",
                "username": "pycon",
                "url": url,
                "moved": None,
            },
            status=200,
        )

        result = links.check_mastodon_migration(url)
        assert result is None

    @responses.activate
    def test_moved_field_missing_url(self):
        """Test handling of moved field without URL."""
        url = "https://fosstodon.org/@pycon"

        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "123",
                "username": "pycon",
                "url": url,
                "moved": {"id": "456", "username": "pycon"},  # No URL field
            },
            status=200,
        )

        result = links.check_mastodon_migration(url)
        assert result is None


class TestCheckMastodonMigrationIntegration:
    """Integration tests for Mastodon migration in check_links."""

    @responses.activate
    def test_check_links_updates_mastodon(self):
        """Test that check_links updates migrated Mastodon accounts."""
        from sort_yaml import check_links

        old_url = "https://old-instance.social/@pycon"
        new_url = "https://new-instance.social/@pycon"

        # Mock the link availability check
        responses.add(
            responses.GET,
            "https://example.com/",
            status=200,
        )

        # Mock Mastodon migration
        responses.add(
            responses.GET,
            "https://old-instance.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "123",
                "username": "pycon",
                "url": old_url,
                "moved": {"id": "456", "username": "pycon", "url": new_url},
            },
            status=200,
        )

        responses.add(
            responses.GET,
            "https://new-instance.social/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "456",
                "username": "pycon",
                "url": new_url,
            },
            status=200,
        )

        data = [
            {
                "conference": "Test Conf",
                "year": 2025,
                "link": "https://example.com",
                "mastodon": old_url,
                "start": "2025-06-01",
            },
        ]

        with patch("tidy_conf.links.time.sleep"), patch("sort_yaml.get_cache") as mock_cache:
            mock_cache.return_value = (set(), set())
            result = check_links(data)

        assert result[0]["mastodon"] == new_url

    @responses.activate
    def test_check_links_preserves_non_migrated(self):
        """Test that check_links preserves non-migrated Mastodon accounts."""
        from sort_yaml import check_links

        url = "https://fosstodon.org/@pycon"

        # Mock the link availability check
        responses.add(
            responses.GET,
            "https://example.com/",
            status=200,
        )

        # Mock Mastodon - no migration
        responses.add(
            responses.GET,
            "https://fosstodon.org/api/v1/accounts/lookup?acct=pycon",
            json={
                "id": "123",
                "username": "pycon",
                "url": url,
            },
            status=200,
        )

        data = [
            {
                "conference": "Test Conf",
                "year": 2025,
                "link": "https://example.com",
                "mastodon": url,
                "start": "2025-06-01",
            },
        ]

        with patch("sort_yaml.get_cache") as mock_cache:
            mock_cache.return_value = (set(), set())
            result = check_links(data)

        assert result[0]["mastodon"] == url
