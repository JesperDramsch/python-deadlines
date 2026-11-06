"""Tests for utils/wayback.py: CDX capture lists, the capture rule and saves."""

import sys
from datetime import date
from pathlib import Path

import pytest
import requests
import responses

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import wayback

# The captures CDX lists for https://pycon.or.tz/sponsor/, as fetched on 2026-11-03.
# PyCon Tanzania 2024 ran 3-4 December 2024; the 2026 edition's CfP was open in October 2026.
TANZANIA_SPONSOR = [
    "20211206210540",
    "20221018220431",
    "20231209151121",
    "20240923213321",
    "20240927025243",
    "20241004214743",
    "20250618114933",
    "20261018085052",
]


class TestPickCapture:
    """The capture for an edition is the last one on or before its end plus the grace days."""

    def test_tanzania_2024_gets_its_own_edition(self):
        """Not the 2026 capture, which shows the next edition, and not the in-between 2025 one."""
        assert wayback.pick_capture(TANZANIA_SPONSOR, date(2024, 12, 4)) == "20241004214743"

    def test_capture_within_grace_days_counts(self):
        assert wayback.pick_capture(["20240101000000", "20241215120000"], date(2024, 12, 4)) == "20241215120000"

    def test_capture_on_the_last_grace_day_counts(self):
        assert wayback.pick_capture(["20241218235959"], date(2024, 12, 4)) == "20241218235959"

    def test_capture_after_grace_days_does_not(self):
        assert wayback.pick_capture(["20241219000000"], date(2024, 12, 4)) is None

    def test_no_captures(self):
        assert wayback.pick_capture([], date(2024, 12, 4)) is None

    def test_order_does_not_matter(self):
        assert wayback.pick_capture(list(reversed(TANZANIA_SPONSOR)), date(2024, 12, 4)) == "20241004214743"

    def test_grace_days_can_be_changed(self):
        assert wayback.pick_capture(["20241215120000"], date(2024, 12, 4), grace_days=0) is None


class TestCaptures:
    """captures() lists successful captures, and tells a failed lookup from an empty one."""

    @responses.activate
    def test_lists_timestamps_oldest_first(self):
        responses.add(
            responses.GET,
            wayback.CDX_URL,
            json=[["timestamp", "statuscode"], ["20241004214743", "200"], ["20211206210540", "200"]],
        )

        assert wayback.captures("https://pycon.or.tz/sponsor/") == ["20211206210540", "20241004214743"]

    @responses.activate
    def test_asks_for_successful_captures_of_the_url(self):
        responses.add(responses.GET, wayback.CDX_URL, json=[["timestamp", "statuscode"]])

        wayback.captures("https://pycon.or.tz/sponsor/")

        params = responses.calls[0].request.params
        assert params["url"] == "https://pycon.or.tz/sponsor/"
        assert params["filter"] == "statuscode:200"
        assert params["output"] == "json"

    @responses.activate
    def test_empty_answer_means_no_captures(self):
        responses.add(responses.GET, wayback.CDX_URL, body="")

        assert wayback.captures("https://example.org/") == []

    @responses.activate
    def test_header_only_means_no_captures(self):
        responses.add(responses.GET, wayback.CDX_URL, json=[["timestamp", "statuscode"]])

        assert wayback.captures("https://example.org/") == []

    @responses.activate
    def test_rows_without_a_timestamp_are_skipped(self):
        responses.add(
            responses.GET,
            wayback.CDX_URL,
            json=[["timestamp", "statuscode"], ["2024", "200"], [], ["20241004214743", "200"]],
        )

        assert wayback.captures("https://example.org/") == ["20241004214743"]

    @responses.activate
    def test_error_status_raises(self):
        responses.add(responses.GET, wayback.CDX_URL, status=503)

        with pytest.raises(wayback.WaybackError, match="HTTP 503"):
            wayback.captures("https://example.org/")

    @responses.activate
    def test_connection_error_raises(self):
        responses.add(responses.GET, wayback.CDX_URL, body=requests.ConnectionError("reset"))

        with pytest.raises(wayback.WaybackError, match="failed"):
            wayback.captures("https://example.org/")

    @responses.activate
    def test_answer_that_is_not_json_raises(self):
        responses.add(responses.GET, wayback.CDX_URL, body="<html>busy</html>")

        with pytest.raises(wayback.WaybackError, match="not JSON"):
            wayback.captures("https://example.org/")

    @responses.activate
    def test_answer_that_is_not_a_listing_raises(self):
        responses.add(responses.GET, wayback.CDX_URL, json={"error": "busy"})

        with pytest.raises(wayback.WaybackError, match="not a listing"):
            wayback.captures("https://example.org/")


class TestSave:
    """save() reports whether the archive accepted the request."""

    @responses.activate
    def test_accepted(self):
        responses.add(responses.GET, wayback.SAVE_URL + "https://pycon.tz/", status=200)

        result = wayback.save("https://pycon.tz/")

        assert result == wayback.SaveResult("https://pycon.tz/", ok=True, detail="HTTP 200")
        assert responses.calls[0].request.headers["User-Agent"] == wayback.USER_AGENT

    @responses.activate
    def test_refused(self):
        responses.add(responses.GET, wayback.SAVE_URL + "https://pycon.tz/", status=429)

        result = wayback.save("https://pycon.tz/")

        assert not result.ok
        assert result.detail == "HTTP 429"

    @responses.activate
    def test_connection_error(self):
        responses.add(responses.GET, wayback.SAVE_URL + "https://pycon.tz/", body=requests.ConnectionError("reset"))

        result = wayback.save("https://pycon.tz/")

        assert not result.ok
        assert result.detail.startswith("error:")


class TestLinks:
    """Archive links: recognised, and built from a full capture timestamp."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/",
            "http://web.archive.org/web/2018/https://pycon.se/",
            "https://WEB.ARCHIVE.ORG/web/20180412093011/https://pycon.se/",
        ],
    )
    def test_is_archived(self, url):
        assert wayback.is_archived(url)

    @pytest.mark.parametrize(
        "url",
        ["https://pycon.or.tz/sponsor/", "https://web.archive.org/", "https://archive.org/details/x", ""],
    )
    def test_is_not_archived(self, url):
        assert not wayback.is_archived(url)

    def test_archive_url(self):
        assert (
            wayback.archive_url("20241004214743", "https://pycon.or.tz/sponsor/")
            == "https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/"
        )

    @pytest.mark.parametrize("timestamp", ["20241203", "", "2024100421474x"])
    def test_archive_url_needs_a_capture_timestamp(self, timestamp):
        with pytest.raises(ValueError, match="14-digit"):
            wayback.archive_url(timestamp, "https://pycon.or.tz/")
