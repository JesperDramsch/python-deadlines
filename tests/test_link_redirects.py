"""Tests for redirects to a different site during link checking.

A conference link that now redirects to another site (a lapsed domain taken
over by a casino, a series that moved to a barcamp platform) must not be
treated as healthy, swapped for a Wayback copy or replaced by the target.
check_link_availability keeps the original URL and records the redirect for
a person to review. Redirects within the same site behave as before.
"""

import json
import sys
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import responses
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import sort_yaml
from tidy_conf import links

# Recent enough to be checked (younger than five years) but in the past, so a
# healthy link does not trigger a Wayback save request.
TODAY = datetime.now(tz=timezone.utc).date()
PAST_START = TODAY - timedelta(days=60)


@pytest.fixture(autouse=True)
def _clean_redirect_records(monkeypatch):
    """Start every test with no recorded redirects and no output file."""
    monkeypatch.delenv(links.REDIRECT_RECORDS_ENV, raising=False)
    links.REDIRECT_RECORDS.clear()
    yield
    links.REDIRECT_RECORDS.clear()


def _redirect(source: str, target: str, status: int = 200) -> None:
    responses.add(responses.GET, source, status=301, headers={"Location": target})
    responses.add(responses.GET, target, status=status)


def _check(url: str, start: date = PAST_START, **context) -> str:
    return links.check_link_availability(url, start, cache=set(), cache_archived=set(), **context)


class TestRegistrableDomain:
    """Registrable domain is the last two labels, or three under a two-level public suffix."""

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("pycon.de", "pycon.de"),
            ("2027.pycon.de", "pycon.de"),
            ("ug.pycon.org", "pycon.org"),
            ("pycon.org.au", "pycon.org.au"),
            ("2026.pycon.org.au", "pycon.org.au"),
            ("pyconuk.co.uk", "pyconuk.co.uk"),
            ("www.pydata.co.uk", "pydata.co.uk"),
            ("pycon.jp", "pycon.jp"),
        ],
    )
    def test_registrable_domain(self, host, expected):
        assert links.registrable_domain(host) == expected

    def test_required_two_level_suffixes_present(self):
        required = {
            "co.uk",
            "org.uk",
            "ac.uk",
            "gov.uk",
            "com.au",
            "org.au",
            "net.au",
            "com.br",
            "org.br",
            "co.jp",
            "or.jp",
            "ne.jp",
            "com.ar",
            "org.ar",
            "co.za",
            "org.za",
            "co.nz",
            "com.mx",
            "com.tr",
            "co.in",
            "com.cn",
            "com.sg",
        }
        assert required <= links.TWO_LEVEL_PUBLIC_SUFFIXES


class TestIsDifferentSite:
    """Hosts on different sites: different, not nested, different registrable domain."""

    @pytest.mark.parametrize(
        ("url", "other"),
        [
            ("https://pythoncamp.de/", "https://barcamps.eu/pythoncamp/"),
            ("https://pytennessee.org/", "https://infojudislotonline.com/"),
            ("https://example.co.uk/", "https://other.co.uk/"),
            ("https://pycon.org.au/", "https://pyconau.org.au/"),
        ],
    )
    def test_different_sites(self, url, other):
        assert links.is_different_site(url, other)

    @pytest.mark.parametrize(
        ("url", "other"),
        [
            ("https://2026.pycon.it/", "https://2026.pycon.it/en"),
            ("https://www.pycon.de/", "https://pycon.de/"),
            ("http://pycon.de/", "https://pycon.de:443/"),
            ("https://pycon.de/", "https://2027.pycon.de/"),
            ("https://2027.pycon.de/", "https://pycon.de/"),
            ("https://ug.pycon.org/", "https://africa.pycon.org/"),
            ("https://a.example.co.uk/", "https://b.example.co.uk/"),
            ("https://2026.pycon.org.au/", "https://pycon.org.au/"),
        ],
    )
    def test_same_site(self, url, other):
        assert not links.is_different_site(url, other)

    def test_missing_host_is_not_different(self):
        assert not links.is_different_site("https://pycon.de/", "not a url")


class TestCrossSiteRedirect:
    """A redirect to a different site keeps the original URL and is recorded."""

    @responses.activate
    def test_pythoncamp_to_barcamps_kept_and_recorded(self):
        url = "https://pythoncamp.de/"
        _redirect(url, "https://barcamps.eu/pythoncamp/")

        result = _check(url, conference="PythonCamp Germany", year=2026, field="link")

        assert result == url
        assert len(links.REDIRECT_RECORDS) == 1
        record = links.REDIRECT_RECORDS[0]
        assert record["source"] == "link-check"
        assert record["kind"] == "redirect"
        assert record["title"] == "PythonCamp Germany"
        assert record["url"] == url
        assert record["year"] == 2026
        assert record["payload"] == {
            "conference": "PythonCamp Germany",
            "year": 2026,
            "field": "link",
            "final_url": "https://barcamps.eu/pythoncamp/",
            "status": 200,
        }

    @responses.activate
    def test_pytennessee_to_casino_kept_and_recorded(self):
        url = "https://pytennessee.org/"
        _redirect(url, "https://infojudislotonline.com/")

        result = _check(url, conference="PyTennessee", year=2025, field="link")

        assert result == url
        assert [r["payload"]["final_url"] for r in links.REDIRECT_RECORDS] == ["https://infojudislotonline.com/"]

    @responses.activate
    def test_no_wayback_lookup_or_save(self):
        """Neither a future start (archive save) nor an error status (archive lookup) touches the Wayback Machine."""
        url = "https://pytennessee.org/"
        _redirect(url, "https://infojudislotonline.com/", status=404)

        result = _check(url, start=TODAY + timedelta(days=60), field="cfp_link")

        assert result == url
        assert [call.request.url for call in responses.calls] == [url, "https://infojudislotonline.com/"]
        assert links.REDIRECT_RECORDS[0]["payload"]["status"] == 404
        assert links.REDIRECT_RECORDS[0]["payload"]["field"] == "cfp_link"

    @responses.activate
    def test_without_context_uses_url_as_title(self):
        url = "https://pythoncamp.de/"
        _redirect(url, "https://barcamps.eu/pythoncamp/")

        assert _check(url) == url
        record = links.REDIRECT_RECORDS[0]
        assert record["title"] == url
        assert record["year"] is None
        assert record["payload"]["conference"] is None
        assert record["payload"]["field"] is None


