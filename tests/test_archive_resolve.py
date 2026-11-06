"""Tests for utils/archive_resolve.py: which links of old editions are archived, and how."""

import sys
from datetime import date
from pathlib import Path

import pytest
import requests
import responses
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import archive_resolve
import wayback
from tidy_conf import links

TODAY = date(2026, 11, 6)
TANZANIA_SPONSOR = [
    "20211206210540",
    "20231209151121",
    "20241004214743",
    "20250618114933",
    "20261018085052",
]


def _edition(year: int, start: date, end: date | None = None, conference: str = "PyCon Tanzania", **fields) -> dict:
    return {"conference": conference, "year": year, "start": start, "end": end or start, **fields}


@pytest.fixture()
def tanzania() -> list[dict]:
    """PyCon Tanzania as the data held it: the 2024 edition on the old domain, the 2026 one on the new."""
    return [
        _edition(
            2024,
            date(2024, 12, 3),
            date(2024, 12, 4),
            link="https://pycon.or.tz/",
            sponsor="https://pycon.or.tz/sponsor/",
            coc="https://pycon.tz/conduct/",
        ),
        _edition(
            2026,
            date(2026, 11, 25),
            date(2026, 11, 27),
            link="https://pycon.tz/",
            sponsor="https://pycon.or.tz/sponsor/",
        ),
    ]


@pytest.fixture(autouse=True)
def _clean_redirect_records(monkeypatch):
    monkeypatch.delenv(links.REDIRECT_RECORDS_ENV, raising=False)
    links.REDIRECT_RECORDS.clear()
    yield
    links.REDIRECT_RECORDS.clear()


class TestHasYear:
    @pytest.mark.parametrize(
        "url",
        [
            "https://2024.pycon.de/",
            "https://pycon.hk/2024/",
            "https://pydata.org/global2023/",
            "https://pretalx.com/pycon-lithuania-2025/cfp",
            "https://ep2024.europython.eu/",
            "https://pycon.fr/1999/",
        ],
    )
    def test_year_urls(self, url):
        assert archive_resolve.has_year(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://pycon.or.tz/sponsor/",
            "https://pycon25.uber.space/en/",
            "https://indico.cern.ch/event/1375573/",
            "https://pycon.de/",
            "https://example.org/12024/",
        ],
    )
    def test_yearless_urls(self, url):
        assert not archive_resolve.has_year(url)


class TestSuperseded:
    """An edition is superseded once it has ended and the series has a later edition."""

    def test_old_edition_with_later_one(self, tanzania):
        assert archive_resolve.superseded(tanzania, TODAY) == [tanzania[0]]

    def test_latest_edition_is_never_superseded(self, tanzania):
        """Even once it has ended."""
        assert archive_resolve.superseded(tanzania, date(2027, 6, 1)) == [tanzania[0]]

    def test_edition_that_has_not_ended(self):
        entries = [_edition(2026, date(2026, 11, 10)), _edition(2027, date(2027, 11, 10))]

        assert archive_resolve.superseded(entries, date(2026, 11, 10)) == []

    def test_later_edition_of_another_series_does_not_count(self):
        entries = [_edition(2024, date(2024, 12, 3)), _edition(2026, date(2026, 11, 25), conference="PyCon Kenya")]

        assert archive_resolve.superseded(entries, TODAY) == []


class TestSupersededCandidates:
    def test_yearless_live_urls_of_superseded_editions(self, tanzania):
        candidates = archive_resolve.superseded_candidates(tanzania, TODAY)

        assert [(c.entry["year"], c.field, c.url, c.reason) for c in candidates] == [
            (2024, "link", "https://pycon.or.tz/", "superseded"),
            (2024, "sponsor", "https://pycon.or.tz/sponsor/", "superseded"),
            (2024, "coc", "https://pycon.tz/conduct/", "superseded"),
        ]

    def test_year_urls_and_archive_links_are_left_alone(self):
        entries = [
            _edition(
                2024,
                date(2024, 4, 22),
                conference="PyCon Germany",
                link="https://2024.pycon.de/",
                cfp_link="https://web.archive.org/web/20240101000000/https://pycon.de/cfp/",
                finaid="https://pycon.de/financial-aid/",
            ),
            _edition(2025, date(2025, 4, 23), conference="PyCon Germany", link="https://2025.pycon.de/"),
        ]

        candidates = archive_resolve.superseded_candidates(entries, TODAY)

        assert [(c.field, c.url) for c in candidates] == [("finaid", "https://pycon.de/financial-aid/")]


