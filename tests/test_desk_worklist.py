"""Tests for desk_worklist: the deadline desk's deterministic daily worklist."""

import hashlib
import itertools
import json
import socket
import sys
from datetime import date
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_worklist import build_worklist
from desk_worklist import clean_watch_title
from desk_worklist import load_queue
from desk_worklist import main
from desk_worklist import rotation_slot

TODAY = date(2026, 10, 14)  # a Wednesday, weekday() == 2
GENERATED = "2026-10-14T06:00:00Z"


def conf(name, year, **fields):
    """Build an entry whose dated cfp is far from today, so no deadline check fires."""
    entry = {
        "conference": name,
        "year": year,
        "link": "https://example.org/",
        "cfp": f"{year}-12-01 23:59:00",
        "place": "Online",
        "start": date(year, 12, 10),
        "end": date(year, 12, 11),
        "sub": "PY",
    }
    entry.update(fields)
    return entry


def dataset(conferences=(), archive=(), legacy=()):
    return {"conferences": list(conferences), "archive": list(archive), "legacy": list(legacy)}


def queue_item(
    kind="signal",
    title="",
    *,
    source="changedetection",
    year=None,
    payload=None,
    file="queue/example.json",
    series=None,
    item_id=None,
    received="2026-10-14T06:00:00Z",
):
    """Build a queue item the way load_queue returns it."""
    if item_id is None:
        item_id = hashlib.sha1(f"{source}|{kind}|{title}|{file}".encode(), usedforsecurity=False).hexdigest()
    return {
        "id": item_id,
        "source": source,
        "kind": kind,
        "received": received,
        "title": title,
        "url": "https://example.org/",
        "year": year,
        "payload": payload or {},
        "file": file,
        "series": series,
    }


def build(data, queue=(), today=TODAY, **kwargs):
    return build_worklist(data, list(queue), today, generated=GENERATED, **kwargs)


def items(worklist, reason=None):
    """Return the items without the scout item, optionally only those with a reason."""
    found = [item for item in worklist["items"] if item["reasons"] != ["scout"]]
    if reason is not None:
        found = [item for item in found if reason in item["reasons"]]
    return found


def only(worklist):
    found = items(worklist)
    assert len(found) == 1, found
    return found[0]


def name_in_slot(base, slot, year=None):
    """Return a name whose rotation slot (with year, for TBA entries) is the given weekday."""
    for number in range(1, 200):
        name = f"{base} {number}"
        if rotation_slot(name if year is None else f"{name}|{year}") == slot:
            return name
    raise AssertionError("no name found")


def days_ago(days, time="11:00:00"):
    """Return a deadline the given number of days before TODAY.

    11:00 falls on the same UTC date in AoE, Tokyo, Los Angeles and UTC+5, so days_since is ``days``.
    """
    return f"{TODAY - timedelta(days=days)} {time}"


class TestCleanWatchTitle:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("[Conference] PyCon Greece 2027 - Main", ("PyCon Greece", 2027)),
            ("[conference] PyCon Greece 2027 - CFP", ("PyCon Greece", 2027)),
            ("[CONFERENCE] PyCon Greece 2027 - cfp", ("PyCon Greece", 2027)),
            ("[Conference] PyCon Greece - Main", ("PyCon Greece", None)),
            ("PyCon Greece 2027 - Main", ("PyCon Greece", 2027)),
            ("PyCon Greece", ("PyCon Greece", None)),
            ("PyCon Greece 2027", ("PyCon Greece 2027", None)),
            ("[Conference] Python - Main Track 2027 - Main", ("Python - Main Track", 2027)),
        ],
    )
    def test_strips_prefix_and_suffix(self, title, expected):
        assert clean_watch_title(title) == expected


