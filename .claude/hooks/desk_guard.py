#!/usr/bin/env python3
"""PreToolUse guard for the deadline desk and every other Claude Code session in this repository.

Claude Code runs this script before Bash, Edit, Write, MultiEdit, NotebookEdit and WebFetch calls, before every
MCP tool, before CronCreate, CronDelete, CronList, RemoteTrigger and ScheduleWakeup, and before Agent, the tool
that starts a subagent, which older versions name Task (see ``.claude/settings.json``). It passes the call as
JSON on stdin: ``tool_name``, ``tool_input``, ``cwd`` and, when a subagent makes the call, ``agent_id`` and the
subagent's type as ``agent_type``. Exit code 2 blocks the call and the one-line reason on stderr is shown to the
agent; exit code 0 lets the call through to the normal permission flow. Claude Code treats any other exit
code as a non-blocking error, so in desk runs the settings command turns one, such as a crash on import, into
exit code 2. A desk run is a session with ``DESK_ROUTINE=1``.

Rules for every session:

1. A Bash ``git push`` that targets ``main`` or ``master`` is blocked, and so are the plumbing commands
   ``git send-pack`` and ``git http-push``, which write remote refs the same way and take the same remote
   and refspecs. That is a refspec whose destination is
   the branch (``main``, ``HEAD:main``, ``:main``, ``refs/heads/main``, ``heads/main``, ``--delete main``) or a
   glob that covers it (``refs/heads/*:refs/heads/*``), the matching refspec ``:``, ``--all``, ``--mirror`` or
   ``--branches``, or a push without refspecs while the current branch is ``main`` or ``master``. A
   ``--dry-run`` push and a push of ``--tags`` alone send no branch and pass, unless ``--no-dry-run`` or
   ``--no-tags`` undoes the option. A long option counts in any abbreviation git accepts (``--mirr``,
   ``--al``). A refspec built from a ``$NAME`` or ``${NAME}`` resolves when that name is assigned a literal
   value earlier in the same command line (``BR=x:main; git push origin $BR``); a name set outside the
   command line cannot be resolved and is a stated limit below.
2. On branch ``auto/conference-updates``, Edit, Write, MultiEdit and NotebookEdit on a path under a
   repository's own ``.github/`` directory are blocked. Bash commands that write there are not inspected.
3. When ``~/.desk-guard.json`` exists, its optional regular-expression lists ``deny_bash``, ``deny_tools``,
   ``deny_paths`` and ``deny_urls`` are searched in the Bash command, the tool name, the file path and the
   WebFetch URL. A file path is searched twice: as given, and as the absolute path it names from ``cwd``
   with ``~`` expanded and ``.``, ``..`` and repeated slashes removed. Symlinks are not followed. Outside desk
   runs a malformed file is ignored, and Agent and Task calls, which reach the hook only for rule 10, pass
   without this check.

Rules for desk runs, on top of those:

4. ``~/.desk-guard.json`` must exist and hold a JSON object in the form rule 3 reads. When it is missing,
   unreadable or malformed, every call is blocked.
5. Every MCP tool (``mcp__*``) and CronCreate, CronDelete, CronList, RemoteTrigger and ScheduleWakeup are
   blocked.
6. Rule 2 holds on every branch.
7. ``git push`` must name the remote ``origin`` and at least one refspec, and every refspec must write
   ``auto/conference-updates`` or ``desk-queue``. ``--force``, ``--force-with-lease``, ``-f``, ``--delete``,
   ``-d``, ``--mirror``, ``--all``, ``--branches``, ``--tags``, ``--follow-tags``, ``--prune`` and
   ``--recurse-submodules`` (with any value) are blocked, alone, bundled (``-fu``) or abbreviated
   (``--force-w``, ``--del``), and so is a refspec that starts with ``+`` or ``:``. Dry runs get no exemption.
   ``git send-pack`` and ``git http-push`` are held to this rule too, as rule 1 says.
8. Desk runs make no git config changes. Every ``-c`` and ``--config-env`` setting on a git command is
   blocked, whatever it sets, and so is every ``git config`` call that is not a pure read: one that names
   ``--get``, ``--get-all``, ``--get-regexp``, ``--list`` or ``-l`` before the first word that is not an
   option or an option's value. ``git config get`` and ``git config list``, the read subcommands of newer
   git, are blocked as well. A word that assigns an environment variable whose name starts with
   ``GIT_CONFIG`` (``GIT_CONFIG_COUNT``, ``GIT_CONFIG_KEY_<n>``, ``GIT_CONFIG_PARAMETERS``,
   ``GIT_CONFIG_GLOBAL`` and the rest) is blocked too: as a leading assignment, an ``env`` operand, or an
   ``export``, ``declare``, ``typeset``, ``local`` or ``readonly`` argument. Such an argument is blocked
   without a value as well (``export GIT_CONFIG_COUNT``), since it exports a value set another way. This
   closes the routes through aliases, ``include.path``, ``includeIf``, ``help.autocorrect``, ``push.*``,
   ``remote.*`` and ``url.*``.
9. ``gh`` runs only as ``gh api``. A request is a write when ``-X`` or ``--method`` sets a method other than
   GET, or when it passes ``-f``, ``-F``, ``--field``, ``--raw-field`` or ``--input``. The only writes allowed
   go to ``repos/JesperDramsch/python-deadlines``: POST ``pulls``, PATCH ``pulls/<n>``, POST
   ``issues/<n>/comments`` and POST ``issues/<n>/labels``. The endpoint is written out literally, with or
   without a leading slash or as a full ``https://api.github.com/`` URL, and without ``--hostname``.
10. An Agent or Task call must start a subagent of a type in ``DESK_AGENT_TYPES``, which holds only
    ``desk-research`` (``.claude/agents/desk-research.md``). A call whose ``subagent_type`` names another type,
    or that has no ``subagent_type``, is blocked.

Rules for subagents in desk runs, on top of those:

11. Only ``desk-research`` subagents may act. A call that carries ``agent_id`` is blocked when its
    ``agent_type`` is not in ``DESK_AGENT_TYPES`` or is missing. The hook sees only the tools listed above, so
    such a subagent's Read, Grep, Glob and WebSearch calls never reach this rule.

``desk-research`` has only Read, Grep, Glob, WebFetch and WebSearch: no Bash and no file tools. Rules 12 to 16
are a second layer: they matter only if that type restriction fails.

12. ``git`` runs only status, log, show, diff, grep, ls-files, ls-remote, ls-tree, rev-parse, rev-list,
    merge-base, blame, cat-file, fetch, describe, shortlog, for-each-ref, show-ref and a pure ``config``
    read (rule 8), or with no subcommand at all (``git --version``). Rule 8 already blocks every ``-c``,
    ``--config-env`` and ``GIT_CONFIG*`` setting. A ``fetch`` refspec after the remote that contains ``:``
    or starts with ``+`` writes a local ref and is blocked, and so is the word ``tag`` after the remote
    (``git fetch origin tag v1``), which writes a local tag, and ``--refmap`` and ``--stdin``, which set
    refspecs.
13. ``gh`` runs only as a ``gh api`` read.
14. A command that runs ``utils/desk_queue.py`` add, remove, snooze or init, ``utils/desk_pr_body.py``,
    ``utils/merge_data.py``, ``utils/sort_yaml.py``, ``utils/main.py``, ``utils/import_python_official.py``
    or ``utils/import_python_organizers.py`` (the queue, the PR body, the merge, the sort and the
    importers, which all write the data, the queue or the PR) is blocked. A script counts as run when it is
    the program, when a Python interpreter or a runner such as ``uv`` or ``pixi`` is the program and names
    the script (or its module after ``-m``, also attached as in ``-mutils.sort_yaml``), or as the
    ``pixi run sort``, ``pixi run links`` and ``pixi run merge`` tasks, also after ``pixi run`` options
    such as ``-e <environment>`` or ``-m <manifest>``. ``main.py`` counts only in a folder named ``utils``.
15. Edit, Write, MultiEdit and NotebookEdit are blocked on any path inside a repository: the one that holds
    ``cwd`` or the one that holds the path, with symlinks resolved. Paths outside, such as ``/tmp``, are
    allowed. A Bash command that writes into the repository is blocked too, by rule 16; the other Bash
    calls, apart from the git and script calls of rules 12 and 14, are not inspected.
16. A Bash command may not write a path inside a repository, by the same test rule 15 uses: the repository
    that holds ``cwd`` or the one that holds the target, with symlinks resolved. A target outside every
    repository, such as one under ``/tmp``, is allowed, and so are ``/dev/null``, ``/dev/stdout``,
    ``/dev/stderr`` and ``/dev/fd/*``. The writes read are an output redirection in any form (``>``, ``>>``,
    ``>|``, ``&>``, ``&>>``, ``n>``, ``n>>`` and the read-write ``<>``) and the file-writing programs and
    options ``tee``, ``cp``, ``mv``, ``rm``, ``rmdir``, ``touch``, ``mkdir``, ``ln``, ``chmod``, ``chown``,
    ``chgrp``, ``truncate``, ``dd`` (``of=``), ``install``, ``rsync``, ``patch``, ``shred``, ``split``,
    ``unlink``, ``sponge``, ``sed -i``/``--in-place``, ``perl -i``, ``unzip`` and ``tar`` extraction (``-x``
    with or without ``-C``). ``cd`` and a wrapper chdir move the directory a relative target is taken
    against, as they do for the push rule. A target the hook cannot resolve to a path (a variable, a glob, a
    brace, a command substitution or a here-string path) counts as inside a repository, so the command is
    blocked.

Commands are pattern matched, never run: the script splits the command line into simple commands, steps over
shell reserved words (``do``, ``then``, ``!``, ``{``), variable assignments and wrappers with their options
(``sudo -u bob``, ``timeout 120``, ``env -C dir``, ``env -iC dir``), follows ``cd``, ``sh -c`` and ``eval``,
and reads the
``git`` (with ``-C``), ``gh`` and script invocations. A program named ``git-<sub>`` in any folder, such as
``/usr/lib/git-core/git-push``, counts as ``git <sub>``. Outside desk runs, an alias set with
``git -c alias.<name>=<value>`` is expanded before the rules apply, a shell alias (``!...``) included. The
aliases are read again after each expansion, so one set by a ``-c`` inside another alias's value is expanded
too; expansion stops at ``push``, at a name already expanded and at a name no ``-c`` defines. Outside desk
runs, these are not inspected: aliases from config files, from ``--config-env`` or from ``GIT_CONFIG_*``
variables, which are not expanded; config that sets push targets or options (``remote.<name>.push``,
``remote.<name>.pushurl``, ``push.default``, ``push.followTags``, ``push.recurseSubmodules``,
``url.<base>.pushInsteadOf``), which is not read; a subcommand git autocorrects (``help.autocorrect``); and
commands git runs from its config, such as hooks, ``core.pager`` and ``core.sshCommand``. Desk runs block all
of these by refusing config changes (rule 8). That covers git commands and the assignments rule 8 names. A file
tool or another program that writes a config file directly is not inspected, and neither are other ways a shell
sets or exports a variable, such as ``read``, ``printf -v`` or ``set -a``. A ``$NAME`` or ``${NAME}`` in a push
refspec resolves only from a literal ``NAME=value`` assignment earlier in the same command line; a name set
outside the command line, or by one of those uninspected routes, is left unresolved and the refspec it carries
is read as written. A desk run blocks an ``env``
split-string option (``-S``, ``--split-string``, clustered or as ``--split-string=STRING``) outright. Outside
desk runs the string it takes is split the way GNU env does, into whitespace-separated words with single and
double quotes and backslash escapes (a backslash-underscore separates words, a backslash-c ends the string),
and those words are read as the rest of the command line, so the push rule sees them; a ``${VAR}`` is left as a
word that cannot be resolved, and a string that cannot be split, or that holds such a reference where the
program or subcommand would stand, is blocked when any word could be ``git`` or ``push``. Programs other than
``git`` and ``gh``, such as ``curl``, are not inspected beyond rules 3, 8, 14 and 16. Rule 16 reads the writes
a program makes through its own arguments and redirections, but not code an interpreter runs inline, such as
``python -c``, a ``python`` here-document, ``node -e`` or ``perl -e``: a file such code writes is a stated
limit, covered by the desk's own checks. Code a program runs on its own, such as a script file, is not read
either. The current branch comes from the repository's ``HEAD`` file. Unreadable hook
input and internal errors block in a desk run and pass elsewhere. Only the Python standard library is used.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import NamedTuple

PROTECTED_BRANCHES = frozenset({"main", "master"})
ROLLING_BRANCH = "auto/conference-updates"
QUEUE_BRANCH = "desk-queue"
DESK_REMOTE = "origin"
DESK_PUSH_DESTINATIONS = frozenset({f"refs/heads/{ROLLING_BRANCH}", f"refs/heads/{QUEUE_BRANCH}"})
FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
MCP_TOOL_PREFIX = "mcp__"
SCHEDULING_TOOLS = frozenset({"CronCreate", "CronDelete", "CronList", "RemoteTrigger", "ScheduleWakeup"})
# The tool that starts a subagent: Agent, named Task in older Claude Code versions
AGENT_TOOLS = frozenset({"Agent", "Task"})
# The subagent types a desk run may start, defined in .claude/agents/, and the only subagents that may act in one
DESK_AGENT_TYPES = frozenset({"desk-research"})
DENY_LIST_NAME = ".desk-guard.json"
DENY_LIST_KEYS = ("deny_bash", "deny_tools", "deny_paths", "deny_urls")

# The subcommands that write remote refs with the same positionals as push (a remote or URL, then
# refspecs): the porcelain "push" and the plumbing "send-pack" and "http-push". All three go through the
# push rules.
PUSH_SUBCOMMANDS = frozenset({"push", "send-pack", "http-push"})
# git options that take the next word as their value, before and after the "push" subcommand. No push
# switch is a prefix of a push option here, so an abbreviation of one of these takes a value too.
GIT_OPTIONS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"})
PUSH_OPTIONS_WITH_VALUE = frozenset(
    {"--repo", "-o", "--push-option", "--receive-pack", "--exec", "--recurse-submodules"},
)
# git options that set a config value for one call ("-c alias.p=push", "--config-env=alias.p=VARIABLE")
GIT_CONFIG_OPTIONS = frozenset({"-c", "--config-env"})
# git config options that only read, and the options that take the next word as their value
CONFIG_READ_OPTIONS = frozenset({"--get", "--get-all", "--get-regexp", "--list", "-l"})
CONFIG_OPTIONS_WITH_VALUE = frozenset({"--blob", "--comment", "--default", "--file", "--type", "--value", "-f"})
# An environment variable that changes git config, and the shell builtins that assign or export one in an
# argument, where the name alone counts too ("export GIT_CONFIG_COUNT")
GIT_CONFIG_VARIABLE = re.compile(r"GIT_CONFIG[A-Za-z0-9_]*\+?=")
GIT_CONFIG_NAME = re.compile(r"GIT_CONFIG[A-Za-z0-9_]*(?:\+?=|$)")
ASSIGNING_BUILTINS = frozenset({"declare", "export", "local", "readonly", "typeset"})
PUSH_EVERY_BRANCH = frozenset({"--all", "--mirror", "--branches"})
PUSH_DRY_RUN = frozenset({"--dry-run", "-n"})
# Push options a desk run may not use: they force, delete or send more than the named branch
DESK_PUSH_FORBIDDEN = frozenset(
    {"--all", "--branches", "--delete", "--follow-tags", "--force", "--force-with-lease", "--mirror", "--prune"}
    | {"--recurse-submodules", "--tags", "-d", "-f"},
)
# git subcommands a subagent may run in a desk run; "config" is allowed with --get only
SUBAGENT_GIT_SUBCOMMANDS = frozenset(
    {"status", "log", "show", "diff", "grep", "ls-files", "ls-remote", "ls-tree", "rev-parse", "rev-list"}
    | {"merge-base", "blame", "cat-file", "fetch", "describe", "shortlog", "for-each-ref", "show-ref"},
)
# git fetch options that take the next word as their value, matched in full only, and the options that set
# a refspec of their own, matched in any abbreviation
FETCH_OPTIONS_WITH_VALUE = frozenset(
    {"--deepen", "--depth", "--filter", "--jobs", "--negotiation-tip", "--server-option", "--shallow-exclude"}
    | {"--shallow-since", "--upload-pack", "-j", "-o"},
)
FETCH_REFSPEC_OPTIONS = frozenset({"--refmap", "--stdin"})

# gh api options that take a value, and what the value sets
GH_API_OPTIONS_WITH_VALUE = {
    "-X": "method",
    "--method": "method",
    "-f": "field",
    "--raw-field": "field",
    "-F": "field",
    "--field": "field",
    "--input": "field",
    "--hostname": "hostname",
    "-H": "other",
    "--header": "other",
    "-p": "other",
    "--preview": "other",
    "-q": "other",
    "--jq": "other",
    "-t": "other",
    "--template": "other",
    "--cache": "other",
}
DESK_API_ENDPOINT = r"(?:https://api\.github\.com/|/)?repos/JesperDramsch/python-deadlines/"
# The gh api writes a desk run may make: method and endpoint
DESK_API_WRITES = (
    ("POST", re.compile(DESK_API_ENDPOINT + r"pulls")),
    ("PATCH", re.compile(DESK_API_ENDPOINT + r"pulls/[0-9]+")),
    ("POST", re.compile(DESK_API_ENDPOINT + r"issues/[0-9]+/comments")),
    ("POST", re.compile(DESK_API_ENDPOINT + r"issues/[0-9]+/labels")),
)

# Scripts that write the data, the queue or the PR body, which a subagent in a desk run may not run; a set
# limits the rule to those subcommands
DESK_SCRIPTS: dict[str, frozenset[str] | None] = {
    "desk_pr_body.py": None,
    "desk_queue.py": frozenset({"add", "init", "remove", "snooze"}),
    "import_python_official.py": None,
    "import_python_organizers.py": None,
    "main.py": None,
    "merge_data.py": None,
    "sort_yaml.py": None,
}
# Scripts with a common name, which count only in a folder named utils
UTILS_ONLY_SCRIPTS = frozenset({"main.py"})
# pixi.toml tasks that run one of them, and the pixi run options that take a value
PIXI_TASKS = {"sort": "sort_yaml.py", "links": "sort_yaml.py", "merge": "main.py"}
PIXI_RUN_OPTIONS_WITH_VALUE = frozenset({"-e", "--environment", "-m", "--manifest-path"})
# Programs that run a script named among their arguments
SCRIPT_RUNNER = re.compile(r"(?:python|pypy)[0-9.]*|uvx?|pixi|poetry|pipenv|pdm|hatch|rye|conda|mamba|micromamba")
# The -m option of a Python interpreter, alone or after other switches, with the module attached or not:
# "-m", "-Im", "-mutils.sort_yaml"
MODULE_OPTION = re.compile(r"-[bBdEhiIOPqRsSuvVx]*m(.*)")

# Shell reserved words that can stand before a command: "do git push", "if ! git push", "{ git push; }"
RESERVED_WORDS = frozenset({"!", "{", "}", "if", "then", "elif", "else", "do", "while", "until", "coproc"})
# Words that run the command after them, with their options that take a value and the number of operands
# before that command: "sudo -u bob git push", "timeout -s KILL 120 git push", "flock lockfile git push"
WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "builtin": (frozenset(), 0),
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
# env options that take a command string and split it into the arguments that follow
ENV_SPLIT_OPTIONS = frozenset({"-S", "--split-string"})
SHELLS = frozenset({"bash", "dash", "ksh", "sh", "su", "zsh"})
SHELL_COMMAND_FLAG = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")  # -c, -lc, -ec
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")  # NAME=value or NAME+=value
VARIABLE_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")  # ${NAME}, $NAME
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SHELL_PUNCTUATION = ";&|()<>"
MAX_NESTING = 3

# Shell operators built from the punctuation characters, longest first so a greedy walk reads "&>>" before
# "&", and the three kinds a run of punctuation decomposes into. A separator ends the simple command before
# it; an output or read-write redirect takes the next word as a file it writes; a read, here-string or
# file-descriptor duplication takes a word that is not a file write.
SHELL_OPERATORS = (
    "<<<",
    "&>>",
    ";;",
    "&&",
    "||",
    "|&",
    ">>",
    "<<",
    ">|",
    "<>",
    ">&",
    "<&",
    "&>",
    ";",
    "&",
    "|",
    "(",
    ")",
    "<",
    ">",
)
SEPARATOR_OPERATORS = frozenset({";", ";;", "&", "&&", "|", "||", "|&", "(", ")"})
WRITE_REDIRECT_OPERATORS = frozenset({">", ">>", ">|", "<>", "&>", "&>>"})
READ_REDIRECT_OPERATORS = frozenset({"<", "<<", "<<<", "<&", ">&"})

# The redirection targets that write no repository file: the bit bucket and the standard streams
DEV_WRITE_TARGET = re.compile(r"/dev/(?:null|stdout|stderr|fd/[0-9]+)\Z")
# A target the hook cannot resolve to a literal path: a leftover variable, a glob or brace, a command
# substitution (its "$(" or ")" survives) or an empty word
UNRESOLVED_TARGET = re.compile(r"[$*?\[\]{}()]")

# Programs a subagent in a desk run may not run when they write a repository path. Each kind names the
# options that take a following value, so the operands that are targets can be told apart.
# Writers whose every file operand is a target they create, truncate or remove.
WRITER_ALL_OPERANDS: dict[str, frozenset[str]] = {
    "rm": frozenset(),
    "rmdir": frozenset(),
    "unlink": frozenset(),
    "sponge": frozenset(),
    "tee": frozenset(),
    "touch": frozenset({"-d", "--date", "-r", "--reference", "-t", "--time"}),
    "mkdir": frozenset({"-m", "--mode", "-Z", "--context"}),
    "shred": frozenset({"-n", "--iterations", "-s", "--size"}),
    "truncate": frozenset({"-s", "--size", "-r", "--reference", "-o", "--io-blocks"}),
    "split": frozenset(
        {"-a", "--suffix-length", "-b", "--bytes", "-C", "--line-bytes", "-l", "--lines", "-n", "--number"},
    ),
}
# Writers whose last operand is the destination; the target-directory option names it instead.
WRITER_DEST_LAST: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "cp": (frozenset({"-S", "--suffix", "--sparse"}), frozenset({"-t", "--target-directory"})),
    "mv": (frozenset({"-S", "--suffix"}), frozenset({"-t", "--target-directory"})),
    "ln": (frozenset({"-S", "--suffix"}), frozenset({"-t", "--target-directory"})),
    "install": (
        frozenset({"-m", "--mode", "-o", "--owner", "-g", "--group", "-S", "--suffix"}),
        frozenset({"-t", "--target-directory"}),
    ),
    "rsync": (frozenset(), frozenset()),
}
# Writers whose first operand is a mode or owner, the rest being targets, unless --reference reads one.
WRITER_SKIP_FIRST = frozenset({"chmod", "chown", "chgrp"})
# Writers that unpack into the working directory, or the directory a directory option names.
WRITER_INTO_DIR: dict[str, frozenset[str]] = {
    "unzip": frozenset({"-d"}),
    "patch": frozenset({"-d", "--directory"}),
}
# sed and perl edit the file operands in place only with an in-place option; sed and perl take a script or
# code as a value, and sed reads its first operand as the script when no script option gives one.
INPLACE_SCRIPT_OPTIONS = {
    "sed": frozenset({"-e", "--expression", "-f", "--file"}),
    "perl": frozenset({"-e", "-E", "-M", "-m", "-I", "-F", "-x"}),
}


class BlockError(Exception):
    """Raised with the one-line reason when the tool call must be blocked."""


class BadInputError(ValueError):
    """Raised when the hook input is not a PreToolUse JSON object."""


class SimpleCommand(NamedTuple):
    """One simple command: its words from the program on, the directory it runs in and the words before it."""

    words: list[str]
    directory: str
    prefix: list[str]  # reserved words, assignments and wrappers with their options and operands
    redirects: list[str]  # the targets of its output redirections (>, >>, >|, &>, &>>, n>, n>>, <>)


class GitCommand(NamedTuple):
    """Where the subcommand of a ``git`` call starts, the directory git works in and its config settings."""

    index: int
    directory: str
    settings: list[tuple[str, str]]  # (option, value) for each -c and --config-env


class PushArguments(NamedTuple):
    """The words after ``git push``, sorted into positionals, option names and the ``--repo`` value."""

    positionals: list[str]
    flags: frozenset[str]
    repo_option: str | None


class ApiRequest(NamedTuple):
    """The parts of a ``gh api`` call that decide whether it writes and where."""

    method: str | None
    sends_fields: bool
    hostname: str | None
    endpoints: list[str]


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


def split_operators(token: str) -> list[str] | None:
    """Split a run of shell punctuation into its operators, or None when a character fits none.

    Parameters
    ----------
    token : str
        A token made only of the characters in ``SHELL_PUNCTUATION``.

    Returns
    -------
    list[str] | None
        The operators in order (``a&&>b`` gives ``["&&", ">"]``), or None when the run cannot be read as a
        sequence of known operators.
    """
    operators: list[str] = []
    index = 0
    while index < len(token):
        for operator in SHELL_OPERATORS:
            if token.startswith(operator, index):
                operators.append(operator)
                index += len(operator)
                break
        else:
            return None
    return operators


def split_commands(command: str) -> list[tuple[list[str], list[str]]]:
    """Split a command line into simple commands at ``;``, ``&&``, ``||``, ``|``, ``&``, brackets and newlines.

    Parameters
    ----------
    command : str
        The Bash command line.

    Returns
    -------
    list[tuple[list[str], list[str]]]
        For each simple command, its words from the program on, and the targets of its output redirections
        (``>``, ``>>``, ``>|``, ``&>``, ``&>>``, ``n>``, ``n>>`` and the read-write ``<>``). Read redirects,
        here-strings and file-descriptor duplications take a word that is not a file write, so their targets
        are left out, as are the targets of every redirect for a command line the lexer cannot read.
    """
    text = strip_heredocs(command).replace("\n", " ; ").replace("`", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: fall back to plain whitespace words between the separators, redirects dropped
        return [(part.split(), []) for part in re.split(r"[;&|()<>]+", text) if part.split()]

    commands: list[tuple[list[str], list[str]]] = [([], [])]
    pending: str | None = None  # "write": the next word is a file write; "skip": a redirect word to drop
    for token in tokens:
        if pending is not None:
            if pending == "write":
                commands[-1][1].append(token)
            pending = None
        elif token and all(char in SHELL_PUNCTUATION for char in token):
            operators = split_operators(token)
            if operators is None:
                commands.append(([], []))
                continue
            for operator in operators:
                if operator in SEPARATOR_OPERATORS:
                    commands.append(([], []))
                    pending = None
                elif operator in WRITE_REDIRECT_OPERATORS:
                    pending = "write"
                elif operator in READ_REDIRECT_OPERATORS:
                    pending = "skip"
        else:
            commands[-1][0].append(token)
    return [command for command in commands if command[0] or command[1]]


def takes_value(option: str, options: frozenset[str]) -> bool:
    """Return True when ``option`` is followed by a separate value word.

    Parameters
    ----------
    option : str
        An option word, such as ``-u``, ``--user`` or a cluster of short options like ``-Eu``. In a cluster
        the first option that takes a value takes the rest of the word, so ``-uroot`` has its value attached.
    options : frozenset[str]
        The options of the program that take a value.

    Returns
    -------
    bool
        Whether the next word is the option's value.
    """
    if option in options:
        return True
    if option.startswith("--"):
        return False
    for position, char in enumerate(option[1:], start=2):
        if f"-{char}" in options:
            return position == len(option)
    return False


def option_value(word: str, options: frozenset[str]) -> tuple[str | None, str | None, bool]:
    """Return which option of ``word`` takes a value, its attached value and whether the next word is it.

    Parameters
    ----------
    word : str
        One option argument, such as ``-C``, ``--chdir=dir``, ``-iC`` or ``-Cdir``.
    options : frozenset[str]
        The options of the program that take a value.

    Returns
    -------
    tuple[str | None, str | None, bool]
        The option that takes a value (the word itself for a long option, the first value-taking short
        option in a cluster, or None when none does), the value attached in the word (after ``=`` for a
        long option, the rest of a short cluster, or None) and whether the following word is the value.
    """
    name, equals, attached = word.partition("=")
    if name.startswith("--"):
        if name in options:
            return name, (attached if equals else None), not equals
        return None, None, False
    for position, char in enumerate(name[1:], start=2):
        if f"-{char}" in options:
            if position < len(name):
                return f"-{char}", name[position:], False  # the value is attached in the cluster
            return f"-{char}", None, True  # the value is the next word
    return None, None, False


def read_variable(string: str, index: int) -> tuple[str, int] | None:
    """Return a ``${VAR}`` or ``$VAR`` reference at ``string[index]`` and the index after it, or None."""
    if index + 1 < len(string) and string[index + 1] == "{":
        end = string.find("}", index + 2)
        if end != -1:
            return string[index : end + 1], end + 1
        return None
    match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*", string[index:])
    return (match.group(0), index + match.end()) if match else None


def split_env_string(string: str) -> tuple[list[str], set[int], bool]:
    """Split an ``env`` split-string the way GNU env does.

    Words are separated by whitespace outside quotes. A single-quoted run is literal; a double-quoted run
    takes backslash escapes before a double quote, a backslash and a dollar sign; outside quotes a backslash
    escapes the next character, with a backslash-underscore separating words and a backslash-c stopping. A
    ``${VAR}`` or ``$VAR`` reference cannot be resolved here, so it is kept verbatim and its word is marked.

    Parameters
    ----------
    string : str
        The string the option takes.

    Returns
    -------
    tuple[list[str], set[int], bool]
        The words, the indices of the words that hold an unresolved variable, and whether the split was
        clean (an unbalanced quote leaves it unclean).
    """
    words: list[str] = []
    variables: set[int] = set()
    current: list[str] = []
    has_word = False
    has_variable = False
    quote: str | None = None
    index = 0

    def flush() -> None:
        nonlocal current, has_word, has_variable
        if has_word:
            if has_variable:
                variables.add(len(words))
            words.append("".join(current))
            current, has_word, has_variable = [], False, False

    while index < len(string):
        char = string[index]
        if quote == "'":
            if char == "'":
                quote = None
            else:
                current.append(char)
            index += 1
        elif quote == '"':
            if char == '"':
                quote = None
                index += 1
            elif char == "\\" and index + 1 < len(string) and string[index + 1] in '"\\$':
                current.append(string[index + 1])
                index += 2
            elif char == "$" and (reference := read_variable(string, index)) is not None:
                current.append(reference[0])
                has_variable = True
                index = reference[1]
            else:
                current.append(char)
                index += 1
        elif char in " \t\n\r\f\v":
            flush()
            index += 1
            continue
        elif char == "'":
            quote = "'"
            index += 1
        elif char == '"':
            quote = '"'
            index += 1
        elif char == "\\":
            following = string[index + 1] if index + 1 < len(string) else ""
            if following == "c":
                break  # stop processing the rest of the string
            if following == "_":
                flush()  # a backslash-underscore separates words, like whitespace
                index += 2
                continue
            current.append("\\" if following == "" else following)
            index += 2 if following else 1
        elif char == "$" and (reference := read_variable(string, index)) is not None:
            current.append(reference[0])
            has_variable = True
            index = reference[1]
        else:
            current.append(char)
            index += 1
        has_word = True
    flush()
    return words, variables, quote is None


def split_string_pieces(string: str) -> list[str]:
    """Return the words of an ``env`` split-string, failing closed when it may hide ``git push``.

    Parameters
    ----------
    string : str
        The string the option takes.

    Returns
    -------
    list[str]
        The split words, to read as the rest of the command line.

    Raises
    ------
    BlockError
        When the string cannot be split cleanly, or holds a variable where the program or subcommand would
        stand, and any word could be ``git`` or ``push``.
    """
    words, variables, clean = split_env_string(string)
    variable_in_command = 0 in variables or (len(words) > 1 and words[0] == "git" and 1 in variables)
    if (not clean or variable_in_command) and (variables or any(word in {"git", "push"} for word in words)):
        raise BlockError("an env split-string that could run git push cannot be read, so it is blocked")
    return words


def expand_variables(word: str, variables: dict[str, str]) -> str:
    """Replace ``$NAME`` and ``${NAME}`` in ``word`` with the values of ``variables``, leaving others as is.

    Only a variable assigned a literal value earlier in the same command line is known, so a variable set
    outside it, or by a command the guard does not read, stays unresolved. Command substitutions such as
    ``$(...)`` are not references and are left alone.

    Parameters
    ----------
    word : str
        One word of a command.
    variables : dict[str, str]
        Known variable names and their values.

    Returns
    -------
    str
        The word with its known variable references resolved.
    """
    return VARIABLE_REFERENCE.sub(lambda match: variables.get(match.group(1) or match.group(2), match.group(0)), word)


def command_start(words: list[str], directory: str, *, desk: bool = False) -> tuple[int, str, list[str]]:
    """Find the program of a simple command behind reserved words, assignments and wrappers.

    Parameters
    ----------
    words : list[str]
        The words of one simple command.
    directory : str
        Directory the command starts in.
    desk : bool
        Whether this is a desk run, where an ``env`` split-string option is blocked outright.

    Returns
    -------
    tuple[int, str, list[str]]
        The index of the program (``len(words)`` when there is none), the directory it runs in, which
        ``env -C`` and ``sudo -D`` change in their separate or clustered forms, and the words, which an
        ``env`` split-string option rewrites into the command it carries.

    Raises
    ------
    BlockError
        When a desk run uses an ``env`` split-string option, or a split string outside a desk run may hide
        ``git push``.
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
            chdir = WRAPPER_CHDIR.get(name, frozenset())
            split_options = ENV_SPLIT_OPTIONS if name == "env" else frozenset()
            start = index
            index += 1
            restart = False
            while index < len(words) and words[index].startswith("-") and words[index] != "-":
                argument = words[index]
                index += 1
                if argument == "--":
                    break
                consumed, value, next_is_value = option_value(argument, options)
                if value is None and next_is_value and index < len(words):
                    value = words[index]
                    index += 1
                if consumed in split_options:
                    if desk:
                        raise BlockError(f"env {consumed} splits a command string, which is off limits in desk runs")
                    words = [*words[:start], *split_string_pieces(value or ""), *words[index:]]
                    index = start
                    restart = True
                    break
                if value is not None and consumed in chdir:
                    directory = str(Path(directory, Path(value).expanduser()))
            if restart:
                continue
            index += operands
        else:
            break
    return min(index, len(words)), directory, words


