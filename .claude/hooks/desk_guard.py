#!/usr/bin/env python3
"""PreToolUse guard for the deadline desk and every other Claude Code session in this repository.

Claude Code runs this script before Bash, file-edit, WebFetch and claude-code-remote tool calls (see
``.claude/settings.json``) and passes the call as JSON on stdin (``tool_name``, ``tool_input``, ``cwd``).
Exit code 2 blocks the call and the one-line reason on stderr is shown to the agent; exit code 0 lets the
call through to the normal permission flow.

Rules, checked in this order:

1. Any session: a Bash ``git push`` that targets ``main`` or ``master``. That is a refspec whose destination
   is the branch (``main``, ``HEAD:main``, ``:main``, ``refs/heads/main``, ``heads/main``, ``--delete main``)
   or a glob that covers it (``refs/heads/*:refs/heads/*``), the matching refspec ``:``, ``--all``,
   ``--mirror`` or ``--branches``, or a push without refspecs while the current branch is ``main`` or
   ``master``. A ``--dry-run`` push and a push of ``--tags`` alone send no branch and pass.
2. On branch ``auto/conference-updates`` or with ``DESK_ROUTINE=1``: Edit, Write, MultiEdit and
   NotebookEdit on a path under a repository's own ``.github/`` directory. Bash commands that write there
   are not inspected.
3. With ``DESK_ROUTINE=1``: every ``mcp__claude-code-remote__*`` tool.
4. When ``~/.desk-guard.json`` exists: its optional regular-expression lists ``deny_bash``, ``deny_tools``,
   ``deny_paths`` and ``deny_urls`` are searched in the Bash command, the tool name, the file path and the
   WebFetch URL. A malformed file blocks every call in a desk run and is ignored elsewhere.

Commands are pattern matched, never run: the script splits the command line into simple commands, steps over
shell reserved words (``do``, ``then``, ``!``, ``{``), variable assignments and wrappers with their options
(``sudo -u bob``, ``timeout 120``, ``env -C dir``), and reads the ``git`` invocations. The current branch
comes from the repository's ``HEAD`` file. Unreadable hook input blocks in a desk run and passes elsewhere.
Only the Python standard library is used.
"""

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

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
PUSH_DRY_RUN = frozenset({"--dry-run", "-n"})
# Shell reserved words that can stand before a command: "do git push", "if ! git push", "{ git push; }"
RESERVED_WORDS = frozenset({"!", "{", "}", "if", "then", "elif", "else", "do", "while", "until", "coproc"})
# Words that run the command after them, with their options that take a value and the number of operands
# before that command: "sudo -u bob git push", "timeout -s KILL 120 git push", "flock lockfile git push"
WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "command": (frozenset(), 0),
    "doas": (frozenset({"-C", "-u"}), 0),
    "env": (frozenset({"-C", "--chdir", "-S", "--split-string", "-u", "--unset"}), 0),
    "exec": (frozenset({"-a"}), 0),
    "flock": (frozenset({"-E", "--conflict-exit-code", "-w", "--timeout", "--wait"}), 1),
    "ionice": (frozenset({"-c", "--class", "-n", "--classdata"}), 0),
    "nice": (frozenset({"-n", "--adjustment"}), 0),
    "nohup": (frozenset(), 0),
    "setsid": (frozenset(), 0),
    "stdbuf": (frozenset({"-e", "--error", "-i", "--input", "-o", "--output"}), 0),
    "sudo": (
        frozenset({"-C", "--close-from", "-D", "--chdir", "-g", "--group", "-p", "--prompt", "-r", "--role"})
        | {"-T", "--command-timeout", "-t", "--type", "-U", "--other-user", "-u", "--user"},
        0,
    ),
    "time": (frozenset({"-f", "--format", "-o", "--output"}), 0),
    "timeout": (frozenset({"-k", "--kill-after", "-s", "--signal"}), 1),
    "watch": (frozenset({"-n", "--interval"}), 0),
    "xargs": (
        frozenset({"-a", "--arg-file", "-d", "--delimiter", "-E", "-I", "-L", "--max-lines", "-n", "--max-args"})
        | {"-P", "--max-procs", "-s", "--max-chars"},
        0,
    ),
}
# Wrapper options that set the directory the command runs in
WRAPPER_CHDIR = {"env": frozenset({"-C", "--chdir"}), "sudo": frozenset({"-D", "--chdir"})}
SHELLS = frozenset({"bash", "dash", "ksh", "sh", "su", "zsh"})
SHELL_COMMAND_FLAG = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")  # -c, -lc, -ec
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SHELL_PUNCTUATION = ";&|()<>"
MAX_NESTING = 3


