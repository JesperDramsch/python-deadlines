"""Tests for desk_pr_body: the writers' blocks of the rolling PR body."""

import io
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import desk_pr_body
from desk_pr_body import BLOCKS
from desk_pr_body import WRITABLE
from desk_pr_body import describe
from desk_pr_body import parse
from desk_pr_body import render
from desk_pr_body import update

HEAD = "Desk last ran: 2026-10-31 01:22 UTC, model claude-opus-5-5, 3 checked, 1 committed, 1 needs you"
OLD_BODY = (
    "Desk last ran: 2026-10-28 01:22 UTC, model claude-opus-5-5, 27 checked, 11 changed\n\n"
    "### Evidence\n\n<!-- DESK_END -->\n"
    "## 🐍 Automated Conference Updates\n\n"
    "| Conference | Commit | Date |\n|------------|--------|------|\n"
    "| 📊 Canonical sources | [abc1234](https://github.com/x/y/commit/abc1234) | 2026-10-13 |\n"
    "<!-- REVIEW_ITEMS -->\n- [ ] ⚠️ North Bay Python 2027: bluesky differs\n<!-- END_REVIEW_ITEMS -->\n"
    "<!-- END_UPDATES -->"
)
# Content a block can hold: no line of it may be a block marker
block_text = st.text().filter(lambda text: not any(desk_pr_body.MARKER_LINE.match(line) for line in text.splitlines()))


class TestParse:
    def test_empty_body_has_no_blocks(self):
        assert parse("") == {}

    def test_body_before_the_layout_is_kept_whole_as_legacy(self):
        assert parse(OLD_BODY) == {"LEGACY": OLD_BODY.strip()}

    def test_old_markers_are_not_blocks(self):
        assert "DESK_END" not in parse(render({"HEAD:desk": HEAD, "LEGACY": OLD_BODY}))

    def test_round_trip(self):
        blocks = {"HEAD:desk": HEAD, "NEEDS:enrich": "- [ ] a\n- [x] b", "COMMITTED:canonical": "- line"}
        assert parse(render(blocks)) == blocks

    def test_unknown_and_unterminated_markers_are_layout_text(self):
        body = render({"HEAD:desk": HEAD}) + "<!-- NEEDS:other -->\nx\n<!-- /NEEDS:other -->\n<!-- MORE:desk -->\n"
        assert parse(body) == {"HEAD:desk": HEAD}

    def test_markers_tolerate_spaces_and_carriage_returns(self):
        body = "  <!-- HEAD:desk -->\t\r\nhead\r\n<!-- /HEAD:desk -->\r\n"
        assert parse(body) == {"HEAD:desk": "head"}

    def test_a_repeated_block_keeps_its_first_copy(self):
        body = render({"HEAD:desk": "first"}) + "<!-- HEAD:desk -->\nsecond\n<!-- /HEAD:desk -->\n"
        assert parse(body)["HEAD:desk"] == "first"


class TestRender:
    def test_skeleton_has_every_block_and_empty_states(self):
        skeleton = render({})
        for name in BLOCKS[:-1]:
            assert f"<!-- {name} -->" in skeleton
        assert "LEGACY" not in skeleton
        assert "Nothing waiting." in skeleton
        assert "Nothing yet." in skeleton
        assert "has not run on this PR yet" in skeleton

    def test_empty_states_go_once_a_block_has_content(self):
        body = render({"HEAD:desk": HEAD, "NEEDS:canonical": "- [ ] x", "COMMITTED:enrich": "- y"})
        assert "Nothing waiting." not in body
        assert "Nothing yet." not in body
        assert "has not run" not in body

    def test_sections_come_in_order(self):
        body = render({"HEAD:desk": HEAD, "LEGACY": "old"})
        order = ["<!-- HEAD:desk -->", "## Needs you", "## Committed", "<!-- MORE:desk -->", "<!-- LEGACY -->"]
        positions = [body.index(mark) for mark in order]
        assert positions == sorted(positions)

    def test_legacy_is_folded(self):
        body = render({"LEGACY": "old"})
        assert body.index("<details>") < body.index("<!-- LEGACY -->") < body.index("</details>")