def simple_commands(command: str, cwd: str, depth: int = 0, *, desk: bool = False) -> list[SimpleCommand]:
    """List every simple command of a command line, with the directory it runs in.

    Parameters
    ----------
    command : str
        The Bash command line.
    cwd : str
        Directory the command line starts in; ``cd``, ``env -C`` and ``sudo -D`` move it.
    depth : int
        Nesting level of ``sh -c`` and ``eval`` strings already unwrapped.
    desk : bool
        Whether this is a desk run, passed through to ``command_start`` for the ``env`` split-string rule.

    Returns
    -------
    list[SimpleCommand]
        The words of each command from the program on, the directory the program runs in, the words
        before the program and the targets of its output redirections. A command made only of assignments
        or a bare redirect has no words. The commands inside an ``sh -c`` or ``eval`` string follow the
        command that runs them.
    """
    found: list[SimpleCommand] = []
    directory = cwd
    for words, redirects in split_commands(command):
        start, command_directory, words = command_start(words, directory, desk=desk)
        found.append(SimpleCommand(words[start:], command_directory, words[:start], redirects))
        if start == len(words):
            continue
        program, rest = Path(words[start]).name, words[start + 1 :]

        if program == "cd":
            target = rest[0] if rest else "~"
            directory = str(Path(command_directory, Path(target).expanduser()))
        elif program in SHELLS and depth < MAX_NESTING:
            for index, word in enumerate(rest[:-1]):
                if SHELL_COMMAND_FLAG.match(word):
                    found.extend(simple_commands(rest[index + 1], command_directory, depth + 1, desk=desk))
                    break
        elif program == "eval" and depth < MAX_NESTING:
            found.extend(simple_commands(" ".join(rest), command_directory, depth + 1, desk=desk))
    return found


