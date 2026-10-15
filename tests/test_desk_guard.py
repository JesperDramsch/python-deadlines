"""Tests for .claude/hooks/desk_guard.py, the PreToolUse guard registered in .claude/settings.json.

Each test runs the hook as a subprocess, the way Claude Code runs it: a crafted PreToolUse payload on stdin
(with ``agent_id`` for a subagent's call), DESK_ROUTINE and HOME set per test, and temporary git repositories
for branch and repository detection. HOME holds an empty .desk-guard.json unless a test replaces or removes
it, since a desk run without one blocks every call. pytester runs the subprocesses, with a timeout and
captured exit code and stderr. The push spellings the hook blocks are also run with real git against a local
bare remote, to show that git reads them as the options they abbreviate, and so are an alias set inside an
alias, a tag fetch, a ``git config`` call whose ``--file`` takes ``--get`` as its value and ``GIT_CONFIG*``
variables that bash sets with ``printf -v`` and exports by name.
"""

import ast
import json
import re
import shlex
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
BASH = shutil.which("bash")

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
def git_ref(pytester):
    """Return the object a ref names in a repository, or None when the ref does not exist."""

    def resolve(repo, ref):
        result = pytester.run(GIT, "-C", str(repo), "rev-parse", "--verify", "--quiet", ref, timeout=30)
        return result.outlines[0] if result.ret == 0 else None

    return resolve


@pytest.fixture()
def remote_clone(git, tmp_path):
    """Create a bare remote and a clone whose branches have moved on, and return both.

    The remote has main, desk-queue and old/stale at commit A, and auto/conference-updates at R, a child of
    A. The clone has auto/conference-updates checked out at L, another child of A that carries the annotated
    tag v2, and main at M, a third child of A. Pushing L to desk-queue is a fast-forward; pushing it to
    auto/conference-updates needs a force.
    """
    seed, remote, clone = tmp_path / "seed", tmp_path / "remote.git", tmp_path / "clone"
    git("init", "-q", str(seed))
    git("-C", str(seed), "symbolic-ref", "HEAD", "refs/heads/main")
    git("-C", str(seed), "commit", "-q", "--allow-empty", "-m", "A")
    git("-C", str(seed), "branch", "desk-queue")
    git("-C", str(seed), "branch", "old/stale")
    git("-C", str(seed), "checkout", "-q", "-b", ROLLING)
    git("-C", str(seed), "commit", "-q", "--allow-empty", "-m", "R")
    git("-C", str(seed), "checkout", "-q", "main")
    git("clone", "-q", "--bare", str(seed), str(remote))
    git("clone", "-q", str(remote), str(clone))
    git("-C", str(clone), "checkout", "-q", "--no-track", "-b", ROLLING, "origin/main")
    git("-C", str(clone), "commit", "-q", "--allow-empty", "-m", "L")
    git("-C", str(clone), "tag", "-a", "v2", "-m", "v2")
    git("-C", str(clone), "checkout", "-q", "main")
    git("-C", str(clone), "commit", "-q", "--allow-empty", "-m", "M")
    git("-C", str(clone), "checkout", "-q", ROLLING)
    return remote, clone


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
        "sudo -uroot git push origin main",
        "timeout -k5s 120 git push origin main",
        "env -uS git push origin main",
        "env -u GIT_DIR git push origin main",
        "/usr/bin/env GIT_TRACE=1 git push origin main",
        "nice -n 10 git push origin main",
        "flock /tmp/push.lock git push origin main",
        "echo main | xargs -n 1 git push origin main",
        # abbreviations git reads as the option they start, and a dry run undone later
        "git push --mirr origin",
        "git push --al origin",
        "git push --bra origin",
        "git push --mirror=x origin",
        "git push --dry-run --no-dry-run --all origin",
        "git push -n --no-dry --mirror origin",
        # aliases set on the command line, and the dashed programs
        "git -c alias.p=push p origin main",
        "git -c Alias.P=push P origin HEAD:main",
        "git -c 'alias.p=push origin' p main",
        "git -c alias.p=q -c alias.q=push p origin main",
        "git -C <repo> -c alias.p=push p origin main",
        "git -c 'alias.p=!git push origin main' p",
        "git -c 'alias.p=!git push' p origin HEAD:main",
        "git -c alias.push=status push origin main",
        "git -c 'alias.p=-c alias.q=push q' p origin HEAD:main",
        "git -c 'alias.p=-c \"alias.q=-c alias.r=push r\" q' p origin main",
        "git-push origin main",
        "/usr/lib/git-core/git-push --force origin HEAD:main",
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
        "git push --tags --no-tags",
        "git push --tags --no-t origin",
        "git push --push-o ci.skip origin",
        "git push --recurse-submodules check origin",
        "git -c alias.p=push p",
        "git -c 'alias.p=!git push' p origin",
        "git -c 'alias.p=-c alias.q=push q' p",
        "git-push origin",
    ],
)
def test_push_without_refspec_from_main_is_blocked(run_hook, make_repo, branch, command):
    repo = make_repo(branch)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), branch)


