"""Tests for .claude/hooks/desk_guard.py, the PreToolUse guard registered in .claude/settings.json.

Each test runs the hook as a subprocess, the way Claude Code runs it: a crafted PreToolUse payload on stdin
(with ``agent_id`` for a subagent's call), DESK_ROUTINE and HOME set per test, and temporary git repositories
for branch and repository detection. HOME holds an empty .desk-guard.json unless a test replaces or removes
it, since a desk run without one blocks every call. pytester runs the subprocesses, with a timeout and
captured exit code and stderr.
"""

import ast
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "desk_guard.py"
SETTINGS = ROOT / ".claude" / "settings.json"
ROLLING = "auto/conference-updates"
REPO = "JesperDramsch/python-deadlines"
SUBAGENT = {"agent_id": "agent-1", "agent_type": "general-purpose"}
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git builds the test repositories")


@pytest.fixture()
def home(pytester, tmp_path, monkeypatch):
    """Point HOME at a directory with an empty deny-list, after pytester has set its own HOME."""
    path = tmp_path / "home"
    path.mkdir()
    (path / ".desk-guard.json").write_text("{}", encoding="utf-8")
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
def queue_repo(git, tmp_path):
    """Create a repository with a detached HEAD, like the desk's desk-queue worktree."""
    repo = tmp_path / "queue"
    git("init", "-q", str(repo))
    git("-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init")
    git("-C", str(repo), "checkout", "-q", "--detach")
    return repo


@pytest.fixture()
def run_hook(pytester, home, monkeypatch):
    """Run the hook with a PreToolUse payload and return (exit code, stderr lines).

    Keyword arguments other than ``cwd``, ``desk`` and ``raw`` go into the payload, such as ``agent_id``.
    """

    def run(tool_name, tool_input, *, cwd, desk=False, raw=None, **fields):
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
            **fields,
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


# --- MCP and scheduling tools (desk run) ---


GUARDED_TOOLS = [
    "mcp__github__merge_pull_request",
    "mcp__github__create_or_update_file",
    "mcp__github__push_files",
    "mcp__github__delete_file",
    "mcp__claude-code-remote__send_message",
    "mcp__claude-code-remote__create_trigger",
    "CronCreate",
    "CronDelete",
    "CronList",
    "RemoteTrigger",
    "ScheduleWakeup",
]


@pytest.mark.parametrize("tool", GUARDED_TOOLS)
@pytest.mark.parametrize("fields", [{}, SUBAGENT])
def test_mcp_and_scheduling_tools_in_a_desk_run_are_blocked(run_hook, tmp_path, tool, fields):
    assert_blocked(run_hook(tool, {}, cwd=tmp_path, desk=True, **fields), tool, "desk runs")


@pytest.mark.parametrize("tool", GUARDED_TOOLS)
def test_mcp_and_scheduling_tools_outside_desk_runs_are_allowed(run_hook, tmp_path, tool):
    assert_allowed(run_hook(tool, {"message": "hi"}, cwd=tmp_path))


# --- pushes in a desk run ---