def git_subcommand(args: list[str], directory: str) -> GitCommand:
    """Find the subcommand of a ``git`` invocation behind its global options.

    Parameters
    ----------
    args : list[str]
        Words after ``git``.
    directory : str
        Directory git starts in.

    Returns
    -------
    GitCommand
        The index of the subcommand in ``args`` (``len(args)`` when there is none), the directory git
        works in, which ``-C`` changes, and the values of ``-c`` and ``--config-env``.
    """
    index = 0
    settings: list[tuple[str, str]] = []
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        value = args[index + 1] if option in GIT_OPTIONS_WITH_VALUE and index + 1 < len(args) else None
        if option == "-C" and value is not None:
            directory = str(Path(directory, Path(value).expanduser()))
        elif option in GIT_CONFIG_OPTIONS and value is not None:
            settings.append((option, value))
        elif option.startswith("--config-env="):
            settings.append(("--config-env", option.removeprefix("--config-env=")))
        index += 2 if option in GIT_OPTIONS_WITH_VALUE else 1
    return GitCommand(min(index, len(args)), directory, settings)


def git_aliases(settings: list[tuple[str, str]]) -> dict[str, str]:
    """Return the aliases that ``-c alias.<name>=<value>`` settings define.

    Parameters
    ----------
    settings : list[tuple[str, str]]
        The ``-c`` and ``--config-env`` values of a git call. A ``--config-env`` value names an environment
        variable, not the alias, so it is left out.

    Returns
    -------
    dict[str, str]
        Each alias name in lower case, as git matches it, and the last value set for it.
    """
    aliases = {}
    for option, setting in settings:
        key, equals, value = setting.partition("=")
        section, dot, name = key.partition(".")
        if option == "-c" and equals and dot and section.lower() == "alias":
            aliases[name.lower()] = value
    return aliases


