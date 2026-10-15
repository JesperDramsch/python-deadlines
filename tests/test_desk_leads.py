"""Tests for desk_leads: lead importers for pretalx, developers.events and the PyCon registries.

Nothing here touches the network: every request goes to the responses mock,
and opening a socket fails the test.
"""

import json
import socket
import sys
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
import requests
import responses
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import desk_leads
from desk_leads import PageFetcher
from desk_leads import SourceError
from desk_leads import TrackingIndex
from desk_leads import developers_events_records
from desk_leads import drift_record
from desk_leads import front_matter
from desk_leads import link_host
from desk_leads import link_key
from desk_leads import main
from desk_leads import name_variants
from desk_leads import next_slug
from desk_leads import parse_submissions
from desk_leads import pretalx_drift
from desk_leads import pretalx_probe
from desk_leads import pretalx_slug
from desk_leads import pycon_org_record
from desk_leads import registry_paths
from desk_leads import trademark_items
from desk_queue import add_items
from desk_queue import normalise_record
from desk_worklist import build_worklist
from desk_worklist import load_queue

TODAY = date(2026, 10, 14)
NOW = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)

PYCASCADES_OPEN = "Submissions close on 2026-10-26 05:00 (America/Los_Angeles), 1 week, 5 days from now."
PYTEXAS_OPEN = "Submissions close on 2026-12-11 17:00 (America/Chicago), 1 month, 3 weeks from now."
NAMIBIA_CLOSED = "Submissions closed on 2026-10-13 14:00 (Africa/Windhoek)."
EUROPYTHON_LEGACY = "Submissions close on 2027-02-01 23:59 (Poland), 3 months, 2 weeks from now."


def entry(name, year, **fields):
    """Build a data entry; every test entry names its own link."""
    value = {
        "conference": name,
        "year": year,
        "cfp": f"{year}-01-15 23:59:00",
        "place": "Online",
        "start": date(year, 3, 20),
        "end": date(year, 3, 21),
        "sub": "PY",
    }
    value.update(fields)
    return value


def dataset():
    """A small copy of the data, with real series and links."""
    return {
        "conferences": [
            entry(
                "PyCascades",
                2027,
                link="https://2027.pycascades.com/",
                cfp_link="https://pretalx.com/pycascades-2027/cfp",
                cfp="2026-10-26 23:59:00",
                place="Seattle, USA",
            ),
            entry(
                "PyTexas",
                2027,
                link="https://www.pytexas.org/2027/",
                cfp_link="https://pretalx.com/pytexas-2027/cfp",
                cfp="2026-12-11 17:00:00",
                timezone="America/Chicago",
                start=date(2027, 4, 16),
                end=date(2027, 4, 18),
            ),
            entry(
                "Wagtail Space",
                2026,
                link="https://wagtail.space/",
                cfp_link="https://pretalx.com/wagtail-space-2026/cfp",
                cfp="TBA",
                start=date(2026, 12, 3),
                end=date(2026, 12, 4),
                sub="WEB",
            ),
            entry(
                "PyCon Sweden",
                2026,
                link="https://pycon.se/",
                cfp_link="https://pretalx.com/pycon-sweden-2026/",
                cfp="None",
                start=date(2026, 11, 5),
                end=date(2026, 11, 6),
            ),
            entry(
                "PyBeach",
                2026,
                link="https://2026.pybeach.org/",
                cfp_link="https://pretalx.com/pybeach2026/cfp",
                cfp="2026-06-07 23:59:00",
                start=date(2026, 9, 26),
                end=date(2026, 9, 26),
            ),
            entry(
                "PyCon Slovakia",
                2027,
                alt_name="PyCon SK",
                link="https://pycon.sk/",
                cfp="TBA",
                start=date(2027, 3, 12),
                end=date(2027, 3, 13),
            ),
            entry(
                "SciPy India",
                2026,
                link="https://scipy.in/2026/",
                cfp_link="https://cfp.scipy.in/scipy-india-2026/cfp",
                cfp="2026-10-19 23:59:00",
                timezone="Asia/Kolkata",
                start=date(2026, 12, 19),
                end=date(2026, 12, 20),
                sub="SCIPY",
            ),
            entry(
                "PyCon Ireland",
                2026,
                link="https://python.ie/pycon-2026/",
                start=date(2026, 11, 21),
                end=date(2026, 11, 21),
            ),
        ],
        "archive": [
            entry(
                "PyCascades",
                2026,
                link="https://2026.pycascades.com/",
                cfp_link="https://pretalx.com/pycascades-2026/cfp",
            ),
            entry(
                "PyCon Namibia",
                2026,
                link="https://na.pycon.org/",
                cfp_link="https://pretalx.com/pycon-namibia-2026/cfp",
                start=date(2026, 2, 17),
                end=date(2026, 2, 20),
            ),
            entry(
                "PyCon Greece",
                2026,
                link="https://2026.pycon.gr/",
                cfp_link="https://pretalx.com/pycongr26/cfp",
                start=date(2026, 6, 12),
                end=date(2026, 6, 13),
            ),
            entry(
                "PyCon Japan",
                2024,
                link="https://2024.pycon.jp/",
                cfp_link="https://pretalx.com/pyconjp2024/cfp",
            ),
            entry("PyData Berlin", 2025, link="https://pydata.org/berlin2025/", sub="DATA"),
            entry("PyCon MEA", 2024, alt_name="PyCon MEA & Data Science", link="https://pyconmea.example/"),
        ],
        "legacy": [
            entry("Kiwi PyCon", 2019, link="https://kiwi.pycon.org/"),
        ],
    }