@pytest.mark.parametrize(
    "command",
    [
        "cd <repo> && git push",
        "env -C <repo> git push",
        "env --chdir=<repo> git push",
        "sudo -D <repo> git push",
        # a chdir option bundled into an option cluster moves the directory too
        "env -iC <repo> git push",
        "env -iC<repo> git push",
        "env -i --chdir=<repo> git push",
        "sudo -D<repo> git push",
    ],
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
        "git push --dry-run --no-verify --all origin",
        "git push --tags --no-verify origin",
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
        "git push --force-w origin HEAD:feature",
        "git push --recurse-submodules check origin HEAD:feature",
        "git -c alias.p=push p origin HEAD:feature",
        "git -c alias.st=status st",
        "git -c 'alias.p=!echo git push origin main' p",
        "git -c alias.p=q -c alias.q=p p origin main",
        # git stops at a loop and at an alias that redefines itself
        "git -c 'alias.p=-c alias.q=p q' p origin main",
        "git -c 'alias.p=-c alias.p=push p' p origin main",
        "git -c 'alias.p=-c alias.q=push q' p origin HEAD:feature",
        "git-push origin HEAD:feature",
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
        # abbreviations git reads as the option they start, with and without a value
        ("git push --force-w origin HEAD:auto/conference-updates", "--force-with-lease"),
        ("git push --force-with origin HEAD:auto/conference-updates", "--force-with-lease"),
        ("git push --force-w=auto/conference-updates origin HEAD:auto/conference-updates", "--force-with-lease"),
        ("git push --forc origin HEAD:auto/conference-updates", "--force"),
        ("git push --del origin desk-queue", "--delete"),
        ("git push --pru origin HEAD:auto/conference-updates", "--prune"),
        ("git push --tag origin HEAD:auto/conference-updates", "--tags"),
        ("git push --follow-t origin HEAD:auto/conference-updates", "--follow-tags"),
        ("git push --mirr origin", "--mirror"),
        ("git push --al origin", "--all"),
        ("git push --bra origin", "--branches"),
        # --recurse-submodules with any value
        ("git push --recurse-submodules=check origin HEAD:auto/conference-updates", "--recurse-submodules"),
        ("git push --recurse-submodules on-demand origin HEAD:auto/conference-updates", "--recurse-submodules"),
        ("git push --recurse-submodules=no origin HEAD:auto/conference-updates", "--recurse-submodules"),
        ("git push --recurse-sub=only origin HEAD:desk-queue", "--recurse-submodules"),
        # the dashed program
        ("/usr/lib/git-core/git-push --force origin HEAD:auto/conference-updates", "--force"),
        ("git-push origin HEAD:feature", "'HEAD:feature'"),
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


# Push spellings the hook blocks, whether it blocks them in desk runs only, the reason's fragment, and the
# remote ref git then changes with the clone's ref it ends up at (None: git deletes it)
HARMFUL_PUSHES = [
    ("--force-w origin HEAD:auto/conference-updates", True, "--force-with-lease", f"refs/heads/{ROLLING}", "HEAD"),
    ("--force-with origin HEAD:auto/conference-updates", True, "--force-with-lease", f"refs/heads/{ROLLING}", "HEAD"),
    (
        "--force-w=auto/conference-updates origin HEAD:auto/conference-updates",
        True,
        "--force-with-lease",
        f"refs/heads/{ROLLING}",
        "HEAD",
    ),
    ("--del origin desk-queue", True, "--delete", "refs/heads/desk-queue", None),
    ("--pru origin 'refs/heads/old/*:refs/heads/old/*'", True, "--prune", "refs/heads/old/stale", None),
    ("--tag origin HEAD:desk-queue", True, "--tags", "refs/tags/v2", "v2"),
    ("--follow-t origin HEAD:desk-queue", True, "--follow-tags", "refs/tags/v2", "v2"),
    ("--mirr origin", False, "--mirror", "refs/heads/main", "main"),
    ("--al origin", False, "--all", "refs/heads/main", "main"),
]


@pytest.mark.parametrize(("arguments", "desk", "fragment", "ref", "target"), HARMFUL_PUSHES)
def test_blocked_push_spellings_do_harm_with_real_git(
    run_hook,
    pytester,
    remote_clone,
    git_ref,
    arguments,
    desk,
    fragment,
    ref,
    target,
):
    remote, clone = remote_clone
    assert_blocked(run_hook("Bash", {"command": f"git push {arguments}"}, cwd=clone, desk=desk), "git push", fragment)
    expected = git_ref(clone, target) if target else None
    assert git_ref(remote, ref) != expected
    # The exit code is left alone: --al also tries the diverged branch, which the remote rejects
    pytester.run(GIT, "-C", str(clone), "push", *shlex.split(arguments), timeout=30)
    assert git_ref(remote, ref) == expected


def test_alias_set_inside_an_alias_pushes_main_with_real_git(run_hook, pytester, remote_clone, git_ref):
    remote, clone = remote_clone
    command = "git -c 'alias.p=-c alias.q=push q' p origin HEAD:main"
    assert_blocked(run_hook("Bash", {"command": command}, cwd=clone), "git push", "main")
    assert git_ref(remote, "refs/heads/main") != git_ref(clone, "HEAD")
    result = pytester.run(GIT, "-C", str(clone), *shlex.split(command)[1:], timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(remote, "refs/heads/main") == git_ref(clone, "HEAD")


# --- send-pack and http-push: git's plumbing that writes remote refs like push (any session) ---


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("git send-pack origin main", "main"),
        ("git send-pack origin HEAD:main", "main"),
        ("git send-pack ./rem +feature:main", "main"),
        ("git send-pack origin 'refs/heads/*:refs/heads/*'", "main"),
        ("git send-pack --mirror origin", "--mirror"),
        ("git send-pack --force origin HEAD:refs/heads/master", "master"),
        ("git http-push https://example.com/r.git HEAD:main", "main"),
        ("git http-push https://example.com/r.git refs/heads/master", "master"),
        ("/usr/lib/git-core/git-send-pack origin main", "main"),
        ("git-send-pack origin HEAD:main", "main"),
        ("git-http-push https://example.com/r.git HEAD:main", "main"),
    ],
)
def test_send_pack_and_http_push_to_main_are_blocked(run_hook, make_repo, command, fragment):
    repo = make_repo("feature")
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), "git push", fragment)


