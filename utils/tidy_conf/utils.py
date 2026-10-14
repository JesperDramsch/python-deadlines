import sys
import unicodedata

import pandas as pd
import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

from yaml.representer import SafeRepresenter

try:
    from tidy_conf.queue_out import append_queue_record
    from tidy_conf.queue_out import utc_now
except ImportError:
    from .queue_out import append_queue_record
    from .queue_out import utc_now

_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


def dict_constructor(loader, node):
    return dict(loader.construct_pairs(node))


Dumper.add_representer(dict, dict_representer)
Loader.add_constructor(_mapping_tag, dict_constructor)

Dumper.add_representer(str, SafeRepresenter.represent_str)


def ordered_dump(data, stream=None, dumper=yaml.Dumper, **kwds):
    class OrderedDumper(dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items())

    OrderedDumper.add_representer(dict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


def strip_accents(text: str) -> str:
    """Remove diacritics while preserving case, e.g. "PyCon Panamá" -> "PyCon Panama".

    Only use this for matching. Stored conference names keep their original spelling.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if not unicodedata.combining(c)))


def fold_name(text: str) -> str:
    """Fold a name for comparison: strip accents, casefold, and collapse whitespace.

    "PyDay  México" and "pyday mexico" both fold to "pyday mexico".
    """
    return " ".join(strip_accents(text).casefold().split())


def pretty_print(header, conf, tba=None, expired=None) -> None:
    """Print order of conferences.

    Args:
        header (_type_): Header for print
        conf (_type_): conferences
        tba (_type_, optional): tba conferences. Defaults to None.
        expired (_type_, optional): expired conferences. Defaults to None.
    """
    print(header)
    for data in [conf, tba, expired]:
        if data is not None:
            for q in data:
                if "cfp" in q and "conference" in q:
                    print(q["cfp"], " - ", q["conference"])
                else:
                    print(q)
            print("\n")


# Merge questions asked where no one could answer them (CI). Each is also
# handed to the desk queue when DESK_QUEUE_OUT names a file (queue_out.py), so
# the desk checks the live site; the merge itself keeps the default answer.
QUESTION_RECORDS: list[dict] = []


def _queue_text(value) -> str | None:
    """Return a merge value as text for a queue record, or None when it is empty."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def record_question(question: str, default_answer: bool, context: dict) -> dict:
    """Record a merge question that was answered with its default.

    Parameters
    ----------
    question : str
        The question as it would have been asked.
    default_answer : bool
        The answer the merge went on with.
    context : dict
        What the question is about: "conference", "year" (int or None),
        "field", "yaml_value", "remote_value", "source_name" and "url".

    Returns
    -------
    dict
        The record, a queue item without "id" with source "canonical-import"
        and kind "question".
    """
    year = context.get("year")
    payload = {
        "question": question,
        "conference": context.get("conference"),
        "year": year,
        "field": context.get("field"),
        "yaml_value": _queue_text(context.get("yaml_value")),
        "remote_value": _queue_text(context.get("remote_value")),
        "default_answer": default_answer,
        "source_name": context.get("source_name"),
    }
    record = {
        "source": "canonical-import",
        "kind": "question",
        "received": utc_now(),
        "title": payload["conference"] or question,
        "url": context.get("url") or "",
        "year": year,
        "payload": payload,
    }
    QUESTION_RECORDS.append(record)
    append_queue_record(record)
    return record


# Helper function for yes no questions
def query_yes_no(question, default="no", context=None):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user. "default" is the presumed
    answer if the user just hits <Enter>.     It must be "yes" (the default), "no" or
    None (meaning     an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".

    In non-interactive environments (e.g., CI), returns the default value. When
    "context" describes what the question is about (see record_question), the
    unanswered question is recorded for the desk.
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}

    # In non-interactive environments, use the default value
    if not sys.stdin.isatty():
        # If no default and non-interactive, default to "no" for safety
        answer = valid[default] if default is not None else False
        if context is not None:
            record_question(question, answer, context)
        return answer

    match default:
        case "yes":
            prompt = " [Y/n] "
        case "no":
            prompt = " [y/N] "
        case _:
            prompt = " [y/n] "

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        if choice in valid:
            return valid[choice]
        sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")


def _load_subs_keywords():
    """Load sub keywords from subs.yml for auto-detection.

    Returns empty dict if loading fails, allowing fallback to DEFAULT_SUB.
    """
    try:
        from .subs import load_subs

        return load_subs()
    except (FileNotFoundError, ImportError):
        return {}


def _auto_detect_sub(conference_name: str) -> str | None:
    """Auto-detect sub category based on conference name.

    Parameters
    ----------
    conference_name : str
        Name of the conference

    Returns
    -------
    str | None
        Sub category string if matched, None otherwise.
    """
    keywords = _load_subs_keywords()
    name_lower = conference_name.lower()
    for sub_key, sub_keywords in keywords.items():
        if any(word in name_lower for word in sub_keywords):
            return sub_key
    return None


# Default sub value for conferences that don't match any keyword
DEFAULT_SUB = "PY"


def fill_missing_required(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing required fields in the DataFrame.

    In non-interactive environments (CI), uses auto-detection and defaults
    instead of prompting for user input.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with conference data

    Returns
    -------
    pd.DataFrame
        DataFrame with missing required fields filled.
    """
    required = [
        "conference",
        "year",
        "link",
        "cfp",
        "place",
        "start",
        "end",
        "sub",
    ]

    is_interactive = sys.stdin.isatty()

    for i, row in df.copy().iterrows():
        for keyword in required:
            if pd.isna(row[keyword]):
                # Handle sub field specially - try auto-detection first
                if keyword == "sub":
                    detected_sub = _auto_detect_sub(row["conference"])
                    if detected_sub:
                        df.loc[i, keyword] = detected_sub
                        continue
                    # Use default if no match and non-interactive
                    if not is_interactive:
                        df.loc[i, keyword] = DEFAULT_SUB
                        continue

                # In non-interactive mode, skip prompting for other fields
                if not is_interactive:
                    # Leave as NaN - will be caught by validation later
                    continue

                # Interactive mode - prompt user
                user_input = input(
                    f"What's the value of '{keyword}' for conference '{row['conference']}' check {row['link']} ?: ",
                )
                if user_input != "":
                    df.loc[i, keyword] = user_input
    return df