DESK_PUSHES = [
    "git push origin HEAD:auto/conference-updates",
    "git push origin HEAD:refs/heads/auto/conference-updates",
    "git push -u origin HEAD:auto/conference-updates",
    "git push --no-verify -o ci.skip origin HEAD:auto/conference-updates",
    "git push origin auto/conference-updates",
    "git push origin HEAD",
    "git -C <queue> push origin HEAD:desk-queue",
    "git -C <queue> push origin HEAD:refs/heads/desk-queue",
    "cd <queue> && git push origin HEAD:desk-queue",
    # the retry loops of desk.md "Pushing"
    "for i in 1 2 3 4 5; do git push origin HEAD:auto/conference-updates && break; "
    "git fetch origin auto/conference-updates; git rebase origin/auto/conference-updates; done",
    "for i in 1 2 3 4 5; do git -C <queue> push origin HEAD:desk-queue && break; "
    "git -C <queue> fetch origin desk-queue; git -C <queue> reset --hard origin/desk-queue; done",
]


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("git push", "default remote"),
        ("git push origin", "without a refspec"),
        ("git push -u origin", "without a refspec"),
        ("git push upstream HEAD:auto/conference-updates", "origin"),
        (f"git push https://github.com/{REPO}.git HEAD:auto/conference-updates", "origin"),
        ("git push --repo=upstream HEAD:auto/conference-updates", "origin"),
        ("git push origin HEAD:feature", "'HEAD:feature'"),
        ("git push origin feature", "'feature'"),
        ("git push origin HEAD:auto/conference-updates HEAD:feature", "'HEAD:feature'"),
        ("git push origin HEAD:refs/tags/v1", "refs/tags/v1"),
        ("git push origin tag v1", "'tag'"),
        ("git push --dry-run origin HEAD:feature", "'HEAD:feature'"),
        ("git push --force origin HEAD:auto/conference-updates", "--force"),
        ("git push --force-with-lease origin HEAD:auto/conference-updates", "--force-with-lease"),
        ("git push --force-with-lease=auto/conference-updates:abc origin HEAD:auto/conference-updates", "--force"),
        ("git push -f origin HEAD:auto/conference-updates", "-f"),
        ("git push -fu origin HEAD:auto/conference-updates", "-f"),
        ("git push -uf origin HEAD:auto/conference-updates", "-f"),
        ("git push -o ci.skip -f origin HEAD:auto/conference-updates", "-f"),
        ("git push --delete origin desk-queue", "--delete"),
        ("git push -d origin desk-queue", "-d"),
        ("git push --mirror origin", "--mirror"),
        ("git push --all origin", "--all"),
        ("git push --tags origin HEAD:auto/conference-updates", "--tags"),
        ("git push --follow-tags origin HEAD:auto/conference-updates", "--follow-tags"),
        ("git push --prune origin HEAD:auto/conference-updates", "--prune"),
        ("git push origin +HEAD:auto/conference-updates", "'+HEAD:auto/conference-updates'"),
        ("git push origin :desk-queue", "':desk-queue'"),
        ("git -C <queue> push origin HEAD", "'HEAD'"),
        ("git -C <queue> push --force origin HEAD:desk-queue", "--force"),
        ("git -C <queue> push -fu origin HEAD:desk-queue", "-f"),
        ("git -C <queue> push origin +HEAD:desk-queue", "'+HEAD:desk-queue'"),
        ("git -C <queue> push origin :desk-queue", "':desk-queue'"),
        ("timeout 120 git push --force origin HEAD:auto/conference-updates", "--force"),
        ("bash -c 'git push -f origin HEAD:desk-queue'", "-f"),
        ("for i in 1 2 3; do git push --force origin HEAD:desk-queue && break; done", "--force"),
    ],
)
def test_desk_push_outside_the_desk_branches_is_blocked(run_hook, make_repo, queue_repo, command, fragment):
    repo = make_repo(ROLLING)
    outcome = run_hook("Bash", {"command": command.replace("<queue>", str(queue_repo))}, cwd=repo, desk=True)
    assert_blocked(outcome, "git push", fragment)


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push upstream feature",
        "git push --force origin HEAD:feature",
        "git push -fu origin feature",
        "git push origin +HEAD:feature",
        "git push origin :old-feature",
        "git push --tags origin",
        "git -C <queue> push --force origin HEAD:desk-queue",
    ],
)
def test_push_rules_outside_desk_runs_stay_as_they_were(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    assert_allowed(run_hook("Bash", {"command": command.replace("<queue>", str(queue_repo))}, cwd=repo))


# --- gh in a desk run ---


GH_READS = [
    f'gh api --paginate "repos/{REPO}/issues/12/comments?per_page=100&since=2026-10-01T06:00:00Z"',
    f'gh api --paginate "repos/{REPO}/pulls/12/comments?per_page=100&since=2026-10-01T06:00:00Z"',
    f'gh api --paginate "repos/{REPO}/pulls/12/reviews?per_page=100" '
    "--jq '.[] | select(.submitted_at > \"2026-10-01T06:00:00Z\")'",
    f"gh api repos/{REPO}/issues/comments/99 --jq .user.id",
    f"gh api repos/{REPO}/pulls/comments/99 --jq .user.id",
    f"gh api repos/{REPO}/pulls/12/reviews/99 --jq .user.id",
    f"gh api \"repos/{REPO}/pulls?head=JesperDramsch:auto/conference-updates&state=open\" --jq '.[0].number // empty'",
    f"gh api repos/{REPO}/pulls/12 --jq .body",
    f"gh api -X GET repos/{REPO}/pulls/12",
    f"gh api --method get /repos/{REPO}/issues/12/labels -H 'Accept: application/vnd.github+json'",
    "gh api repos/python/cpython/pulls --jq '.[].number'",
]
GH_WRITES = [
    f"gh api repos/{REPO}/issues/12/comments -f body='Desk: this request stays with the maintainer'",
    f'gh api repos/{REPO}/pulls -f title="🐍 Conference updates" -f head=auto/conference-updates -f base=main '
    "-F draft=true -F body=@/tmp/body.md",
    f'gh api repos/{REPO}/issues/12/labels -f "labels[]=automated" -f "labels[]=conference-update"',
    f"gh api -X PATCH repos/{REPO}/pulls/12 -F body=@/tmp/body.md",
    f"gh api --method PATCH /repos/{REPO}/pulls/12 --input /tmp/body.json",
    f"gh api -XPATCH https://api.github.com/repos/{REPO}/pulls/12 -F body=@/tmp/body.md",
    f"gh api --method=POST repos/{REPO}/issues/12/comments --raw-field body=x",
    f"gh api -X post /repos/{REPO}/issues/12/labels --field 'labels[]=automated'",
]


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("gh pr create --draft --title x --body y", "gh pr"),
        ("gh pr merge 12 --squash", "gh pr"),
        ("gh issue comment 12 --body x", "gh issue"),
        ("gh workflow run recurring-sort.yml", "gh workflow"),
        (f"gh repo delete {REPO} --yes", "gh repo"),
        ("gh auth token", "gh auth"),
        (f"gh api -X PUT repos/{REPO}/pulls/12/merge", "PUT"),
        (f"gh api -X DELETE repos/{REPO}/git/refs/heads/main", "DELETE"),
        (f"gh api --method=DELETE repos/{REPO}/issues/12/labels/automated", "DELETE"),
        (f"gh api -iX DELETE repos/{REPO}/issues/12/labels/automated", "DELETE"),
        (f"gh api -X PATCH repos/{REPO}/issues/12 -f state=closed", "PATCH"),
        (f"gh api -X PATCH repos/{REPO}/pulls", "PATCH"),
        (f"gh api repos/{REPO}/pulls/12 -f state=closed", "POST"),
        (f"gh api repos/{REPO}/pulls/12 -fstate=closed", "POST"),
        (f"gh api -X POST repos/{REPO}/pulls/12/merge", "POST"),
        (f"gh api repos/{REPO}/pulls/12/reviews -f event=APPROVE", "reviews"),
        (f"gh api repos/{REPO}/issues -f title=x", "POST"),
        (f"gh api repos/{REPO}/git/refs -f ref=refs/heads/main -f sha=abc", "git/refs"),
        (f"gh api repos/{REPO}/issues/12/comments/../../../dispatches -f event_type=x", "dispatches"),
        (f"gh api repos/{REPO}/actions/workflows/sort.yml/dispatches -f ref=main", "dispatches"),
        ("gh api repos/JesperDramsch/other-repo/pulls -f title=x", "other-repo"),
        ("gh api repos/someone/python-deadlines/issues/1/comments -f body=x", "someone"),
        ("gh api https://evil.example/repos/JesperDramsch/python-deadlines/pulls -f title=x", "evil.example"),
        (f"gh api --hostname evil.example repos/{REPO}/pulls -f title=x", "POST"),
        ("gh api graphql -f query='mutation { mergePullRequest }'", "graphql"),
        (f"gh api -X GET repos/{REPO}/pulls -f per_page=100", "GET"),
        (f"gh api repos/{REPO}/pulls/12 --input /tmp/body.json", "POST"),
    ],
)
def test_desk_gh_other_than_the_allowed_api_calls_is_blocked(run_hook, make_repo, command, fragment):
    repo = make_repo(ROLLING)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True), "gh", fragment)


