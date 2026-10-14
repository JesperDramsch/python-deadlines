#!/usr/bin/env python3
"""Resolve a git merge that stopped on conflicts in the conference data files.

Main and the rolling branch ``auto/conference-updates`` both run
``utils/sort_yaml.py``, which moves entries between conferences.yml,
archive.yml and legacy.yml and orders them by date. Once both sides have
sorted an entry the rolling branch edited, a plain ``git merge`` conflicts in
``_data`` even when no field changed on both sides.

Run this while ``git merge`` is stopped on conflicts. It keys every entry on
(conference, year) across the three files, so a move between files does not
matter (``merge_entries`` says how it tells apart the few old pairs that
repeat), and merges the merge base, HEAD (ours) and MERGE_HEAD (theirs) field by
field. When no field changed differently on both sides, it writes the result,
sorts it back into place with ``sort_yaml.sort_data``, checks that no entry was
lost and stages the three files. The caller then runs ``git commit --no-edit``.

Exit codes:

- 0: the data files are merged, sorted and staged;
- 1: a conflict, a key repeated within one side, a failed sort or a lost
  entry; the data files are left as git left them;
- 2: not a git repository, no merge in progress, nothing conflicted, a
  conflicted path outside the data files, or no merge base.

Usage::

    git merge origin/main --no-edit || { python utils/merge_data.py && git commit --no-edit; }
"""

import argparse
import json
import os
import shutil
import subprocess  # noqa: S404
import sys
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from itertools import starmap
from pathlib import Path
from typing import Any

import yaml

try:
    from sort_yaml import sort_data
    from tidy_conf.yaml import write_conference_yaml
except ImportError:
    from .sort_yaml import sort_data
    from .tidy_conf.yaml import write_conference_yaml

DATA_FILES = ("_data/conferences.yml", "_data/archive.yml", "_data/legacy.yml")

# (conference, year), or (conference, year, place) for a pair the merge base already repeats
Key = tuple[Any, ...]


