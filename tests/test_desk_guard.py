"""Tests for .claude/hooks/desk_guard.py, the PreToolUse guard registered in .claude/settings.json.

Each test runs the hook as a subprocess, the way Claude Code runs it: a crafted PreToolUse payload on stdin,
DESK_ROUTINE and HOME set per test (HOME with or without .desk-guard.json), and a temporary git repository
for branch detection. pytester runs the subprocesses, with a timeout and captured exit code and stderr.
"""

import ast
import json
import shutil
import sys
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "desk_guard.py"
SETTINGS = ROOT / ".claude" / "settings.json"
ROLLING = "auto/conference-updates"
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git builds the test repositories")


@pytest.fixture()
def home(pytester, tmp_path, monkeypatch):
    """Point HOME at an empty directory, after pytester has set its own HOME."""
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.delenv("DESK_ROUTINE", raising=False)
    return path


@pytest.fixture()
def git(pytester):
    """Run git in a subprocess and fail the test when it fails."""

    def run(*args):
        result = pytester.run(GIT, "-c", "user.name=Test", "-c", "user.email=test@example.com", *args, timeout=30)
        assert result.ret == 0, result.errlines

    return run


@pytest.fixture()
def make_repo(git, tmp_path):
    """Create a git repository with the given branch checked out."""

    def make(branch, name="repo"):
        repo = tmp_path / name
        git("init", "-q", str(repo))
        git("-C", str(repo), "symbolic-ref", "HEAD", f"refs/heads/{branch}")
        return repo

    return make


@pytest.fixture()
def run_hook(pytester, home, monkeypatch):
    """Run the hook with a PreToolUse payload and return (exit code, stderr lines)."""

    def run(tool_name, tool_input, *, cwd, desk=False, raw=None):
        if desk:
            monkeypatch.setenv("DESK_ROUTINE", "1")
        else:
            monkeypatch.delenv("DESK_ROUTINE", raising=False)
        payload = {
            "session_id": "test",
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
        stdin = raw if raw is not None else json.dumps(payload).encode()
        result = pytester.run(sys.executable, str(HOOK), stdin=stdin, timeout=30)
        return int(result.ret), result.errlines

    return run


def assert_blocked(outcome, *fragments):
    code, errlines = outcome
    assert code == 2
    assert len(errlines) == 1, "the reason must be one line"
    assert errlines[0].startswith("desk_guard: ")
    for fragment in fragments:
        assert fragment in errlines[0]


def assert_allowed(outcome):
    assert outcome == (0, [])


# --- pushes to main or master (any session) ---


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push origin master",
        "git push origin HEAD:main",
        "git push origin :main",
        "git push origin refs/heads/main",
        "git push origin feature:refs/heads/master",
        "git push --force origin +main",
        "git push -u origin main",
        "git push origin --delete main",
        "git push --all origin",
        "git push --mirror origin",
        "git push --repo=origin main",
        "GIT_TRACE=1 git push origin main",
        "git status && git push origin main",
        "git -C <repo> push origin main",
        "bash -c 'git push origin main'",
        "echo $(git push origin main)",
        # globs, shorthand destinations and the matching refspec
        "git push origin 'refs/heads/*:refs/heads/*'",
        "git push origin '*:*'",
        "git push origin HEAD:heads/main",
        "git push origin heads/main",
        "git push origin :",
        "git push --tags origin main",
        "git push origin tag v1 main",
        # compound commands: the retry loop of desk.md "Pushing" and its relatives
        "for i in 1 2 3 4 5; do git push origin main && break; git fetch origin main; done",
        "if git fetch origin; then git push origin main; fi",
        "if ! git push origin main; then git pull --rebase; fi",
        "until git push origin main; do sleep 1; done",
        "while true; do git push origin main; done",
        "true && { git push origin main; }",
        "! git push origin main",
        "function retry { git push origin main; }",
        # wrappers that take arguments before the command
        "timeout 120 git push origin main",
        "timeout -s KILL 120 git push origin main",
        "sudo -u bob git push origin main",
        "sudo -Eu bob -- git push origin main",
        "env -u GIT_DIR git push origin main",
        "/usr/bin/env GIT_TRACE=1 git push origin main",
        "nice -n 10 git push origin main",
        "flock /tmp/push.lock git push origin main",
        "echo main | xargs -n 1 git push origin main",
    ],
)
def test_push_targeting_main_is_blocked(run_hook, make_repo, command):
    repo = make_repo("feature")
    outcome = run_hook("Bash", {"command": command.replace("<repo>", str(repo))}, cwd=repo)
    assert_blocked(outcome, "git push")


@pytest.mark.parametrize("branch", ["main", "master"])
@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push origin",
        "git push -u origin",
        "git push origin HEAD",
        "git push --follow-tags",
        "for i in 1 2 3; do git push && break; done",
        "timeout 120 git push",
    ],
)
def test_push_without_refspec_from_main_is_blocked(run_hook, make_repo, branch, command):
    repo = make_repo(branch)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), branch)