@pytest.fixture()
def index():
    return TrackingIndex.from_data(dataset())


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test opened a network connection")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture()
def web():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture()
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(desk_leads.time, "sleep", calls.append)
    return calls


def cfp_page(sentence=None, closed=False):
    """A pretalx CfP page, trimmed to the parts that matter."""
    button = "Proposals are closed" if closed else "Submit a proposal"
    deadline = f"<p><strong> {sentence} </strong>" if sentence else ""
    return (
        "<html><head><title>pretalx</title></head><body><main id=content>"
        "<div class=page-heading><h2>Call For Proposals</h2></div><p>Talks are 25 minutes long."
        f'{deadline}<div class=url-links><a class="btn btn-success btn-lg btn-block" href=/x/submit/>'
        f" {button} </a></div></main></body></html>"
    )


# Series whose latest edition is this year, so their 2027 page is probed too.
OTHER_PROBES = ("pybeach2027", "pycon-sweden-2027", "wagtail-space-2027")


def not_found(web, *slugs):
    for slug in slugs:
        web.add(responses.GET, f"https://pretalx.com/{slug}/cfp", status=404)


def epoch_ms(day):
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)


class TestLinkKey:
    @pytest.mark.parametrize(
        ("first", "second"),
        [
            ("https://2027.pycon.gr/", "https://2026.pycon.gr/"),
            ("https://pytexas.org/2027/", "https://www.pytexas.org/2026"),
            ("https://pretalx.com/pycon-namibia-2027/cfp", "https://pretalx.com/pycon-namibia-2026/cfp/"),
            ("https://pycon.sk/?utm_source=x#cfp", "http://www.pycon.sk"),
            (
                "https://web.archive.org/web/20240329144646/https://pretalx.com/pytexas-2024/",
                "https://pretalx.com/pytexas-2025/",
            ),
        ],
    )
    def test_same_series(self, first, second):
        assert link_key(first) == link_key(second)

    def test_years_are_removed(self):
        assert link_key("https://2027.pycon.gr/") == "pycon.gr"
        assert link_key("https://www.pytexas.org/2027/") == "pytexas.org"

    def test_paths_tell_shared_hosts_apart(self):
        assert link_key("https://pydata.org/lagos2027/") == "pydata.org/lagos"
        assert link_key("https://pydata.org/lagos2027/") != link_key("https://pydata.org/berlin2026/")

    def test_long_numbers_keep_their_digits(self):
        assert link_key("https://example.org/v120261/") == "example.org/v120261"

    @pytest.mark.parametrize("value", [None, "", "mailto:cfp@pycon.gr", "pycon.gr", 2027])
    def test_not_a_link(self, value):
        assert link_key(value) is None

    def test_host(self):
        assert link_host("https://www.2027.pycon.gr/en/") == "pycon.gr"


class TestNameVariants:
    def test_year_and_conference_are_stripped(self):
        assert name_variants("SciPy India 2026 Conference") == ["SciPy India Conference", "SciPy India"]

    def test_parentheses(self):
        assert name_variants("PyCon MEA (Middle East & Africa)") == ["PyCon MEA (Middle East & Africa)", "PyCon MEA"]


class TestClassify:
    def test_tracked_edition_is_skipped(self, index):
        assert index.classify("PyTexas 2027", 2027, "https://www.pytexas.org/2027/") is None

    def test_any_data_file_counts(self, index):
        assert index.classify("Kiwi PyCon 2019", 2019, None) is None
        assert index.classify("PyCon Namibia", 2026, None) is None

    def test_titles_mapping_and_alt_name(self, index):
        assert index.classify("PyCon SK 2027", 2027, "https://pycon.sk/") is None
        assert index.classify("PyCon SK 2028", 2028, None) == {
            "classification": "MISSING_EDITION",
            "matched": {"conference": "PyCon Slovakia", "file": "conferences", "year": 2027, "score": 100},
        }

    def test_trailing_conference_is_stripped(self, index):
        assert index.classify("SciPy India 2026 Conference", 2026, None) is None

    def test_missing_edition_names_the_latest_edition(self, index):
        found = index.classify("PyCon Namibia 2027", 2027, "https://na.pycon.org/")
        assert found == {
            "classification": "MISSING_EDITION",
            "matched": {"conference": "PyCon Namibia", "file": "archive", "year": 2026, "score": 100},
        }

    def test_link_with_years_removed_is_tracked(self, index):
        found = index.classify("Python Greece", 2027, "https://2027.pycon.gr/")
        assert found["classification"] == "MISSING_EDITION"
        assert found["matched"]["conference"] == "PyCon Greece"

    def test_link_on_a_shared_host_is_tracked_by_path(self, index):
        found = index.classify("PyData Berlin & PyCon DE", 2027, "https://pydata.org/berlin2027/")
        assert found["matched"] == {"conference": "PyData Berlin", "file": "archive", "year": 2025, "score": 100}

    def test_same_host_other_path_is_maybe(self, index):
        assert index.classify("Python Hellas Summit 2027", 2027, "https://pycon.gr/summit/") == {
            "classification": "MAYBE",
            "matched": {"conference": "PyCon Greece", "file": "archive", "year": 2026, "score": 50},
        }

    @pytest.mark.parametrize(
        "link",
        ["https://pydata.org/lagos2027/", "https://pretalx.com/pydata-lagos-2027/cfp", "https://pydata.org/"],
    )
    def test_shared_host_alone_proves_nothing(self, index, link):
        assert index.classify("PyData Lagos 2027", 2027, link) == {"classification": "NEW_SERIES", "matched": None}

    def test_new_series(self, index):
        assert index.classify("PyCon Nepal 2027", 2027, "https://pycon.org.np/") == {
            "classification": "NEW_SERIES",
            "matched": None,
        }