@pytest.mark.parametrize("command", ["gh pr merge 12 --squash", f"gh api -X PUT repos/{REPO}/pulls/12/merge"])
def test_gh_outside_desk_runs_is_allowed(run_hook, make_repo, command):
    assert_allowed(run_hook("Bash", {"command": command}, cwd=make_repo(ROLLING)))


# --- the desk procedure in .claude/routines/desk.md (desk run, main agent) ---


DESK_SCRIPTS = [
    "python utils/desk_pr_body.py /tmp/ledger.md",
    "python utils/merge_data.py",
    "python utils/sort_yaml.py --skip_links",
    "python3 ./utils/sort_yaml.py --skip_links",
    "/usr/bin/python utils/sort_yaml.py --skip_links",
    "uv run --python 3.11 --with pyyaml,pydantic python utils/sort_yaml.py --skip_links",
    "./utils/sort_yaml.py --skip_links",
    "cd utils && python sort_yaml.py --skip_links",
    "python -m utils.sort_yaml",
    "pixi run sort",
    "pixi run -e default links",
    "timeout 600 python utils/merge_data.py",
    "bash -c 'python3 utils/desk_pr_body.py /tmp/ledger.md'",
    "python utils/desk_queue.py add <queue> --jsonl /tmp/records.jsonl",
    "python utils/desk_queue.py remove <queue> abc123 def456",
    "python utils/desk_queue.py snooze <queue> abc123",
    "python utils/desk_queue.py init <queue>",
]
DESK_PROCEDURE = [
    "date -u",
    "date -u +%Y-%m-%dT%H:%M:%SZ",
    "git fetch origin main",
    "git fetch origin auto/conference-updates",
    "git fetch origin desk-queue",
    "git checkout -B auto/conference-updates origin/auto/conference-updates",
    "git merge-base --is-ancestor origin/main HEAD",
    "git merge --no-edit origin/main",
    "git merge --abort",
    "git checkout --no-track -b auto/conference-updates origin/main",
    "git branch --show-current",
    "git status --short",
    "git worktree add --detach $(mktemp -d)/desk-queue origin/desk-queue",
    "python utils/desk_worklist.py --queue-dir <queue> > /tmp/worklist.json",
    "git add _data/conferences.yml _data/archive.yml _data/legacy.yml",
    "git commit -m 'PyCon Greece 2027: cfp_ext' -m 'cfp_ext: null -> 2027-03-01 23:59:00'",
    "git show --stat HEAD",
    "git rev-parse HEAD",
    "git rev-parse origin/auto/conference-updates",
    "git rebase origin/auto/conference-updates",
    "git rebase --abort",
    "git reset --hard origin/auto/conference-updates",
    "git rev-list --count origin/main..origin/auto/conference-updates",
    "git -C <queue> add -A",
    "git -C <queue> commit -m 'Remove handled queue items'",
    "git -C <queue> fetch origin desk-queue",
]