@pytest.mark.parametrize(
    "command",
    ["cd <repo> && git push", "env -C <repo> git push", "env --chdir=<repo> git push", "sudo -D <repo> git push"],
)
def test_push_after_moving_into_a_repository_on_main_is_blocked(run_hook, make_repo, tmp_path, command):
    repo = make_repo("main")
    assert_blocked(run_hook("Bash", {"command": command.replace("<repo>", str(repo))}, cwd=tmp_path), "main")


@pytest.mark.parametrize(
    "command",
    [
        "git push --tags",
        "git push origin --tags",
        "git push --tags origin",
        "git push --dry-run",
        "git push -n origin main",
        "git push --dry-run --all origin",
    ],
)
def test_push_that_sends_no_branch_from_main_is_allowed(run_hook, make_repo, command):
    repo = make_repo("main")
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo))


def test_push_from_a_worktree_on_main_is_blocked(run_hook, make_repo, git, tmp_path):
    repo = make_repo("feature")
    git("-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init")
    worktree = tmp_path / "worktree"
    git("-C", str(repo), "worktree", "add", "-q", "-b", "main", str(worktree))
    assert_blocked(run_hook("Bash", {"command": "git push"}, cwd=worktree), "main")


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push origin",
        "git push origin HEAD",
        "git push origin auto/conference-updates",
        "git push origin HEAD:auto/conference-updates",
        "git push origin HEAD:desk-queue",
        "git push origin main:feature",
        "git push origin maintenance",
        "git push origin --delete old-feature",
        "git fetch origin main && git merge origin/main",
        "git commit -m 'never git push origin main'",
        "echo git push origin main",
        "cat > notes.md <<'EOF'\ngit push origin main\nEOF",
        "git push origin 'refs/tags/*:refs/tags/*'",
        "git push origin 'refs/heads/feature/*:refs/heads/feature/*'",
        "git push origin tag main",
        "for i in 1 2 3 4 5; do git push origin HEAD:desk-queue && break; git fetch origin desk-queue; done",
        "timeout 120 git push origin HEAD",
        "sudo -u bob git push origin HEAD",
        "if true; then echo git push origin main; fi",
    ],
)
def test_push_to_another_branch_is_allowed(run_hook, make_repo, command):
    repo = make_repo(ROLLING)
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo))


def test_push_without_refspec_outside_a_repository_is_allowed(run_hook, tmp_path):
    assert_allowed(run_hook("Bash", {"command": "git push"}, cwd=tmp_path))


# --- edits under .github/ (rolling branch or desk run) ---


def github_edit(tool, path):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return {key: str(path), "old_string": "a", "new_string": "b", "content": "b"}


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_github_edit_on_the_rolling_branch_is_blocked(run_hook, make_repo, tool):
    repo = make_repo(ROLLING)
    outcome = run_hook(tool, github_edit(tool, repo / ".github" / "workflows" / "ci.yml"), cwd=repo)
    assert_blocked(outcome, ".github/", ROLLING)


def test_github_edit_by_relative_path_on_the_rolling_branch_is_blocked(run_hook, make_repo):
    repo = make_repo(ROLLING)
    assert_blocked(run_hook("Edit", github_edit("Edit", ".github/labeler.yml"), cwd=repo), ".github/")


def test_github_edit_in_a_worktree_on_the_rolling_branch_is_blocked(run_hook, make_repo, git, tmp_path):
    repo = make_repo("main")
    git("-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init")
    worktree = tmp_path / "worktree"
    git("-C", str(repo), "worktree", "add", "-q", "-b", ROLLING, str(worktree))
    outcome = run_hook("Write", github_edit("Write", worktree / ".github" / "dependabot.yml"), cwd=worktree)
    assert_blocked(outcome, ROLLING)


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_github_edit_in_a_desk_run_is_blocked(run_hook, make_repo, tool):
    repo = make_repo("feature")
    outcome = run_hook(tool, github_edit(tool, repo / ".github" / "workflows" / "ci.yml"), cwd=repo, desk=True)
    assert_blocked(outcome, "desk runs")


def test_github_edit_on_another_branch_outside_desk_runs_is_allowed(run_hook, make_repo):
    repo = make_repo("feature")
    assert_allowed(run_hook("Edit", github_edit("Edit", repo / ".github" / "workflows" / "ci.yml"), cwd=repo))


def test_github_edit_through_dot_dot_on_the_rolling_branch_is_blocked(run_hook, make_repo):
    repo = make_repo(ROLLING)
    outcome = run_hook("Write", github_edit("Write", repo / "docs" / ".." / ".github" / "ci.yml"), cwd=repo)
    assert_blocked(outcome, ".github/")


@pytest.mark.parametrize(
    "relative",
    [
        "_data/conferences.yml",
        "docs/github/notes.md",
        ".github-notes/todo.md",
        "node_modules/pkg/.github/workflows/a.yml",
        "docs/.github",
    ],
)
@pytest.mark.parametrize("desk", [False, True])
def test_edit_outside_github_is_allowed(run_hook, make_repo, relative, desk):
    repo = make_repo(ROLLING)
    assert_allowed(run_hook("Write", github_edit("Write", repo / relative), cwd=repo, desk=desk))


