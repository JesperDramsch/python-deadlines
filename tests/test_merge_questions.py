"""Tests for merge questions handed to the desk queue when no one can answer them.

In CI the merge has no terminal, so query_yes_no keeps the default answer. When
the caller says what the question is about, the question is also recorded and,
with DESK_QUEUE_OUT set, written as a JSON line for the desk queue.
"""

import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import normalise_record
from tidy_conf import utils as tidy_utils
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import merge_conferences
from tidy_conf.utils import query_yes_no


@pytest.fixture()
def no_terminal(monkeypatch, tmp_path):
    """Run without a terminal, with a fresh record list and a queue file."""
    monkeypatch.setattr(tidy_utils.sys, "stdin", io.StringIO())
    monkeypatch.setattr(tidy_utils, "QUESTION_RECORDS", [])
    out = tmp_path / "questions.jsonl"
    monkeypatch.setenv("DESK_QUEUE_OUT", str(out))
    return out


def read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def frame(name, place, link="https://example-conf.org/"):
    return pd.DataFrame(
        {
            "conference": [name],
            "year": [2027],
            "cfp": ["2027-01-06 23:59:00"],
            "link": [link],
            "place": [place],
            "start": ["2027-06-01"],
            "end": ["2027-06-03"],
        },
    )


SCHEMA = ["conference", "year", "cfp", "link", "place", "start", "end", "sub"]


class TestQueryYesNo:
    def test_records_the_question_with_its_default(self, no_terminal):
        context = {
            "conference": "Example Conf",
            "year": 2027,
            "field": "place",
            "yaml_value": "Vienna, Austria",
            "remote_value": "Graz, Austria",
            "source_name": "python.org",
            "url": "https://example-conf.org/",
        }
        assert query_yes_no("Prefer Graz?", context=context) is False
        (record,) = read_lines(no_terminal)
        assert record == tidy_utils.QUESTION_RECORDS[0]
        assert record["source"] == "canonical-import"
        assert record["kind"] == "question"
        assert record["title"] == "Example Conf"
        assert record["year"] == 2027
        assert record["url"] == "https://example-conf.org/"
        assert record["payload"] == {
            "question": "Prefer Graz?",
            "conference": "Example Conf",
            "year": 2027,
            "field": "place",
            "yaml_value": "Vienna, Austria",
            "remote_value": "Graz, Austria",
            "default_answer": False,
            "source_name": "python.org",
        }
        assert normalise_record(record)["id"]

    def test_yes_default_is_recorded(self, no_terminal):
        assert query_yes_no("Go on?", default="yes", context={"conference": "Example Conf"}) is True
        assert read_lines(no_terminal)[0]["payload"]["default_answer"] is True

    def test_without_context_nothing_is_recorded(self, no_terminal):
        assert query_yes_no("Prefer Graz?") is False
        assert read_lines(no_terminal) == []
        assert tidy_utils.QUESTION_RECORDS == []

    def test_empty_values_become_null(self, no_terminal):
        query_yes_no("Fill it?", context={"conference": "Example Conf", "yaml_value": float("nan")})
        payload = read_lines(no_terminal)[0]["payload"]
        assert payload["yaml_value"] is None
        assert payload["remote_value"] is None

    def test_without_queue_file_the_record_is_kept_in_memory(self, no_terminal, monkeypatch):
        monkeypatch.delenv("DESK_QUEUE_OUT")
        query_yes_no("Prefer Graz?", context={"conference": "Example Conf"})
        assert not no_terminal.exists()
        assert len(tidy_utils.QUESTION_RECORDS) == 1


class TestMergeQuestions:
    def test_conflicting_place_is_queued_and_yaml_kept(self, no_terminal, mock_title_mappings):
        df_yml = frame("Example Summit", "Vienna, Austria")
        df_remote = frame("Example Summit", "Graz, Austria")
        df_matched, df_remote_processed, _ = fuzzy_match(df_yml, df_remote, source_name="python.org")
        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr("tidy_conf.interactive_merge.get_schema", lambda: pd.DataFrame(columns=SCHEMA))
            result = merge_conferences(df_matched, df_remote_processed, source_name="python.org")

        assert result["place"].iloc[0] == "Vienna, Austria"
        questions = [record for record in read_lines(no_terminal) if record["payload"]["field"] == "place"]
        assert len(questions) == 1
        payload = questions[0]["payload"]
        assert payload["conference"] == "Example Summit"
        assert payload["year"] == 2027
        assert payload["yaml_value"] == "Vienna, Austria"
        assert payload["remote_value"] == "Graz, Austria"
        assert payload["source_name"] == "python.org"
        assert questions[0]["url"] == "https://example-conf.org/"

    def test_fuzzy_match_question_is_queued(self, no_terminal, mock_title_mappings):
        df_yml = frame("Example Python Summit", "Vienna, Austria")
        df_remote = frame("Example Python Sumit", "Vienna, Austria")
        fuzzy_match(df_yml, df_remote, source_name="python-organizers")

        (record,) = read_lines(no_terminal)
        assert record["payload"]["field"] == "conference"
        assert record["payload"]["yaml_value"] == "Example Python Summit"
        assert record["payload"]["remote_value"] == "Example Python Sumit"
        assert record["payload"]["source_name"] == "python-organizers"
        assert record["year"] == 2027

    def test_agreeing_sources_ask_nothing(self, no_terminal, mock_title_mappings):
        df_matched, df_remote_processed, _ = fuzzy_match(
            frame("Example Summit", "Vienna, Austria"),
            frame("Example Summit", "Vienna, Austria"),
        )
        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr("tidy_conf.interactive_merge.get_schema", lambda: pd.DataFrame(columns=SCHEMA))
            merge_conferences(df_matched, df_remote_processed)
        assert read_lines(no_terminal) == []
