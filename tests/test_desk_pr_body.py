"""Tests for desk_pr_body: the desk's write of the rolling PR body, which keeps the writers' part."""

import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import desk_pr_body
from desk_pr_body import MARKER
from desk_pr_body import splice
from desk_pr_body import writers_part

DESK = "Desk last ran: 2026-10-14 06:00 UTC, model claude-opus-5-5, 3 checked, 1 changed\n\n### Evidence\n"
WRITERS = (
    "## 🐍 Automated Conference Updates\n\n"
    "| Conference | Commit | Date |\n"
    "|------------|--------|------|\n"
    "| 📊 Canonical sources | [abc1234](https://github.com/x/y/commit/abc1234) | 2026-10-13 |\n"
    "<!-- END_UPDATES -->"
)
ROW = "| TBA Enrichment | [def5678](https://github.com/x/y/commit/def5678) | 2026-10-14 |\n"


def body(desk=DESK, writers=WRITERS):
    return f"{desk.rstrip()}\n{MARKER}\n{writers}"


class TestWritersPart:
    def test_returns_text_after_the_marker_line(self):
        assert writers_part(body()) == WRITERS

    def test_none_without_a_marker_line(self):
        assert writers_part(WRITERS) is None

    def test_marker_inside_a_line_is_not_a_marker_line(self):
        assert writers_part(f"see {MARKER} here\n{WRITERS}") is None

    def test_marker_line_may_carry_spaces_and_a_carriage_return(self):
        assert writers_part(f"desk\r\n  {MARKER}\t\r\nrest\r\n") == "rest\r\n"

    def test_marker_as_last_line_leaves_nothing(self):
        assert writers_part(f"desk\n{MARKER}") == ""
        assert writers_part(f"desk\n{MARKER}\n") == ""

    def test_marker_as_first_line(self):
        assert writers_part(f"{MARKER}\nrest") == "rest"


class TestSplice:
    def test_replaces_the_desk_part_and_keeps_the_writers_part(self):
        new_desk = "Desk last ran: 2026-10-15 06:00 UTC\n"
        assert splice(new_desk, body()) == f"Desk last ran: 2026-10-15 06:00 UTC\n{MARKER}\n{WRITERS}"

    def test_keeps_a_row_a_writer_added_after_the_desk_read_the_body(self):
        """The race the CLI closes: the body the splice sees already holds the writer's new row."""
        with_row = WRITERS.replace("<!-- END_UPDATES -->", ROW + "<!-- END_UPDATES -->")
        result = splice("new desk part", body(writers=with_row))
        assert result.endswith(f"\n{MARKER}\n{with_row}")
        assert ROW in result

    def test_keeps_the_writers_part_byte_for_byte(self):
        writers = "line one\r\nline two  \n\n\n  indented\t\n\u00a0\u2028odd\n\n"
        assert splice("desk", body(writers=writers)) == f"desk\n{MARKER}\n{writers}"

    def test_trims_trailing_whitespace_of_the_desk_part_only(self):
        assert splice("  desk\n\n \t\n", body()) == f"  desk\n{MARKER}\n{WRITERS}"

    def test_body_without_a_marker_follows_the_marker_whole(self):
        assert splice("desk", WRITERS) == f"desk\n{MARKER}\n{WRITERS}"

    def test_empty_body(self):
        assert splice("desk", "") == f"desk\n{MARKER}\n"

    def test_only_the_first_marker_line_splits(self):
        current = f"old desk\n{MARKER}\nwriters\n{MARKER}\nmore writers\n"
        assert splice("desk", current) == f"desk\n{MARKER}\nwriters\n{MARKER}\nmore writers\n"

    def test_old_desk_part_is_dropped(self):
        result = splice("new", body(desk="old ledger rows\n| a | b |\n"))
        assert "old ledger rows" not in result

    def test_refuses_a_desk_part_with_the_marker(self):
        with pytest.raises(ValueError, match="DESK_END"):
            splice(f"desk\n{MARKER}\n", body())

    def test_is_idempotent(self):
        once = splice(DESK, body(desk="old"))
        assert splice(DESK, once) == once

    def test_second_splice_keeps_what_the_first_kept(self):
        first = splice("first", WRITERS)
        assert splice("second", first) == f"second\n{MARKER}\n{WRITERS}"

    @given(
        desk=st.text().filter(lambda text: MARKER not in text),
        before=st.text().filter(lambda text: MARKER not in text),
        writers=st.text(),
    )
    def test_any_writers_part_survives(self, desk, before, writers):
        current = f"{before}\n{MARKER}\n{writers}"
        result = splice(desk, current)
        assert result == f"{desk.rstrip()}\n{MARKER}\n{writers}"
        assert writers_part(result) == writers

    @given(desk=st.text().filter(lambda text: MARKER not in text), current=st.text())
    def test_result_always_starts_with_the_desk_part_and_one_marker_line(self, desk, current):
        result = splice(desk, current)
        head = f"{desk.rstrip()}\n{MARKER}\n"
        assert result.startswith(head)
        rest = writers_part(current)
        assert result[len(head) :] == (current if rest is None else rest)


