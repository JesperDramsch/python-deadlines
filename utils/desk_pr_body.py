#!/usr/bin/env python3
"""Read and write the blocks of the rolling PR body that each writer owns.

The rolling PR on ``auto/conference-updates`` has three writers: the desk
Routine and two GitHub Actions jobs, the canonical-source import
(``canonical``) and the TBA enrichment (``enrich``). Its body tells the
maintainer what needs them and what was committed, so every writer adds to the
same two sections. Each writer owns blocks between marker lines::

    <!-- NEEDS:enrich -->
    - [ ] North Bay Python 2027: bluesky differs ...
    <!-- /NEEDS:enrich -->

A write reads the body, replaces or extends one block, renders the whole body
again in a fixed layout and PATCHes it, all in one command, so it keeps every
other writer's blocks and the boxes the maintainer ticked. Text outside the
blocks is the layout's own and is rendered again on every write. A body
without the blocks, such as one from before this layout, is kept whole in the
``LEGACY`` block, folded at the end.

The desk owns ``HEAD:desk`` (its "Desk last ran" and "Feedback read to"
lines), ``NEEDS:desk``, ``COMMITTED:desk`` and ``MORE:desk`` (folded detail
and earlier runs). Each Actions writer owns ``NEEDS:<writer>`` and
``COMMITTED:<writer>``.

This module uses the standard library and the ``gh`` and ``git`` commands;
``commit-line`` also needs PyYAML.

Usage::

    python utils/desk_pr_body.py skeleton
    python utils/desk_pr_body.py --pr 519 get HEAD:desk
    python utils/desk_pr_body.py --pr 519 set NEEDS:desk needs.md
    python utils/desk_pr_body.py --pr 519 append COMMITTED:canonical line.md
    python utils/desk_pr_body.py --pr 519 set NEEDS:desk needs.md --print
    python utils/desk_pr_body.py commit-line --sha 873c697 --label "PSF Calendar"

``-`` as the file reads standard input. ``--print`` writes the new body to
standard output instead of to the PR. ``commit-line`` prints nothing for a
commit that changed no edition, so a writer adds no line for it.

Exit codes: 0 when the command did its work, 1 when ``gh`` or ``git`` failed,
2 when the arguments, the file or the resulting body are not usable.
"""

import argparse
import re
import shutil
import subprocess  # noqa: S404
import sys
import tempfile
from datetime import datetime
from datetime import timezone
from pathlib import Path

DEFAULT_REPO = "JesperDramsch/python-deadlines"
WRITERS = ("desk", "enrich", "canonical")
BLOCKS = (
    "HEAD:desk",
    *(f"NEEDS:{writer}" for writer in WRITERS),
    *(f"COMMITTED:{writer}" for writer in WRITERS),
    "MORE:desk",
    "LEGACY",
)
WRITABLE = BLOCKS[:-1]
DATA_FILES = ("_data/conferences.yml", "_data/archive.yml", "_data/legacy.yml")
# GitHub refuses a PR body longer than this
BODY_LIMIT = 65536
# Editions a commit line names before it says "and N more"
LINE_NAMES = 8

MARKER_LINE = re.compile(r"^[ \t]*<!-- (/?)([A-Z]+(?::[a-z]+)?) -->[ \t]*\r?$")


class ToolError(Exception):
    """A ``gh`` or ``git`` command that could not run or exited non-zero."""


def parse(body: str) -> dict[str, str]:
    """Return the content of every block in a body.

    Parameters
    ----------
    body : str
        The PR body.

    Returns
    -------
    dict[str, str]
        Block name to content, without the marker lines and with surrounding
        line breaks trimmed; an empty block is left out. A body that holds no ``HEAD:desk`` start marker
        was written before this layout: all of it, trimmed, is ``LEGACY``. An
        unknown name, a repeated block or a start marker without its end
        marker stays layout text, which the next render drops.
    """
    lines = body.splitlines(keepends=True)
    markers = [MARKER_LINE.match(line) for line in lines]
    if not any(m and not m.group(1) and m.group(2) == "HEAD:desk" for m in markers):
        return {"LEGACY": body.strip()} if body.strip() else {}
    blocks: dict[str, str] = {}
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        start = markers[i]
        name = start.group(2) if start and not start.group(1) else None
        if name in BLOCKS and name not in seen:
            for j in range(i + 1, len(lines)):
                end = markers[j]
                if end and end.group(1) and end.group(2) == name:
                    seen.add(name)
                    content = "".join(lines[i + 1 : j]).strip("\r\n")
                    if content:
                        blocks[name] = content
                    i = j
                    break
        i += 1
    return blocks