class TestSameSiteRedirect:
    """Redirects within the same site keep today's behaviour and are not recorded."""

    @responses.activate
    def test_same_host_redirect_followed(self):
        _redirect("https://2026.pycon.it/", "https://2026.pycon.it/en")

        result = _check("https://2026.pycon.it/", conference="PyCon Italia", year=2026, field="link")

        assert result == "https://2026.pycon.it/en"
        assert links.REDIRECT_RECORDS == []

    @responses.activate
    def test_same_registrable_domain_kept_as_before(self):
        """ug.pycon.org to africa.pycon.org is a healthy link, as it was before."""
        _redirect("https://ug.pycon.org/", "https://africa.pycon.org/")

        result = _check("https://ug.pycon.org/", conference="PyCon Uganda", year=2026, field="link")

        assert result == "https://ug.pycon.org/"
        assert links.REDIRECT_RECORDS == []
        assert len(responses.calls) == 2


class TestRedirectQueueFile:
    """With DESK_QUEUE_OUT set, every record is appended to that file as one JSON line."""

    @freeze_time("2026-10-14 06:00:00")
    @responses.activate
    def test_json_lines_written(self, tmp_path, monkeypatch):
        out_file = tmp_path / "queue" / "link-check.jsonl"
        monkeypatch.setenv("DESK_QUEUE_OUT", str(out_file))
        _redirect("https://pythoncamp.de/", "https://barcamps.eu/pythoncamp/")
        _redirect("https://pytennessee.org/", "https://infojudislotonline.com/", status=403)

        _check("https://pythoncamp.de/", conference="PythonCamp Germany", year=2026, field="link")
        _check("https://pytennessee.org/", conference="PyTennessee", year=2025, field="sponsor")

        lines = out_file.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line) for line in lines] == [
            {
                "source": "link-check",
                "kind": "redirect",
                "received": "2026-10-14T06:00:00Z",
                "title": "PythonCamp Germany",
                "url": "https://pythoncamp.de/",
                "year": 2026,
                "payload": {
                    "conference": "PythonCamp Germany",
                    "year": 2026,
                    "field": "link",
                    "final_url": "https://barcamps.eu/pythoncamp/",
                    "status": 200,
                },
            },
            {
                "source": "link-check",
                "kind": "redirect",
                "received": "2026-10-14T06:00:00Z",
                "title": "PyTennessee",
                "url": "https://pytennessee.org/",
                "year": 2025,
                "payload": {
                    "conference": "PyTennessee",
                    "year": 2025,
                    "field": "sponsor",
                    "final_url": "https://infojudislotonline.com/",
                    "status": 403,
                },
            },
        ]
        assert [json.loads(line) for line in lines] == links.REDIRECT_RECORDS

    @responses.activate
    def test_existing_file_appended(self, tmp_path, monkeypatch):
        out_file = tmp_path / "redirects.jsonl"
        out_file.write_text('{"earlier": true}\n', encoding="utf-8")
        monkeypatch.setenv("DESK_QUEUE_OUT", str(out_file))
        _redirect("https://pythoncamp.de/", "https://barcamps.eu/pythoncamp/")

        _check("https://pythoncamp.de/")

        lines = out_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"earlier": True}
        assert json.loads(lines[1])["url"] == "https://pythoncamp.de/"

    @responses.activate
    def test_no_file_without_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _redirect("https://pythoncamp.de/", "https://barcamps.eu/pythoncamp/")

        _check("https://pythoncamp.de/")

        assert len(links.REDIRECT_RECORDS) == 1
        assert not list(tmp_path.glob("*.jsonl"))


class TestCheckLinksContext:
    """sort_yaml.check_links passes the conference, year and field to the link check."""

    @patch("sort_yaml.get_cache", return_value=(set(), set()))
    @patch("sort_yaml.check_link_availability", side_effect=lambda url, *_args, **_kwargs: url)
    def test_context_passed(self, mock_check_link, mock_get_cache):
        data = [
            {
                "conference": "PythonCamp Germany",
                "year": 2026,
                "link": "https://pythoncamp.de/",
                "sponsor": "https://pythoncamp.de/sponsors/",
                "start": PAST_START,
            },
        ]

        sort_yaml.check_links(data)

        contexts = [
            (call.args[0], call.kwargs["conference"], call.kwargs["year"], call.kwargs["field"])
            for call in mock_check_link.call_args_list
        ]
        assert contexts == [
            ("https://pythoncamp.de/", "PythonCamp Germany", 2026, "link"),
            ("https://pythoncamp.de/sponsors/", "PythonCamp Germany", 2026, "sponsor"),
        ]