@pytest.mark.parametrize("fields", [{}, SUBAGENT])
@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("git send-pack origin HEAD:main", "main"),
        ("git send-pack upstream HEAD:auto/conference-updates", "origin"),
        ("git send-pack --force origin HEAD:auto/conference-updates", "--force"),
        ("git send-pack origin HEAD:feature", "'HEAD:feature'"),
        ("git http-push https://example.com/r.git HEAD:main", "main"),
    ],
)
def test_send_pack_and_http_push_in_a_desk_run_are_blocked(run_hook, make_repo, command, fragment, fields):
    repo = make_repo(ROLLING)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **fields), "git push", fragment)


@pytest.mark.parametrize(
    "command",
    [
        "git send-pack origin HEAD:feature",
        "git send-pack ./rem feature",
        "git send-pack origin +feature:topic",
        "git http-push https://example.com/r.git HEAD:feature",
    ],
)
def test_send_pack_and_http_push_to_another_branch_outside_desk_runs_are_allowed(run_hook, make_repo, command):
    assert_allowed(run_hook("Bash", {"command": command}, cwd=make_repo("feature")))


def test_send_pack_to_the_rolling_branch_in_a_desk_run_is_allowed(run_hook, make_repo):
    repo = make_repo(ROLLING)
    assert_allowed(
        run_hook("Bash", {"command": "git send-pack origin HEAD:auto/conference-updates"}, cwd=repo, desk=True),
    )


