"""Tests for which conferences the TBA enrichment visits."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from enrich_tba import find_tba_conferences


def write_conferences(path, cfps):
    entries = [
        {"conference": f"Conf {index}", "year": 2027, "cfp": cfp, "link": "https://example.org/"}
        for index, cfp in enumerate(cfps)
    ]
    path.write_text(yaml.safe_dump(entries), encoding="utf-8")
    return path


@pytest.mark.parametrize("cfp", ["TBA", "tbd", "None", None, "n/a"])
def test_conferences_without_a_dated_cfp_are_visited(tmp_path, cfp):
    path = write_conferences(tmp_path / "conferences.yml", [cfp])

    assert [conf["conference"] for conf in find_tba_conferences(path)] == ["Conf 0"]


@pytest.mark.parametrize("cfp", ["Cancelled", "cancelled", "2027-03-01 23:59:00"])
def test_cancelled_and_dated_conferences_are_left_out(tmp_path, cfp):
    path = write_conferences(tmp_path / "conferences.yml", [cfp])

    assert find_tba_conferences(path) == []