def split_alias(value: str) -> list[str]:
    """Split an alias value into words the way git does, falling back to whitespace on unbalanced quotes."""
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


def long_option(word: str, options: frozenset[str]) -> str | None:
    """Return the long option of ``options`` that ``word`` names, written out or abbreviated.

    git reads any unambiguous prefix of a long option as that option (``--force-w`` is
    ``--force-with-lease``), with or without ``=value``. A prefix that fits several options makes git fail,
    so counting it as the first of them blocks nothing git would run.

    Parameters
    ----------
    word : str
        An argument, such as ``--mirr`` or ``--force-w=main:abc``.
    options : frozenset[str]
        The option names to look for; short options among them never match.

    Returns
    -------
    str | None
        The option, or None when ``word`` is not a long option or names none of them.
    """
    name = word.partition("=")[0]
    if not name.startswith("--"):
        return None
    if name in options:
        return name
    return next((option for option in sorted(options) if option.startswith(name)), None)


def named_options(flags: frozenset[str], options: frozenset[str]) -> list[str]:
    """Return the flags that name one of ``options``, each with the option it stands for when abbreviated.

    Parameters
    ----------
    flags : frozenset[str]
        Option names from a command line, such as ``-f`` or ``--del``.
    options : frozenset[str]
        The options to look for.

    Returns
    -------
    list[str]
        Sorted descriptions such as ``-f``, ``--delete`` or ``--del (--delete)``.
    """
    found = []
    for flag in sorted(flags):
        option = flag if flag in options else long_option(flag, options)
        if option is not None:
            found.append(flag if option == flag else f"{flag} ({option})")
    return found