class TestParseSubmissions:
    def test_open(self):
        page = parse_submissions(cfp_page(PYTEXAS_OPEN))
        assert page["sentence"] == "Submissions close on 2026-12-11 17:00 (America/Chicago)"
        assert page["closed"] is False
        assert page["cfp"] == "2026-12-11 17:00:00"
        assert page["timezone"] == "America/Chicago"
        assert page["moment"] == datetime(2026, 12, 11, 23, 0, tzinfo=timezone.utc)

    def test_closed(self):
        page = parse_submissions(cfp_page(NAMIBIA_CLOSED, closed=True))
        assert page["sentence"] == "Submissions closed on 2026-10-13 14:00 (Africa/Windhoek)"
        assert page["closed"] is True
        assert page["moment"] == datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)

    def test_legacy_zone_is_kept_as_written(self):
        page = parse_submissions(cfp_page(EUROPYTHON_LEGACY))
        assert page["timezone"] == "Poland"
        assert page["moment"] == datetime(2027, 2, 1, 22, 59, tzinfo=timezone.utc)

    def test_unknown_zone(self):
        page = parse_submissions(cfp_page("Submissions close on 2026-12-11 17:00 (Mars/Olympus)"))
        assert page["moment"] is None
        assert page["timezone"] == "Mars/Olympus"

    def test_no_sentence(self):
        assert parse_submissions(cfp_page(closed=True)) is None


class TestDriftRecord:
    def test_aoe_entry_against_pretalx_is_drift(self):
        """PyCascades 2027: the entry says end of 26 October AoE, pretalx closes at 05:00 in Seattle."""
        conference = dataset()["conferences"][0]
        record = drift_record(conference, "https://pretalx.com/pycascades-2027/cfp", parse_submissions(PYCASCADES_OPEN))
        assert record == {
            "source": "pretalx",
            "kind": "drift",
            "title": "PyCascades",
            "url": "https://pretalx.com/pycascades-2027/cfp",
            "year": 2027,
            "payload": {
                "conference": "PyCascades",
                "year": 2027,
                "diffs": {
                    "cfp": {
                        "data": "2026-10-26 23:59:00 AoE",
                        "source": "2026-10-26 05:00 (America/Los_Angeles)",
                    },
                },
            },
        }

    def test_equal_instants_are_not_drift(self):
        pytexas = dataset()["conferences"][1]
        assert drift_record(pytexas, "https://pretalx.com/pytexas-2027/cfp", parse_submissions(PYTEXAS_OPEN)) is None
        same_in_utc = {**pytexas, "cfp": "2026-12-11 23:00:00", "timezone": "UTC"}
        assert drift_record(same_in_utc, "u", parse_submissions(PYTEXAS_OPEN)) is None

    def test_legacy_zone_compares_by_instant(self):
        europython = entry("EuroPython", 2027, cfp="2027-02-01 23:59:00", timezone="Europe/Warsaw")
        assert drift_record(europython, "u", parse_submissions(EUROPYTHON_LEGACY)) is None

    def test_tba_is_drift(self):
        wagtail = dataset()["conferences"][2]
        record = drift_record(wagtail, "https://pretalx.com/wagtail-space-2026/cfp", parse_submissions(PYTEXAS_OPEN))
        assert record["payload"]["diffs"]["cfp"]["data"] == "TBA"

    @pytest.mark.parametrize("cfp", ["None", "Cancelled"])
    def test_no_public_cfp_is_skipped(self, cfp):
        assert drift_record(entry("PyCon Sweden", 2026, cfp=cfp), "u", parse_submissions(PYTEXAS_OPEN)) is None

    def test_extension_is_the_effective_deadline(self):
        namibia = entry(
            "PyCon Namibia",
            2027,
            cfp="2026-09-21 23:59:00",
            cfp_ext="2026-10-05 23:59:00",
            timezone="Africa/Windhoek",
        )
        record = drift_record(namibia, "u", parse_submissions(NAMIBIA_CLOSED))
        assert record["payload"]["diffs"]["cfp"] == {
            "data": "2026-10-05 23:59:00 Africa/Windhoek (cfp_ext)",
            "source": "2026-10-13 14:00 (Africa/Windhoek)",
        }

    def test_seconds_the_page_cannot_show_are_not_drift(self):
        pytexas = {**dataset()["conferences"][1], "cfp": "2026-12-11 17:00:59", "timezone": "America/Chicago"}
        assert drift_record(pytexas, "u", parse_submissions(PYTEXAS_OPEN)) is None

    def test_closing_does_not_change_the_record(self):
        conference = dataset()["conferences"][0]
        open_page = parse_submissions(PYCASCADES_OPEN)
        closed_page = parse_submissions(PYCASCADES_OPEN.replace("Submissions close on", "Submissions closed on"))
        assert drift_record(conference, "u", open_page) == drift_record(conference, "u", closed_page)

    def test_unknown_page_zone_is_not_drift(self):
        page = parse_submissions("Submissions close on 2026-12-11 17:00 (Mars/Olympus)")
        assert drift_record(dataset()["conferences"][1], "u", page) is None