@pytest.mark.parametrize("command", [*DESK_PROCEDURE, *DESK_PUSHES, *GH_READS, *GH_WRITES, *DESK_SCRIPTS])
def test_desk_procedure_is_allowed(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    outcome = run_hook("Bash", {"command": command.replace("<queue>", str(queue_repo))}, cwd=repo, desk=True)
    assert_allowed(outcome)


def test_desk_data_edit_is_allowed(run_hook, make_repo):
    repo = make_repo(ROLLING)
    outcome = run_hook("Edit", github_edit("Edit", repo / "_data" / "conferences.yml"), cwd=repo, desk=True)
    assert_allowed(outcome)


# --- subagents in a desk run ---


SUBAGENT_GIT_READS = [
    "git status --short",
    "git log --oneline -5 -- _data/conferences.yml",
    "git show HEAD:_data/archive.yml",
    "git diff origin/main -- _data",
    "git grep -n 'PyCon Greece'",
    "git ls-files _data",
    "git ls-remote origin",
    "git ls-tree HEAD _data",
    "git rev-parse HEAD",
    "git rev-list --count origin/main..HEAD",
    "git merge-base --is-ancestor origin/main HEAD",
    "git blame -L 1,20 _data/conferences.yml",
    "git cat-file -p HEAD",
    "git fetch origin main",
    "git describe --tags",
    "git shortlog -sn",
    "git for-each-ref refs/heads",
    "git show-ref",
    "git config --get remote.origin.url",
    "git -C <repo> log -1",
    "git --no-pager log -1",
    "git --version",
]
SUBAGENT_OTHER_READS = [
    "python utils/desk_queue.py list <queue>",
    "python utils/desk_worklist.py --queue-dir <queue>",
    "cat utils/sort_yaml.py",
    "grep -n 'def ' utils/merge_data.py",
    "sed -n 1,40p utils/desk_pr_body.py",
    "uv run pytest tests/test_sort_yaml.py -q",
    "grep -rn 'PyCon Greece' _data/conferences.yml _data/archive.yml _data/legacy.yml",
    "curl -sSL https://2027.pycon.gr/cfp/",
]


@pytest.mark.parametrize("command", [*SUBAGENT_GIT_READS, *GH_READS, *SUBAGENT_OTHER_READS])
def test_subagent_reads_are_allowed(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    command = command.replace("<repo>", str(repo)).replace("<queue>", str(queue_repo))
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **SUBAGENT))


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git add _data/conferences.yml",
        "git push origin HEAD:auto/conference-updates",
        "git -C <queue> push origin HEAD:desk-queue",
        "git checkout -b scratch",
        "git switch main",
        "git reset --hard origin/main",
        "git rebase origin/main",
        "git merge origin/main",
        "git stash",
        "git worktree add /tmp/other",
        "git branch --show-current",
        "git branch -D auto/conference-updates",
        "git tag v1",
        "git config user.name x",
        "git config --unset user.name",
        "git restore _data/conferences.yml",
        "git rm _data/legacy.yml",
        "git clean -fd",
        "git apply /tmp/patch.diff",
        "git cherry-pick abc123",
        "git update-ref refs/heads/main HEAD",
        "git -C <repo> commit -m x",
        "git -c user.name=x commit -m y",
        "cd <repo> && git commit -m x",
        "git status && git commit -am x",
        "bash -c 'git commit -m x'",
        "for i in 1 2; do git push origin HEAD:desk-queue; done",
    ],
)
def test_subagent_git_writes_are_blocked(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    command = command.replace("<repo>", str(repo)).replace("<queue>", str(queue_repo))
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **SUBAGENT), "git", "subagents")