def parse_push(args: list[str]) -> PushArguments:
    """Sort the words after ``git push`` into positionals and options.

    Parameters
    ----------
    args : list[str]
        Words after ``push``.

    Returns
    -------
    PushArguments
        The positionals, the option names as written (a bundle such as ``-fu`` gives ``-f`` and ``-u``) and
        the ``--repo`` value. An abbreviated long option takes a value as the option it stands for does.
    """
    positionals: list[str] = []
    flags: set[str] = set()
    repo_option = None
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            positionals.extend(args[index:])
            break
        if arg.startswith("--"):
            name, equals, value = arg.partition("=")
            flags.add(name)
            if long_option(name, PUSH_OPTIONS_WITH_VALUE) and not equals:
                value = args[index] if index < len(args) else ""
                index += 1
            if long_option(name, frozenset({"--repo"})):
                repo_option = value
        elif arg.startswith("-") and arg != "-":
            for position, char in enumerate(arg[1:], start=2):
                flags.add(f"-{char}")
                if f"-{char}" in PUSH_OPTIONS_WITH_VALUE:
                    index += 1 if position == len(arg) else 0  # the value is attached or the next word
                    break
        else:
            positionals.append(arg)
    return PushArguments(positionals, frozenset(flags), repo_option)


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


def push_reason(push: PushArguments, directory: str) -> str | None:
    """Return why a ``git push`` reaches main or master, or None when it does not.

    Parameters
    ----------
    push : PushArguments
        The parsed words after ``push``.
    directory : str
        Repository directory the push runs in.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    # A later --no-dry-run or --no-tags undoes the option, so either one in any spelling ends the exemption
    if push.flags & PUSH_DRY_RUN and not named_options(push.flags, frozenset({"--no-dry-run"})):
        return None
    every_branch = named_options(push.flags, PUSH_EVERY_BRANCH)
    if every_branch:
        return f"git push {every_branch[0]} also pushes main"

    # With --repo every positional counts as a refspec here. git reads the first as the remote instead, so
    # this blocks at least what git would push to main.
    refspecs = push.positionals if push.repo_option is not None else push.positionals[1:]
    if not refspecs:
        if "--tags" in push.flags and not named_options(push.flags, frozenset({"--follow-tags", "--no-tags"})):
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


def desk_push_reason(push: PushArguments, directory: str) -> str | None:
    """Return why a ``git push`` is off limits in a desk run, or None when it may go ahead.

    Parameters
    ----------
    push : PushArguments
        The parsed words after ``push``.
    directory : str
        Repository directory the push runs in.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    forbidden = named_options(push.flags, DESK_PUSH_FORBIDDEN)
    if forbidden:
        return f"git push {forbidden[0]} is off limits in desk runs"
    # git reads the first positional as the remote, even after --repo
    remote = push.positionals[0] if push.positionals else push.repo_option
    if remote != DESK_REMOTE:
        return f"git push to {remote or 'the default remote'} is off limits: desk runs push only to {DESK_REMOTE}"
    refspecs = push.positionals[1:]
    if not refspecs:
        return f"git push without a refspec is off limits in desk runs; use git push {DESK_REMOTE} HEAD:<branch>"
    for refspec in refspecs:
        if refspec.startswith(("+", ":")):
            return f"git push refspec {refspec!r} forces or deletes, which desk runs may not do"
        if refspec_destination(refspec, directory) not in DESK_PUSH_DESTINATIONS:
            return f"git push refspec {refspec!r} is off limits: desk runs push only {ROLLING_BRANCH} or {QUEUE_BRANCH}"
    return None


