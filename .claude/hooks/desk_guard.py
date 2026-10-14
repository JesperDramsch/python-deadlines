#!/usr/bin/env python3
"""PreToolUse guard for the deadline desk and every other Claude Code session in this repository.

Claude Code runs this script before Bash, file-edit, WebFetch and claude-code-remote tool calls (see
``.claude/settings.json``) and passes the call as JSON on stdin (``tool_name``, ``tool_input``, ``cwd``).
Exit code 2 blocks the call and the one-line reason on stderr is shown to the agent; exit code 0 lets the
call through to the normal permission flow.

Rules, checked in this order:

1. Any session: a Bash ``git push`` that targets ``main`` or ``master``. That is an explicit refspec
   (``main``, ``HEAD:main``, ``:main``, ``refs/heads/main``, ``--delete main``), ``--all``, ``--mirror`` or
   ``--branches``, or a push without refspecs while the current branch is ``main`` or ``master``.
2. On branch ``auto/conference-updates`` or with ``DESK_ROUTINE=1``: Edit, Write, MultiEdit and
   NotebookEdit on a path under ``.github/``. Bash commands that write there are not inspected.
3. With ``DESK_ROUTINE=1``: every ``mcp__claude-code-remote__*`` tool.
4. When ``~/.desk-guard.json`` exists: its optional regular-expression lists ``deny_bash``, ``deny_tools``,
   ``deny_paths`` and ``deny_urls`` are searched in the Bash command, the tool name, the file path and the
   WebFetch URL. A malformed file blocks every call in a desk run and is ignored elsewhere.

Commands are pattern matched, never run: the script splits the command line into simple commands and reads
the ``git`` invocations. The current branch comes from the repository's ``HEAD`` file. Unreadable hook input
blocks in a desk run and passes elsewhere. Only the Python standard library is used.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path
from pathlib import PurePosixPath

PROTECTED_BRANCHES = frozenset({"main", "master"})
ROLLING_BRANCH = "auto/conference-updates"
FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
REMOTE_TOOL_PREFIX = "mcp__claude-code-remote__"
DENY_LIST_NAME = ".desk-guard.json"
DENY_LIST_KEYS = ("deny_bash", "deny_tools", "deny_paths", "deny_urls")

# git options that take the next word as their value, before and after the "push" subcommand
GIT_OPTIONS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"})
PUSH_OPTIONS_WITH_VALUE = frozenset({"--repo", "-o", "--push-option", "--receive-pack", "--exec"})
PUSH_EVERY_BRANCH = frozenset({"--all", "--mirror", "--branches"})
# Words that run the command after them: "sudo git push", "env X=1 git push", "command git push"
COMMAND_WRAPPERS = frozenset({"command", "env", "exec", "nice", "nohup", "sudo", "time"})
SHELLS = frozenset({"bash", "dash", "ksh", "sh", "zsh"})
SHELL_COMMAND_FLAG = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")  # -c, -lc, -ec
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SHELL_PUNCTUATION = ";&|()<>"
MAX_NESTING = 3


class BlockError(Exception):
    """Raised with the one-line reason when the tool call must be blocked."""


class BadInputError(ValueError):
    """Raised when the hook input is not a PreToolUse JSON object."""


def current_branch(directory: str) -> str | None:
    """Return the branch checked out in the repository that contains ``directory``.

    Reads ``HEAD`` directly, following the ``.git`` file of a worktree, so no git process is started.

    Parameters
    ----------
    directory : str
        Any directory inside the working tree.

    Returns
    -------
    str | None
        The branch name, or None when HEAD is detached or ``directory`` is outside a repository.
    """
    start = Path(directory).absolute()
    for folder in (start, *start.parents):
        dot_git = folder / ".git"
        try:
            if dot_git.is_file():
                pointer = dot_git.read_text(encoding="utf-8").strip()
                if not pointer.startswith("gitdir:"):
                    return None
                git_dir = folder / pointer.removeprefix("gitdir:").strip()
            elif dot_git.is_dir():
                git_dir = dot_git
            else:
                continue
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        prefix = "ref: refs/heads/"
        return head.removeprefix(prefix) if head.startswith(prefix) else None
    return None


def strip_heredocs(command: str) -> str:
    """Drop here-document bodies, which are data rather than commands.

    Parameters
    ----------
    command : str
        The Bash command line.

    Returns
    -------
    str
        The command line without the lines between each ``<<WORD`` and its closing ``WORD``.
    """
    kept = []
    terminator = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        kept.append(line)
        match = HEREDOC.search(line)
        if match:
            terminator = match.group(2)
    return "\n".join(kept)


def split_commands(command: str) -> list[list[str]]:
    """Split a command line into simple commands at ``;``, ``&&``, ``||``, ``|``, ``&``, brackets and newlines.

    Parameters
    ----------
    command : str
        The Bash command line.

    Returns
    -------
    list[list[str]]
        The words of each simple command; redirections and their targets are left out.
    """
    text = strip_heredocs(command).replace("\n", " ; ").replace("`", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: fall back to plain whitespace words between the separators
        return [part.split() for part in re.split(r"[;&|()<>]+", text) if part.split()]

    commands: list[list[str]] = [[]]
    skip_target = False
    for token in tokens:
        if skip_target:
            skip_target = False
        elif token and all(char in SHELL_PUNCTUATION for char in token):
            if "<" in token or ">" in token:
                skip_target = True
            else:
                commands.append([])
        else:
            commands[-1].append(token)
    return [words for words in commands if words]


def refspec_target(refspec: str, directory: str) -> str:
    """Return the remote branch a push refspec writes to.

    Parameters
    ----------
    refspec : str
        A refspec such as ``main``, ``HEAD:main``, ``+feature:refs/heads/main`` or ``:main``.
    directory : str
        Repository directory, used to resolve ``HEAD``.

    Returns
    -------
    str
        The destination branch name without ``refs/heads/``.
    """
    source, colon, destination = refspec.lstrip("+").partition(":")
    target = destination if colon else source
    if target in {"HEAD", "@"}:
        target = current_branch(directory) or target
    return target.removeprefix("refs/heads/")


def push_reason(args: list[str], directory: str) -> str | None:
    """Return why a ``git push`` with these arguments reaches main or master, or None when it does not.

    Parameters
    ----------
    args : list[str]
        Words after ``push``.
    directory : str
        Repository directory the push runs in.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    positionals: list[str] = []
    remote_given_as_option = False
    skip_value = False
    for index, arg in enumerate(args):
        if skip_value:
            skip_value = False
        elif arg == "--":
            positionals.extend(args[index + 1 :])
            break
        elif arg in PUSH_EVERY_BRANCH:
            return f"git push {arg} also pushes main"
        elif arg in PUSH_OPTIONS_WITH_VALUE:
            skip_value = True
            remote_given_as_option = remote_given_as_option or arg == "--repo"
        elif arg.startswith("-"):
            remote_given_as_option = remote_given_as_option or arg.startswith("--repo=")
        else:
            positionals.append(arg)

    refspecs = positionals if remote_given_as_option else positionals[1:]
    if not refspecs:
        branch = current_branch(directory)
        if branch in PROTECTED_BRANCHES:
            return f"git push without a refspec from branch {branch}"
        return None
    for refspec in refspecs:
        target = refspec_target(refspec, directory)
        if target in PROTECTED_BRANCHES:
            return f"git push refspec {refspec!r} targets {target}"
    return None