@pytest.mark.parametrize("command", [*GH_WRITES, "gh pr view 12", "gh issue list", "gh search repos pycon"])
def test_subagent_gh_other_than_api_reads_is_blocked(run_hook, make_repo, command):
    repo = make_repo(ROLLING)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **SUBAGENT), "gh")


@pytest.mark.parametrize("command", DESK_SCRIPTS)
def test_subagent_desk_scripts_are_blocked(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    command = command.replace("<queue>", str(queue_repo))
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **SUBAGENT), ".py", "subagents")


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
@pytest.mark.parametrize(
    "path",
    [
        "<repo>/_data/conferences.yml",
        "_data/conferences.yml",
        "./utils/../_data/archive.yml",
        "<repo>/new/folder/notes.md",
        "<repo>/../repo/_data/legacy.yml",
        "<repo>",
    ],
)
def test_subagent_edit_inside_the_repository_is_blocked(run_hook, make_repo, tool, path):
    repo = make_repo(ROLLING)
    outcome = run_hook(tool, github_edit(tool, path.replace("<repo>", str(repo))), cwd=repo, desk=True, **SUBAGENT)
    assert_blocked(outcome, tool, "subagents")


def test_subagent_edit_through_a_symlink_into_the_repository_is_blocked(run_hook, make_repo, tmp_path):
    repo = make_repo(ROLLING)
    (repo / "_data").mkdir()
    (tmp_path / "link").symlink_to(repo / "_data")
    outcome = run_hook("Write", github_edit("Write", tmp_path / "link" / "a.yml"), cwd=tmp_path, desk=True, **SUBAGENT)
    assert_blocked(outcome, "subagents")