class TestPretalxSlugs:
    @pytest.mark.parametrize(
        ("url", "slug"),
        [
            ("https://pretalx.com/pycon-namibia-2027/cfp", "pycon-namibia-2027"),
            ("https://pretalx.com/pycon-sweden-2026/", "pycon-sweden-2026"),
            ("https://pretalx.com/pyohio-2026/submit/?track=6985-black", "pyohio-2026"),
            ("https://web.archive.org/web/20240329145604/https://pretalx.com/pycascades-2024/cfp", "pycascades-2024"),
            ("https://pretalx.com/api/events/", None),
            ("https://pretalx.com/", None),
            ("https://cfp.scipy.in/scipy-india-2026/cfp", None),
            (None, None),
        ],
    )
    def test_slug(self, url, slug):
        assert pretalx_slug(url) == slug

    @pytest.mark.parametrize(
        ("slug", "year", "expected"),
        [
            ("pycon-namibia-2026", 2026, "pycon-namibia-2027"),
            ("pyconjp2026", 2026, "pyconjp2027"),
            ("pydata-amsterdam2026", 2026, "pydata-amsterdam2027"),
            ("pycongr26", 2026, "pycongr27"),
            ("pybeach2025", 2025, "pybeach2026"),
            ("pycon-2026", 2025, None),
            ("pyohio", 2026, None),
            ("py26con", 2026, None),
        ],
    )
    def test_next_slug(self, slug, year, expected):
        assert next_slug(slug, year) == expected


class TestPretalxDrift:
    def test_checks_upcoming_entries_on_pretalx(self, web, sleeps):
        web.add(responses.GET, "https://pretalx.com/pycascades-2027/cfp", body=cfp_page(PYCASCADES_OPEN))
        web.add(responses.GET, "https://pretalx.com/pytexas-2027/cfp", body=cfp_page(PYTEXAS_OPEN))
        web.add(responses.GET, "https://pretalx.com/wagtail-space-2026/cfp", body=cfp_page(PYTEXAS_OPEN))
        pages = PageFetcher()
        records = pretalx_drift(dataset()["conferences"], TODAY, pages)
        assert [(record["title"], record["payload"]["diffs"]["cfp"]["data"]) for record in records] == [
            ("PyCascades", "2026-10-26 23:59:00 AoE"),
            ("Wagtail Space", "TBA"),
        ]
        # PyCon Sweden has no public CfP and PyBeach has ended: neither is fetched.
        assert [call.request.url for call in web.calls] == [
            "https://pretalx.com/pycascades-2027/cfp",
            "https://pretalx.com/pytexas-2027/cfp",
            "https://pretalx.com/wagtail-space-2026/cfp",
        ]
        assert sleeps == [1.0, 1.0]

    def test_sends_its_headers_and_never_calls_the_api(self, web, sleeps):
        web.add(responses.GET, "https://pretalx.com/pycascades-2027/cfp", body=cfp_page(PYCASCADES_OPEN))
        pretalx_drift(dataset()["conferences"][:1], TODAY, PageFetcher())
        headers = web.calls[0].request.headers
        assert headers["User-Agent"] == "pythondeadlin.es desk leads (+https://pythondeadlin.es)"
        assert headers["Accept-Language"] == "en"
        assert all("/api/" not in call.request.url for call in web.calls)

    def test_custom_domain_redirect_gives_the_final_url(self, web, sleeps):
        scipy = entry(
            "SciPy India",
            2026,
            cfp_link="https://pretalx.com/scipy-india-2026/cfp",
            cfp="2026-10-19 23:59:00",
            timezone="Asia/Kolkata",
            end=date(2026, 12, 20),
        )
        web.add(
            responses.GET,
            "https://pretalx.com/scipy-india-2026/cfp",
            status=302,
            headers={"Location": "https://cfp.scipy.in/scipy-india-2026/cfp"},
        )
        web.add(
            responses.GET,
            "https://cfp.scipy.in/scipy-india-2026/cfp",
            body=cfp_page("Submissions close on 2026-10-31 23:59 (Asia/Kolkata), 2 weeks from now."),
        )
        records = pretalx_drift([scipy], TODAY, PageFetcher())
        assert records[0]["url"] == "https://cfp.scipy.in/scipy-india-2026/cfp"

    def test_failed_page_is_reported_and_skipped(self, web, sleeps, capsys):
        web.add(
            responses.GET,
            "https://pretalx.com/pycascades-2027/cfp",
            body=requests.ConnectionError("connection reset"),
        )
        web.add(responses.GET, "https://pretalx.com/pytexas-2027/cfp", status=404)
        web.add(responses.GET, "https://pretalx.com/wagtail-space-2026/cfp", body=cfp_page(PYTEXAS_OPEN))
        pages = PageFetcher()
        records = pretalx_drift(dataset()["conferences"], TODAY, pages)
        assert [record["title"] for record in records] == ["Wagtail Space"]
        err = capsys.readouterr().err
        assert "pycascades-2027/cfp: connection reset" in err
        assert "pytexas-2027/cfp returned 404" in err
        assert not pages.all_failed()

    def test_a_blocked_job_fails_as_a_whole(self, web, sleeps):
        for slug in ("pycascades-2027", "pytexas-2027", "wagtail-space-2026"):
            web.add(responses.GET, f"https://pretalx.com/{slug}/cfp", status=403)
        pages = PageFetcher()
        assert pretalx_drift(dataset()["conferences"], TODAY, pages) == []
        assert pages.all_failed()