# send-pack spellings that write remote main, each in the sessions where it is blocked
HARMFUL_SEND_PACKS = [
    ("send-pack {remote} HEAD:main", False),
    ("send-pack {remote} HEAD:main", True),
    ("send-pack --force {remote} HEAD:refs/heads/main", False),
]


@pytest.mark.parametrize(("arguments", "desk"), HARMFUL_SEND_PACKS)
def test_send_pack_to_main_does_harm_with_real_git(run_hook, pytester, remote_clone, git_ref, arguments, desk):
    remote, clone = remote_clone
    arguments = arguments.format(remote=str(remote))
    assert_blocked(run_hook("Bash", {"command": f"git {arguments}"}, cwd=clone, desk=desk), "git push", "main")
    assert git_ref(remote, "refs/heads/main") != git_ref(clone, "HEAD")
    result = pytester.run(GIT, "-C", str(clone), *shlex.split(arguments), timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(remote, "refs/heads/main") == git_ref(clone, "HEAD")


# --- a push refspec carried by a shell variable assigned earlier in the command line (any session) ---


@pytest.mark.parametrize(
    "command",
    [
        "BR=payload:main; git push origin $BR",
        "BR=payload:main; git push origin ${BR}",
        'BR=payload:main; git push origin "$BR"',
        "BR=HEAD:main; git push origin $BR",
        "REMOTE=origin BR=feature:main; git push $REMOTE $BR",
        "DEST=main; git push origin HEAD:$DEST",
    ],
)
def test_push_refspec_from_an_inline_variable_to_main_is_blocked(run_hook, make_repo, command):
    repo = make_repo("feature")
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), "git push", "main")


@pytest.mark.parametrize(
    "command",
    [
        "BR=feature; git push origin $BR",
        "BR=HEAD:feature; git push origin $BR",
        "git push origin $BR",  # set outside the command line: unresolved, a stated limit
        "git push origin ${BR}",
    ],
)
def test_push_refspec_from_a_variable_to_another_branch_is_allowed(run_hook, make_repo, command):
    assert_allowed(run_hook("Bash", {"command": command}, cwd=make_repo("feature")))