class TestRouting:
    def test_upcoming_series_goes_to_enricher(self):
        data = dataset([conf("PyCon Example", 2026)])
        signal = queue_item(title="[Conference] PyCon Example 2026 - Main")

        item = only(build(data, [signal]))

        assert item["skill"] == "enricher"
        assert item["reasons"] == ["signal"]
        assert item["conference"] == "PyCon Example"
        assert item["year"] == 2026
        assert item["entry"]["conference"] == "PyCon Example"
        assert item["entry"]["start"] == "2026-12-10"
        assert item["latest_edition"] is None
        assert item["queue_refs"] == [{"file": "queue/example.json", "id": signal["id"]}]
        assert "ambiguous_matches" not in item

    def test_archive_only_series_goes_to_new_year_checker(self):
        data = dataset(archive=[conf("PyCon Example", 2022), conf("PyCon Example", 2023)])

        item = only(build(data, [queue_item(title="[Conference] PyCon Example 2027 - Main")]))

        assert item["skill"] == "new-year-checker"
        assert item["year"] == 2027
        assert item["entry"] is None
        assert item["latest_edition"]["year"] == 2023
        assert item["context"] == {}

    def test_legacy_only_series_goes_to_new_year_checker(self):
        data = dataset(legacy=[conf("PyCon Example", 2015)])

        item = only(build(data, [queue_item(title="PyCon Example")]))

        assert item["skill"] == "new-year-checker"
        assert item["latest_edition"]["year"] == 2015

    def test_unknown_series_goes_to_scouter(self):
        data = dataset([conf("PyCon Example", 2026)])

        item = only(build(data, [queue_item(title="[Conference] PyCon Nowhere 2027 - CFP")]))

        assert item["skill"] == "scouter"
        assert item["conference"] == "PyCon Nowhere"
        assert item["year"] == 2027
        assert item["entry"] is None
        assert item["latest_edition"] is None

    @pytest.mark.parametrize(
        ("existing", "title"),
        [
            (conf("PyCon Example", 2026, alt_name="PyEx"), "[Conference] PyEx 2026 - Main"),
            (conf("PyDay México", 2026), "[Conference] pyday mexico 2026 - Main"),
            (conf("Xtreme Python", 2026), "[Conference] XtremePython 2026 - Main"),
            (conf("Kiwi PyCon", 2026), "[Conference] PyCon NZ 2026 - Main"),
        ],
        ids=["alt_name", "accents-and-case", "whitespace", "titles-mapping"],
    )
    def test_name_matching(self, existing, title):
        item = only(build(dataset([existing]), [queue_item(title=title)]))

        assert item["skill"] == "enricher"
        assert item["conference"] == existing["conference"]

    def test_entry_for_the_item_year(self):
        data = dataset([conf("PyCon Example", 2026), conf("PyCon Example", 2027)])

        with_year = only(build(data, [queue_item(title="PyCon Example 2027 - Main")]))
        without_year = only(build(data, [queue_item(title="PyCon Example")]))

        assert (with_year["year"], with_year["entry"]["year"], with_year["context"]) == (2027, 2027, {})
        assert (without_year["year"], without_year["entry"]["year"], without_year["context"]) == (2026, 2026, {})

    def test_year_from_item_field(self):
        data = dataset([conf("PyCon Example", 2026), conf("PyCon Example", 2027)])

        item = only(build(data, [queue_item(title="PyCon Example", year=2026)]))

        assert item["entry"]["year"] == 2026

    def test_payload_conference_is_matched_before_title(self):
        data = dataset([conf("PyCon Example", 2026)])
        redirect = queue_item(
            "redirect",
            "https://example.org/old",
            source="link-check",
            payload={"conference": "PyCon Example", "year": 2026, "field": "link", "final_url": "x", "status": 301},
        )

        item = only(build(data, [redirect]))

        assert (item["skill"], item["conference"], item["year"]) == ("enricher", "PyCon Example", 2026)

    def test_file_series_is_used_when_title_does_not_match(self):
        data = dataset([conf("PyCon Example", 2026)])

        item = only(build(data, [queue_item(title="Some page title", series="PyCon Example")]))

        assert item["skill"] == "enricher"