class TestResolve:
    def test_tanzania_2024_gets_the_capture_from_its_own_time(self, tanzania):
        candidates = archive_resolve.superseded_candidates(tanzania, TODAY)

        outcomes = archive_resolve.resolve(
            [c for c in candidates if c.field == "sponsor"],
            lookup=lambda url: TANZANIA_SPONSOR,
            delay=0,
        )

        expected = "https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/"
        assert tanzania[0]["sponsor"] == expected
        assert tanzania[1]["sponsor"] == "https://pycon.or.tz/sponsor/"
        assert [(o.new_url, o.detail) for o in outcomes] == [(expected, "capture 20241004214743")]

    def test_one_lookup_per_url(self):
        url = "https://pycon.se/"
        entries = [_edition(year, date(year, 11, 1), conference="PyCon Sweden", link=url) for year in (2022, 2023)]
        candidates = [archive_resolve.Candidate(entry, "link", url, "superseded") for entry in entries]
        lookups = []

        archive_resolve.resolve(candidates, lookup=lambda u: lookups.append(u) or ["20221020000000"], delay=0)

        assert lookups == [url]
        # Each edition gets the capture from its own time, from the same listing
        assert entries[0]["link"] == "https://web.archive.org/web/20221020000000/https://pycon.se/"
        assert entries[1]["link"] == "https://web.archive.org/web/20221020000000/https://pycon.se/"

    def test_field_listed_twice_is_resolved_once(self, tanzania):
        candidate = archive_resolve.superseded_candidates(tanzania, TODAY)[0]

        outcomes = archive_resolve.resolve([candidate, candidate], lookup=lambda url: TANZANIA_SPONSOR, delay=0)

        assert len(outcomes) == 1

    def test_no_capture_keeps_the_url(self, tanzania):
        candidate = archive_resolve.superseded_candidates(tanzania, TODAY)[0]

        (outcome,) = archive_resolve.resolve([candidate], lookup=lambda url: ["20261018085052"], delay=0)

        assert outcome.new_url is None
        assert outcome.detail == "no capture on or before 2024-12-04"
        assert tanzania[0]["link"] == "https://pycon.or.tz/"

    def test_failed_lookup_keeps_the_url(self, tanzania):
        candidate = archive_resolve.superseded_candidates(tanzania, TODAY)[0]

        def fail(url):
            raise wayback.WaybackError("CDX request returned HTTP 503")

        (outcome,) = archive_resolve.resolve([candidate], lookup=fail, delay=0)

        assert outcome.new_url is None
        assert outcome.detail.startswith("lookup failed")
        assert tanzania[0]["link"] == "https://pycon.or.tz/"


class TestProbe:
    """Only a lasting failure counts as broken: replacing a link is not undone."""

    @pytest.mark.parametrize(("status", "broken"), [(404, True), (410, True), (403, False), (429, False), (500, False)])
    @responses.activate
    def test_status(self, status, broken):
        responses.add(responses.GET, "https://example.org/", status=status)

        assert links.probe("https://example.org/").broken is broken

    @pytest.mark.parametrize(
        ("error", "broken"),
        [
            (requests.ConnectionError("name or service not known"), True),
            (requests.Timeout("slow"), False),
            (requests.exceptions.SSLError("bad certificate"), True),
            (requests.exceptions.InvalidURL("bad url"), False),
        ],
    )
    @responses.activate
    def test_errors(self, error, broken):
        responses.add(responses.GET, "https://example.org/", body=error)

        result = links.probe("https://example.org/")

        assert result.status is None
        assert result.broken is broken

    @responses.activate
    def test_redirect_elsewhere(self):
        responses.add(responses.GET, "https://pythoncamp.de/", status=301, headers={"Location": "https://barcamps.eu/"})
        responses.add(responses.GET, "https://barcamps.eu/", status=200)

        result = links.probe("https://pythoncamp.de/")

        assert result.final_url == "https://barcamps.eu/"
        assert result.redirects_elsewhere