def wrap(name: str, blocks: dict[str, str]) -> str:
    """Return one block between its marker lines.

    Parameters
    ----------
    name : str
        The block name.
    blocks : dict[str, str]
        All blocks.

    Returns
    -------
    str
        The start marker, the content when there is any, and the end marker.
    """
    content = blocks.get(name, "")
    inner = f"{content}\n" if content else ""
    return f"<!-- {name} -->\n{inner}<!-- /{name} -->"


def render(blocks: dict[str, str]) -> str:
    """Render the whole body from its blocks.

    Parameters
    ----------
    blocks : dict[str, str]
        Block name to content.

    Returns
    -------
    str
        The body in the fixed layout, with every block present, empty or not.
    """
    needs = [f"NEEDS:{writer}" for writer in WRITERS]
    committed = [f"COMMITTED:{writer}" for writer in WRITERS]
    parts = [wrap("HEAD:desk", blocks)]
    if not blocks.get("HEAD:desk"):
        parts.append("_The desk has not run on this PR yet._")
    parts.extend(
        (
            "## Needs you",
            "_Answer in a PR comment to have the desk act on an item; tick its box once it needs nothing more._",
        ),
    )
    parts.extend(wrap(name, blocks) for name in needs)
    if not any(blocks.get(name) for name in needs):
        parts.append("Nothing waiting.")
    parts.append("## Committed")
    parts.extend(wrap(name, blocks) for name in committed)
    if not any(blocks.get(name) for name in committed):
        parts.append("Nothing yet.")
    parts.append(wrap("MORE:desk", blocks))
    if blocks.get("LEGACY"):
        parts.extend(
            (
                "<details><summary>Body before the current layout</summary>\n",
                wrap("LEGACY", blocks),
                "</details>",
            ),
        )
    return "\n\n".join(parts) + "\n"


def check_content(content: str) -> None:
    """Refuse content that holds a marker line of the layout.

    Parameters
    ----------
    content : str
        Text for one block.

    Raises
    ------
    ValueError
        When a line of ``content`` is a block marker, which would split the
        block on the next read.
    """
    for line in content.splitlines():
        if MARKER_LINE.match(line):
            raise ValueError(f"the content holds the marker line {line.strip()!r}")


def update(body: str, name: str, content: str, *, append: bool = False) -> str:
    """Replace or extend one block and render the body again.

    Parameters
    ----------
    body : str
        The PR body as it is now.
    name : str
        The block to write.
    content : str
        The new content, or the lines to add below the current content.
    append : bool, optional
        Add ``content`` below the block's content instead of replacing it.

    Returns
    -------
    str
        The new body.

    Raises
    ------
    ValueError
        When ``name`` is not a writable block or ``content`` holds a marker line.
    """
    if name not in WRITABLE:
        raise ValueError(f"not a writable block: {name!r} (one of {', '.join(WRITABLE)})")
    check_content(content)
    blocks = parse(body)
    content = content.strip("\r\n")
    current = blocks.get(name, "")
    blocks[name] = f"{current}\n{content}".strip("\r\n") if append and current else content
    return render(blocks)