class FakeGh:
    """Stand in for subprocess.run, answering the body read and recording the PATCH."""

    def __init__(self, body_output="", read_code=0, patch_code=0):
        self.body_output = body_output
        self.read_code = read_code
        self.patch_code = patch_code
        self.calls = []
        self.patched = None
        self.patch_file = None

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if "PATCH" in args:
            field = args[-1]
            assert field.startswith("body=@")
            self.patch_file = Path(field.removeprefix("body=@"))
            self.patched = self.patch_file.read_bytes().decode("utf-8")
            code, stdout = self.patch_code, '{"number": 7}'
        else:
            code, stdout = self.read_code, self.body_output
        if code:
            raise desk_pr_body.subprocess.CalledProcessError(code, args, output="", stderr="HTTP 404: Not Found")
        return desk_pr_body.subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")


@pytest.fixture()
def gh(monkeypatch):
    """Install a FakeGh and a gh on PATH; set its fields before running the CLI."""
    fake = FakeGh()
    monkeypatch.setattr(desk_pr_body.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(desk_pr_body.subprocess, "run", fake)
    return fake


@pytest.fixture()
def desk_file(tmp_path):
    path = tmp_path / "desk.md"
    path.write_text(DESK, encoding="utf-8")
    return path


class TestCommandLine:
    def test_reads_splices_and_patches(self, gh, desk_file, capsys):
        gh.body_output = body(desk="old ledger") + "\n"

        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 0

        assert gh.calls[0] == ["/usr/bin/gh", "api", "repos/JesperDramsch/python-deadlines/pulls/7", "--jq", ".body"]
        assert gh.calls[1][:6] == [
            "/usr/bin/gh",
            "api",
            "-X",
            "PATCH",
            "repos/JesperDramsch/python-deadlines/pulls/7",
            "-F",
        ]
        assert len(gh.calls) == 2
        assert gh.patched == body()
        assert not gh.patch_file.exists()
        assert "updated the body of JesperDramsch/python-deadlines#7" in capsys.readouterr().out

    def test_strips_only_the_newline_gh_adds(self, gh, desk_file):
        gh.body_output = f"old\n{MARKER}\nrows\n\n" + "\n"
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 0
        assert gh.patched == f"{DESK.rstrip()}\n{MARKER}\nrows\n\n"

    def test_null_body(self, gh, desk_file):
        gh.body_output = "\n"
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 0
        assert gh.patched == f"{DESK.rstrip()}\n{MARKER}\n"

    def test_body_a_writer_opened_gets_the_desk_part_above_it(self, gh, desk_file):
        gh.body_output = WRITERS + "\n"
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 0
        assert gh.patched == body()

    def test_print_writes_the_body_and_does_not_patch(self, gh, desk_file, capsys):
        gh.body_output = body(desk="old ledger") + "\n"

        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file), "--print"]) == 0

        assert len(gh.calls) == 1
        assert capsys.readouterr().out == body()

    def test_repo_option(self, gh, desk_file):
        gh.body_output = "\n"
        assert desk_pr_body.main(["--pr", "12", "--desk", str(desk_file), "--repo", "someone/fork"]) == 0
        assert gh.calls[0][2] == "repos/someone/fork/pulls/12"
        assert gh.calls[1][4] == "repos/someone/fork/pulls/12"

    def test_refuses_a_desk_file_with_the_marker(self, gh, tmp_path, capsys):
        path = tmp_path / "desk.md"
        path.write_text(f"ledger\n{MARKER}\nwriters\n", encoding="utf-8")

        assert desk_pr_body.main(["--pr", "7", "--desk", str(path)]) == 2

        assert gh.calls == []
        assert "refusing" in capsys.readouterr().err

    def test_missing_desk_file(self, gh, tmp_path, capsys):
        assert desk_pr_body.main(["--pr", "7", "--desk", str(tmp_path / "absent.md")]) == 2
        assert gh.calls == []
        assert "cannot read" in capsys.readouterr().err

    def test_pr_must_be_positive(self, gh, desk_file):
        assert desk_pr_body.main(["--pr", "0", "--desk", str(desk_file)]) == 2
        assert gh.calls == []

    def test_failed_read_does_not_patch(self, gh, desk_file, capsys):
        gh.read_code = 1
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 1
        assert len(gh.calls) == 1
        assert "HTTP 404" in capsys.readouterr().err

    def test_failed_patch_exits_1_and_removes_the_file(self, gh, desk_file, capsys):
        gh.body_output = "\n"
        gh.patch_code = 1
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 1
        assert not gh.patch_file.exists()
        assert "failed" in capsys.readouterr().err

    def test_gh_not_on_path(self, monkeypatch, desk_file, capsys):
        calls = []
        monkeypatch.setattr(desk_pr_body.shutil, "which", lambda name: None)
        monkeypatch.setattr(desk_pr_body.subprocess, "run", lambda *args, **kwargs: calls.append(args))
        assert desk_pr_body.main(["--pr", "7", "--desk", str(desk_file)]) == 1
        assert calls == []
        assert "gh is not on PATH" in capsys.readouterr().err

    def test_body_keeps_non_ascii_text(self, gh, tmp_path):
        path = tmp_path / "desk.md"
        path.write_text("PyCon México: cfp_ext\n", encoding="utf-8")
        gh.body_output = f"old\n{MARKER}\n| 📊 python-organizers | x | 2026-10-14 |\n" + "\n"
        assert desk_pr_body.main(["--pr", "7", "--desk", str(path)]) == 0
        assert gh.patched == f"PyCon México: cfp_ext\n{MARKER}\n| 📊 python-organizers | x | 2026-10-14 |\n"