class TestCheckLinks:
    """The weekly link check: every live URL once, broken ones on ended editions become candidates."""

    def test_broken_url_on_ended_edition(self):
        entry = _edition(2024, date(2024, 12, 3), link="https://pycon.or.tz/")

        candidates = archive_resolve.check_links(
            [entry],
            TODAY,
            request=lambda url: links.Probe(url, url, 404),
        )

        assert [(c.field, c.reason) for c in candidates] == [("link", "broken")]

    def test_broken_url_on_upcoming_edition_is_left_alone(self):
        entry = _edition(2026, date(2026, 11, 25), link="https://pycon.tz/")

        candidates = archive_resolve.check_links([entry], TODAY, request=lambda url: links.Probe(url, url, 404))

        assert candidates == []

    def test_each_url_requested_once(self, tanzania):
        requested = []

        archive_resolve.check_links(
            tanzania,
            TODAY,
            request=lambda url: requested.append(url) or links.Probe(url, url, 200),
        )

        assert sorted(requested) == [
            "https://pycon.or.tz/",
            "https://pycon.or.tz/sponsor/",
            "https://pycon.tz/",
            "https://pycon.tz/conduct/",
        ]

    def test_archive_links_are_not_requested(self):
        entry = _edition(2020, date(2020, 1, 1), link="https://web.archive.org/web/20200101000000/https://x.org/")
        requested = []

        archive_resolve.check_links([entry], TODAY, request=lambda url: requested.append(url))

        assert requested == []

    def test_checks_coc(self):
        """Coc is a URL field like the others."""
        entry = _edition(2024, date(2024, 1, 1), coc="https://pycon.tz/conduct/")
        requested = []

        archive_resolve.check_links(
            [entry], TODAY, request=lambda url: requested.append(url) or links.Probe(url, url, 200),
        )

        assert requested == ["https://pycon.tz/conduct/"]


class TestFollowMastodon:
    def test_moved_accounts_updated_each_checked_once(self):
        old, new = "https://mastodon.social/@pycon", "https://fosstodon.org/@pycon"
        entries = [{"mastodon": old}, {"mastodon": old}, {"mastodon": "https://fosstodon.org/@other"}, {}]
        checked = []

        updated = archive_resolve.follow_mastodon(
            entries,
            check=lambda url: checked.append(url) or (new if url == old else None),
        )

        assert updated == 2
        assert checked == [old, "https://fosstodon.org/@other"]
        assert [e.get("mastodon") for e in entries] == [new, new, "https://fosstodon.org/@other", None]


class TestMain:
    """The command edits the data files in place and reports what it changed and kept."""

    @pytest.fixture()
    def repo(self, tmp_path, tanzania):
        data = tmp_path / "_data"
        data.mkdir()
        (data / "conferences.yml").write_text(yaml.safe_dump([tanzania[1]]), encoding="utf-8")
        (data / "archive.yml").write_text(yaml.safe_dump([tanzania[0]]), encoding="utf-8")
        return tmp_path

    def _run(self, repo, monkeypatch, lookup):
        monkeypatch.setattr(archive_resolve.wayback, "captures", lookup)
        archive_resolve.main(
            [
                "--base",
                str(repo),
                "--today",
                TODAY.isoformat(),
                "--no-probe",
                "--delay",
                "0",
                "--changes",
                str(repo / "changes.md"),
                "--needs",
                str(repo / "needs.md"),
            ],
        )

    def test_replaces_and_reports(self, repo, monkeypatch):
        captures = {"https://pycon.or.tz/sponsor/": TANZANIA_SPONSOR, "https://pycon.or.tz/": ["20241001000000"]}

        self._run(repo, monkeypatch, lambda url: captures.get(url, []))

        (old,) = yaml.safe_load((repo / "_data" / "archive.yml").read_text(encoding="utf-8"))
        assert old["link"] == "https://web.archive.org/web/20241001000000/https://pycon.or.tz/"
        assert old["sponsor"] == "https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/"
        assert old["coc"] == "https://pycon.tz/conduct/"
        (current,) = yaml.safe_load((repo / "_data" / "conferences.yml").read_text(encoding="utf-8"))
        assert current["sponsor"] == "https://pycon.or.tz/sponsor/"

        changes = (repo / "changes.md").read_text(encoding="utf-8").splitlines()
        assert changes == [
            "- PyCon Tanzania 2024: `link` https://pycon.or.tz/ → "
            "https://web.archive.org/web/20241001000000/https://pycon.or.tz/",
            "- PyCon Tanzania 2024: `sponsor` https://pycon.or.tz/sponsor/ → "
            "https://web.archive.org/web/20241004214743/https://pycon.or.tz/sponsor/",
        ]
        assert (repo / "needs.md").read_text(encoding="utf-8") == (
            "- [ ] PyCon Tanzania 2024: `coc` https://pycon.tz/conduct/ (superseded) kept: "
            "no capture on or before 2024-12-04\n"
        )

    def test_nothing_replaced_leaves_the_files_alone(self, repo, monkeypatch):
        before = (repo / "_data" / "archive.yml").read_text(encoding="utf-8")

        self._run(repo, monkeypatch, lambda url: [])

        assert (repo / "_data" / "archive.yml").read_text(encoding="utf-8") == before
        assert (repo / "changes.md").read_text(encoding="utf-8") == ""
