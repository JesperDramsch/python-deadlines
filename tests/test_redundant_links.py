"""Tests for dropping sub-page link fields that just repeat the homepage.

Upstream sources sometimes fill every URL column with the conference
homepage (e.g. python-organizers' Proposal URL). A cfp_link/sponsor/finaid
identical to the main link carries no information and must be dropped
during sanitation - but a different path, subdomain, query, or #anchor is a
different pointer and must survive.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.links import drop_redundant_link_fields
from tidy_conf.links import normalize_url_pointer


class TestNormalizeUrlPointer:
    """Test URL normalization for same-pointer comparison."""

    def test_scheme_ignored(self):
        assert normalize_url_pointer("http://pycon.de/") == normalize_url_pointer("https://pycon.de/")

    def test_www_prefix_ignored(self):
        assert normalize_url_pointer("https://www.pycon.de/") == normalize_url_pointer("https://pycon.de/")

    def test_trailing_slash_ignored(self):
        assert normalize_url_pointer("https://2027.pycon.de/") == normalize_url_pointer("https://2027.pycon.de")

    def test_fragment_is_different_pointer(self):
        assert normalize_url_pointer("http://pycon.sg/#sponsors") != normalize_url_pointer("http://pycon.sg/")

    def test_path_is_different_pointer(self):
        assert normalize_url_pointer("https://pycon.de/sponsoring/") != normalize_url_pointer("https://pycon.de/")

    def test_subdomain_is_different_pointer(self):
        assert normalize_url_pointer("https://cfp.pycon.de/") != normalize_url_pointer("https://pycon.de/")

    def test_query_is_different_pointer(self):
        assert normalize_url_pointer("https://pycon.de/?page=cfp") != normalize_url_pointer("https://pycon.de/")


class TestDropRedundantLinkFields:
    """Test removal of sub-page links identical to the main link."""

    def test_cfp_link_same_as_link_dropped(self):
        """Reproduces the PyCon DE 2027 case: cfp_link is just the homepage."""
        data = [
            {
                "conference": "PyCon DE & PyData",
                "year": 2027,
                "link": "https://2027.pycon.de/",
                "cfp_link": "https://2027.pycon.de/",
                "cfp": "TBA",
            },
        ]
        result = drop_redundant_link_fields(data)
        assert "cfp_link" not in result[0]
        assert result[0]["link"] == "https://2027.pycon.de/"

    def test_all_redundant_sub_fields_dropped(self):
        data = [
            {
                "conference": "Cheeky Conf",
                "year": 2026,
                "link": "https://cheeky.conf/",
                "cfp_link": "https://cheeky.conf",
                "sponsor": "http://www.cheeky.conf/",
                "finaid": "https://cheeky.conf/",
            },
        ]
        result = drop_redundant_link_fields(data)
        assert "cfp_link" not in result[0]
        assert "sponsor" not in result[0]
        assert "finaid" not in result[0]

    def test_anchor_on_homepage_kept(self):
        """A #anchor is a different pointer (e.g. PyCon SG's sponsor link)."""
        data = [
            {
                "conference": "PyCon Singapore",
                "year": 2026,
                "link": "http://pycon.sg/",
                "sponsor": "http://pycon.sg/index.html#sponsors",
            },
        ]
        result = drop_redundant_link_fields(data)
        assert result[0]["sponsor"] == "http://pycon.sg/index.html#sponsors"

    def test_sub_page_and_subdomain_kept(self):
        data = [
            {
                "conference": "PyCon Africa",
                "year": 2026,
                "link": "https://africa.pycon.org/",
                "cfp_link": "https://africa.pycon.org/2026/talks/proposals/",
                "sponsor": "https://africa.pycon.org/2026/sponsor-us/",
                "finaid": "https://africa.pycon.org/2026/opportunity-grants/",
            },
            {
                "conference": "Sub Conf",
                "year": 2026,
                "link": "https://sub.conf/",
                "cfp_link": "https://cfp.sub.conf/",
            },
        ]
        result = drop_redundant_link_fields(data)
        assert result[0]["cfp_link"] == "https://africa.pycon.org/2026/talks/proposals/"
        assert result[0]["sponsor"] == "https://africa.pycon.org/2026/sponsor-us/"
        assert result[0]["finaid"] == "https://africa.pycon.org/2026/opportunity-grants/"
        assert result[1]["cfp_link"] == "https://cfp.sub.conf/"

    def test_entry_without_link_untouched(self):
        data = [{"conference": "No Link Conf", "year": 2026, "cfp_link": "https://example.com/"}]
        result = drop_redundant_link_fields(data)
        assert result[0]["cfp_link"] == "https://example.com/"

    def test_entry_without_sub_fields_untouched(self):
        data = [{"conference": "Plain Conf", "year": 2026, "link": "https://plain.conf/"}]
        result = drop_redundant_link_fields(data)
        assert result[0] == {"conference": "Plain Conf", "year": 2026, "link": "https://plain.conf/"}