class TestQueueYear:
    """Watch titles keep the year of the edition they were created for, so a queue year can be stale."""

    def test_stale_title_year_takes_the_entry_year(self):
        data = dataset([conf("PyCon US", 2027, cfp=days_ago(1))], [conf("PyCon US", 2026)])
        signal = queue_item(title="[Conference] PyCon US 2026 - Main", year=2026)

        item = only(build(data, [signal]))

        assert item["skill"] == "enricher"
        assert item["reasons"] == ["deadline-check", "signal"]
        assert (item["conference"], item["year"], item["entry"]["year"]) == ("PyCon US", 2027, 2027)
        assert item["context"]["queue_year"] == 2026
        assert item["context"]["days_since"] == 1
        assert item["queue_refs"] == [{"file": "queue/example.json", "id": signal["id"]}]

    def test_stale_title_year_merges_into_tba_rotation(self):
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)
        data = dataset([conf(name, 2027, cfp="TBA")], [conf(name, 2026)])

        item = only(build(data, [queue_item(title=f"[Conference] {name} 2026 - Main", year=2026)]))

        assert item["reasons"] == ["signal", "tba-rotation"]
        assert (item["year"], item["entry"]["year"], item["context"]) == (2027, 2027, {"queue_year": 2026})

    def test_stale_title_year_takes_the_next_edition(self):
        data = dataset([conf("PyCon Example", 2026), conf("PyCon Example", 2027)], [conf("PyCon Example", 2025)])

        item = only(build(data, [queue_item(title="[Conference] PyCon Example 2025 - Main")]))

        assert (item["year"], item["entry"]["year"], item["context"]) == (2026, 2026, {"queue_year": 2025})

    def test_yearless_item_takes_the_next_edition(self):
        """An edition starting next week comes before the TBA entry for the year after."""
        data = dataset(
            [
                conf("PyTorch Conference", 2026, start=TODAY + timedelta(days=6), end=TODAY + timedelta(days=7)),
                conf("PyTorch Conference", 2027),
            ],
        )

        item = only(build(data, [queue_item(title="[Conference] PyTorch Conference - Main")]))

        assert (item["year"], item["entry"]["year"], item["context"]) == (2026, 2026, {})

    @pytest.mark.parametrize(("days_since_end", "expected"), [(1, 2027), (0, 2026)])
    def test_ended_edition_is_passed_over(self, days_since_end, expected):
        """An edition that has ended but is not archived yet is not the next one; one ending today is."""
        end = TODAY - timedelta(days=days_since_end)
        data = dataset(
            [conf("PyCon Example", 2026, start=end - timedelta(days=2), end=end), conf("PyCon Example", 2027)],
        )

        item = only(build(data, [queue_item(title="PyCon Example")]))

        assert item["year"] == expected

    def test_newest_when_every_edition_has_ended(self):
        data = dataset(
            [
                conf("PyCon Example", 2025, start=TODAY - timedelta(days=40), end=TODAY - timedelta(days=38)),
                conf("PyCon Example", 2026, start=TODAY - timedelta(days=5), end=TODAY - timedelta(days=3)),
            ],
        )

        item = only(build(data, [queue_item(title="PyCon Example")]))

        assert item["year"] == 2026

    def test_ambiguous_item_keeps_its_queue_year(self):
        data = dataset([conf("PyHEP.dev", 2027, alt_name="PyHEP")], [conf("PyHEP", 2025)])

        item = only(build(data, [queue_item(title="[Conference] PyHEP 2025 - Main")]))

        assert (item["year"], item["entry"], item["context"]) == (2025, None, {})

    @pytest.mark.parametrize("title_year", [2024, 2025])
    def test_known_edition_year_merges_into_stale_series(self, title_year):
        """For the new-year-checker, a year it already has is not the edition to look for."""
        name = name_in_slot("PyCon Stale", TODAY.weekday())
        data = dataset(archive=[conf(name, 2024), conf(name, 2025)])

        item = only(build(data, [queue_item(title=f"[Conference] {name} {title_year} - Main", year=title_year)]))

        assert item["skill"] == "new-year-checker"
        assert item["reasons"] == ["signal", "stale-series"]
        assert item["year"] is None
        assert item["latest_edition"]["year"] == 2025
        assert item["context"] == {"queue_year": title_year, "latest_year": 2025}

    def test_missing_edition_year_is_kept(self):
        data = dataset(archive=[conf("PyCon Example", 2025)])
        candidate = queue_item(
            "candidate",
            "PyCon Example 2026",
            source="pretalx",
            payload={"classification": "MISSING_EDITION", "fields": {"conference": "PyCon Example", "year": 2026}},
        )

        item = only(build(data, [candidate]))

        assert (item["skill"], item["year"], item["context"]) == ("new-year-checker", 2026, {})