def run(program: str, args: list[str]) -> str:
    """Run ``gh`` or ``git`` and return its standard output.

    The output is read as bytes and decoded here: text mode would turn the
    CRLF line ends of a body edited on GitHub into LF.

    Parameters
    ----------
    program : str
        ``gh`` or ``git``.
    args : list[str]
        Arguments after the program.

    Returns
    -------
    str
        The standard output, decoded as UTF-8, carriage returns kept.

    Raises
    ------
    ToolError
        When the program is not on PATH, exits non-zero or writes output that is not UTF-8.
    """
    executable = shutil.which(program)
    if executable is None:
        raise ToolError(f"{program} is not on PATH")
    try:
        result = subprocess.run(
            [executable, *args],  # noqa: S603
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        message = (error.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ToolError(f"{program} {' '.join(args)} failed: {message}") from error
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ToolError(f"{program} {' '.join(args)} wrote output that is not UTF-8: {error}") from error


def read_body(repo: str, pr: int) -> str:
    """Read a PR's body.

    Parameters
    ----------
    repo : str
        The repository, as OWNER/NAME.
    pr : int
        The PR number.

    Returns
    -------
    str
        The body. An empty body, which the API returns as null, is "".
    """
    output = run("gh", ["api", f"repos/{repo}/pulls/{pr}", "--jq", '.body // ""'])
    # gh ends the --jq result with a newline of its own; the body is what comes before it.
    return output.removesuffix("\n")


def write_body(repo: str, pr: int, body: str) -> None:
    """Replace a PR's body.

    Parameters
    ----------
    repo : str
        The repository, as OWNER/NAME.
    pr : int
        The PR number.
    body : str
        The new body.
    """
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, "body.md")
        # Bytes, so that no line end is translated on the way to gh
        path.write_bytes(body.encode("utf-8"))
        run("gh", ["api", "-X", "PATCH", f"repos/{repo}/pulls/{pr}", "-F", f"body=@{path}", "--silent"])


def editions(ref: str) -> dict[tuple[str, object], dict]:
    """Return every edition the three data files hold at a commit.

    Parameters
    ----------
    ref : str
        A commit.

    Returns
    -------
    dict[tuple[str, object], dict]
        (``conference``, ``year``) to the entry. A data file missing at the
        commit adds nothing.
    """
    import yaml  # only commit-line needs PyYAML, so the other commands run on the standard library

    found: dict[tuple[str, object], dict] = {}
    for path in DATA_FILES:
        try:
            text = run("git", ["show", f"{ref}:{path}"])
        except ToolError:
            continue
        for entry in yaml.safe_load(text) or []:
            if isinstance(entry, dict) and entry.get("conference"):
                found[(str(entry["conference"]), entry.get("year"))] = entry
    return found


def describe(before: dict[tuple[str, object], dict], after: dict[tuple[str, object], dict]) -> list[str]:
    """Name the editions a commit added, removed or changed, with the changed fields.

    Parameters
    ----------
    before : dict[tuple[str, object], dict]
        The editions before the commit, as ``editions`` returns them.
    after : dict[tuple[str, object], dict]
        The editions after the commit.

    Returns
    -------
    list[str]
        One phrase per edition, such as ``PyCon Togo 2026 (coc, finaid)`` or
        ``PyDay Valparaiso 2025 (added)``, sorted by name. ``location`` belongs
        to the sort and is not named.
    """
    phrases = []
    for key in sorted(set(before) | set(after), key=lambda k: (k[0].casefold(), str(k[1]))):
        name = f"{key[0]} {key[1]}"
        if key not in before:
            phrases.append(f"{name} (added)")
        elif key not in after:
            phrases.append(f"{name} (removed)")
        else:
            old, new = before[key], after[key]
            fields = sorted(f for f in set(old) | set(new) if f != "location" and old.get(f) != new.get(f))
            if fields:
                phrases.append(f"{name} ({', '.join(fields)})")
    return phrases


def commit_line(sha: str, label: str, repo: str, day: str | None = None) -> str:
    """Return the Committed line for a writer's commit.

    Parameters
    ----------
    sha : str
        The commit, which must be in the local repository with its first parent.
    label : str
        What made the commit, such as ``PSF Calendar`` or ``TBA enrichment``.
    repo : str
        The repository, as OWNER/NAME, for the commit link.
    day : str | None, optional
        The date to show, by default today in UTC.

    Returns
    -------
    str
        A list item: date, label, linked short hash, and the editions the
        commit touched (the first ``LINE_NAMES``, then a count of the rest).
        "" when the commit changed no edition, such as a commit that only
        reformats the files or moves entries between them: the maintainer has
        nothing to look at there.
    """
    full = run("git", ["rev-parse", "--verify", f"{sha}^{{commit}}"]).strip()
    phrases = describe(editions(f"{full}^"), editions(full))
    if not phrases:
        return ""
    shown = "; ".join(phrases[:LINE_NAMES])
    if len(phrases) > LINE_NAMES:
        shown += f"; and {len(phrases) - LINE_NAMES} more"
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"- {day} · {label} · [{full[:7]}](https://github.com/{repo}/commit/{full}): {shown}"


def read_content(path: str) -> str:
    """Read a block's content from a file, or from standard input for ``-``.

    Parameters
    ----------
    path : str
        The file, or ``-``.

    Returns
    -------
    str
        The content, decoded as UTF-8.
    """
    if path == "-":
        return sys.stdin.buffer.read().decode("utf-8")
    return Path(path).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser.

    Returns
    -------
    argparse.ArgumentParser
        The parser for the commands the module docstring lists.
    """
    parser = argparse.ArgumentParser(description="Read and write the writers' blocks of the rolling PR body.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"OWNER/NAME, by default {DEFAULT_REPO}")
    parser.add_argument("--pr", type=int, help="the rolling PR's number, for get, set and append")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("skeleton", help="print an empty body, for opening the PR")
    get = commands.add_parser("get", help="print one block's content")
    get.add_argument("block", choices=BLOCKS)
    for verb in ("set", "append"):
        write = commands.add_parser(verb, help=f"{verb} one block's content and write the body")
        write.add_argument("block", choices=WRITABLE)
        write.add_argument("file", help="the content, or - for standard input")
        write.add_argument("--print", action="store_true", help="print the new body instead of writing it")
    line = commands.add_parser("commit-line", help="print the Committed line for a commit")
    line.add_argument("--sha", required=True)
    line.add_argument("--label", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface.

    Parameters
    ----------
    argv : list[str] | None, optional
        The arguments, by default those of the process.

    Returns
    -------
    int
        The exit code, as the module docstring describes.
    """
    args = build_parser().parse_args(argv)
    if args.command == "skeleton":
        sys.stdout.write(render({}))
        return 0
    try:
        if args.command == "commit-line":
            line = commit_line(args.sha, args.label, args.repo)
            sys.stdout.write(f"{line}\n" if line else "")
            return 0
        if args.pr is None or args.pr <= 0:
            print("desk_pr_body: --pr must be a positive number", file=sys.stderr)
            return 2
        if args.command == "get":
            content = parse(read_body(args.repo, args.pr)).get(args.block, "")
            sys.stdout.write(f"{content}\n" if content else "")
            return 0
        try:
            content = read_content(args.file)
        except (OSError, UnicodeDecodeError) as error:
            print(f"desk_pr_body: cannot read {args.file}: {error}", file=sys.stderr)
            return 2
        try:
            body = update(read_body(args.repo, args.pr), args.block, content, append=args.command == "append")
        except ValueError as error:
            print(f"desk_pr_body: refusing {args.file}: {error}", file=sys.stderr)
            return 2
        if len(body) > BODY_LIMIT:
            print(f"desk_pr_body: the body would have {len(body)} characters, over {BODY_LIMIT}", file=sys.stderr)
            return 2
        if args.print:
            # Bytes here too, so the body shows as it would be written
            sys.stdout.flush()
            sys.stdout.buffer.write(body.encode("utf-8"))
            sys.stdout.buffer.flush()
            return 0
        write_body(args.repo, args.pr, body)
    except ToolError as error:
        print(f"desk_pr_body: {error}", file=sys.stderr)
        return 1
    print(f"desk_pr_body: wrote {args.block} of {args.repo}#{args.pr} ({len(body)} characters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
