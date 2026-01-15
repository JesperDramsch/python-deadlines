import sys

import pandas as pd
import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

from yaml.representer import SafeRepresenter

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


# Helper function for yes no questions
def query_yes_no(question, default="no"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user. "default" is the presumed
    answer if the user just hits <Enter>.     It must be "yes" (the default), "no" or
    None (meaning     an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
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


def fill_missing_required(df):
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

    for i, row in df.copy().iterrows():
        for keyword in required:
            if pd.isna(row[keyword]):
                user_input = input(
                    f"What's the value of '{keyword}' for conference '{row['conference']}' check {row['link']} ?: ",
                )
                if user_input != "":
                    df.loc[i, keyword] = user_input
    return df