class TestKindOverrides:
    @pytest.mark.parametrize("kind", ["question", "redirect", "drift"])
    def test_archive_only_series_still_goes_to_enricher(self, kind):
        data = dataset(archive=[conf("PyCon Example", 2023)])

        item = only(build(data, [queue_item(kind, "PyCon Example")]))

        assert item["skill"] == "enricher"
        assert item["reasons"] == [kind]
        assert item["conference"] == "PyCon Example"
        assert item["entry"] is None

    @pytest.mark.parametrize("kind", ["question", "redirect", "drift"])
    def test_archive_only_series_names_why_entry_is_empty(self, kind):
        data = dataset(archive=[conf("PyCon Example", 2023)])

        item = only(build(data, [queue_item(kind, "PyCon Example")]))

        assert item["context"] == {"no_entry": "no data file holds an edition of this series for this year"}

    @pytest.mark.parametrize("kind", ["question", "redirect", "drift"])
    def test_archived_edition_for_the_year_is_bound(self, kind):
        data = dataset(archive=[conf("PyCon Example", 2023), conf("PyCon Example", 2024)])

        item = only(build(data, [queue_item(kind, "PyCon Example", year=2023)]))

        assert (item["skill"], item["year"], item["context"]) == ("enricher", 2023, {})
        assert (item["entry"]["conference"], item["entry"]["year"]) == ("PyCon Example", 2023)

    @pytest.mark.parametrize("kind", ["question", "redirect", "drift"])
    def test_unknown_series_still_goes_to_enricher(self, kind):
        item = only(build(dataset(), [queue_item(kind, "PyCon Nowhere")]))

        assert item["skill"] == "enricher"
        assert item["context"] == {"no_entry": "no data file holds this series"}

    def test_missing_edition_goes_to_new_year_checker(self):
        data = dataset([conf("PyCon Example", 2026)], [conf("PyCon Example", 2023)])
        candidate = queue_item(
            "candidate",
            "PyCon Exmple 2027",
            source="pretalx",
            payload={
                "classification": "MISSING_EDITION",
                "fields": {"conference": "PyCon Exmple", "year": 2027},
                "matched": {"conference": "PyCon Example", "file": "_data/conferences.yml", "year": 2026, "score": 92},
                "flags": [],
            },
        )

        item = only(build(data, [candidate]))

        assert item["skill"] == "new-year-checker"
        assert item["reasons"] == ["candidate"]
        assert item["conference"] == "PyCon Example"
        assert item["year"] == 2027
        assert item["latest_edition"]["year"] == 2026

    @pytest.mark.parametrize("classification", ["NEW_SERIES", "MAYBE"])
    def test_new_series_and_maybe_go_to_scouter(self, classification):
        data = dataset([conf("PyCon Example", 2026)])
        candidate = queue_item(
            "candidate",
            "PyCon Example",
            payload={"classification": classification, "fields": {"conference": "PyCon Example"}, "matched": None},
        )

        item = only(build(data, [candidate]))

        assert item["skill"] == "scouter"
        assert item["entry"] is None

    def test_registry_goes_to_scouter(self):
        data = dataset([conf("PyCon Example", 2026)])
        registry = queue_item(
            "registry",
            "Registry change",
            source="registry",
            payload={"names": ["PyCon Example"], "change": "removed", "evidence_url": "https://example.org/"},
        )

        item = only(build(data, [registry]))

        assert (item["skill"], item["reasons"], item["conference"]) == ("scouter", ["registry"], "PyCon Example")

    def test_unknown_kind_is_treated_as_signal(self):
        item = only(build(dataset([conf("PyCon Example", 2026)]), [queue_item("mystery", "PyCon Example")]))

        assert (item["skill"], item["reasons"]) == ("enricher", ["signal"])


class TestAmbiguousMatches:
    def test_any_upcoming_match_goes_to_enricher(self):
        data = dataset([conf("PyHEP.dev", 2026, alt_name="PyHEP")], [conf("PyHEP", 2023)])

        item = only(build(data, [queue_item(title="[Conference] PyHEP 2026 - Main")]))

        assert item["skill"] == "enricher"
        assert item["conference"] == "PyHEP"
        assert item["year"] == 2026
        assert item["entry"] is None
        assert item["ambiguous_matches"] == [
            {"conference": "PyHEP", "year": 2023, "file": "_data/archive.yml"},
            {"conference": "PyHEP.dev", "year": 2026, "file": "_data/conferences.yml"},
        ]

    def test_archive_only_matches_go_to_new_year_checker(self):
        data = dataset(archive=[conf("PyCon Old", 2023, alt_name="PyCon Shared"), conf("PyCon Shared", 2022)])

        item = only(build(data, [queue_item(title="PyCon Shared")]))

        assert item["skill"] == "new-year-checker"
        assert [match["conference"] for match in item["ambiguous_matches"]] == ["PyCon Old", "PyCon Shared"]

    def test_unique_name_wins_over_ambiguous_one(self):
        data = dataset([conf("PyHEP.dev", 2026, alt_name="PyHEP")], [conf("PyHEP", 2023)])

        item = only(build(data, [queue_item(title="PyHEP", series="PyHEP.dev")]))

        assert item["conference"] == "PyHEP.dev"
        assert item["entry"]["conference"] == "PyHEP.dev"
        assert "ambiguous_matches" not in item


