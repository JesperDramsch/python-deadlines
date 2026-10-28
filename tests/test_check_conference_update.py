"""Tests for the queue record that check-conference-update.yml builds from a changedetection dispatch.

The script is read from the workflow file itself, so the test runs what CI runs.
"""

import json
import runpy
import sys
from pathlib import Path

import pytest
import yaml
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from desk_queue import normalise_record

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "check-conference-update.yml"


def build_script() -> str:
    """Return the Python the "Build the queue record" step runs."""
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["queue"]["steps"]
    run = next(step["run"] for step in steps if step.get("name") == "Build the queue record")
    return run.split("<< 'BUILD'\n", 1)[1].rsplit("BUILD", 1)[0]


@pytest.fixture()
def dispatch(tmp_path, monkeypatch):
    """Run the build script for one repository_dispatch and return the record it writes."""
    script = tmp_path / "build.py"
    script.write_text(build_script(), encoding="utf-8")

    def run(action, payload):
        event = tmp_path / "event.json"
        event.write_text(json.dumps({"action": action, "client_payload": payload}), encoding="utf-8")
        records, output, summary = tmp_path / "records.jsonl", tmp_path / "output", tmp_path / "summary"
        monkeypatch.chdir(ROOT)
        monkeypatch.setenv("GITHUB_EVENT_NAME", "repository_dispatch")
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
        monkeypatch.setenv("RECORDS", str(records))
        monkeypatch.setenv("GITHUB_OUTPUT", str(output))
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        runpy.run_path(str(script), run_name="__main__")
        return json.loads(records.read_text(encoding="utf-8")), output.read_text(encoding="utf-8")

    return run


PAYLOAD = {
    "url": "https://{% now 'utc' + 'months=3', '%Y' %}.pycon.ie/",
    "title": "PyCon Ireland 2026 - Main",
    "watch_uuid": "e20815ae",
    "diff": "+ Call for proposals open",
}


@freeze_time("2026-10-28")
class TestDispatch:
    def test_conference_change_queues_a_signal_with_the_fetched_url(self, dispatch):
        record, output = dispatch("conference-change", PAYLOAD)
        assert record["kind"] == "signal"
        assert record["url"] == "https://2027.pycon.ie/"
        assert record["year"] == 2026
        assert "registry" not in record["payload"]
        assert "series=PyCon Ireland" in output

    def test_listing_change_queues_a_registry_item(self, dispatch):
        listing = {
            "url": "https://pydata.org/upcoming-events/",
            "title": "PyData Upcoming",
            "watch_uuid": "abc",
            "diff": "+ PyData Lagos 2027",
        }
        record, _ = dispatch("listing-change", listing)
        assert record["source"] == "changedetection"
        assert record["kind"] == "registry"
        assert record["payload"] == {
            "diff": "+ PyData Lagos 2027",
            "watch_uuid": "abc",
            "trigger": "website_change",
            "registry": "listing",
        }

    @pytest.mark.parametrize("action", ["conference-change", "listing-change"])
    def test_the_queue_accepts_both(self, dispatch, action):
        record, _ = dispatch(action, PAYLOAD)
        assert normalise_record(record)["kind"] == record["kind"]

    def test_both_dispatch_types_trigger_the_workflow(self):
        # PyYAML reads the bare key `on` as True
        triggers = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))[True]
        assert triggers["repository_dispatch"]["types"] == ["conference-change", "listing-change"]