@pytest.mark.skipif(BASH is None, reason="bash runs the command")
def test_push_refspec_from_an_inline_variable_moves_main_with_real_git(run_hook, pytester, remote_clone, git_ref):
    remote, clone = remote_clone
    command = "BR=HEAD:main; git push origin $BR"
    assert_blocked(run_hook("Bash", {"command": command}, cwd=clone), "git push", "main")
    assert git_ref(remote, "refs/heads/main") != git_ref(clone, "HEAD")
    result = pytester.run(BASH, "-c", f"cd {shlex.quote(str(clone))} && {command}", timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(remote, "refs/heads/main") == git_ref(clone, "HEAD")


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
    "python -mutils.sort_yaml",
    "python3 -Im utils.merge_data",
    "uv run -m utils.sort_yaml --skip_links",
    "python utils/main.py",
    "python ./utils/main.py",
    "cd utils && python main.py",
    "python -m utils.main",
    "pixi run merge",
    "pixi run sort",
    "pixi run -e default links",
    "pixi run -m pixi.toml sort",
    "pixi run --manifest-path pixi.toml merge",
    "python utils/import_python_official.py",
    "python3 ./utils/import_python_organizers.py",
    "uv run --with pyyaml python utils/import_python_organizers.py",
    "python -m utils.import_python_official",
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
    "git update-ref -d refs/remotes/origin/auto/conference-updates",
    "git rev-parse -q --verify origin/auto/conference-updates",
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


def test_desk_routine_makes_no_git_config_changes():
    text = (ROOT / ".claude" / "routines" / "desk.md").read_text(encoding="utf-8")
    assert not re.search(r"git (?:-C \S+ )?(?:-c|--config-env)\b|git config|GIT_CONFIG", text)


def test_desk_data_edit_is_allowed(run_hook, make_repo):
    repo = make_repo(ROLLING)
    outcome = run_hook("Edit", github_edit("Edit", repo / "_data" / "conferences.yml"), cwd=repo, desk=True)
    assert_allowed(outcome)


# --- git config changes in a desk run ---


DESK_CONFIG_CHANGES = [
    # -c and --config-env settings, whatever they set
    "git -c alias.p=push p --force origin HEAD:main",
    "git -c alias.p=push p origin HEAD:auto/conference-updates",
    "git -c ALIAS.P=push P origin HEAD:auto/conference-updates",
    "git -c 'alias.c=!git commit' c -m x",
    "git -c user.name=Desk commit -m x",
    "git -c core.quotepath=off status --short",
    "git -c include.path=/tmp/extra.cfg status",
    "git -c includeIf.onbranch:auto/**.path=/tmp/extra.cfg status",
    "git -c help.autocorrect=immediate status",
    "git -c push.default=matching push origin HEAD:auto/conference-updates",
    "git -c push.followTags=true push origin HEAD:auto/conference-updates",
    "git -c 'remote.origin.push=refs/heads/*:refs/heads/*' push origin HEAD:auto/conference-updates",
    "git -c remote.origin.pushurl=/tmp/other.git push origin HEAD:auto/conference-updates",
    "git -c url./tmp/other.git.pushInsteadOf=https://github.com/ status",
    "git -C <queue> -c remote.origin.pushurl=/tmp/other.git push origin HEAD:desk-queue",
    "git --config-env=alias.p=PUSH p origin HEAD:auto/conference-updates",
    "git --config-env alias.p=PUSH p origin HEAD:auto/conference-updates",
    "git --config-env=push.default=MODE push origin HEAD:auto/conference-updates",
    # git config calls that are not pure reads
    "git config alias.p push",
    "git config --global alias.p push",
    "git config --add Alias.p push",
    "git config --file .git/config alias.p 'push --force'",
    "git config set alias.p push",
    "git config --rename-section old alias",
    "git config alias.p push && git p origin HEAD:auto/conference-updates",
    "/usr/lib/git-core/git-config alias.p push",
    "git config user.email desk@example.com",
    "git config --unset user.name",
    "git config include.path /tmp/extra.cfg",
    "git config remote.origin.pushurl /tmp/other.git",
    "git config --global push.default matching",
    "git config --edit",
    "git config user.name --get",
    "git config -- user.name --list",
    "git config --file --get probe.key value",
    "git config -f --list probe.key value",
    "git config --fil --get probe.key value",
    "git config --type --get probe.key value",
    # the read subcommands of newer git
    "git config get user.name",
    "git config list",
    "git config get --all remote.origin.fetch",
    # GIT_CONFIG* environment variables
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=push git p origin HEAD:auto/conference-updates",
    "GIT_CONFIG_PARAMETERS=\"'push.default'='matching'\" git push origin HEAD:auto/conference-updates",
    "GIT_CONFIG_GLOBAL=/tmp/extra.cfg git status",
    "GIT_CONFIG_SYSTEM=/tmp/extra.cfg git status",
    "GIT_CONFIG_NOSYSTEM=1 git status",
    "GIT_CONFIG=/tmp/extra.cfg git status",
    "GIT_CONFIG_COUNT+=1 git status",
    "GIT_CONFIG_COUNT=1",
    "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=push.default GIT_CONFIG_VALUE_0=matching git push origin HEAD",
    "env -u GIT_DIR GIT_CONFIG_GLOBAL=/tmp/extra.cfg git status",
    "sudo GIT_CONFIG_GLOBAL=/tmp/extra.cfg git status",
    "export GIT_CONFIG_GLOBAL=/tmp/extra.cfg",
    "export GIT_CONFIG_GLOBAL=/tmp/extra.cfg && git status",
    "export -n X GIT_CONFIG_COUNT=1",
    "declare -x GIT_CONFIG_COUNT=1",
    "typeset -x GIT_CONFIG_KEY_0=alias.p",
    "f() { local GIT_CONFIG_VALUE_0=push; git status; }; f",
    "readonly GIT_CONFIG_NOSYSTEM=1",
    "builtin export GIT_CONFIG_COUNT=1",
    "command export GIT_CONFIG_COUNT=1",
    "bash -c 'GIT_CONFIG_COUNT=1 git status'",
    "eval export GIT_CONFIG_GLOBAL=/tmp/extra.cfg",
    "for i in 1; do GIT_CONFIG_COUNT=1 git status; done",
    # an exported name, whose value another command set
    "export GIT_CONFIG_COUNT",
    "printf -v GIT_CONFIG_COUNT 1; export GIT_CONFIG_COUNT",
    "read GIT_CONFIG_KEY_0 <<< alias.p && export GIT_CONFIG_KEY_0",
    "export -- GIT_CONFIG_VALUE_0",
    "declare -x GIT_CONFIG_PARAMETERS",
    "typeset -x GIT_CONFIG_GLOBAL",
    "f() { local GIT_CONFIG_NOSYSTEM; }; f",
]


@pytest.mark.parametrize("command", DESK_CONFIG_CHANGES)
@pytest.mark.parametrize(("fields", "scope"), [({}, "in desk runs"), (SUBAGENT, "for subagents in desk runs")])
def test_desk_git_config_changes_are_blocked(run_hook, make_repo, queue_repo, command, fields, scope):
    repo = make_repo(ROLLING)
    command = command.replace("<queue>", str(queue_repo))
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **fields), "config", scope)