class TestDeadlineChecks:
    @pytest.mark.parametrize("days", [1, 3, 7])
    def test_aoe(self, days):
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(days))])

        item = only(build(data))

        assert item["skill"] == "enricher"
        assert item["reasons"] == ["deadline-check"]
        assert item["entry"]["conference"] == "PyCon Example"
        assert item["context"] == {
            "effective_deadline": f"{TODAY - timedelta(days=days)}T11:00:00-12:00",
            "deadline_field": "cfp",
            "timezone": "AoE",
            "days_since": days,
        }

    @pytest.mark.parametrize("days", [1, 3, 7])
    def test_explicit_timezone(self, days):
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(days, "12:00:00"), timezone="Asia/Tokyo")])

        item = only(build(data))

        assert item["context"]["effective_deadline"] == f"{TODAY - timedelta(days=days)}T12:00:00+09:00"
        assert item["context"]["timezone"] == "Asia/Tokyo"
        assert item["context"]["days_since"] == days

    @pytest.mark.parametrize("days", [-1, 0, 2, 4, 5, 6, 8, 30])
    @pytest.mark.parametrize("zone", [None, "Asia/Tokyo", "America/Los_Angeles"])
    def test_other_days_are_skipped(self, days, zone):
        fields = {"timezone": zone} if zone else {}
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(days), **fields)])

        assert items(build(data)) == []

    def test_counts_from_the_utc_date(self):
        """00:30 in Tokyo on the 14th is 15:30 UTC on the 13th, so a run on the 14th is one day after."""
        data = dataset([conf("PyCon Example", 2026, cfp="2026-10-14 00:30:00", timezone="Asia/Tokyo")])

        assert only(build(data))["context"]["days_since"] == 1

    def test_aoe_deadline_counts_from_its_utc_date(self):
        """23:59 AoE on the 12th closes at 11:59 UTC on the 13th, one day before the 14th."""
        data = dataset([conf("PyCon Example", 2026, cfp="2026-10-12 23:59:00")])

        assert only(build(data))["context"]["days_since"] == 1

    def test_no_check_while_an_aoe_deadline_is_open(self):
        """23:59 AoE on the 13th closes at 11:59 UTC on the 14th, after a desk run early that day."""
        data = dataset([conf("PyCon Example", 2026, cfp="2026-10-13 23:59:00")])

        assert items(build(data)) == []

    def test_cfp_ext_takes_precedence(self):
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(7), cfp_ext=days_ago(3))])

        item = only(build(data))

        assert item["context"]["deadline_field"] == "cfp_ext"
        assert item["context"]["days_since"] == 3

    def test_cfp_ext_in_future_suppresses_cfp_check(self):
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(1), cfp_ext=days_ago(-5))])

        assert items(build(data)) == []

    def test_tba_cfp_is_not_checked(self):
        data = dataset([conf("PyCon Example", 2026, cfp="TBA", cfp_ext=days_ago(1), start=date(2026, 10, 1))])

        assert items(build(data)) == []

    @pytest.mark.parametrize("value", [str(TODAY - timedelta(days=2)), TODAY - timedelta(days=2)])
    def test_date_only_deadline(self, value):
        """A date-only deadline is 23:59 AoE, which falls on the next UTC date."""
        item = only(build(dataset([conf("PyCon Example", 2026, cfp=value)])))

        assert item["context"]["effective_deadline"] == f"{TODAY - timedelta(days=2)}T23:59:00-12:00"
        assert item["context"]["days_since"] == 1

    def test_utc_offset_timezone(self):
        item = only(build(dataset([conf("PyCon Example", 2026, cfp=days_ago(1), timezone="UTC+5")])))

        assert item["context"]["effective_deadline"].endswith("+05:00")
        assert item["context"]["timezone"] == "UTC+5"

    def test_unknown_timezone_falls_back_to_aoe(self):
        item = only(build(dataset([conf("PyCon Example", 2026, cfp=days_ago(1), timezone="Mars/Olympus")])))

        assert item["context"]["timezone"] == "AoE"
        assert item["context"]["unknown_timezone"] == "Mars/Olympus"

    def test_most_recent_deadline_first(self):
        data = dataset(
            [
                conf("A Conf", 2026, cfp=days_ago(7)),
                conf("B Conf", 2026, cfp=days_ago(1)),
                conf("C Conf", 2026, cfp=days_ago(3)),
                conf("A Conf Two", 2026, cfp=days_ago(1)),
            ],
        )

        assert [item["conference"] for item in items(build(data))] == ["A Conf Two", "B Conf", "C Conf", "A Conf"]