class _Sentinel:
    """A value that stands for something one version does not have."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"({self.label})"


MISSING = _Sentinel("missing")
NO_ENTRY = _Sentinel("no entry")


class DataError(Exception):
    """A data file that cannot be merged: not a list of mappings, or a key repeated within one side."""


@dataclass(frozen=True)
class Conflict:
    """One field that both sides changed in different ways.

    ``base``, ``ours`` and ``theirs`` hold the loaded value, ``MISSING`` when
    that version has the entry but not the field, or ``NO_ENTRY`` when it does
    not have the entry at all.
    """

    key: Key
    field: str
    base: Any
    ours: Any
    theirs: Any

    def describe(self) -> str:
        """Return the conflict as one line for a person to read.

        Returns
        -------
        str
            The key, the field and the three values.
        """
        return (
            f"{describe_key(self.key)}, field {self.field}: "
            f"base {show(self.base)}, ours {show(self.ours)}, theirs {show(self.theirs)}"
        )


@dataclass
class MergeResult:
    """The merged entries, the conflicts found and what each side contributed."""

    entries: list[dict] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    fields_from_ours: int = 0
    fields_from_theirs: int = 0
    added_ours: int = 0
    added_theirs: int = 0
    deleted_ours: int = 0
    deleted_theirs: int = 0

    def summary(self) -> str:
        """Return one line on what the merge did.

        Returns
        -------
        str
            The entry count and what came from each side.
        """
        return (
            f"merged {count(len(self.entries), 'entry', 'entries')}: "
            f"{count(self.fields_from_ours, 'field')} from HEAD and {self.fields_from_theirs} from MERGE_HEAD, "
            f"{count(self.added_ours, 'entry', 'entries')} added on HEAD and {self.added_theirs} on MERGE_HEAD, "
            f"{self.deleted_ours} deleted on HEAD and {self.deleted_theirs} on MERGE_HEAD"
        )


def count(number: int, singular: str, plural: str = "") -> str:
    """Write a number with a noun in the right form.

    Parameters
    ----------
    number : int
        How many.
    singular : str
        The noun for one.
    plural : str, optional
        The noun for any other number, by default ``singular`` with an s.

    Returns
    -------
    str
        For example "1 field" or "3 fields".
    """
    return f"{number} {singular if number == 1 else plural or singular + 's'}"


def show(value: Any) -> str:
    """Format a loaded value, or a sentinel, for a conflict report.

    Parameters
    ----------
    value : Any
        A value loaded from YAML, ``MISSING`` or ``NO_ENTRY``.

    Returns
    -------
    str
        The sentinel's label in brackets, or the value as JSON.
    """
    if isinstance(value, _Sentinel):
        return repr(value)
    return json.dumps(value, default=str, ensure_ascii=False)


def same_value(a: Any, b: Any) -> bool:
    """Compare two loaded values, types included, so that ``1`` and ``True`` differ.

    Mappings compare without regard to key order, lists in order.

    Parameters
    ----------
    a : Any
        First value.
    b : Any
        Second value.

    Returns
    -------
    bool
        True when the values are the same.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_value(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(starmap(same_value, zip(a, b, strict=True)))
    return a == b


def describe_key(key: Key) -> str:
    """Write a key for a person to read.

    Parameters
    ----------
    key : Key
        (conference, year), or (conference, year, place).

    Returns
    -------
    str
        For example "PyData Amsterdam 2026" or "PyCon China 2023 (Beijing, China)".
    """
    text = f"{key[0]} {key[1]}"
    return f"{text} ({key[2]})" if len(key) > 2 else text


def repeated_pairs(entries: list) -> set[Key]:
    """Find the (conference, year) pairs that more than one entry has.

    Parameters
    ----------
    entries : list
        The entries of the three data files of one side, concatenated.

    Returns
    -------
    set[Key]
        The repeated pairs. Entries that are not mappings are left to ``index_entries``.
    """
    pairs = Counter((entry.get("conference"), entry.get("year")) for entry in entries if isinstance(entry, dict))
    return {pair for pair, number in pairs.items() if number > 1}


def index_entries(entries: list, side: str, by_place: set[Key] | frozenset = frozenset()) -> dict[Key, dict]:
    """Key one side's entries on (conference, year), or on (conference, year, place) for the pairs in ``by_place``.

    Parameters
    ----------
    entries : list
        The entries of the three data files of one side, concatenated.
    side : str
        The side's name for error messages: base, ours or theirs.
    by_place : set[Key] | frozenset, optional
        (conference, year) pairs whose entries are told apart by place, by default none.

    Returns
    -------
    dict[Key, dict]
        Entries by key, in their original order.

    Raises
    ------
    DataError
        When an entry is not a mapping, lacks its conference or year, or
        repeats a key already seen on this side.
    """
    index: dict[Key, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise DataError(f"{side}: an entry is not a mapping: {show(entry)}")
        key: Key = (entry.get("conference"), entry.get("year"))
        if key[0] is None or key[1] is None:
            raise DataError(f"{side}: an entry has no conference or no year: {show(entry)}")
        if key in by_place:
            key = (*key, entry.get("place"))
        if key in index:
            raise DataError(f"{side}: {describe_key(key)} appears more than once")
        index[key] = entry
    return index


def _merge_fields(key: Key, base: dict, ours: dict, theirs: dict, result: MergeResult) -> dict:
    """Merge one entry that all three versions have, field by field.

    Parameters
    ----------
    key : Key
        The entry's key.
    base : dict
        The entry at the merge base.
    ours : dict
        The entry at HEAD.
    theirs : dict
        The entry at MERGE_HEAD.
    result : MergeResult
        Collects the conflicts and the counts.

    Returns
    -------
    dict
        The merged entry, without the fields in conflict.
    """
    merged = {}
    for name in dict.fromkeys([*ours, *theirs, *base]):
        b, o, t = base.get(name, MISSING), ours.get(name, MISSING), theirs.get(name, MISSING)
        if same_value(o, t):
            value = o
        elif same_value(o, b):
            value = t
            result.fields_from_theirs += 1
        elif same_value(t, b):
            value = o
            result.fields_from_ours += 1
        else:
            result.conflicts.append(Conflict(key, name, b, o, t))
            continue
        if value is not MISSING:
            merged[name] = value
    return merged


def _changes_to_deleted(key: Key, base: dict, changed: dict, *, deleted_on_ours: bool) -> list[Conflict]:
    """List the fields one side changed on an entry the other side deleted.

    Parameters
    ----------
    key : Key
        The entry's key.
    base : dict
        The entry at the merge base.
    changed : dict
        The entry on the side that kept and changed it.
    deleted_on_ours : bool
        True when HEAD deleted the entry, False when MERGE_HEAD did.

    Returns
    -------
    list[Conflict]
        One conflict per changed field.
    """
    conflicts = []
    for name in dict.fromkeys([*base, *changed]):
        b, c = base.get(name, MISSING), changed.get(name, MISSING)
        if same_value(b, c):
            continue
        if deleted_on_ours:
            conflicts.append(Conflict(key, name, b, NO_ENTRY, c))
        else:
            conflicts.append(Conflict(key, name, b, c, NO_ENTRY))
    return conflicts


def merge_entries(base: list, ours: list, theirs: list) -> MergeResult:
    """Merge three versions of the conference data, entry by entry and field by field.

    Each version is the entries of conferences.yml, archive.yml and legacy.yml
    together, so an entry moved between files is the same entry. Entries are
    keyed on (conference, year). A few old pairs repeat at the merge base,
    such as a PyCon China held in several cities in one year, so the entries
    of a pair the base repeats are told apart by place on every side. Any
    other repeated key is an error. A field missing from an entry counts as
    deleted there.

    - A field both sides agree on is kept.
    - A field one side changed while the other left it as base takes the change.
    - A field both sides changed differently is a conflict.
    - An entry added on one side is kept. Added on both sides, it must be the
      same on both, or every field that differs is a conflict.
    - An entry deleted on one side and unchanged on the other is deleted.
      Changed on the other side, every changed field is a conflict.

    Parameters
    ----------
    base : list
        Entries at the merge base.
    ours : list
        Entries at HEAD.
    theirs : list
        Entries at MERGE_HEAD.

    Returns
    -------
    MergeResult
        The merged entries, in the order of ours followed by those only theirs
        has, and the conflicts found. The entries are complete only when there
        are no conflicts.

    Raises
    ------
    DataError
        When an entry is not a mapping or lacks its key, or a key repeats within one side.
    """
    by_place = repeated_pairs(base)
    base_index = index_entries(base, "base", by_place)
    ours_index = index_entries(ours, "ours", by_place)
    theirs_index = index_entries(theirs, "theirs", by_place)
    result = MergeResult()

    for key in dict.fromkeys([*ours_index, *theirs_index, *base_index]):
        b, o, t = base_index.get(key), ours_index.get(key), theirs_index.get(key)
        if b is None:
            if o is not None and t is not None:
                if same_value(o, t):
                    result.entries.append(o)
                    result.added_ours += 1
                    result.added_theirs += 1
                    continue
                for name in dict.fromkeys([*o, *t]):
                    ov, tv = o.get(name, MISSING), t.get(name, MISSING)
                    if not same_value(ov, tv):
                        result.conflicts.append(Conflict(key, name, NO_ENTRY, ov, tv))
            elif o is not None:
                result.entries.append(o)
                result.added_ours += 1
            else:
                result.entries.append(t)
                result.added_theirs += 1
        elif o is not None and t is not None:
            result.entries.append(_merge_fields(key, b, o, t, result))
        elif o is None and t is None:
            result.deleted_ours += 1
            result.deleted_theirs += 1
        elif o is None:
            if same_value(b, t):
                result.deleted_ours += 1
            else:
                result.conflicts.extend(_changes_to_deleted(key, b, t, deleted_on_ours=True))
        elif same_value(b, o):
            result.deleted_theirs += 1
        else:
            result.conflicts.extend(_changes_to_deleted(key, b, o, deleted_on_ours=False))
    return result


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and capture its output as UTF-8 text.

    Parameters
    ----------
    *args : str
        Arguments after ``git``.
    cwd : Path
        Directory to run in.
    check : bool, optional
        Raise on a non-zero exit, by default True.

    Returns
    -------
    subprocess.CompletedProcess
        The finished process.

    Raises
    ------
    FileNotFoundError
        When git is not on PATH.
    """
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("git is not on PATH")
    return subprocess.run(
        [executable, *args],  # noqa: S603
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check,
    )


def conflicted_paths(cwd: Path) -> list[str]:
    """List the paths git reports as unmerged, relative to the repository root.

    Parameters
    ----------
    cwd : Path
        A directory inside the repository.

    Returns
    -------
    list[str]
        The unmerged paths.
    """
    output = git("diff", "--name-only", "--diff-filter=U", "-z", cwd=cwd).stdout
    return [path for path in output.split("\0") if path]


def load_yaml_list(text: str, where: str) -> list:
    """Load a data file's text as a list of entries.

    Parameters
    ----------
    text : str
        The file's content.
    where : str
        Where the text came from, for error messages.

    Returns
    -------
    list
        The entries. An empty file is an empty list.

    Raises
    ------
    DataError
        When the text does not parse or does not hold a list.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise DataError(f"{where} does not parse: {error}") from error
    if data is None:
        return []
    if not isinstance(data, list):
        raise DataError(f"{where} does not hold a list")
    return data


def read_side(rev: str, cwd: Path) -> list:
    """Load the three data files of one commit. A file the commit does not have counts as empty.

    Parameters
    ----------
    rev : str
        A commit, such as HEAD, MERGE_HEAD or a merge base sha.
    cwd : Path
        A directory inside the repository.

    Returns
    -------
    list
        The entries of conferences.yml, archive.yml and legacy.yml, concatenated.
    """
    entries = []
    for path in DATA_FILES:
        if git("cat-file", "-e", f"{rev}:{path}", cwd=cwd, check=False).returncode != 0:
            continue
        text = git("show", f"{rev}:{path}", cwd=cwd).stdout
        entries.extend(load_yaml_list(text, f"{rev}:{path}"))
    return entries


def read_worktree_keys(root: Path) -> list[Key]:
    """List the (conference, year) key of every entry in the working tree's data files.

    Parameters
    ----------
    root : Path
        The repository root.

    Returns
    -------
    list[Key]
        One key per entry, repeats included.
    """
    keys = []
    for path in DATA_FILES:
        file = root / path
        if not file.exists():
            continue
        for entry in load_yaml_list(file.read_text(encoding="utf-8"), path):
            if isinstance(entry, dict):
                keys.append((entry.get("conference"), entry.get("year")))
            else:
                keys.append((None, None))
    return keys


def write_and_sort(entries: list[dict], root: Path) -> None:
    """Write the merged entries, sort them into place and check that none was lost.

    When anything fails, the data files get back the content git left in them.

    Parameters
    ----------
    entries : list[dict]
        The merged entries.
    root : Path
        The repository root. It must be the working directory, since the
        schema check reads utils/schema.yml and _data/types.yml from there.

    Raises
    ------
    DataError
        When the sorted files hold a different set of keys from the merged entries.
    """
    originals = {path: (root / path).read_bytes() if (root / path).exists() else None for path in DATA_FILES}
    try:
        write_conference_yaml(entries, str(root / DATA_FILES[0]))
        for path in DATA_FILES[1:]:
            write_conference_yaml([], str(root / path))
        sort_data(base=str(root), skip_links=True)

        expected = Counter((entry["conference"], entry["year"]) for entry in entries)
        found = Counter(read_worktree_keys(root))
        if found != expected:
            lost = sorted(f"{conference} {year}" for conference, year in expected - found)
            gained = sorted(f"{conference} {year}" for conference, year in found - expected)
            raise DataError(
                "the sort changed the set of entries; "
                f"lost: {', '.join(lost) or 'none'}; gained: {', '.join(gained) or 'none'}",
            )
    except BaseException:
        for path, content in originals.items():
            if content is None:
                (root / path).unlink(missing_ok=True)
            else:
                (root / path).write_bytes(content)
        raise


def resolve(root: Path) -> int:
    """Merge the data files of a stopped ``git merge`` and stage them.

    Parameters
    ----------
    root : Path
        The repository root. It must be the working directory.

    Returns
    -------
    int
        The exit code, as the module docstring describes.
    """
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=root, check=False).returncode != 0:
        print("merge_data: no merge in progress (MERGE_HEAD is missing)", file=sys.stderr)
        return 2

    paths = conflicted_paths(root)
    if not paths:
        print("merge_data: git reports no conflicted paths, so there is nothing to resolve", file=sys.stderr)
        return 2
    outside = [path for path in paths if path not in DATA_FILES]
    if outside:
        print("merge_data: conflicts outside the data files, resolve them by hand:", file=sys.stderr)
        for path in outside:
            print(f"  {path}", file=sys.stderr)
        return 2

    merge_base = git("merge-base", "HEAD", "MERGE_HEAD", cwd=root, check=False)
    if merge_base.returncode != 0:
        print("merge_data: HEAD and MERGE_HEAD have no merge base", file=sys.stderr)
        return 2

    try:
        result = merge_entries(
            read_side(merge_base.stdout.strip(), root),
            read_side("HEAD", root),
            read_side("MERGE_HEAD", root),
        )
    except DataError as error:
        print(f"merge_data: {error}", file=sys.stderr)
        return 1

    if result.conflicts:
        print(
            f"merge_data: {count(len(result.conflicts), 'conflict')} to resolve by hand, nothing written:",
            file=sys.stderr,
        )
        for conflict in result.conflicts:
            print(f"  {conflict.describe()}", file=sys.stderr)
        return 1

    try:
        write_and_sort(result.entries, root)
    except Exception as error:
        print(f"merge_data: {error}; the data files are as git left them", file=sys.stderr)
        return 1

    git("add", "--", *DATA_FILES, cwd=root)
    print(f"merge_data: {result.summary()}; staged {', '.join(DATA_FILES)}")
    return 0


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
        description="Resolve a stopped git merge whose only conflicts are in the conference data files.",
    )
    parser.parse_args(argv)

    toplevel = git("rev-parse", "--show-toplevel", cwd=Path.cwd(), check=False)
    if toplevel.returncode != 0:
        print("merge_data: not inside a git repository", file=sys.stderr)
        return 2
    root = Path(toplevel.stdout.strip())
    # The schema check in sort_data reads utils/schema.yml and _data/types.yml from the working directory.
    os.chdir(root)
    return resolve(root)


if __name__ == "__main__":
    sys.exit(main())
