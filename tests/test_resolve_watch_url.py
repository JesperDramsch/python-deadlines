"""Tests for resolve_watch_url: the year templates of a changedetection watch URL."""

import sys
from datetime import date
from pathlib import Path

import pytest
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import resolve_watch_url

TODAY = date(2026, 10, 28)


class TestResolveWatchUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://{% now 'utc', '%Y' %}.pycon.ie/", "https://2026.pycon.ie/"),
            ("https://{% now 'utc' + 'months=2', '%Y' %}.pycon.ie/", "https://2026.pycon.ie/"),
            ("https://{% now 'utc' + 'months=3', '%Y' %}.pycon.ie/", "https://2027.pycon.ie/"),
            ("https://{% now 'utc' + 'months=13', '%Y' %}.fosdem.org/", "https://2027.fosdem.org/"),
            ("https://{% now 'utc' + 'months=15', '%Y' %}.fosdem.org/", "https://2028.fosdem.org/"),
            ("https://x.org/{% now 'utc' + 'years=1', '%Y' %}.csv", "https://x.org/2027.csv"),
            ("https://x.org/nbpy-{% now 'utc' + 'months=10', '%y' %}/cfp", "https://x.org/nbpy-27/cfp"),
            ("https://x.org/{% now 'utc' + 'days=64', '%Y' %}/", "https://x.org/2026/"),
            ("https://x.org/{% now 'utc' + 'days=65', '%Y' %}/", "https://x.org/2027/"),
            ("https://www.scipy{% now 'utc' + 'months=7', '%Y' %}.scipy.org/", "https://www.scipy2027.scipy.org/"),
        ],
    )
    def test_fills_in_the_year(self, url, expected):
        assert resolve_watch_url(url, TODAY) == expected

    def test_every_template_in_a_url(self):
        url = "https://{% now 'utc', '%Y' %}.x.org/{% now 'utc' + 'years=1', '%Y' %}/"
        assert resolve_watch_url(url, TODAY) == "https://2026.x.org/2027/"

    def test_a_plain_url_stays(self):
        assert resolve_watch_url("https://pycon.org/2026/", TODAY) == "https://pycon.org/2026/"

    def test_another_template_shape_stays(self):
        url = "https://x.org/{% now 'local', '%Y' %}/"
        assert resolve_watch_url(url, TODAY) == url

    @freeze_time("2026-12-31 23:30:00")
    def test_defaults_to_today_in_utc(self):
        assert resolve_watch_url("https://{% now 'utc' + 'days=1', '%Y' %}.x.org") == "https://2027.x.org"