def test_subagent_edit_in_the_repository_of_the_path_is_blocked(run_hook, queue_repo, tmp_path):
    outcome = run_hook(
        "Write",
        github_edit("Write", queue_repo / "queue" / "a.json"),
        cwd=tmp_path,
        desk=True,
        **SUBAGENT,
    )
    assert_blocked(outcome, "subagents")


@pytest.mark.parametrize("path", ["<tmp>/scratch/change-set.yml", "<tmp>/scratch/notes/lead.md"])
def test_subagent_edit_outside_the_repository_is_allowed(run_hook, make_repo, tmp_path, path):
    repo = make_repo(ROLLING)
    tool_input = github_edit("Write", path.replace("<tmp>", str(tmp_path)))
    assert_allowed(run_hook("Write", tool_input, cwd=repo, desk=True, **SUBAGENT))


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Bash", {"command": "git commit -m x"}),
        ("Bash", {"command": f"gh api repos/{REPO}/issues/12/comments -f body=x"}),
        ("Bash", {"command": "gh pr view 12"}),
        ("Bash", {"command": "python utils/sort_yaml.py --skip_links"}),
        ("Write", {"file_path": "_data/conferences.yml", "content": "x"}),
    ],
)
def test_subagent_rules_apply_to_desk_runs_only(run_hook, make_repo, tool, tool_input):
    repo = make_repo(ROLLING)
    assert_allowed(run_hook(tool, tool_input, cwd=repo, **SUBAGENT))


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Bash", {"command": "git commit -m x"}),
        ("Bash", {"command": "python utils/sort_yaml.py --skip_links"}),
        ("Write", {"file_path": "_data/conferences.yml", "content": "x"}),
    ],
)
def test_agent_type_without_agent_id_is_the_main_agent(run_hook, make_repo, tool, tool_input):
    repo = make_repo(ROLLING)
    assert_allowed(run_hook(tool, tool_input, cwd=repo, desk=True, agent_type="desk"))


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


def test_an_empty_deny_list_allows_everything_else(run_hook, tmp_path):
    assert_allowed(run_hook("WebFetch", {"url": "https://example.org", "prompt": "p"}, cwd=tmp_path, desk=True))


def remove_deny_list(home, how):
    """Take ~/.desk-guard.json away the way ``how`` names."""
    path = home / ".desk-guard.json"
    if how == "deleted":
        path.unlink()
    elif how == "moved":
        path.rename(home / "desk-guard.json.bak")
    elif how == "dangling symlink":
        path.unlink()
        path.symlink_to(home / "gone.json")


@pytest.mark.parametrize("how", ["deleted", "moved", "dangling symlink"])
@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Bash", {"command": "ls"}),
        ("WebFetch", {"url": "https://example.org", "prompt": "p"}),
        ("Write", {"file_path": "scratch/notes.md", "content": "x"}),
    ],
)
def test_missing_deny_list_blocks_desk_runs_only(run_hook, home, tmp_path, how, tool, tool_input):
    remove_deny_list(home, how)
    assert_blocked(run_hook(tool, tool_input, cwd=tmp_path, desk=True), ".desk-guard.json", "missing")
    assert_blocked(run_hook(tool, tool_input, cwd=tmp_path, desk=True, **SUBAGENT), ".desk-guard.json")
    assert_allowed(run_hook(tool, tool_input, cwd=tmp_path))