@pytest.mark.parametrize(
    "command",
    [
        "git config --get alias.p",
        "git config --get-all remote.origin.fetch",
        "git config --get-regexp '^remote\\.'",
        "git config --list",
        "git config -l",
        "git config --show-origin --list",
        "git config --global --get user.name",
        "git config --file .git/config --get user.name",
        "git config -f .git/config --list",
        "git -C <queue> config --get remote.origin.url",
        "git config --get user.name --get",
        # words that name GIT_CONFIG* variables without assigning one
        "echo GIT_CONFIG_COUNT=1",
        "grep -rn GIT_CONFIG_COUNT= utils",
        "env | grep GIT_CONFIG",
        "export GIT_TRACE=1",
        "GIT_TRACE=1 git status",
    ],
)
@pytest.mark.parametrize("fields", [{}, SUBAGENT])
def test_desk_git_config_reads_are_allowed(run_hook, make_repo, queue_repo, command, fields):
    repo = make_repo(ROLLING)
    command = command.replace("<queue>", str(queue_repo))
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **fields))


@pytest.mark.parametrize("command", ["git -c user.name=x status", "GIT_CONFIG_COUNT=0 git status", "git config a.b c"])
def test_git_config_changes_outside_desk_runs_are_allowed(run_hook, make_repo, command):
    assert_allowed(run_hook("Bash", {"command": command}, cwd=make_repo(ROLLING)))


def test_git_config_file_option_takes_the_read_option_as_its_value_with_real_git(run_hook, pytester, remote_clone):
    _, clone = remote_clone
    command = "git config --file --get probe.key value"
    assert_blocked(run_hook("Bash", {"command": command}, cwd=clone, desk=True), "git config", "desk runs")
    assert not (clone / "--get").exists()
    result = pytester.run(GIT, "-C", str(clone), *shlex.split(command)[1:], timeout=30)
    assert result.ret == 0, result.errlines
    assert "probe" in (clone / "--get").read_text(encoding="utf-8")


