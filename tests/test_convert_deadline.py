"""Tests for convert_deadline: a CfP deadline re-expressed in another zone at the same instant."""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from convert_deadline import convert
from convert_deadline import main


class TestConvert:
    def test_aoe_to_los_angeles_in_summer_time(self):
        # 23:59 AoE (UTC-12) is 11:59 UTC the next day, 04:59 PDT (UTC-7)
        assert convert("2026-10-26 23:59:00", "AoE", "America/Los_Angeles") == "2026-10-27 04:59:00"

    def test_aoe_to_los_angeles_in_winter_time(self):
        # After the November change PST is UTC-8
        assert convert("2026-11-09 23:59:00", "AoE", "America/Los_Angeles") == "2026-11-10 03:59:00"

    def test_empty_zone_means_aoe(self):
        assert convert("2026-01-01 00:00:00", "", "UTC") == convert("2026-01-01 00:00:00", "AoE", "UTC")

    def test_into_aoe(self):
        assert convert("2026-06-01 12:00:00", "UTC", "AoE") == "2026-06-01 00:00:00"

    def test_same_zone_is_unchanged(self):
        assert convert("2026-05-08 23:59:00", "America/Santiago", "America/Santiago") == "2026-05-08 23:59:00"

    def test_round_trip(self):
        there = convert("2026-03-29 01:30:00", "Europe/Berlin", "Asia/Tokyo")
        assert convert(there, "Asia/Tokyo", "Europe/Berlin") == "2026-03-29 01:30:00"

    @pytest.mark.parametrize("deadline", ["2026-10-26", "TBA", "2026-10-26T23:59:00"])
    def test_refuses_a_deadline_in_another_format(self, deadline):
        with pytest.raises(ValueError, match="does not match format"):
            convert(deadline, "UTC", "UTC")

    @pytest.mark.parametrize("zone", ["Mars/Olympus", "CET/Nowhere", "../etc/passwd"])
    def test_refuses_an_unknown_zone(self, zone):
        with pytest.raises(ValueError, match="not an IANA time zone"):
            convert("2026-10-26 23:59:00", zone, "UTC")


class TestCommandLine:
    def test_prints_the_converted_deadline(self, capsys):
        assert main(["2026-10-26 23:59:00", "--from", "AoE", "--to", "America/Los_Angeles"]) == 0
        assert capsys.readouterr().out == "2026-10-27 04:59:00\n"

    def test_unknown_zone_exits_2(self, capsys):
        assert main(["2026-10-26 23:59:00", "--from", "AoE", "--to", "Mars/Olympus"]) == 2
        assert "not an IANA time zone" in capsys.readouterr().err