class TestPretalxProbe:
    def test_next_edition_is_a_missing_edition(self, web, sleeps, capsys):
        web.add(
            responses.GET,
            "https://pretalx.com/pycon-namibia-2027/cfp",
            body=cfp_page(NAMIBIA_CLOSED, closed=True),
        )
        web.add(responses.GET, "https://pretalx.com/pycongr27/cfp", status=404, body="Page not found.")
        not_found(web, *OTHER_PROBES)
        index = TrackingIndex.from_data(dataset())
        records = pretalx_probe(index, TODAY, PageFetcher())
        assert records == [
            {
                "source": "pretalx",
                "kind": "candidate",
                "title": "PyCon Namibia 2027",
                "url": "https://pretalx.com/pycon-namibia-2027/cfp",
                "year": 2027,
                "payload": {
                    "classification": "MISSING_EDITION",
                    "fields": {
                        "conference": "PyCon Namibia",
                        "year": 2027,
                        "cfp_link": "https://pretalx.com/pycon-namibia-2027/cfp",
                        "cfp": "2026-10-13 14:00:00",
                        "timezone": "Africa/Windhoek",
                    },
                    "source_id": "pycon-namibia-2027",
                    "evidence_url": "https://pretalx.com/pycon-namibia-2027/cfp",
                    "matched": {"conference": "PyCon Namibia", "file": "archive", "year": 2026, "score": 100},
                    "flags": [],
                },
            },
        ]
        # The other 2027 pages do not exist yet: a 404 says nothing.
        assert capsys.readouterr().err == ""

    def test_only_recent_series_without_the_next_edition_are_probed(self, web, sleeps):
        not_found(web, "pycon-namibia-2027", "pycongr27", *OTHER_PROBES)
        pretalx_probe(TrackingIndex.from_data(dataset()), TODAY, PageFetcher())
        # PyCon Japan (2024) is too old; PyCascades and PyTexas already have 2027;
        # PyCon Slovakia and SciPy India have no pretalx slug of their own.
        assert sorted(call.request.url for call in web.calls) == [
            "https://pretalx.com/pybeach2027/cfp",
            "https://pretalx.com/pycon-namibia-2027/cfp",
            "https://pretalx.com/pycon-sweden-2027/cfp",
            "https://pretalx.com/pycongr27/cfp",
            "https://pretalx.com/wagtail-space-2027/cfp",
        ]
        assert sleeps == [1.0] * 4

    def test_two_digit_slug_and_closed_page_without_a_deadline(self, web, sleeps):
        web.add(responses.GET, "https://pretalx.com/pycon-namibia-2027/cfp", status=404)
        web.add(responses.GET, "https://pretalx.com/pycongr27/cfp", body=cfp_page(closed=True))
        not_found(web, *OTHER_PROBES)
        records = pretalx_probe(TrackingIndex.from_data(dataset()), TODAY, PageFetcher())
        assert [(record["title"], record["payload"]["fields"]["cfp"]) for record in records] == [
            ("PyCon Greece 2027", None),
        ]
        assert records[0]["payload"]["fields"]["timezone"] is None
        assert records[0]["payload"]["source_id"] == "pycongr27"

    def test_page_without_a_cfp_is_not_a_find(self, web, sleeps):
        web.add(responses.GET, "https://pretalx.com/pycon-namibia-2027/cfp", body="<main>Schedule</main>")
        not_found(web, "pycongr27", *OTHER_PROBES)
        assert pretalx_probe(TrackingIndex.from_data(dataset()), TODAY, PageFetcher()) == []