def test_deny_list_that_is_a_directory_blocks_desk_runs_only(run_hook, home, tmp_path):
    (home / ".desk-guard.json").unlink()
    (home / ".desk-guard.json").mkdir()
    assert_blocked(run_hook("Bash", {"command": "ls"}, cwd=tmp_path, desk=True), ".desk-guard.json")
    assert_allowed(run_hook("Bash", {"command": "ls"}, cwd=tmp_path))


@pytest.mark.parametrize(
    "path",
    [
        "<tmp>/secrets/key.txt",
        "<tmp>//secrets/key.txt",
        "<tmp>/./secrets/key.txt",
        "<tmp>/data/../secrets/key.txt",
        "/<tmp>/secrets/key.txt",
        "secrets/key.txt",
        "./secrets//key.txt",
        "data/../secrets/key.txt",
        "~/../secrets/key.txt",
        ".claude//hooks/desk_guard.py",
        ".claude/./hooks/desk_guard.py",
        "<tmp>/.claude/hooks/../hooks/desk_guard.py",
    ],
)
@pytest.mark.parametrize("desk", [False, True])
def test_deny_paths_match_the_normalised_path(run_hook, home, tmp_path, path, desk):
    deny_paths = ["^" + re.escape(str(tmp_path / "secrets")) + "/", r"/\.claude/hooks/"]
    (home / ".desk-guard.json").write_text(json.dumps({"deny_paths": deny_paths}), encoding="utf-8")
    tool_input = {"file_path": path.replace("<tmp>", str(tmp_path)), "content": "x"}
    assert_blocked(run_hook("Write", tool_input, cwd=tmp_path, desk=desk), "deny_paths")


@pytest.mark.parametrize("path", ["<tmp>/secrets-public/key.txt", "<tmp>/data/secrets.txt", "hooks/desk_guard.py"])
def test_deny_paths_leave_other_paths_alone(run_hook, home, tmp_path, path):
    deny_paths = ["^" + re.escape(str(tmp_path / "secrets")) + "/", r"/\.claude/hooks/"]
    (home / ".desk-guard.json").write_text(json.dumps({"deny_paths": deny_paths}), encoding="utf-8")
    tool_input = {"file_path": path.replace("<tmp>", str(tmp_path)), "content": "x"}
    assert_allowed(run_hook("Write", tool_input, cwd=tmp_path, desk=True))


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
        "mcp__.*|Cron.*|Remote.*|Schedule.*",
        "WebFetch",
    }
    for group in groups:
        assert group["hooks"] == [{"type": "command", "command": command}]


def matcher_matches(matcher, tool):
    """Match a tool name the way Claude Code reads a hook matcher.

    A matcher made only of letters, digits, ``_``, ``-``, spaces, commas and ``|`` lists exact names; any
    other matcher is a regular expression searched anywhere in the name.
    """
    if re.fullmatch(r"[A-Za-z0-9_\- ,|]*", matcher):
        return tool in {name.strip() for name in re.split(r"[|,]", matcher)}
    return re.search(matcher, tool) is not None


@pytest.mark.parametrize("tool", ["Bash", "Edit", "Write", "MultiEdit", "NotebookEdit", "WebFetch", *GUARDED_TOOLS])
def test_settings_send_every_guarded_tool_to_the_hook(tool):
    groups = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    assert any(matcher_matches(group["matcher"], tool) for group in groups)


def test_hook_imports_only_the_standard_library():
    tree = ast.parse(HOOK.read_text(encoding="utf-8"))
    modules = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    modules |= {
        node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert modules <= sys.stdlib_module_names