class TestUpdate:
    def test_set_replaces_only_its_block(self):
        body = render({"HEAD:desk": HEAD, "NEEDS:enrich": "- [ ] keep"})
        result = parse(update(body, "NEEDS:desk", "- [ ] new"))
        assert result == {"HEAD:desk": HEAD, "NEEDS:enrich": "- [ ] keep", "NEEDS:desk": "- [ ] new"}

    def test_append_adds_below(self):
        body = render({"HEAD:desk": HEAD, "COMMITTED:canonical": "- one"})
        result = parse(update(body, "COMMITTED:canonical", "- two\n", append=True))
        assert result["COMMITTED:canonical"] == "- one\n- two"

    def test_append_to_an_empty_block(self):
        assert parse(update(render({}), "COMMITTED:enrich", "- one", append=True))["COMMITTED:enrich"] == "- one"

    def test_a_ticked_box_survives_another_writers_update(self):
        body = render({"HEAD:desk": HEAD, "NEEDS:desk": "- [x] PyCascades: take pretalx\n- [ ] FOSDEM"})
        assert parse(update(body, "COMMITTED:canonical", "- c", append=True))["NEEDS:desk"].startswith("- [x]")

    def test_first_update_of_an_old_body_keeps_it_as_legacy(self):
        result = parse(update(OLD_BODY, "HEAD:desk", HEAD))
        assert result == {"HEAD:desk": HEAD, "LEGACY": OLD_BODY.strip()}

    def test_a_writer_before_the_desk_keeps_the_old_body_too(self):
        # An Actions writer may be first to write after the layout lands; HEAD:desk then exists, empty
        once = update(OLD_BODY, "COMMITTED:canonical", "- c", append=True)
        assert parse(once)["LEGACY"] == OLD_BODY.strip()
        assert parse(update(once, "HEAD:desk", HEAD))["LEGACY"] == OLD_BODY.strip()

    def test_refuses_legacy_and_unknown_blocks(self):
        for name in ("LEGACY", "NEEDS:other", "DESK_END"):
            with pytest.raises(ValueError, match="not a writable block"):
                update(render({}), name, "x")

    def test_refuses_content_with_a_marker_line(self):
        with pytest.raises(ValueError, match="marker line"):
            update(render({}), "NEEDS:desk", "- [ ] x\n<!-- /NEEDS:desk -->\n<!-- HEAD:desk -->")

    def test_marker_text_inside_a_line_is_fine(self):
        assert parse(update(render({}), "MORE:desk", "see <!-- HEAD:desk --> here"))["MORE:desk"] == (
            "see <!-- HEAD:desk --> here"
        )

    def test_is_idempotent(self):
        once = update(OLD_BODY, "HEAD:desk", HEAD)
        assert update(once, "HEAD:desk", HEAD) == once

    @given(content=block_text, other=block_text, name=st.sampled_from(WRITABLE))
    def test_any_content_round_trips_and_leaves_other_blocks(self, content, other, name):
        keep = "NEEDS:canonical" if name != "NEEDS:canonical" else "NEEDS:enrich"
        body = render({"HEAD:desk": HEAD, keep: other.strip("\r\n")})
        result = parse(update(body, name, content))
        assert result.get(name, "") == content.strip("\r\n")
        if name != "HEAD:desk":
            assert result.get(keep, "") == other.strip("\r\n")


class TestDescribe:
    def test_names_added_removed_and_changed_fields(self):
        before = {("A", 2026): {"cfp": "TBA", "location": [1]}, ("B", 2025): {"cfp": "x"}}
        after = {("A", 2026): {"cfp": "2026-01-01 23:59:00", "coc": "u", "location": [2]}, ("C", 2027): {}}
        assert describe(before, after) == ["A 2026 (cfp, coc)", "B 2025 (removed)", "C 2027 (added)"]

    def test_an_unchanged_or_moved_entry_is_not_named(self):
        entry = {("A", 2026): {"cfp": "TBA"}}
        assert describe(entry, dict(entry)) == []


class FakeTools:
    """Stand in for subprocess.run: answer the body read and record the PATCH, as bytes like the real one."""

    def __init__(self, body=""):
        self.body = body
        self.read_code = 0
        self.patch_code = 0
        self.calls = []
        self.patched = None

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        assert "text" not in kwargs
        if "PATCH" in args:
            self.patched = Path(args[args.index("-F") + 1].removeprefix("body=@")).read_bytes().decode("utf-8")
            code, stdout = self.patch_code, b""
        else:
            code, stdout = self.read_code, f"{self.body}\n".encode()
        if code:
            raise desk_pr_body.subprocess.CalledProcessError(code, args, output=b"", stderr=b"HTTP 404: Not Found")
        return desk_pr_body.subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")