class TestDevelopersEvents:
    EVENTS = (
        # The PyTexas record as developers.events serves it: tracked, so skipped.
        {
            "name": "PyTexas 2027",
            "date": [1807833600000, 1808006400000],
            "hyperlink": "https://www.pytexas.org/2027/",
            "location": "Austin, TX (USA)",
            "city": "Austin, TX",
            "country": "USA",
            "misc": '<a href="https://pretalx.com/pytexas-2027/cfp">CFP</a>',
            "cfp": {
                "link": "https://pretalx.com/pytexas-2027/cfp",
                "until": "11-December-2026",
                "untilDate": 1796947200000,
            },
            "status": "open",
            "tags": [],
        },
        {
            "name": "PyData Lagos 2027",
            "date": [epoch_ms(date(2027, 5, 14)), epoch_ms(date(2027, 5, 15))],
            "hyperlink": "https://pydata.org/lagos2027/",
            "location": "Lagos (Nigeria)",
            "city": "Lagos",
            "country": "Nigeria",
            "cfp": {"link": "https://pretalx.com/pydata-lagos-2027/cfp", "until": "1-March-2027"},
            "status": "open",
            "tags": [{"key": "tech", "value": "python"}],
        },
        {
            "name": "PyCon Greece 2027",
            "date": [epoch_ms(date(2027, 6, 11))],
            "hyperlink": "https://2027.pycon.gr/",
            "location": "Athens (Greece)",
            "status": "open",
            "tags": [],
        },
        {
            "name": "Python Hellas Summit 2027",
            "date": [epoch_ms(date(2027, 9, 3))],
            "hyperlink": "https://pycon.gr/summit/",
            "location": "Thessaloniki (Greece)",
            "status": "",
        },
        {
            "name": "Snakes & Data Summit 2027",
            "date": [epoch_ms(date(2027, 2, 2))],
            "hyperlink": "https://snakes-and-data.example/2027/",
            "status": "open",
            "tags": [{"key": "tech", "value": "python"}],
        },
        {"name": "SciPy 2027 Financial Aid", "date": [epoch_ms(date(2027, 7, 1))], "hyperlink": "https://x.example/"},
        {"name": "PyCon US 2027 Hatchery Program", "date": [epoch_ms(date(2027, 5, 1))], "hyperlink": "https://h/"},
        {"name": "PyCon Ireland 2025", "date": [epoch_ms(date(2025, 11, 15))], "hyperlink": "https://python.ie/"},
        {
            "name": "DjangoCon Africa 2027",
            "date": [epoch_ms(date(2027, 8, 1))],
            "hyperlink": "https://2027.djangocon.africa/",
            "status": "Canceled",
        },
        {"name": "Craft Conf 2027", "date": [epoch_ms(date(2027, 5, 26))], "hyperlink": "https://craft-conf.com/"},
        {"name": "PyCon Nowhere 2027", "date": [epoch_ms(date(2027, 5, 26))]},
    )

    def records(self, index):
        events = [*self.EVENTS, self.EVENTS[1]]
        return developers_events_records(events, index, TODAY)

    def test_untracked_python_events_become_candidates(self, index):
        found = [(record["title"], record["payload"]["classification"]) for record in self.records(index)]
        assert found == [
            ("PyData Lagos 2027", "NEW_SERIES"),
            ("PyCon Greece 2027", "MISSING_EDITION"),
            ("Python Hellas Summit 2027", "MAYBE"),
        ]

    @pytest.mark.parametrize(
        "name",
        ["EuroPython 2027", "EuroSciPy 2027", "DjangoCon US 2027", "JupyterCon 2027", "GeoPython 2027", "PyData Oslo"],
    )
    def test_python_words_inside_longer_names(self, name):
        assert desk_leads.is_python_event({"name": name})

    @pytest.mark.parametrize("name", ["Craft Conf 2027", "Happy Devs Summit", "Spyware Days", "SQLSaturday Oslo"])
    def test_other_names(self, name):
        assert not desk_leads.is_python_event({"name": name})

    def test_a_python_tag_alone_is_not_enough(self, index):
        assert "Snakes & Data Summit 2027" not in [record["title"] for record in self.records(index)]

    def test_records_carry_only_name_year_and_link(self, index):
        record = self.records(index)[0]
        assert record == {
            "source": "developers-events",
            "kind": "candidate",
            "title": "PyData Lagos 2027",
            "url": "https://pydata.org/lagos2027/",
            "year": 2027,
            "payload": {
                "classification": "NEW_SERIES",
                "fields": {"conference": "PyData Lagos", "year": 2027, "link": "https://pydata.org/lagos2027/"},
                "source_id": "https://pydata.org/lagos2027/",
                "evidence_url": "https://pydata.org/lagos2027/",
                "matched": None,
                "flags": ["lead-only"],
            },
        }
        text = json.dumps(self.records(index))
        for value in ("Lagos (Nigeria)", "Nigeria", "1-March-2027", "pretalx", "2027-05-14", "Thessaloniki"):
            assert value not in text

    def test_whole_source_failure_exits_1(self, tmp_path, web, capsys):
        write_data(tmp_path)
        web.add(responses.GET, desk_leads.DEVELOPERS_EVENTS, status=503)
        out = tmp_path / "records.jsonl"
        assert main(["developers-events", "--base", str(tmp_path), "--today", "2026-10-14", "--out", str(out)]) == 1
        assert not out.exists() or out.read_text(encoding="utf-8") == ""
        assert "503" in capsys.readouterr().err


PSF_CONTENT = """\
<h1>PyCon Conferences around the World</h1>
<p>The following are national-level and regional authorized PyCon conferences:</p>
<blockquote>
<ul class="simple">
<li>&quot;Kiwi PyCon&quot;, &quot;PyCon NZ&quot; in New Zealand</li>
<li>&quot;PyCon MEA (Middle East &amp; Africa)&quot; in Dubai</li>
<li>&quot;PyCon NP&quot;, &quot;PyCon Nepal&quot; in Nepal</li>
<li>&quot;PyCon SK&quot;, &quot;PyCon Slovakia&quot; in Slovakia</li>
<li>&quot;PyCon VE&quot;, &quot;PyCon Venezuela&quot; in Venezuela</li>
</ul>
</blockquote>
<p>If we have forgotten a national or regional PyCon conference in this list, please write to us.</p>
<ul><li>&quot;Not a PyCon&quot; in a later list</li></ul>
"""

REGISTRY_FILES = {
    "/_national/pycon-ireland.yml": "---\nname: PyCon Ireland\nflag: ie\nlocation: Ireland\nwebsite: https://python.ie\n---\n",
    "/_national/pycon-dk.yml": (
        "---\nname: PyCon DK\nflag: dk\nlocation: Denmark\ndiscontinued: true\n"
        "website:  https://web.archive.org/web/20161010045716/https://pycon.dk/\n---\n"
    ),
    "/_national/python-greece.yml": "---\nname: Python Greece\nflag: gr\nwebsite: https://2025.pycon.gr/\n---\n",
    "/_regional/pycascades.yml": (
        "---\nname: PyCascades\nlocation: Pacific Northwest North America\n"
        "website: https://www.pycascades.com\ntwitter: pycascades\n---\n"
    ),
    "/_regional/pygotham.yml": (
        "---\nname: PyGotham\nlocation: New York, United States\nwebsite: https://pygotham.org\ntwitter: PyGotham\n---"
    ),
}