def git_push_reason(command: str, cwd: str, depth: int = 0) -> str | None:
    """Return why a Bash command pushes to main or master, or None when it does not.

    Parameters
    ----------
    command : str
        The Bash command line.
    cwd : str
        Directory the command starts in; ``cd`` and ``git -C`` move it.
    depth : int
        Nesting level of ``sh -c`` and ``eval`` strings already unwrapped.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    directory = cwd
    for words in split_commands(command):
        start = 0
        while start < len(words) and (
            ASSIGNMENT.match(words[start]) or words[start] in COMMAND_WRAPPERS or words[start].startswith("-")
        ):
            start += 1
        if start == len(words):
            continue
        program, rest = Path(words[start]).name, words[start + 1 :]

        if program == "cd":
            target = rest[0] if rest else "~"
            directory = str(Path(directory, Path(target).expanduser()))
        elif program in SHELLS and depth < MAX_NESTING:
            for index, word in enumerate(rest[:-1]):
                if SHELL_COMMAND_FLAG.match(word):
                    reason = git_push_reason(rest[index + 1], directory, depth + 1)
                    if reason:
                        return reason
                    break
        elif program == "eval" and depth < MAX_NESTING:
            reason = git_push_reason(" ".join(rest), directory, depth + 1)
            if reason:
                return reason
        elif program == "git":
            git_directory = directory
            index = 0
            while index < len(rest) and rest[index].startswith("-"):
                if rest[index] == "-C" and index + 1 < len(rest):
                    git_directory = str(Path(git_directory, Path(rest[index + 1]).expanduser()))
                index += 2 if rest[index] in GIT_OPTIONS_WITH_VALUE else 1
            if index < len(rest) and rest[index] == "push":
                reason = push_reason(rest[index + 1 :], git_directory)
                if reason:
                    return reason
    return None


def is_under_github(path: str, cwd: str) -> bool:
    """Return True when ``path`` lies under a ``.github`` directory.

    Parameters
    ----------
    path : str
        File path from the tool input, absolute or relative to ``cwd``.
    cwd : str
        The session's working directory.

    Returns
    -------
    bool
        Whether a path component is ``.github``.
    """
    full = PurePosixPath(cwd.replace("\\", "/"), path.replace("\\", "/"))
    return ".github" in full.parts


def load_deny_list(*, desk: bool) -> dict[str, list[re.Pattern[str]]]:
    """Read the optional deny-list from ``~/.desk-guard.json``.

    Parameters
    ----------
    desk : bool
        Whether this is a desk run, where a malformed file blocks the call.

    Returns
    -------
    dict[str, list[re.Pattern[str]]]
        Compiled patterns per key; empty when the file is absent, or malformed outside a desk run.

    Raises
    ------
    BlockError
        When the file is malformed in a desk run.
    """
    path = Path.home() / DENY_LIST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("the top level is not a JSON object")
        patterns = {}
        for key in DENY_LIST_KEYS:
            values = data.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"{key} is not a list of strings")
            patterns[key] = [re.compile(value) for value in values]
    except (OSError, ValueError, re.error) as error:
        if desk:
            raise BlockError(f"~/{DENY_LIST_NAME} is malformed ({error}); fix or remove it") from error
        return {}
    return patterns


def check(payload: dict, *, desk: bool) -> None:
    """Apply every rule to one PreToolUse call.

    Parameters
    ----------
    payload : dict
        The decoded hook input.
    desk : bool
        Whether ``DESK_ROUTINE=1`` is set.

    Raises
    ------
    BadInputError
        When ``tool_name`` or ``tool_input`` is missing or has the wrong type.
    BlockError
        When a rule blocks the call.
    """
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        raise BadInputError("tool_name or tool_input is missing")
    cwd = payload["cwd"] if isinstance(payload.get("cwd"), str) else str(Path.cwd())
    command = tool_input.get("command") if tool == "Bash" else None
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    url = tool_input.get("url") if tool == "WebFetch" else None

    if isinstance(command, str):
        reason = git_push_reason(command, cwd)
        if reason:
            raise BlockError(f"{reason}; push to another branch instead")

    if tool in FILE_TOOLS and isinstance(path, str) and is_under_github(path, cwd):
        if desk:
            raise BlockError(f"{tool} under .github/ is off limits in desk runs ({path})")
        if current_branch(cwd) == ROLLING_BRANCH:
            raise BlockError(f"{tool} under .github/ is off limits on {ROLLING_BRANCH} ({path})")

    if desk and tool.startswith(REMOTE_TOOL_PREFIX):
        raise BlockError(f"{tool} is off limits in desk runs")

    deny_list = load_deny_list(desk=desk)
    subjects = {"deny_bash": command, "deny_tools": tool, "deny_paths": path, "deny_urls": url}
    for key, subject in subjects.items():
        if not isinstance(subject, str):
            continue
        for pattern in deny_list.get(key, []):
            if pattern.search(subject):
                raise BlockError(f"~/{DENY_LIST_NAME} {key} pattern {pattern.pattern!r} matches")


def block(reason: str) -> int:
    """Print the block reason to stderr on one line and return exit code 2."""
    print("desk_guard: " + " ".join(reason.split()), file=sys.stderr)
    return 2


def main() -> int:
    """Read the hook input from stdin and return the exit code."""
    desk = os.environ.get("DESK_ROUTINE") == "1"
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise BadInputError("the hook input is not a JSON object")
        check(payload, desk=desk)
    except BlockError as error:
        return block(str(error))
    except ValueError as error:
        return block(f"unreadable hook input ({error})") if desk else 0
    except Exception as error:
        # A crash must never let a desk call through; elsewhere it must never get in the way
        return block(f"internal error ({error!r})") if desk else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