def test_github_edit_outside_any_repository_is_allowed(run_hook, make_repo, tmp_path):
    repo = make_repo(ROLLING)
    elsewhere = tmp_path / "elsewhere" / ".github" / "workflows" / "ci.yml"
    assert_allowed(run_hook("Write", github_edit("Write", elsewhere), cwd=repo, desk=True))


def test_bash_writing_under_github_is_not_inspected(run_hook, make_repo):
    repo = make_repo(ROLLING)
    command = "echo name: x > .github/workflows/x.yml"
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo, desk=True))


# --- claude-code-remote tools (desk run) ---


@pytest.mark.parametrize("tool", ["mcp__claude-code-remote__send_message", "mcp__claude-code-remote__create_trigger"])
def test_remote_tools_in_a_desk_run_are_blocked(run_hook, tmp_path, tool):
    assert_blocked(run_hook(tool, {}, cwd=tmp_path, desk=True), tool)


def test_remote_tools_outside_desk_runs_are_allowed(run_hook, tmp_path):
    assert_allowed(run_hook("mcp__claude-code-remote__send_message", {"message": "hi"}, cwd=tmp_path))


# --- optional ~/.desk-guard.json deny-list (any session) ---


@pytest.mark.parametrize(
    ("deny_list", "tool", "tool_input", "blocked"),
    [
        ({"deny_bash": [r"curl\s+\S*evil"]}, "Bash", {"command": "curl https://evil.example/x"}, True),
        ({"deny_bash": [r"curl\s+\S*evil"]}, "Bash", {"command": "curl https://good.example/x"}, False),
        ({"deny_tools": ["^WebFetch$"]}, "WebFetch", {"url": "https://example.com", "prompt": "p"}, True),
        ({"deny_tools": ["^WebFetch$"]}, "Bash", {"command": "ls"}, False),
        ({"deny_paths": ["/secrets/"]}, "Write", {"file_path": "/srv/secrets/key.txt", "content": "x"}, True),
        ({"deny_paths": ["/secrets/"]}, "Write", {"file_path": "/srv/data/key.txt", "content": "x"}, False),
        ({"deny_urls": [r"example\.org"]}, "WebFetch", {"url": "https://example.org/a", "prompt": "p"}, True),
        ({"deny_urls": [r"example\.org"]}, "WebFetch", {"url": "https://example.com/a", "prompt": "p"}, False),
        ({"deny_urls": [r"example\.org"]}, "Bash", {"command": "curl https://example.org/a"}, False),
    ],
)
@pytest.mark.parametrize("desk", [False, True])
def test_deny_list_patterns(run_hook, home, tmp_path, deny_list, tool, tool_input, blocked, desk):
    (home / ".desk-guard.json").write_text(json.dumps(deny_list), encoding="utf-8")
    outcome = run_hook(tool, tool_input, cwd=tmp_path, desk=desk)
    if blocked:
        assert_blocked(outcome, next(iter(deny_list)))
    else:
        assert_allowed(outcome)


def test_without_a_deny_list_everything_else_is_allowed(run_hook, tmp_path):
    assert_allowed(run_hook("WebFetch", {"url": "https://example.org", "prompt": "p"}, cwd=tmp_path, desk=True))


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"deny_bash": "curl"}', '{"deny_urls": [1]}', '{"deny_tools": ["("]}'],
)
def test_malformed_deny_list_blocks_desk_runs_only(run_hook, home, tmp_path, content):
    (home / ".desk-guard.json").write_text(content, encoding="utf-8")
    assert_blocked(run_hook("Bash", {"command": "ls"}, cwd=tmp_path, desk=True), ".desk-guard.json")
    assert_allowed(run_hook("Bash", {"command": "ls"}, cwd=tmp_path))


# --- unreadable input ---


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b'{"tool_name": "Bash"}', b'{"tool_input": {}}'])
def test_unreadable_input_blocks_desk_runs_only(run_hook, tmp_path, raw):
    assert_blocked(run_hook("Bash", {}, cwd=tmp_path, desk=True, raw=raw), "unreadable hook input")
    assert_allowed(run_hook("Bash", {}, cwd=tmp_path, raw=raw))


# --- registration ---


def test_settings_register_the_hook_for_every_matcher():
    groups = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    command = 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/desk_guard.py"'
    assert {group["matcher"] for group in groups} == {
        "Bash",
        "Edit|Write|MultiEdit|NotebookEdit",
        "mcp__claude-code-remote__.*",
        "WebFetch",
    }
    for group in groups:
        assert group["hooks"] == [{"type": "command", "command": command}]


def test_hook_imports_only_the_standard_library():
    tree = ast.parse(HOOK.read_text(encoding="utf-8"))
    modules = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    modules |= {
        node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert modules <= sys.stdlib_module_names