def registry_web(web, psf_status=200, broken=None):
    if psf_status == 200:
        web.add(responses.GET, desk_leads.PSF_TRADEMARKS_API, json={"content": PSF_CONTENT, "path": "/psf/pycon/"})
    else:
        web.add(responses.GET, desk_leads.PSF_TRADEMARKS_API, status=psf_status)
    listing = [{"name": path, "hash": "x", "size": 90} for path in REGISTRY_FILES]
    listing += [{"name": "/index.html", "hash": "x", "size": 9}, {"name": "/_national/README.md", "hash": "x"}]
    web.add(responses.GET, desk_leads.PYCON_ORG_FILES, json={"type": "gh", "files": listing})
    for path, text in REGISTRY_FILES.items():
        url = f"{desk_leads.PYCON_ORG_RAW}{path}"
        if path == broken:
            web.add(responses.GET, url, status=404)
        else:
            web.add(responses.GET, url, body=text)


class TestRegistry:
    def test_trademark_items(self):
        assert trademark_items(PSF_CONTENT) == [
            ["Kiwi PyCon", "PyCon NZ"],
            ["PyCon MEA (Middle East & Africa)"],
            ["PyCon NP", "PyCon Nepal"],
            ["PyCon SK", "PyCon Slovakia"],
            ["PyCon VE", "PyCon Venezuela"],
        ]

    def test_trademark_page_without_the_list(self):
        with pytest.raises(ValueError, match="no list"):
            trademark_items("<p>Nothing here</p>")

    def test_front_matter(self):
        assert front_matter(REGISTRY_FILES["/_regional/pygotham.yml"]) == {
            "name": "PyGotham",
            "location": "New York, United States",
            "website": "https://pygotham.org",
            "twitter": "PyGotham",
        }
        assert front_matter("name: PyGotham\n") is None
        assert front_matter("---\n- a list\n---\n") is None

    def test_pycon_org_records(self, index):
        def record(path):
            return pycon_org_record(front_matter(REGISTRY_FILES[path]), f"raw{path}", index)

        assert record("/_national/pycon-dk.yml") is None  # discontinued
        assert record("/_national/pycon-ireland.yml") is None  # tracked by name
        assert record("/_national/python-greece.yml") is None  # tracked by website
        assert record("/_regional/pygotham.yml") == {
            "source": "registry",
            "kind": "registry",
            "title": "PyGotham",
            "url": "https://pygotham.org",
            "year": None,
            "payload": {
                "names": ["PyGotham"],
                "change": "untracked",
                "registry": "pycon.org",
                "evidence_url": "raw/_regional/pygotham.yml",
                "website": "https://pygotham.org",
            },
        }

    def test_registry_paths(self):
        listing = {"files": [{"name": "/_national/a.yml"}, {"name": "/_regional/b.yml"}, {"name": "/_posts/c.yml"}]}
        assert registry_paths(listing) == ["/_national/a.yml", "/_regional/b.yml"]
        with pytest.raises(ValueError, match="no files"):
            registry_paths({"files": None})

    def test_both_registries(self, index, web):
        registry_web(web)
        records = desk_leads.registry_leads(index)
        assert [(record["payload"]["registry"], record["payload"]["names"]) for record in records] == [
            ("psf-trademarks", ["PyCon NP", "PyCon Nepal"]),
            ("psf-trademarks", ["PyCon VE", "PyCon Venezuela"]),
            ("pycon.org", ["PyGotham"]),
        ]
        assert records[0] == {
            "source": "registry",
            "kind": "registry",
            "title": "PyCon NP",
            "url": "https://www.python.org/psf/trademarks/pycon/",
            "year": None,
            "payload": {
                "names": ["PyCon NP", "PyCon Nepal"],
                "change": "untracked",
                "registry": "psf-trademarks",
                "evidence_url": "https://www.python.org/psf/trademarks/pycon/",
            },
        }

    def test_one_failed_file_is_skipped(self, index, web, capsys):
        registry_web(web, broken="/_regional/pygotham.yml")
        records = desk_leads.registry_leads(index)
        assert [record["title"] for record in records] == ["PyCon NP", "PyCon VE"]
        assert "pygotham.yml" in capsys.readouterr().err

    def test_failed_registry_keeps_the_other(self, index, web):
        registry_web(web, psf_status=500)
        with pytest.raises(SourceError, match="psf-trademarks") as raised:
            desk_leads.registry_leads(index)
        assert [record["title"] for record in raised.value.records] == ["PyGotham"]


def write_data(base, data=None):
    folder = base / "_data"
    folder.mkdir(parents=True, exist_ok=True)
    for name, entries in (data or dataset()).items():
        (folder / f"{name}.yml").write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")


def pretalx_web(web):
    web.add(responses.GET, "https://pretalx.com/pycascades-2027/cfp", body=cfp_page(PYCASCADES_OPEN))
    web.add(responses.GET, "https://pretalx.com/pytexas-2027/cfp", body=cfp_page(PYTEXAS_OPEN))
    web.add(responses.GET, "https://pretalx.com/wagtail-space-2026/cfp", body=cfp_page(PYTEXAS_OPEN))
    web.add(responses.GET, "https://pretalx.com/pycon-namibia-2027/cfp", body=cfp_page(NAMIBIA_CLOSED, closed=True))
    not_found(web, "pycongr27", *OTHER_PROBES)