class TestTbaRotation:
    def test_included_on_its_weekday(self):
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)
        data = dataset([conf(name, 2027, cfp="TBA")])

        item = only(build(data))

        assert (item["skill"], item["reasons"], item["conference"], item["year"]) == (
            "enricher",
            ["tba-rotation"],
            name,
            2027,
        )
        assert item["entry"]["cfp"] == "TBA"

    def test_skipped_on_other_weekdays(self):
        name = name_in_slot("PyCon TBA", (TODAY.weekday() + 1) % 7, 2027)

        assert items(build(dataset([conf(name, 2027, cfp="TBA")]))) == []

    def test_once_a_week(self):
        data = dataset([conf("PyCon Example", 2027, cfp="TBA")])
        days = [day for day in range(7) if items(build(data, today=TODAY + timedelta(days=day)))]

        assert len(days) == 1

    @pytest.mark.parametrize("word", ["TBA", "tbd", " Tba "])
    def test_tba_words(self, word):
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)

        assert items(build(dataset([conf(name, 2027, cfp=word)])))

    @pytest.mark.parametrize("word", ["None", "Cancelled", None, "n/a"])
    def test_settled_cfp_is_not_rotated(self, word):
        """None means no public CfP and Cancelled a cancelled edition: no deadline to look for."""
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)
        data = dataset([conf(name, 2027, cfp=word)])

        assert [item for day in range(7) for item in items(build(data, today=TODAY + timedelta(days=day)))] == []

    @pytest.mark.parametrize("start", [TODAY, TODAY - timedelta(days=1)])
    def test_started_event_excluded(self, start):
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2026)
        data = dataset([conf(name, 2026, cfp="TBA", start=start, end=start + timedelta(days=2))])

        assert items(build(data)) == []

    def test_slot_rule(self):
        expected = int(hashlib.sha1(b"PyCon Example|2027", usedforsecurity=False).hexdigest(), 16) % 7

        assert rotation_slot("PyCon Example|2027") == expected


class TestStaleSeries:
    def test_included_on_its_weekday(self):
        name = name_in_slot("PyCon Stale", TODAY.weekday())
        data = dataset(archive=[conf(name, 2024), conf(name, 2025)])

        item = only(build(data))

        assert (item["skill"], item["reasons"], item["conference"], item["year"]) == (
            "new-year-checker",
            ["stale-series"],
            name,
            None,
        )
        assert item["latest_edition"]["year"] == 2025
        assert item["context"] == {"latest_year": 2025}

    def test_once_a_week(self):
        data = dataset(archive=[conf("PyCon Stale", 2025)])
        days = [day for day in range(7) if items(build(data, today=TODAY + timedelta(days=day)))]

        assert len(days) == 1

    def test_respelt_upcoming_edition_tracks_the_series(self):
        data = dataset([conf("XtremePython", 2026)], [conf("Xtreme Python", 2025)])

        for day in range(7):
            assert items(build(data, today=TODAY + timedelta(days=day))) == []

    def test_outside_lookback_skipped(self):
        name = name_in_slot("PyCon Stale", TODAY.weekday())

        assert items(build(dataset(archive=[conf(name, 2023)]))) == []


class TestScout:
    def test_exactly_one_scout_item_last(self):
        worklist = build(dataset([conf("PyCon Example", 2026, cfp=days_ago(1))]))

        scouts = [item for item in worklist["items"] if "scout" in item["reasons"]]
        assert scouts == [worklist["items"][-1]]
        assert scouts[0] == {
            "id": hashlib.sha1(b"scout", usedforsecurity=False).hexdigest(),
            "skill": "scouter",
            "reasons": ["scout"],
            "conference": None,
            "year": None,
            "entry": None,
            "latest_edition": None,
            "queue_refs": [],
            "context": {},
        }

    def test_no_scout(self):
        assert build(dataset(), scout=False)["items"] == []

    def test_scout_not_merged_with_scouter_queue_items(self):
        worklist = build(dataset(), [queue_item(title="PyCon Nowhere")])

        assert [item["reasons"] for item in worklist["items"]] == [["signal"], ["scout"]]


class TestMerging:
    def test_queue_item_merges_into_deadline_check(self):
        data = dataset([conf("PyCon Example", 2026, cfp=days_ago(1))])
        signal = queue_item(title="[Conference] PyCon Example 2026 - CFP")

        item = only(build(data, [signal]))

        assert item["reasons"] == ["deadline-check", "signal"]
        assert item["queue_refs"] == [{"file": "queue/example.json", "id": signal["id"]}]
        assert item["context"]["days_since"] == 1

    def test_items_for_same_series_from_several_files(self):
        first = queue_item(title="PyCon Nowhere", file="queue/a.json")
        second = queue_item("question", "PyCon Nowhere", file="queue/b.json")
        third = queue_item(title="[Conference] PyCon Nowhere - Main", file="queue/c.json")

        worklist = build(dataset(), [first, second, third])

        assert [(item["skill"], item["reasons"], len(item["queue_refs"])) for item in items(worklist)] == [
            ("scouter", ["signal"], 2),
            ("enricher", ["question"], 1),
        ]

    def test_duplicate_refs_collapse(self):
        signal = queue_item(title="PyCon Example")

        item = only(build(dataset([conf("PyCon Example", 2026)]), [signal, dict(signal)]))

        assert len(item["queue_refs"]) == 1

    def test_tba_rotation_merges_into_queue_item(self):
        name = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)
        data = dataset([conf(name, 2027, cfp="TBA")])

        item = only(build(data, [queue_item(title=name)]))

        assert item["reasons"] == ["signal", "tba-rotation"]

    def test_stale_series_merges_with_queue_item(self):
        name = name_in_slot("PyCon Stale", TODAY.weekday())
        data = dataset(archive=[conf(name, 2025)])

        item = only(build(data, [queue_item(title=name)]))

        assert item["skill"] == "new-year-checker"
        assert item["reasons"] == ["signal", "stale-series"]
        assert item["latest_edition"]["year"] == 2025

    def test_different_years_stay_apart(self):
        data = dataset([conf("PyCon Example", 2026), conf("PyCon Example", 2027)])
        signals = [
            queue_item(title="PyCon Example 2027 - Main", received="2026-10-14T06:00:00Z"),
            queue_item(title="PyCon Example 2026 - Main", received="2026-10-13T06:00:00Z"),
        ]

        assert [item["year"] for item in items(build(data, signals))] == [2026, 2027]


