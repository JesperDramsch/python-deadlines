"""Tests for archived_watches: pausing the watches on links the data replaced with an archived copy."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from archived_watches import archived_original
from archived_watches import live_links
from archived_watches import normalise_url
from archived_watches import replaced_links
from archived_watches import watches_to_pause

TODAY = date(2026, 10, 28)
ARCHIVED = "https://web.archive.org/web/20250601000000/https://pycon.org.so/"
WATCHES = {
    "hijacked": {"url": "https://pycon.org.so"},
    "series": {"url": "https://us.pycon.org/{% now 'utc' + 'months=9', '%Y' %}/"},
    "dead-this-year": {"url": "https://{% now 'utc' + 'months=3', '%Y' %}.pycon.ie/"},
    "alive": {"url": "https://euroscipy.org/"},
    "paused": {"url": "https://pycon.org.so/", "paused": True},
}


class TestArchivedOriginal:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (ARCHIVED, "https://pycon.org.so/"),
            ("https://web.archive.org/web/20250601000000id_/https://x.org/cfp", "https://x.org/cfp"),
            ("https://pycon.org.so/", None),
            ("https://web.archive.org/", None),
            (None, None),
        ],
    )
    def test_reads_the_archived_url(self, url, expected):
        assert archived_original(url) == expected


def test_normalise_url_ignores_scheme_www_case_and_trailing_slash():
    assert normalise_url("http://www.PyCon.org.so/") == normalise_url("https://pycon.org.so") == "pycon.org.so"


class TestReplacedLinks:
    def test_finds_a_link_swapped_for_its_archived_copy(self):
        before = [{"conference": "PyCon Somalia", "year": 2025, "link": "https://pycon.org.so/"}]
        after = [{"conference": "PyCon Somalia", "year": 2025, "link": ARCHIVED}]
        assert replaced_links(before, after) == [("PyCon Somalia", 2025, "https://pycon.org.so/")]

    def test_cfp_link_counts_too(self):
        before = [{"conference": "A", "year": 2024, "cfp_link": "https://a.org/cfp"}]
        after = [{"conference": "A", "year": 2024, "cfp_link": "https://web.archive.org/web/2024/https://a.org/cfp"}]
        assert replaced_links(before, after) == [("A", 2024, "https://a.org/cfp")]

    def test_ignores_a_move_to_another_live_site_and_a_new_entry(self):
        before = [{"conference": "A", "year": 2024, "link": "https://a.org/"}]
        after = [
            {"conference": "A", "year": 2024, "link": "https://a.com/"},
            {"conference": "B", "year": 2024, "link": "https://web.archive.org/web/2024/https://b.org/"},
        ]
        assert replaced_links(before, after) == []

    def test_ignores_an_archive_of_another_page(self):
        before = [{"conference": "A", "year": 2024, "link": "https://a.org/"}]
        after = [{"conference": "A", "year": 2024, "link": "https://web.archive.org/web/2024/https://evil.example/"}]
        assert replaced_links(before, after) == []

    def test_ignores_one_archived_copy_replacing_another(self):
        before = [{"conference": "A", "year": 2024, "link": "https://web.archive.org/web/2023/https://a.org/"}]
        after = [{"conference": "A", "year": 2024, "link": "https://web.archive.org/web/2024/https://a.org/"}]
        assert replaced_links(before, after) == []


def test_live_links_leave_out_archived_copies():
    entries = [
        {"link": "https://www.EuroSciPy.org/", "cfp_link": ARCHIVED},
        {"link": None},
    ]
    assert live_links(entries) == {"euroscipy.org"}


class TestWatchesToPause:
    def test_pauses_the_watch_on_a_dead_link(self):
        assert watches_to_pause(WATCHES, ["https://pycon.org.so/"], set(), TODAY) == ["hijacked"]

    def test_a_template_is_compared_by_the_page_it_fetches_today(self):
        # Today the template gives 2027.pycon.ie, so archiving that page pauses the watch
        assert watches_to_pause(WATCHES, ["https://2027.pycon.ie/"], set(), TODAY) == ["dead-this-year"]

    def test_an_old_editions_archive_leaves_the_series_watch_on(self):
        # us.pycon.org/2015/ was archived long ago; the watch fetches 2027 now
        assert watches_to_pause(WATCHES, ["https://us.pycon.org/2015/"], set(), TODAY) == []

    def test_a_link_still_live_elsewhere_keeps_its_watch(self):
        # An old edition's link was archived, but the series still uses the homepage
        assert watches_to_pause(WATCHES, ["https://euroscipy.org/"], {"euroscipy.org"}, TODAY) == []

    def test_a_paused_watch_is_left_alone(self):
        watches = {"paused": WATCHES["paused"]}
        assert watches_to_pause(watches, ["https://pycon.org.so/"], set(), TODAY) == []

    def test_nothing_dead(self):
        assert watches_to_pause(WATCHES, [], set(), TODAY) == []
