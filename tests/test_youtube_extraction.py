"""Tests for YouTube link extraction and Mastodon/YouTube disambiguation."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from enrich_tba import extract_links_from_url


class TestYouTubeExtraction:
    """Test YouTube link detection in extract_links_from_url."""

    @patch("enrich_tba.get_all_links")
    def test_youtube_channel_detected(self, mock_links):
        """YouTube /@channel links are detected as youtube, not mastodon."""
        mock_links.return_value = [
            "https://www.youtube.com/@PyConUS",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert "youtube" in result
        assert result["youtube"] == "https://www.youtube.com/@PyConUS"
        assert "mastodon" not in result

    @patch("enrich_tba.get_all_links")
    def test_youtube_channel_url_without_at(self, mock_links):
        """YouTube channel links without @ are detected."""
        mock_links.return_value = [
            "https://www.youtube.com/channel/UCMjMBMGt0WP2usFilILnbcA",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert "youtube" in result
        assert "mastodon" not in result

    @patch("enrich_tba.get_all_links")
    def test_youtube_not_mistaken_for_mastodon(self, mock_links):
        """YouTube /@username must not end up in mastodon field."""
        mock_links.return_value = [
            "https://www.youtube.com/@EuroPython",
            "https://fosstodon.org/@europython",
        ]
        result = extract_links_from_url("https://europython.eu")
        assert result.get("youtube") == "https://www.youtube.com/@EuroPython"
        assert result.get("mastodon") == "https://fosstodon.org/@europython"

    @patch("enrich_tba.get_all_links")
    def test_youtu_be_short_link(self, mock_links):
        """Short youtu.be links are detected as youtube."""
        mock_links.return_value = [
            "https://youtu.be/abc123",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert "youtube" in result
        assert "mastodon" not in result

    @patch("enrich_tba.get_all_links")
    def test_mastodon_still_works(self, mock_links):
        """Mastodon links on known instances still detected correctly."""
        mock_links.return_value = [
            "https://fosstodon.org/@pycon",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert "mastodon" in result
        assert result["mastodon"] == "https://fosstodon.org/@pycon"
        assert "youtube" not in result

    @patch("enrich_tba.get_all_links")
    def test_generic_mastodon_still_works(self, mock_links):
        """Generic /@username on unknown instances still detected as mastodon."""
        mock_links.return_value = [
            "https://social.example.org/@pyconf",
        ]
        result = extract_links_from_url("https://pyconf.org")
        assert "mastodon" in result
        assert "youtube" not in result

    @patch("enrich_tba.get_all_links")
    def test_youtube_first_seen_wins(self, mock_links):
        """Only the first YouTube link is kept."""
        mock_links.return_value = [
            "https://www.youtube.com/@PyConUS",
            "https://www.youtube.com/@AnotherChannel",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert result["youtube"] == "https://www.youtube.com/@PyConUS"

    @patch("enrich_tba.get_all_links")
    def test_all_social_links_extracted(self, mock_links):
        """YouTube, Mastodon, and Bluesky can all be extracted together."""
        mock_links.return_value = [
            "https://bsky.app/profile/pycon.org",
            "https://www.youtube.com/@PyConUS",
            "https://fosstodon.org/@pycon",
        ]
        result = extract_links_from_url("https://pycon.org")
        assert "bluesky" in result
        assert "youtube" in result
        assert "mastodon" in result