@pytest.fixture()
def tools(monkeypatch):
    fake = FakeTools()
    monkeypatch.setattr(desk_pr_body.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(desk_pr_body.subprocess, "run", fake)
    return fake


@pytest.fixture()
def content(tmp_path):
    path = tmp_path / "content.md"
    path.write_text(f"{HEAD}\n", encoding="utf-8")
    return path


class TestCommandLine:
    def test_set_reads_updates_and_patches(self, tools, content, capsys):
        tools.body = OLD_BODY
        assert desk_pr_body.main(["--pr", "7", "set", "HEAD:desk", str(content)]) == 0
        assert tools.calls[0][1:] == ["api", "repos/JesperDramsch/python-deadlines/pulls/7", "--jq", '.body // ""']
        assert tools.calls[1][1:5] == ["api", "-X", "PATCH", "repos/JesperDramsch/python-deadlines/pulls/7"]
        assert parse(tools.patched) == {"HEAD:desk": HEAD, "LEGACY": OLD_BODY}
        assert "wrote HEAD:desk" in capsys.readouterr().out

    def test_append_from_stdin(self, tools, monkeypatch):
        tools.body = render({"COMMITTED:canonical": "- one"})
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"- two\n"), encoding="utf-8"))
        assert desk_pr_body.main(["--pr", "7", "append", "COMMITTED:canonical", "-"]) == 0
        assert parse(tools.patched)["COMMITTED:canonical"] == "- one\n- two"

    def test_get_prints_a_block(self, tools, capsys):
        tools.body = render({"HEAD:desk": HEAD})
        assert desk_pr_body.main(["--pr", "7", "get", "HEAD:desk"]) == 0
        assert capsys.readouterr().out == f"{HEAD}\n"
        assert len(tools.calls) == 1

    def test_print_does_not_patch(self, tools, content, capsysbinary):
        assert desk_pr_body.main(["--pr", "7", "set", "HEAD:desk", str(content), "--print"]) == 0
        assert parse(capsysbinary.readouterr().out.decode("utf-8"))["HEAD:desk"] == HEAD
        assert len(tools.calls) == 1

    def test_skeleton_needs_no_pr(self, tools, capsys):
        assert desk_pr_body.main(["skeleton"]) == 0
        assert capsys.readouterr().out == render({})
        assert tools.calls == []

    def test_refuses_marker_content_without_patching(self, tools, tmp_path, capsys):
        bad = tmp_path / "bad.md"
        bad.write_text("<!-- /NEEDS:desk -->\n", encoding="utf-8")
        assert desk_pr_body.main(["--pr", "7", "set", "NEEDS:desk", str(bad)]) == 2
        assert "marker line" in capsys.readouterr().err
        assert tools.patched is None

    def test_refuses_a_body_over_the_limit(self, tools, tmp_path, capsys):
        big = tmp_path / "big.md"
        big.write_text("x" * desk_pr_body.BODY_LIMIT, encoding="utf-8")
        assert desk_pr_body.main(["--pr", "7", "set", "MORE:desk", str(big)]) == 2
        assert "over" in capsys.readouterr().err
        assert tools.patched is None

    def test_legacy_is_not_writable_on_the_command_line(self, tools, content):
        with pytest.raises(SystemExit):
            desk_pr_body.main(["--pr", "7", "set", "LEGACY", str(content)])

    def test_missing_file(self, tools, tmp_path, capsys):
        assert desk_pr_body.main(["--pr", "7", "set", "NEEDS:desk", str(tmp_path / "none.md")]) == 2
        assert "cannot read" in capsys.readouterr().err

    def test_pr_must_be_positive(self, tools, content):
        assert desk_pr_body.main(["--pr", "0", "set", "NEEDS:desk", str(content)]) == 2
        assert desk_pr_body.main(["set", "NEEDS:desk", str(content)]) == 2

    def test_failed_read_exits_1_without_patching(self, tools, content, capsys):
        tools.read_code = 1
        assert desk_pr_body.main(["--pr", "7", "set", "NEEDS:desk", str(content)]) == 1
        assert "404" in capsys.readouterr().err
        assert tools.patched is None

    def test_failed_patch_exits_1(self, tools, content):
        tools.patch_code = 1
        assert desk_pr_body.main(["--pr", "7", "set", "NEEDS:desk", str(content)]) == 1

    def test_gh_not_on_path(self, monkeypatch, content, capsys):
        monkeypatch.setattr(desk_pr_body.shutil, "which", lambda name: None)
        assert desk_pr_body.main(["--pr", "7", "set", "NEEDS:desk", str(content)]) == 1
        assert "not on PATH" in capsys.readouterr().err

    def test_carriage_returns_inside_a_block_survive(self, tools, content):
        crlf = render({"HEAD:desk": HEAD}).replace("\n", "\r\n")
        tools.body = crlf.replace("<!-- NEEDS:desk -->\r\n", "<!-- NEEDS:desk -->\r\n- [x] ticked\r\n- [ ] open\r\n")
        assert desk_pr_body.main(["--pr", "7", "set", "COMMITTED:enrich", str(content)]) == 0
        assert parse(tools.patched)["NEEDS:desk"] == "- [x] ticked\r\n- [ ] open"
