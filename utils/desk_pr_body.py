#!/usr/bin/env python3
"""Write the desk's part of the rolling PR body and keep the writers' part as it is.

The body of the rolling PR on ``auto/conference-updates`` has two parts: the
desk's ledger, a ``<!-- DESK_END -->`` line, then the part the GitHub Actions
writers add rows to. Reading the body, writing a file and PATCHing it later
loses any row a writer added in between. This script reads the body and
PATCHes it in one command, and keeps everything after the marker byte for
byte.

This module uses only the standard library and the ``gh`` command.

Usage::

    python utils/desk_pr_body.py --pr 512 --desk desk-part.md
    python utils/desk_pr_body.py --pr 512 --desk desk-part.md --print

The desk's part must not contain ``<!-- DESK_END -->``,
``<!-- END_UPDATES -->`` or ``<!-- REVIEW_ITEMS -->``. The writers add their
rows before the first ``<!-- END_UPDATES -->``. The enrich writer replaces
the section from the first ``<!-- REVIEW_ITEMS -->`` to the next
``<!-- END_REVIEW_ITEMS -->``, and inserts a new section before
``<!-- END_UPDATES -->`` only when the body has no ``<!-- REVIEW_ITEMS -->``.
Either marker in the desk's part puts their writes above the
``<!-- DESK_END -->`` line, where the next splice drops them, or makes them
delete that line. When the desk's part holds ``<!-- REVIEW_ITEMS -->`` and
the writers' part has no review section yet, the enrich writer writes no
review section at all: the body has the marker, so it skips the insert, and
the replace finds no ``<!-- END_REVIEW_ITEMS -->`` after it.

Exit codes: 0 when the body was written (or printed), 1 when ``gh`` failed,
2 when the arguments or the desk file are not usable.
"""

import argparse
import shutil
import subprocess  # noqa: S404
import sys
import tempfile
from pathlib import Path

MARKER = "<!-- DESK_END -->"
# The marker and the two markers the writers look for first: none may be in the desk's part.
# There, either of the two would put what the writers add above the marker or make them delete it,
# and REVIEW_ITEMS with no review section in the writers' part makes the enrich writer write none.
RESERVED = (MARKER, "<!-- END_UPDATES -->", "<!-- REVIEW_ITEMS -->")
DEFAULT_REPO = "JesperDramsch/python-deadlines"


class GhError(Exception):
    """A ``gh`` command that could not run or exited non-zero."""


def writers_part(body: str) -> str | None:
    """Return everything after the first marker line of a PR body.

    A marker line holds ``<!-- DESK_END -->`` and nothing else but spaces,
    tabs or a carriage return.

    Parameters
    ----------
    body : str
        The current PR body.

    Returns
    -------
    str | None
        The text after the marker line's newline, byte for byte, or None when
        the body has no marker line.
    """
    start = 0
    while True:
        end = body.find("\n", start)
        line = body[start:] if end == -1 else body[start:end]
        if line.strip(" \t\r") == MARKER:
            return "" if end == -1 else body[end + 1 :]
        if end == -1:
            return None
        start = end + 1


def reserved_in(desk_part: str) -> list[str]:
    """List the markers of ``RESERVED`` that the desk's part contains.

    Parameters
    ----------
    desk_part : str
        The desk's part of the body.

    Returns
    -------
    list[str]
        The markers found anywhere in ``desk_part``, in the order of ``RESERVED``.
    """
    return [marker for marker in RESERVED if marker in desk_part]


def splice(desk_part: str, current_body: str) -> str:
    """Join the desk's new part to the writers' part of the current body.

    Parameters
    ----------
    desk_part : str
        The desk's part of the body. Trailing whitespace is trimmed.
    current_body : str
        The PR body as it is now.

    Returns
    -------
    str
        ``desk_part``, a marker line, then everything after the first marker
        line of ``current_body``. When ``current_body`` has no marker line,
        all of it follows the marker.

    Raises
    ------
    ValueError
        When ``desk_part`` contains the marker, which would hide the writers'
        part from the next splice, or a marker the writers add rows at.
    """
    found = reserved_in(desk_part)
    if found:
        raise ValueError(f"the desk part contains {', '.join(found)}")
    rest = writers_part(current_body)
    if rest is None:
        rest = current_body
    return f"{desk_part.rstrip()}\n{MARKER}\n{rest}"


def run_gh(args: list[str]) -> str:
    """Run a ``gh`` command and return its standard output.

    The output is read as bytes and decoded here: text mode would turn the
    CRLF line ends of a body edited on GitHub into LF.

    Parameters
    ----------
    args : list[str]
        Arguments after ``gh``.

    Returns
    -------
    str
        The command's standard output, decoded as UTF-8, carriage returns kept.

    Raises
    ------
    GhError
        When ``gh`` is not on PATH, exits non-zero or writes output that is not UTF-8.
    """
    executable = shutil.which("gh")
    if executable is None:
        raise GhError("gh is not on PATH")
    try:
        result = subprocess.run(
            [executable, *args],  # noqa: S603
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        message = (error.stderr or b"").decode("utf-8", errors="replace").strip()
        raise GhError(f"gh {' '.join(args)} failed: {message}") from error
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GhError(f"gh {' '.join(args)} wrote output that is not UTF-8: {error}") from error


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
    output = run_gh(["api", f"repos/{repo}/pulls/{pr}", "--jq", ".body"])
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
        run_gh(["api", "-X", "PATCH", f"repos/{repo}/pulls/{pr}", "-F", f"body=@{path}"])


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
    parser = argparse.ArgumentParser(
        description=f"Write the desk's part of the rolling PR body and keep everything after {MARKER}.",
    )
    parser.add_argument("--pr", type=int, required=True, help="the rolling PR's number")
    parser.add_argument("--desk", type=Path, required=True, help="file with the desk's part of the body")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"OWNER/NAME, by default {DEFAULT_REPO}")
    parser.add_argument("--print", action="store_true", help="write the new body to stdout instead of to the PR")
    args = parser.parse_args(argv)

    if args.pr <= 0:
        print(f"desk_pr_body: --pr must be a positive number, not {args.pr}", file=sys.stderr)
        return 2
    try:
        desk_part = args.desk.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"desk_pr_body: cannot read {args.desk}: {error}", file=sys.stderr)
        return 2
    found = reserved_in(desk_part)
    if found:
        print(f"desk_pr_body: refusing {args.desk}: it contains {', '.join(found)}", file=sys.stderr)
        return 2

    try:
        body = splice(desk_part, read_body(args.repo, args.pr))
        if args.print:
            # Bytes here too, so the body shows as it would be written
            sys.stdout.flush()
            sys.stdout.buffer.write(body.encode("utf-8"))
            sys.stdout.buffer.flush()
            return 0
        write_body(args.repo, args.pr, body)
    except GhError as error:
        print(f"desk_pr_body: {error}", file=sys.stderr)
        return 1
    print(f"desk_pr_body: updated the body of {args.repo}#{args.pr} ({len(body)} characters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