def config_change_reason(change: str, *, subagent: bool) -> str:
    """Return why a git config change is blocked in a desk run, naming subagents when one makes it.

    Parameters
    ----------
    change : str
        The words that make the change, such as ``git -c user.name=x`` or ``GIT_CONFIG_COUNT=1``.
    subagent : bool
        Whether a subagent of the desk run makes the call.

    Returns
    -------
    str
        The block reason.
    """
    scope = "for subagents in desk runs" if subagent else "in desk runs"
    return f"{change} is off limits {scope}, which make no git config changes"


def config_reads(args: list[str]) -> bool:
    """Return True when ``git config`` only reads.

    A read names ``--get``, ``--get-all``, ``--get-regexp``, ``--list`` or ``-l`` before the first word
    that is not an option. git config stops reading options at that word, so a later one is a value it
    writes (``git config user.name --get``), and so is a word an option such as ``--file`` takes as its
    value (``git config --file --get user.name x``).

    Parameters
    ----------
    args : list[str]
        Words after ``config``.

    Returns
    -------
    bool
        Whether the call is a pure read.
    """
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if word in CONFIG_READ_OPTIONS:
            return True
        if word in {"--", "-"} or not word.startswith("-"):
            return False
        # An option that takes a value, written out or abbreviated, or a short cluster that ends in one
        if "=" not in word and (
            long_option(word, CONFIG_OPTIONS_WITH_VALUE) or takes_value(word, CONFIG_OPTIONS_WITH_VALUE)
        ):
            index += 1
    return False


def fetch_reason(args: list[str]) -> str | None:
    """Return why a subagent's ``git fetch`` sets a refspec that writes local refs, or None.

    Parameters
    ----------
    args : list[str]
        Words after ``fetch``.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    positionals: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            positionals.extend(args[index:])
            break
        if arg.startswith("--"):
            name, equals, _ = arg.partition("=")
            option = named_options(frozenset({name}), FETCH_REFSPEC_OPTIONS)
            if option:
                return f"git fetch {option[0]} sets a refspec, which subagents in desk runs may not do"
            index += 1 if name in FETCH_OPTIONS_WITH_VALUE and not equals else 0
        elif arg.startswith("-") and arg != "-":
            for position, char in enumerate(arg[1:], start=2):
                if f"-{char}" in FETCH_OPTIONS_WITH_VALUE:
                    index += 1 if position == len(arg) else 0  # the value is attached or the next word
                    break
        else:
            positionals.append(arg)
    # The first positional is the remote; a refspec with a destination or a "+" writes a local ref, and so
    # does "tag <name>", which fetches refs/tags/<name> into the local tag
    for refspec in positionals[1:]:
        if refspec == "tag":
            return "git fetch tag <name> writes a local tag, which subagents in desk runs may not do"
        if ":" in refspec or refspec.startswith("+"):
            return f"git fetch refspec {refspec!r} writes a local ref, which subagents in desk runs may not do"
    return None


def git_reason(args: list[str], directory: str, *, desk: bool, subagent: bool, depth: int = 0) -> str | None:
    """Return why a ``git`` invocation is blocked, or None.

    Parameters
    ----------
    args : list[str]
        Words after ``git``.
    directory : str
        Directory git starts in.
    desk : bool
        Whether this is a desk run.
    subagent : bool
        Whether a subagent of a desk run makes the call.
    depth : int
        Nesting level of shell strings already unwrapped, which a shell alias adds to.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    command = git_subcommand(args, directory)
    if desk and command.settings:
        option, setting = command.settings[0]
        return config_change_reason(f"git {option} {setting}", subagent=subagent)

    # Outside desk runs, expand the aliases the call sets. An alias value can set more aliases with -c, so
    # the map is read again after each expansion. git ignores an alias that hides one of its own commands,
    # so none stands in for push itself, and it stops at a loop, so no name is expanded twice.
    expanded: set[str] = set()
    while not desk and command.index < len(args):
        name = args[command.index].lower()
        aliases = git_aliases(command.settings)
        if args[command.index] == "push" or name in expanded or name not in aliases:
            break
        expanded.add(name)
        value, rest = aliases[name], args[command.index + 1 :]
        if value.startswith("!"):
            # A shell alias runs its command with the remaining words appended
            if depth >= MAX_NESTING:
                return None
            shell_command = " ".join([value[1:], *(shlex.quote(word) for word in rest)])
            return bash_reason(shell_command, command.directory, desk=desk, subagent=subagent, depth=depth + 1)
        args = [*args[: command.index], *split_alias(value), *rest]
        command = git_subcommand(args, directory)

    index, git_directory = command.index, command.directory
    if index == len(args):
        return None
    subcommand, rest = args[index], args[index + 1 :]
    if subcommand in PUSH_SUBCOMMANDS:
        push = parse_push(rest)
        reason = push_reason(push, git_directory)
        if reason:
            return f"{reason}; push to another branch instead"
        if desk:
            reason = desk_push_reason(push, git_directory)
            if reason:
                return reason
    reads = subcommand == "config" and config_reads(rest)
    if subagent and subcommand == "fetch":
        return fetch_reason(rest)
    if subagent and subcommand not in SUBAGENT_GIT_SUBCOMMANDS and not reads:
        return f"git {subcommand} is off limits for subagents in desk runs; return a change set to the desk"
    if desk and subcommand == "config" and not reads:
        return "git config is off limits in desk runs, which make no git config changes, apart from pure reads"
    return None


def parse_gh_api(args: list[str]) -> ApiRequest:
    """Read the method, fields, host and endpoint of a ``gh api`` call.

    Parameters
    ----------
    args : list[str]
        Words after ``gh api``.

    Returns
    -------
    ApiRequest
        The method set with ``-X`` or ``--method`` (upper case, None when unset), whether fields or an input
        file are sent, the ``--hostname`` value and the positional words.
    """
    method = None
    sends_fields = False
    hostname = None
    endpoints: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            endpoints.extend(args[index:])
            break
        if arg.startswith("--"):
            name, equals, value = arg.partition("=")
            kind = GH_API_OPTIONS_WITH_VALUE.get(name)
            if kind is None:
                continue  # a switch such as --paginate
            if not equals:
                value = args[index] if index < len(args) else ""
                index += 1
        elif arg.startswith("-") and arg != "-":
            # Short options can be bundled and take their value attached: -i, -XPATCH, -iX PATCH, -fkey=v
            kind = None
            for position, char in enumerate(arg[1:], start=2):
                kind = GH_API_OPTIONS_WITH_VALUE.get(f"-{char}")
                if kind is not None:
                    value = arg[position:].removeprefix("=")
                    if position == len(arg):
                        value = args[index] if index < len(args) else ""
                        index += 1
                    break
            if kind is None:
                continue
        else:
            endpoints.append(arg)
            continue
        if kind == "method":
            method = value.upper()
        elif kind == "field":
            sends_fields = True
        elif kind == "hostname":
            hostname = value
    return ApiRequest(method, sends_fields, hostname, endpoints)