@pytest.mark.skipif(BASH is None, reason="bash runs the command")
def test_git_config_variables_exported_by_name_push_main_with_real_git(run_hook, pytester, remote_clone, git_ref):
    remote, clone = remote_clone
    command = (
        "printf -v GIT_CONFIG_COUNT 1; printf -v GIT_CONFIG_KEY_0 alias.p; printf -v GIT_CONFIG_VALUE_0 push; "
        "export GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0; git p origin HEAD:main"
    )
    outcome = run_hook("Bash", {"command": command}, cwd=clone, desk=True)
    assert_blocked(outcome, "export GIT_CONFIG_COUNT", "desk runs")
    assert git_ref(remote, "refs/heads/main") != git_ref(clone, "HEAD")
    result = pytester.run(BASH, "-c", f"cd {shlex.quote(str(clone))} && {command}", timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(remote, "refs/heads/main") == git_ref(clone, "HEAD")


@pytest.mark.parametrize(
    ("command", "named"),
    [
        ("read GIT_CONFIG_COUNT <<< 1", "``read``"),
        ("printf -v GIT_CONFIG_COUNT 1", "``printf -v``"),
        ("set -a; printf -v GIT_CONFIG_COUNT 1", "``set -a``"),
    ],
)
def test_routes_the_docstring_names_as_limits_are_not_inspected(run_hook, make_repo, command, named):
    docstring = " ".join(ast.get_docstring(ast.parse(HOOK.read_text(encoding="utf-8"))).split())
    assert named in docstring
    assert_allowed(run_hook("Bash", {"command": command}, cwd=make_repo(ROLLING), desk=True))


# --- env split-string (any session) ---


ENV_SPLIT_PUSHES = [
    "env -S 'git push origin HEAD:main'",
    "env -iS 'git push origin HEAD:main'",
    "env -S 'git\\_push\\_origin\\_HEAD:main'",
    "env -S 'git push origin \"HEAD:main\"'",
    "env -S 'git push origin HEAD:refs/heads/main'",
    "env --split-string='git push origin HEAD:main'",
    "env --split-string 'git push origin HEAD:main'",
    "env -S git push origin HEAD:main",
    "timeout 120 env -S 'git push origin HEAD:main'",
]


@pytest.mark.parametrize("command", ENV_SPLIT_PUSHES)
def test_env_split_string_push_to_main_is_blocked(run_hook, make_repo, command):
    repo = make_repo("feature")
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), "git push", "main")


@pytest.mark.parametrize(
    "command",
    [
        "env -S '$GIT push origin HEAD:main'",
        "env -S 'git $CMD origin HEAD:main'",
        "env -S 'git push origin \"HEAD:main'",
    ],
)
def test_env_split_string_that_cannot_be_read_is_blocked(run_hook, make_repo, command):
    repo = make_repo("feature")
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo), "env split-string")


@pytest.mark.parametrize(
    "command",
    [
        "env -S 'git status'",
        "env -S 'git push origin HEAD:feature'",
        "env -S 'git push origin $BRANCH'",
        "env -S 'echo git push origin main'",
    ],
)
def test_env_split_string_harmless_commands_outside_desk_runs_are_allowed(run_hook, make_repo, command):
    repo = make_repo("feature")
    assert_allowed(run_hook("Bash", {"command": command}, cwd=repo))


@pytest.mark.parametrize(
    "command",
    [
        "env -S 'git push origin HEAD:main'",
        "env -S 'git status'",
        "env -iS 'git push origin HEAD:main'",
        "env --split-string='git status'",
        "env --split-string 'git status'",
    ],
)
@pytest.mark.parametrize(("fields", "scope"), [({}, "desk runs"), (SUBAGENT, "desk runs")])
def test_env_split_string_in_a_desk_run_is_blocked(run_hook, make_repo, command, fields, scope):
    repo = make_repo(ROLLING)
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **fields), "split", scope)