class TestOrdering:
    @pytest.fixture()
    def mixed(self):
        tba = name_in_slot("PyCon TBA", TODAY.weekday(), 2027)
        stale = name_in_slot("PyCon Stale", TODAY.weekday())
        data = dataset(
            [
                conf("PyCon Deadline", 2026, cfp=days_ago(3)),
                conf("PyCon Queue", 2026),
                conf(tba, 2027, cfp="TBA"),
            ],
            [conf(stale, 2025)],
        )
        queue = [
            queue_item(title="PyCon Unknown", file="queue/pycon-unknown.json", received="2026-10-13T06:00:00Z"),
            queue_item(title="PyCon Queue", file="queue/pycon-queue.json"),
            queue_item("question", "PyCon Queue", file="queue/pycon-queue.json", received="2026-10-12T06:00:00Z"),
        ]
        return data, queue

    def test_group_order(self, mixed):
        data, queue = mixed

        worklist = build(data, queue)

        assert [item["reasons"] for item in worklist["items"]] == [
            ["deadline-check"],
            ["signal", "question"],
            ["signal"],
            ["tba-rotation"],
            ["stale-series"],
            ["scout"],
        ]
        assert [item["conference"] for item in worklist["items"][1:3]] == ["PyCon Queue", "PyCon Unknown"]
        # Queue items are taken by file, then by time received.
        assert [ref["id"] for ref in worklist["items"][1]["queue_refs"]] == [queue[2]["id"], queue[1]["id"]]

    def test_same_output_whatever_the_queue_order(self, mixed):
        data, queue = mixed
        expected = json.dumps(build(data, queue))

        for order in itertools.permutations(queue):
            assert json.dumps(build(data, order)) == expected

    def test_ids_are_stable_and_distinct(self, mixed):
        data, queue = mixed

        ids = [item["id"] for item in build(data, queue)["items"]]

        assert ids == [item["id"] for item in build(data, queue)["items"]]
        assert len(set(ids)) == len(ids)
        deadline = build(data, queue)["items"][0]
        assert deadline["id"] == hashlib.sha1(b"enricher|PyCon Deadline|2026", usedforsecurity=False).hexdigest()

    def test_document_fields(self, mixed):
        data, queue = mixed

        worklist = build(data, queue)

        assert list(worklist) == ["generated", "today", "items"]
        assert (worklist["generated"], worklist["today"]) == (GENERATED, "2026-10-14")
        for item in worklist["items"]:
            assert list(item)[:9] == [
                "id",
                "skill",
                "reasons",
                "conference",
                "year",
                "entry",
                "latest_edition",
                "queue_refs",
                "context",
            ]

    def test_input_data_is_not_modified(self, mixed):
        data, queue = mixed
        before = json.dumps(data, default=str), json.dumps(queue)

        build(data, queue)

        assert (json.dumps(data, default=str), json.dumps(queue)) == before


def write_queue_file(directory, key, series, queue_items):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    path.write_text(json.dumps({"items": queue_items, "series": series}, indent=2, sort_keys=True), encoding="utf-8")
    return path


def raw_item(number, **fields):
    item = {
        "id": hashlib.sha1(str(number).encode(), usedforsecurity=False).hexdigest(),
        "kind": "signal",
        "payload": {"diff": f"change {number}", "trigger": "website_change", "watch_uuid": None},
        "received": f"2026-10-{1 + number % 14:02d}T06:00:{number % 60:02d}Z",
        "source": "changedetection",
        "title": "[Conference] PyCon Greece 2027 - Main",
        "url": "https://pycon.gr/",
        "year": 2027,
    }
    item.update(fields)
    return item


