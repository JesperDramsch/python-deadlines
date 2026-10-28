"""Tests for watch_templates: when a watch moves on to the next edition's page."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import resolve_watch_url
from watch_templates import retemplate
from watch_templates import rollover_day
from watch_templates import rollover_offset

PYCASCADES = {"year": 2027, "start": date(2027, 3, 20), "cfp": "2026-10-26 23:59:00", "cfp_ext": "2026-11-09 05:00:00"}


class TestRolloverDay:
    def test_two_weeks_after_the_extension(self):
        assert rollover_day(PYCASCADES) == date(2026, 11, 23)

    def test_the_original_deadline_without_an_extension(self):
        assert rollover_day({**PYCASCADES, "cfp_ext": None}) == date(2026, 11, 9)

    def test_never_after_the_start(self):
        entry = {"year": 2026, "start": date(2026, 6, 5), "cfp": "2026-05-30 23:59:00"}
        assert rollover_day(entry) == date(2026, 6, 5)

    @pytest.mark.parametrize("cfp", ["TBA", "None", "Cancelled", None])
    def test_the_start_without_a_deadline(self, cfp):
        assert rollover_day({"year": 2026, "start": "2026-10-02", "cfp": cfp}) == date(2026, 10, 2)

    def test_none_without_a_start(self):
        assert rollover_day({"year": 2026, "cfp": "2026-01-01 23:59:00"}) is None


class TestRolloverOffset:
    def test_pycascades(self):
        # Rollover 23 Nov 2026, so the template moves on on 1 Dec 2026
        assert rollover_offset(PYCASCADES) == 13

    @pytest.mark.parametrize(
        "entry",
        [
            PYCASCADES,
            {"year": 2026, "start": date(2026, 6, 5), "cfp": "2026-02-01 23:59:00"},
            {"year": 2026, "start": date(2026, 10, 2), "cfp": "TBA"},
            {"year": 2026, "start": date(2026, 12, 1), "cfp": "2026-11-17 23:59:00"},
            {"year": 2027, "start": date(2027, 1, 31), "cfp": "2026-11-01 23:59:00"},
        ],
    )
    def test_the_template_moves_on_at_the_first_month_start_on_or_after_the_rollover(self, entry):
        template = retemplate("https://{% now 'utc', '%Y' %}.x.org/", rollover_offset(entry))
        day = rollover_day(entry)
        switch = day if day.day == 1 else date(day.year + day.month // 12, day.month % 12 + 1, 1)
        before = date.fromordinal(switch.toordinal() - 1)
        assert resolve_watch_url(template, before) == f"https://{entry['year']}.x.org/"
        assert resolve_watch_url(template, switch) == f"https://{entry['year'] + 1}.x.org/"
        assert before < switch and day <= switch

    def test_none_without_year_or_start(self):
        assert rollover_offset({"start": date(2026, 1, 1)}) is None
        assert rollover_offset({"year": 2026}) is None


class TestRetemplate:
    def test_sets_the_months_offset_and_keeps_the_format(self):
        url = "https://x.org/nbpy-{% now 'utc' + 'months=10', '%y' %}/{% now 'utc', '%Y' %}"
        expected = "https://x.org/nbpy-{% now 'utc' + 'months=3', '%y' %}/{% now 'utc' + 'months=3', '%Y' %}"
        assert retemplate(url, 3) == expected

    def test_leaves_years_and_days_alone(self):
        url = "https://x.org/{% now 'utc' + 'years=1', '%Y' %}.csv"
        assert retemplate(url, 5) == url

    def test_plain_url_unchanged(self):
        assert retemplate("https://pycon.org/2026/", 4) == "https://pycon.org/2026/"