@pytest.mark.skipif(BASH is None, reason="bash runs the command")
@pytest.mark.parametrize(
    "command",
    [
        "env -S 'git push origin HEAD:main'",
        "env -S 'git\\_push\\_origin\\_HEAD:main'",
        "env -S 'git push origin \"HEAD:main\"'",
        "env --split-string='git push origin HEAD:main'",
    ],
)
def test_env_split_string_push_moves_main_with_real_git(run_hook, pytester, remote_clone, git_ref, command):
    remote, clone = remote_clone
    assert_blocked(run_hook("Bash", {"command": command}, cwd=clone), "git push", "main")
    assert git_ref(remote, "refs/heads/main") != git_ref(clone, "HEAD")
    result = pytester.run(BASH, "-c", f"cd {shlex.quote(str(clone))} && {command}", timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(remote, "refs/heads/main") == git_ref(clone, "HEAD")


@pytest.mark.skipif(BASH is None, reason="bash runs the command")
def test_env_split_string_status_passes_outside_desk_runs_with_real_git(run_hook, pytester, remote_clone):
    _, clone = remote_clone
    command = "env -S 'git status --short'"
    assert_allowed(run_hook("Bash", {"command": command}, cwd=clone))
    result = pytester.run(BASH, "-c", f"cd {shlex.quote(str(clone))} && {command}", timeout=30)
    assert result.ret == 0, result.errlines


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
    "git config --global --get user.name",
    "git config --get user.name --get",
    "git config --get-all remote.origin.fetch",
    "git config --list",
    "git fetch --depth 1 origin main",
    "git fetch --depth=1 origin refs/heads/main",
    "git fetch -j 2 origin main",
    "git fetch --shallow-since 2026-01-01T00:00:00 origin main",
    f"git fetch https://github.com/{REPO}.git main",
    "git fetch --multiple origin upstream",
    "git -C <repo> log -1",
    "git --no-pager log -1",
    "git --version",
    "/usr/lib/git-core/git-log -1",
    "git-status --short",
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
    "python /tmp/scratch/main.py",
    "python -m main",
    "python -m json.tool /tmp/scratch/change-set.json",
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
        "git update-ref -d refs/remotes/origin/auto/conference-updates",
        "git -C <repo> commit -m x",
        "cd <repo> && git commit -m x",
        "git status && git commit -am x",
        "bash -c 'git commit -m x'",
        "for i in 1 2; do git push origin HEAD:desk-queue; done",
        # a --get after the key is the value git config writes
        "git config user.name --get",
        "git config --global user.name --get",
        "git config -- user.name --get",
        # the dashed programs
        "/usr/lib/git-core/git-commit -m x",
        "git-add _data/conferences.yml",
        # fetches that write local refs
        "git fetch origin main:main",
        "git fetch origin +main",
        "git fetch origin +refs/heads/main:refs/heads/auto/conference-updates",
        "git fetch origin HEAD:scratch",
        "git fetch --depth 1 origin main:main",
        "git -C <queue> fetch origin +desk-queue:desk-queue",
        "git fetch origin -- main:main",
        "git fetch --stdin origin",
        "git fetch --refmap=+refs/heads/*:refs/heads/* origin main",
        "git fetch --refm '+refs/heads/*:refs/heads/*' origin main",
        "git fetch origin tag v1",
        "git fetch --depth 1 origin main tag v1",
        "git -C <queue> fetch --no-tags origin tag v1",
    ],
)
def test_subagent_git_writes_are_blocked(run_hook, make_repo, queue_repo, command):
    repo = make_repo(ROLLING)
    command = command.replace("<repo>", str(repo)).replace("<queue>", str(queue_repo))
    assert_blocked(run_hook("Bash", {"command": command}, cwd=repo, desk=True, **SUBAGENT), "git", "subagents")


def test_subagent_fetch_of_a_tag_writes_a_local_tag_with_real_git(run_hook, pytester, git, remote_clone, git_ref):
    remote, clone = remote_clone
    git("-C", str(remote), "tag", "v0", "main")
    command = "git fetch origin tag v0"
    assert_blocked(run_hook("Bash", {"command": command}, cwd=clone, desk=True, **SUBAGENT), "tag", "subagents")
    assert git_ref(clone, "refs/tags/v0") is None
    result = pytester.run(GIT, "-C", str(clone), *shlex.split(command)[1:], timeout=30)
    assert result.ret == 0, result.errlines
    assert git_ref(clone, "refs/tags/v0") == git_ref(remote, "refs/tags/v0")


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