class TestLoadQueue:
    def test_fifty_items_and_truncated_payload(self, tmp_path):
        fifty = [raw_item(number) for number in range(50)]
        truncated = raw_item(
            99,
            payload={"diff": "x" * 20000, "truncated": True, "trigger": "website_change", "watch_uuid": "abc"},
        )
        write_queue_file(tmp_path / "queue", "pycon-greece", "PyCon Greece", fifty)
        write_queue_file(tmp_path / "queue", "pycon-example", "PyCon Example", [truncated])

        loaded = load_queue(tmp_path)

        assert len(loaded) == 51
        assert loaded[0]["file"] == "queue/pycon-example.json"
        assert loaded[0]["series"] == "PyCon Example"
        assert len(loaded[0]["payload"]["diff"]) == 20000
        assert loaded[0]["payload"]["truncated"] is True
        assert {item["file"] for item in loaded[1:]} == {"queue/pycon-greece.json"}

        item = only(build(dataset(archive=[conf("PyCon Greece", 2023)]), loaded[1:]))
        assert item["skill"] == "new-year-checker"
        assert len(item["queue_refs"]) == 50

    def test_accepts_the_queue_directory_itself(self, tmp_path):
        write_queue_file(tmp_path / "queue", "pycon-greece", "PyCon Greece", [raw_item(1)])

        assert load_queue(tmp_path / "queue") == load_queue(tmp_path)

    def test_bad_files_are_skipped(self, tmp_path, capsys):
        queue = tmp_path / "queue"
        write_queue_file(queue, "good", "PyCon Greece", [raw_item(1), "not an item"])
        (queue / "broken.json").write_text('{"items": [', encoding="utf-8")
        (queue / "list.json").write_text("[]", encoding="utf-8")
        (queue / "README.md").write_text("not json", encoding="utf-8")

        loaded = load_queue(tmp_path)

        assert [item["file"] for item in loaded] == ["queue/good.json"]
        errors = capsys.readouterr().err
        assert "broken.json" in errors
        assert "list.json" in errors

    def test_empty_directory(self, tmp_path):
        assert load_queue(tmp_path) == []


class TestCli:
    @pytest.fixture()
    def repo(self, tmp_path):
        data = tmp_path / "repo" / "_data"
        data.mkdir(parents=True)
        (data / "conferences.yml").write_text(
            yaml.safe_dump([conf("PyCon Example", 2026, cfp=days_ago(7))]),
            encoding="utf-8",
        )
        (data / "archive.yml").write_text(yaml.safe_dump([conf("PyCon Greece", 2023)]), encoding="utf-8")
        write_queue_file(tmp_path / "desk-queue" / "queue", "pycon-greece", "PyCon Greece", [raw_item(1)])
        return tmp_path

    def run(self, capsys, *args):
        main(list(args))
        return json.loads(capsys.readouterr().out)

    def test_full_run(self, repo, capsys):
        worklist = self.run(
            capsys,
            "--base",
            str(repo / "repo"),
            "--queue-dir",
            str(repo / "desk-queue"),
            "--today",
            "2026-10-14",
        )

        assert worklist["today"] == "2026-10-14"
        assert [(item["skill"], item["reasons"]) for item in worklist["items"]] == [
            ("enricher", ["deadline-check"]),
            ("new-year-checker", ["signal"]),
            ("scouter", ["scout"]),
        ]
        assert worklist["items"][1]["queue_refs"] == [{"file": "queue/pycon-greece.json", "id": raw_item(1)["id"]}]

    def test_no_scout_and_no_queue(self, repo, capsys):
        worklist = self.run(capsys, "--base", str(repo / "repo"), "--today", "2026-10-14", "--no-scout")

        assert [item["reasons"] for item in worklist["items"]] == [["deadline-check"]]

    @freeze_time("2026-10-14 06:00:00")
    def test_defaults_to_utc_today(self, repo, capsys):
        worklist = self.run(capsys, "--base", str(repo / "repo"))

        assert (worklist["generated"], worklist["today"]) == ("2026-10-14T06:00:00Z", "2026-10-14")

    def test_missing_queue_dir_is_an_error(self, repo):
        with pytest.raises(SystemExit):
            main(["--base", str(repo / "repo"), "--queue-dir", str(repo / "absent")])

    def test_never_opens_a_socket(self, repo, capsys, monkeypatch):
        def refuse(*args, **kwargs):
            raise AssertionError("network access")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)

        worklist = self.run(
            capsys,
            "--base",
            str(repo / "repo"),
            "--queue-dir",
            str(repo / "desk-queue"),
            "--today",
            "2026-10-14",
        )

        assert len(worklist["items"]) == 3