class BlockError(Exception):
    """Raised with the one-line reason when the tool call must be blocked."""


class BadInputError(ValueError):
    """Raised when the hook input is not a PreToolUse JSON object."""


def find_repository(directory: Path) -> tuple[Path, Path] | None:
    """Return the working-tree root and git directory of the repository that contains ``directory``.

    Follows the ``.git`` file of a worktree or submodule, so no git process is started. ``directory`` need
    not exist: its existing ancestors are searched.

    Parameters
    ----------
    directory : Path
        An absolute directory path.

    Returns
    -------
    tuple[Path, Path] | None
        The root and the git directory, or None when ``directory`` is outside a repository.
    """
    for folder in (directory, *directory.parents):
        dot_git = folder / ".git"
        try:
            if dot_git.is_file():
                pointer = dot_git.read_text(encoding="utf-8").strip()
                if not pointer.startswith("gitdir:"):
                    return None
                return folder, folder / pointer.removeprefix("gitdir:").strip()
            if dot_git.is_dir():
                return folder, dot_git
        except OSError:
            return None
    return None


def current_branch(directory: str) -> str | None:
    """Return the branch checked out in the repository that contains ``directory``.

    Reads ``HEAD`` directly, so no git process is started.

    Parameters
    ----------
    directory : str
        Any directory inside the working tree.

    Returns
    -------
    str | None
        The branch name, or None when HEAD is detached or ``directory`` is outside a repository.
    """
    repository = find_repository(Path(directory).absolute())
    if repository is None:
        return None
    try:
        head = (repository[1] / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "ref: refs/heads/"
    return head.removeprefix(prefix) if head.startswith(prefix) else None


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


def takes_value(option: str, options: frozenset[str]) -> bool:
    """Return True when ``option`` is followed by a separate value word.

    Parameters
    ----------
    option : str
        An option word, such as ``-u``, ``--user`` or a cluster of short options like ``-Eu``.
    options : frozenset[str]
        The options of the program that take a value.

    Returns
    -------
    bool
        Whether the next word is the option's value.
    """
    if option in options:
        return True
    return not option.startswith("--") and len(option) > 2 and f"-{option[-1]}" in options


def command_start(words: list[str], directory: str) -> tuple[int, str]:
    """Find the program of a simple command behind reserved words, assignments and wrappers.

    Parameters
    ----------
    words : list[str]
        The words of one simple command.
    directory : str
        Directory the command starts in.

    Returns
    -------
    tuple[int, str]
        The index of the program in ``words`` (``len(words)`` when there is none) and the directory it runs
        in, which ``env -C`` and ``sudo -D`` change.
    """
    index = 0
    while index < len(words):
        word = words[index]
        name = Path(word).name
        if word in RESERVED_WORDS or ASSIGNMENT.match(word):
            index += 1
        elif word == "function":
            index += 2  # the function's name follows
        elif name in WRAPPERS:
            options, operands = WRAPPERS[name]
            index += 1
            while index < len(words) and words[index].startswith("-") and words[index] != "-":
                option, equals, attached = words[index].partition("=")
                index += 1
                if option == "--":
                    break
                value = attached if equals else None
                if value is None and takes_value(option, options) and index < len(words):
                    value = words[index]
                    index += 1
                if value is not None and option in WRAPPER_CHDIR.get(name, ()):
                    directory = str(Path(directory, Path(value).expanduser()))
            index += operands
        else:
            break
    return min(index, len(words)), directory


def refspec_destination(refspec: str, directory: str) -> str:
    """Return the remote ref a push refspec writes to.

    Parameters
    ----------
    refspec : str
        A refspec such as ``main``, ``HEAD:main``, ``+feature:refs/heads/main``, ``:main`` or a glob such
        as ``refs/heads/*:refs/heads/*``.
    directory : str
        Repository directory, used to resolve ``HEAD``.

    Returns
    -------
    str
        The destination as a full ref (``refs/heads/main``), still holding any ``*`` of a glob. The
        refspec ``:`` pushes every matching branch and gives ``refs/heads/*``.
    """
    if refspec.lstrip("+") == ":":
        return "refs/heads/*"
    source, colon, destination = refspec.lstrip("+").partition(":")
    target = destination if colon else source
    if target in {"HEAD", "@"}:
        target = current_branch(directory) or target
    if target.startswith("refs/"):
        return target
    if target.startswith("heads/"):
        return "refs/" + target
    return "refs/heads/" + target


def protected_branch(destination: str) -> str | None:
    """Return the protected branch a push destination reaches, or None.

    Parameters
    ----------
    destination : str
        A full destination ref, possibly a glob (``refs/heads/*``).

    Returns
    -------
    str | None
        ``main`` or ``master`` when the destination is that branch or a glob that covers it.
    """
    for branch in sorted(PROTECTED_BRANCHES):
        # Ref names cannot contain "?" or "[", so "*" is the only pattern character left to match
        if fnmatch.fnmatchcase(f"refs/heads/{branch}", destination):
            return branch
    return None


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
    flags: set[str] = set()
    remote_given_as_option = False
    skip_value = False
    for index, arg in enumerate(args):
        if skip_value:
            skip_value = False
        elif arg == "--":
            positionals.extend(args[index + 1 :])
            break
        elif arg in PUSH_OPTIONS_WITH_VALUE:
            skip_value = True
            remote_given_as_option = remote_given_as_option or arg == "--repo"
        elif arg.startswith("-"):
            flags.add(arg.partition("=")[0])
        else:
            positionals.append(arg)
    remote_given_as_option = remote_given_as_option or "--repo" in flags

    if flags & PUSH_DRY_RUN:
        return None
    every_branch = sorted(flags & PUSH_EVERY_BRANCH)
    if every_branch:
        return f"git push {every_branch[0]} also pushes main"

    refspecs = positionals if remote_given_as_option else positionals[1:]
    if not refspecs:
        if "--tags" in flags and "--follow-tags" not in flags:
            return None  # pushes refs/tags/* only
        branch = current_branch(directory)
        if branch in PROTECTED_BRANCHES:
            return f"git push without a refspec from branch {branch}"
        return None
    after_tag = False
    for refspec in refspecs:
        if after_tag:
            after_tag = False  # "tag <name>" pushes refs/tags/<name>
            continue
        if refspec == "tag":
            after_tag = True
            continue
        branch = protected_branch(refspec_destination(refspec, directory))
        if branch:
            return f"git push refspec {refspec!r} targets {branch}"
    return None


def git_push_reason(command: str, cwd: str, depth: int = 0) -> str | None:
    """Return why a Bash command pushes to main or master, or None when it does not.

    Parameters
    ----------
    command : str
        The Bash command line.
    cwd : str
        Directory the command starts in; ``cd``, ``git -C`` and ``env -C`` move it.
    depth : int
        Nesting level of ``sh -c`` and ``eval`` strings already unwrapped.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    directory = cwd
    for words in split_commands(command):
        start, command_directory = command_start(words, directory)
        if start == len(words):
            continue
        program, rest = Path(words[start]).name, words[start + 1 :]

        if program == "cd":
            target = rest[0] if rest else "~"
            directory = str(Path(command_directory, Path(target).expanduser()))
        elif program in SHELLS and depth < MAX_NESTING:
            for index, word in enumerate(rest[:-1]):
                if SHELL_COMMAND_FLAG.match(word):
                    reason = git_push_reason(rest[index + 1], command_directory, depth + 1)
                    if reason:
                        return reason
                    break
        elif program == "eval" and depth < MAX_NESTING:
            reason = git_push_reason(" ".join(rest), command_directory, depth + 1)
            if reason:
                return reason
        elif program == "git":
            git_directory = command_directory
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


def github_repository(path: str, cwd: str) -> Path | None:
    """Return the root of the repository whose own ``.github/`` directory holds ``path``.

    Parameters
    ----------
    path : str
        File path from the tool input, absolute or relative to ``cwd``.
    cwd : str
        The session's working directory.

    Returns
    -------
    Path | None
        The repository root, or None when ``path`` is outside every repository or not under its root's
        ``.github/`` (a ``.github`` deeper in the tree, such as a vendored package's, does not count).
    """
    full = Path(cwd, Path(path).expanduser()).resolve()
    repository = find_repository(full.parent)
    if repository is None:
        return None
    parts = full.relative_to(repository[0]).parts
    return repository[0] if len(parts) > 1 and parts[0] == ".github" else None


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

    root = github_repository(path, cwd) if tool in FILE_TOOLS and isinstance(path, str) else None
    if root is not None:
        if desk:
            raise BlockError(f"{tool} under .github/ is off limits in desk runs ({path})")
        if ROLLING_BRANCH in {current_branch(str(root)), current_branch(cwd)}:
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