def gh_reason(args: list[str], *, desk: bool, subagent: bool) -> str | None:
    """Return why a ``gh`` invocation is blocked, or None.

    Parameters
    ----------
    args : list[str]
        Words after ``gh``.
    desk : bool
        Whether this is a desk run.
    subagent : bool
        Whether a subagent of a desk run makes the call.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    if not desk:
        return None
    if not args or args[0] != "api":
        return f"gh {args[0] if args else ''} is off limits in desk runs; use gh api"
    request = parse_gh_api(args[1:])
    if (request.method is None or request.method == "GET") and not request.sends_fields:
        return None
    if subagent:
        return "gh api writes are off limits for subagents in desk runs; return a change set to the desk"
    method = request.method or "POST"
    endpoint = " ".join(request.endpoints)
    if request.hostname is None and len(request.endpoints) == 1:
        for allowed_method, pattern in DESK_API_WRITES:
            if method == allowed_method and pattern.fullmatch(endpoint):
                return None
    return f"gh api {method} {endpoint} is not a write desk runs may make"


def module_argument(words: list[str], index: int) -> str | None:
    """Return the module that ``words[index]`` names after ``-m`` or ``--module``, or None.

    Parameters
    ----------
    words : list[str]
        The words of a simple command from the program on.
    index : int
        The word to look at.

    Returns
    -------
    str | None
        The module: the word itself after ``-m``, ``-Im`` or ``--module``, the part after ``-m`` in
        ``-mutils.sort_yaml`` or after ``--module=``, or None.
    """
    word = words[index]
    if word.startswith("--module="):
        return word.removeprefix("--module=")
    attached = MODULE_OPTION.fullmatch(word)
    if attached and attached.group(1):
        return attached.group(1)
    if index > 0:
        previous = words[index - 1]
        before = MODULE_OPTION.fullmatch(previous)
        if previous == "--module" or (before and not before.group(1)):
            return word
    return None


def desk_script(words: list[str], directory: str) -> str | None:
    """Return the desk script a simple command runs, or None.

    Parameters
    ----------
    words : list[str]
        The words of a simple command from the program on.
    directory : str
        Directory the command runs in, which places a script named without a folder.

    Returns
    -------
    str | None
        The script, with its subcommand when the rule is limited to some, or None.
    """
    program = Path(words[0]).name
    if program not in DESK_SCRIPTS and not SCRIPT_RUNNER.fullmatch(program):
        return None
    for index, word in enumerate(words):
        module = module_argument(words, index) if index > 0 else None
        if module is not None:
            # python -m utils.sort_yaml, or python -m main inside utils
            package, _, leaf = module.rpartition(".")
            name, folder = leaf + ".py", package.rpartition(".")[2] if package else Path(directory).name
        else:
            name, folder = Path(word).name, Path(directory, word).parent.name
        if name not in DESK_SCRIPTS or (name in UTILS_ONLY_SCRIPTS and folder != "utils"):
            continue
        subcommands = DESK_SCRIPTS[name]
        if subcommands is None:
            return name
        subcommand = next((later for later in words[index + 1 :] if not later.startswith("-")), None)
        if subcommand in subcommands:
            return f"{name} {subcommand}"
    if program == "pixi" and "run" in words:
        rest = words[words.index("run") + 1 :]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 2 if rest[index] in PIXI_RUN_OPTIONS_WITH_VALUE else 1
        if index < len(rest) and rest[index] in PIXI_TASKS:
            return PIXI_TASKS[rest[index]]
    return None


def git_config_assignment(prefix: list[str], words: list[str]) -> str | None:
    """Return the words of a simple command that assign or export a ``GIT_CONFIG*`` variable, or None.

    Parameters
    ----------
    prefix : list[str]
        The words before the program: leading assignments and wrappers, with ``env``'s operands.
    words : list[str]
        The words from the program on, whose arguments assign or export when the program is ``export``,
        ``declare``, ``typeset``, ``local`` or ``readonly``. There the name alone counts, since it exports a
        value set another way, such as with ``printf -v``.

    Returns
    -------
    str | None
        The assignment, such as ``GIT_CONFIG_COUNT=1`` or ``export GIT_CONFIG_COUNT``, or None.
    """
    assignment = next((word for word in prefix if GIT_CONFIG_VARIABLE.match(word)), None)
    if assignment is None and words and words[0] in ASSIGNING_BUILTINS:
        argument = next((word for word in words[1:] if GIT_CONFIG_NAME.match(word)), None)
        assignment = f"{words[0]} {argument}" if argument else None
    return assignment


def writer_operands(args: list[str], value_options: frozenset[str]) -> list[str]:
    """Return the operands of a command, dropping its options and the words they take as values.

    Parameters
    ----------
    args : list[str]
        The words after the program.
    value_options : frozenset[str]
        Options that take the next word as their value, so that word is not an operand. An option written
        ``--name=value`` keeps its value attached and takes no following word.

    Returns
    -------
    list[str]
        The operands in order; everything after a lone ``--`` is an operand.
    """
    found: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            found.extend(args[index:])
            break
        if arg.startswith("-") and arg != "-":
            consumed, attached, next_is_value = option_value(arg, value_options)
            if consumed is not None and attached is None and next_is_value:
                index += 1  # a short cluster ending in a value option, or "--name", takes the next word
            continue
        found.append(arg)
    return found


def valued_option(args: list[str], names: frozenset[str]) -> str | None:
    """Return the value of the first option in ``names`` the command passes, or None when none is passed."""
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            return None
        name, equals, attached = arg.partition("=")
        if name in names:
            return attached if equals else (args[index] if index < len(args) else "")
    return None


def tar_extracts(args: list[str]) -> bool:
    """Return True when a ``tar`` call extracts an archive (``-x``, ``--extract`` or a leading ``x``)."""
    for position, arg in enumerate(args):
        if arg in {"--extract", "--get"}:
            return True
        if arg.startswith("-") and not arg.startswith("--") and "x" in arg:
            return True
        if position == 0 and not arg.startswith("-") and "x" in arg:
            return True
    return False


def inplace_edit_targets(program: str, args: list[str]) -> list[str] | None:
    """Return the files ``sed`` or ``perl`` edits in place, or None when the call does not edit in place.

    Parameters
    ----------
    program : str
        ``sed`` or ``perl``.
    args : list[str]
        The words after the program.

    Returns
    -------
    list[str] | None
        The file operands, or None when no in-place option is present.
    """
    in_place = False
    for arg in args:
        if arg == "--":
            break
        if (
            arg == "--in-place"
            or arg.startswith("--in-place=")
            or (arg.startswith("-") and not arg.startswith("--") and "i" in arg.partition("=")[0])
        ):
            in_place = True
    if not in_place:
        return None
    value_options = INPLACE_SCRIPT_OPTIONS[program]
    files = writer_operands(args, value_options)
    if program == "sed" and valued_option(args, value_options) is None:
        files = files[1:]  # the first operand is the script when no -e or -f gives one
    return files


def writer_targets(program: str, args: list[str], directory: str) -> list[str] | None:
    """Return the repository-relevant paths a file-writing program writes, or None when it is not one.

    Parameters
    ----------
    program : str
        The program name, without its directory.
    args : list[str]
        The words after the program, with inline variables already resolved.
    directory : str
        The directory the command runs in, which a program that unpacks into the working directory writes.

    Returns
    -------
    list[str] | None
        The target paths to test, or None when ``program`` does not write a file.
    """
    if program in WRITER_ALL_OPERANDS:
        return writer_operands(args, WRITER_ALL_OPERANDS[program])
    if program in WRITER_DEST_LAST:
        value_options, directory_options = WRITER_DEST_LAST[program]
        target_directory = valued_option(args, directory_options)
        if target_directory is not None:
            return [target_directory]
        operands = writer_operands(args, value_options | directory_options)
        return operands[-1:]
    if program in WRITER_SKIP_FIRST:
        if valued_option(args, frozenset({"--reference"})) is not None:
            return writer_operands(args, frozenset({"--reference"}))
        return writer_operands(args, frozenset({"--reference"}))[1:]
    if program in WRITER_INTO_DIR:
        target_directory = valued_option(args, WRITER_INTO_DIR[program])
        return [target_directory if target_directory is not None else directory]
    if program == "dd":
        return [arg.partition("=")[2] for arg in args if arg.startswith("of=")]
    if program == "tar" and tar_extracts(args):
        target_directory = valued_option(args, frozenset({"-C", "--directory"}))
        return [target_directory if target_directory is not None else directory]
    if program in INPLACE_SCRIPT_OPTIONS:
        return inplace_edit_targets(program, args)
    return None


def writes_repository(target: str, directory: str) -> bool:
    """Return True when a write to ``target`` lands inside a repository, or the hook cannot resolve it.

    Parameters
    ----------
    target : str
        A redirection target or a writer program's operand, with inline variables already resolved.
    directory : str
        The directory the write runs in, which a relative target is taken against.

    Returns
    -------
    bool
        True when the target is inside a repository, or is a variable, glob, brace, command substitution,
        here-string or empty word the hook cannot resolve to a path; False for ``/dev/null`` and the
        standard streams, and for a path outside every repository, such as one under ``/tmp``.
    """
    if not target or UNRESOLVED_TARGET.search(target):
        return True
    if DEV_WRITE_TARGET.fullmatch(target):
        return False
    return enclosing_repository(target, directory) is not None


def repository_write_reason(program: str, args: list[str], directory: str) -> str | None:
    """Return why a subagent's file-writing program writes a repository path in a desk run, or None.

    Parameters
    ----------
    program : str
        The program name, without its directory.
    args : list[str]
        The words after the program, with inline variables already resolved.
    directory : str
        The directory the command runs in.

    Returns
    -------
    str | None
        The block reason, naming the program and the target, or None.
    """
    targets = writer_targets(program, args, directory)
    if not targets:
        return None
    for target in targets:
        if writes_repository(target, directory):
            where = target or "an unresolved path"
            return (
                f"{program} writes into the repository ({where}), which is off limits for subagents in desk "
                "runs; write scratch files outside it and return a change set to the desk"
            )
    return None


def bash_reason(command: str, cwd: str, *, desk: bool, subagent: bool, depth: int = 0) -> str | None:
    """Return why a Bash command is blocked, or None when no rule covers it.

    Parameters
    ----------
    command : str
        The Bash command line.
    cwd : str
        Directory the command starts in.
    desk : bool
        Whether this is a desk run.
    subagent : bool
        Whether a subagent of a desk run makes the call.
    depth : int
        Nesting level of shell strings already unwrapped, such as the command of a git shell alias.

    Returns
    -------
    str | None
        The block reason, or None.
    """
    # Literal "NAME=value" assignments set a variable so that a "$NAME" later in the command line resolves.
    # A standalone assignment persists; one before a command is for that command alone, as in the shell.
    variables: dict[str, str] = {}
    for words, directory, prefix, redirects in simple_commands(command, cwd, depth, desk=desk):
        if desk:
            assignment = git_config_assignment(prefix, words)
            if assignment:
                return config_change_reason(assignment, subagent=subagent)
        local = dict(variables)
        for word in prefix:
            name, equals, value = word.partition("=")
            if equals and ASSIGNMENT.match(word) and not name.endswith("+"):
                local[name] = value
                if not words:
                    variables[name] = value  # a command of assignments only persists them
        # A subagent may not redirect into the repository, whatever program (if any) the redirect follows
        if subagent:
            for target in redirects:
                resolved = expand_variables(target, local)
                if writes_repository(resolved, directory):
                    where = resolved or "an unresolved path"
                    return (
                        f"redirecting into the repository ({where}) is off limits for subagents in desk "
                        "runs; write scratch files outside it and return a change set to the desk"
                    )
        if not words:
            continue
        words = [expand_variables(word, local) for word in words]
        program, rest = Path(words[0]).name, words[1:]
        if program.startswith("git-") and len(program) > len("git-"):
            # The dashed programs in git's exec path, such as git-push, run as the subcommand
            program, rest = "git", [program.removeprefix("git-"), *rest]
        reason = None
        if program == "git":
            reason = git_reason(rest, directory, desk=desk, subagent=subagent, depth=depth)
        elif program == "gh":
            reason = gh_reason(rest, desk=desk, subagent=subagent)
        if reason is None and subagent:
            script = desk_script(words, directory)
            if script:
                reason = f"{script} is off limits for subagents in desk runs; return a change set to the desk"
        if reason is None and subagent:
            reason = repository_write_reason(program, rest, directory)
        if reason:
            return reason
    return None


def expand_user(path: str) -> Path:
    """Return ``path`` with a leading ``~`` expanded, or unchanged when the home directory is unknown."""
    try:
        return Path(path).expanduser()
    except RuntimeError:
        return Path(path)


def normalise_path(path: str, cwd: str) -> str:
    """Return the absolute path a tool's file path names, without following symlinks.

    Parameters
    ----------
    path : str
        File path from the tool input, absolute or relative to ``cwd``.
    cwd : str
        The session's working directory.

    Returns
    -------
    str
        The path joined to ``cwd``, with ``~`` expanded and ``.``, ``..`` and repeated slashes removed.
    """
    joined = os.path.normpath(Path(cwd, expand_user(path)))
    return "/" + joined.lstrip("/") if joined.startswith("//") else joined


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


def enclosing_repository(path: str, cwd: str) -> Path | None:
    """Return the root of a repository that holds ``path``: the one that holds ``cwd`` or the path itself.

    Parameters
    ----------
    path : str
        File path from the tool input, absolute or relative to ``cwd``.
    cwd : str
        The session's working directory.

    Returns
    -------
    Path | None
        The repository root, or None when ``path`` lies outside both, before and after resolving
        symlinks.
    """
    full = Path(normalise_path(path, cwd))
    candidates = {full, full.resolve()}
    for start in (Path(cwd).absolute(), *(candidate.parent for candidate in candidates)):
        repository = find_repository(start)
        if repository is None:
            continue
        for root in {repository[0], repository[0].resolve()}:
            if any(candidate.is_relative_to(root) for candidate in candidates):
                return repository[0]
    return None


def load_deny_list(*, desk: bool) -> dict[str, list[re.Pattern[str]]]:
    """Read the optional deny-list from ``~/.desk-guard.json``.

    Parameters
    ----------
    desk : bool
        Whether this is a desk run, where a missing, unreadable or malformed file blocks the call.

    Returns
    -------
    dict[str, list[re.Pattern[str]]]
        Compiled patterns per key. Outside a desk run, empty when the file is missing, unreadable or
        malformed.

    Raises
    ------
    BlockError
        When the file is missing, unreadable or malformed in a desk run.
    """
    path = Path.home() / DENY_LIST_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        if desk:
            raise BlockError(f"~/{DENY_LIST_NAME} is missing and desk runs need it; restore it") from error
        return {}
    except OSError as error:
        if desk:
            raise BlockError(f"~/{DENY_LIST_NAME} is unreadable ({error}); fix it") from error
        return {}
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("the top level is not a JSON object")
        patterns = {}
        for key in DENY_LIST_KEYS:
            values = data.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"{key} is not a list of strings")
            patterns[key] = [re.compile(value) for value in values]
    except (ValueError, re.error) as error:
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
    if tool in AGENT_TOOLS and not desk:
        return  # Agent calls reach the hook for rule 10 alone
    cwd = payload["cwd"] if isinstance(payload.get("cwd"), str) else str(Path.cwd())
    # Claude Code sets agent_id only for a subagent's calls; agent_type also comes with --agent sessions
    subagent = desk and payload.get("agent_id") is not None
    command = tool_input.get("command") if tool == "Bash" else None
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    url = tool_input.get("url") if tool == "WebFetch" else None

    if desk and (tool.startswith(MCP_TOOL_PREFIX) or tool in SCHEDULING_TOOLS):
        raise BlockError(f"{tool} is off limits in desk runs")

    # A desk run starts only desk-research subagents (rule 10), and only those may act in it (rule 11)
    desk_types = ", ".join(sorted(DESK_AGENT_TYPES))
    if desk and tool in AGENT_TOOLS:
        subagent_type = tool_input.get("subagent_type")
        if not isinstance(subagent_type, str) or subagent_type not in DESK_AGENT_TYPES:
            named = "no subagent_type" if subagent_type is None else f"subagent_type {subagent_type!r}"
            raise BlockError(
                f"{tool} with {named} is off limits in desk runs; start every subagent with subagent_type {desk_types}",
            )
    if subagent:
        agent_type = payload.get("agent_type")
        if not isinstance(agent_type, str) or agent_type not in DESK_AGENT_TYPES:
            named = "a subagent with no agent_type" if agent_type is None else f"a subagent of type {agent_type!r}"
            raise BlockError(f"{tool} from {named} is off limits in desk runs; only {desk_types} subagents may act")

    if isinstance(command, str):
        reason = bash_reason(command, cwd, desk=desk, subagent=subagent)
        if reason:
            raise BlockError(reason)

    if tool in FILE_TOOLS and isinstance(path, str):
        root = github_repository(path, cwd)
        if root is not None:
            if desk:
                raise BlockError(f"{tool} under .github/ is off limits in desk runs ({path})")
            if ROLLING_BRANCH in {current_branch(str(root)), current_branch(cwd)}:
                raise BlockError(f"{tool} under .github/ is off limits on {ROLLING_BRANCH} ({path})")
        if subagent and enclosing_repository(path, cwd) is not None:
            raise BlockError(
                f"{tool} inside the repository is off limits for subagents in desk runs ({path}); "
                "write scratch files outside it and return a change set to the desk",
            )

    deny_list = load_deny_list(desk=desk)
    subjects = {
        "deny_bash": [command],
        "deny_tools": [tool],
        "deny_paths": [path, normalise_path(path, cwd)] if isinstance(path, str) else [],
        "deny_urls": [url],
    }
    for key, values in subjects.items():
        for subject in values:
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