class TestCli:
    def test_appends_json_lines_and_counts(self, tmp_path, web, sleeps, capsys):
        write_data(tmp_path)
        pretalx_web(web)
        out = tmp_path / "records.jsonl"
        out.write_text('{"earlier": true}\n', encoding="utf-8")
        assert main(["pretalx", "--base", str(tmp_path), "--today", "2026-10-14", "--out", str(out)]) == 0
        lines = out.read_text(encoding="utf-8").splitlines()
        assert lines[0] == '{"earlier": true}'
        assert [(json.loads(line)["kind"], json.loads(line)["title"]) for line in lines[1:]] == [
            ("drift", "PyCascades"),
            ("drift", "Wagtail Space"),
            ("candidate", "PyCon Namibia 2027"),
        ]
        assert capsys.readouterr().err.strip().splitlines()[-1] == "desk_leads: pretalx: 3 record(s)"

    def test_stdout_without_out(self, tmp_path, web, capsys):
        write_data(tmp_path)
        web.add(
            responses.GET,
            desk_leads.DEVELOPERS_EVENTS,
            json=[TestDevelopersEvents.EVENTS[0], TestDevelopersEvents.EVENTS[1]],
        )
        assert main(["developers-events", "--base", str(tmp_path), "--today", "2026-10-14"]) == 0
        captured = capsys.readouterr()
        assert [json.loads(line)["title"] for line in captured.out.splitlines()] == ["PyData Lagos 2027"]
        assert captured.err.strip() == "desk_leads: developers-events: 1 record(s)"

    def test_every_pretalx_page_failing_exits_1(self, tmp_path, web, sleeps, capsys):
        write_data(tmp_path)
        out = tmp_path / "records.jsonl"
        assert main(["pretalx", "--base", str(tmp_path), "--today", "2026-10-14", "--out", str(out)]) == 1
        assert "every one of 8 page fetches failed" in capsys.readouterr().err

    def test_failed_registry_still_writes_the_other(self, tmp_path, web, capsys):
        write_data(tmp_path)
        registry_web(web, psf_status=500)
        out = tmp_path / "records.jsonl"
        assert main(["registry", "--base", str(tmp_path), "--out", str(out)]) == 1
        assert [json.loads(line)["title"] for line in out.read_text(encoding="utf-8").splitlines()] == ["PyGotham"]


class TestQueueRoundTrip:
    """Every record goes through the queue writer and reaches the skill its kind needs."""

    def test_records_route_to_their_skills(self, tmp_path, web, sleeps):
        pretalx_web(web)
        web.add(responses.GET, desk_leads.DEVELOPERS_EVENTS, json=list(TestDevelopersEvents.EVENTS))
        registry_web(web)
        data = dataset()
        index = TrackingIndex.from_data(data)
        records = []
        for source in desk_leads.SOURCES:
            records.extend(desk_leads.collect(source, data, index, TODAY))

        for record in records:
            assert normalise_record(record, NOW)["source"] == record["source"]
        results = add_items(tmp_path, records, NOW)
        assert {result.get("status") for result in results} == {"added"}

        worklist = build_worklist(data, load_queue(tmp_path), TODAY, scout=False)
        routed = {
            (tuple(item["reasons"]), item["conference"], item["year"]): item["skill"]
            for item in worklist["items"]
            if item["queue_refs"]
        }
        # A candidate is routed by the worklist's own match: a tracked series
        # without the edition goes to the new-year-checker with the find's
        # year, and a series the data does not track goes to the scouter. The
        # MAYBE on pycon.gr names no tracked series, so it is a scouter item.
        assert routed == {
            (("drift",), "PyCascades", 2027): "enricher",
            (("drift",), "Wagtail Space", 2026): "enricher",
            (("candidate",), "PyCon Namibia", 2027): "new-year-checker",
            (("candidate",), "PyCon Greece", 2027): "new-year-checker",
            (("candidate",), "PyData Lagos", 2027): "scouter",
            (("candidate",), "Python Hellas Summit", 2027): "scouter",
            (("registry",), "PyCon Nepal", None): "scouter",
            (("registry",), "PyCon Venezuela", None): "scouter",
            (("registry",), "PyGotham", None): "scouter",
        }

    def test_candidates_follow_the_data_the_worklist_reads(self, tmp_path, web, sleeps):
        """An edition added after the find was queued sends the candidate to the enricher."""
        pretalx_web(web)
        web.add(responses.GET, desk_leads.DEVELOPERS_EVENTS, json=list(TestDevelopersEvents.EVENTS))
        data = dataset()
        index = TrackingIndex.from_data(data)
        records = [*desk_leads.collect("pretalx", data, index, TODAY)]
        records.extend(desk_leads.collect("developers-events", data, index, TODAY))
        add_items(tmp_path, [record for record in records if record["kind"] == "candidate"], NOW)

        data["conferences"].append(
            entry("PyCon Greece", 2027, link="https://2027.pycon.gr/", start=date(2027, 6, 11), end=date(2027, 6, 12)),
        )
        worklist = build_worklist(data, load_queue(tmp_path), TODAY, scout=False)
        routed = {
            (item["conference"], item["year"]): (item["skill"], (item["entry"] or {}).get("link"))
            for item in worklist["items"]
            if item["queue_refs"]
        }
        assert routed == {
            ("PyCon Namibia", 2027): ("new-year-checker", None),
            ("PyCon Greece", 2027): ("enricher", "https://2027.pycon.gr/"),
            ("PyData Lagos", 2027): ("scouter", None),
            ("Python Hellas Summit", 2027): ("scouter", None),
        }
