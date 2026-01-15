import contextlib
import re
from pathlib import Path

import pandas as pd
import yaml

try:
    from tidy_conf.schema import Conference
    from tidy_conf.schema import get_schema
    from tidy_conf.utils import ordered_dump
except ImportError:
    from .schema import Conference
    from .schema import get_schema
    from .utils import ordered_dump


def write_conference_yaml(data: list[dict] | pd.DataFrame, url: str) -> None:
    """Write a list of dictionaries to a YAML file.

    Parameters
    ----------
    data : Union[List[Dict], pd.DataFrame]
        Data with conferences for YAML file.
    url : str
        Location of the YAML file.
    """
    if isinstance(data, pd.DataFrame):
        data = [{k: v for k, v in record.items() if pd.notnull(v)} for record in data.to_dict(orient="records")]

    # Check if data is empty before accessing elements
    if not data:
        data = []
    elif isinstance(data[0], Conference):
        data = [record.model_dump(exclude_defaults=True, exclude_none=True) for record in data]
    with Path(url).open(
        "w",
        encoding="utf-8",
    ) as outfile:
        for line in ordered_dump(
            data,
            dumper=yaml.SafeDumper,
            default_flow_style=False,
            explicit_start=True,
            allow_unicode=True,
        ).splitlines():
            outfile.write(line.replace("- conference:", "\n- conference:"))
            outfile.write("\n")


def load_conferences() -> pd.DataFrame:
    """Load the conferences from the YAML files.

    Returns
    -------
    pd.DataFrame
        DataFrame conforming with schema.yaml from conferences in _data.
    """
    schema = get_schema()

    data_path = Path("_data")

    # Load the YAML file
    with Path(data_path, "conferences.yml").open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    with Path(data_path, "archive.yml").open(encoding="utf-8") as file:
        archive = yaml.safe_load(file)
    with Path(data_path, "legacy.yml").open(encoding="utf-8") as file:
        legacy = yaml.safe_load(file)

    # Convert the YAML data to a Pandas DataFrame
    return pd.concat(
        [schema, pd.DataFrame.from_dict(data), pd.DataFrame.from_dict(archive), pd.DataFrame.from_dict(legacy)],
        ignore_index=True,
    ).set_index("conference", drop=False)


def load_title_mappings(reverse=False, path="utils/tidy_conf/data/titles.yml"):
    """Load the title mappings from the YAML file."""
    original_path = Path(path)
    module_dir = Path(__file__).parent

    # Determine filename based on what was requested
    if "rejection" in str(original_path).lower():
        filename = "rejections.yml"
    else:
        filename = "titles.yml"

    # Try paths in order of preference, checking for non-empty files
    # Priority: module-relative path (most reliable for imports from any working directory)
    candidates = [
        module_dir / "data" / filename,  # Most reliable - relative to module
        original_path,  # As specified (backwards compatibility)
    ]

    path = None
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            path = candidate
            break

    if path is None:
        # Create default file in module's data directory
        path = module_dir / "data" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as file:
            yaml.dump({"spelling": [], "alt_name": {}}, file, default_flow_style=False, allow_unicode=True)
        return [], {}

    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # Handle case where file is empty or contains only whitespace
    if data is None:
        return [], {}

    spellings = data.get("spelling", [])
    alt_names = {}

    for key, values in data.get("alt_name", {}).items():
        global_name = values.get("global")
        variations_raw = values.get("variations", [])
        regexes = values.get("regexes", [])

        variations = []
        for current_variation in (global_name, *variations_raw):
            if not current_variation:
                continue
            # Create a set with the string (not a set of characters!)
            current_variations = {current_variation.strip()}
            # Add variations without "Conference" or "Conf"
            current_variations.update(
                variation.replace("Conference", "").strip().replace("Conf", "").strip()
                for variation in current_variations.copy()
            )
            # Add variations without spaces
            current_variations.update(re.sub(r"\s+", "", variation).strip() for variation in current_variations.copy())
            # Add variations without non-word characters
            current_variations.update(re.sub(r"\W", "", variation).strip() for variation in current_variations.copy())
            # Add variations without years
            current_variations.update(
                re.sub(r"\b\s*(19|20)\d{2}\s*\b", "", variation).strip() for variation in current_variations.copy()
            )
            # Filter out empty strings
            variations.extend(v for v in current_variations if v)

        if reverse:
            # Reverse mapping: map variations and regexes back to the global name
            if global_name:
                alt_names[global_name] = key
            for variation in variations:
                alt_names[variation] = key
            for regex in regexes:
                alt_names[regex] = key
        else:
            # Forward mapping: map the key to its global name, variations, and regexes
            if global_name:
                variations = [global_name, *variations]
            alt_names[key] = {
                "global": global_name,
                "variations": variations,
                "regexes": regexes,
            }

    return spellings, alt_names


def update_title_mappings(data, path="utils/tidy_conf/data/titles.yml"):
    """Update the title mappings in the YAML file."""
    original_path = Path(path)
    module_dir = Path(__file__).parent

    # Determine filename based on what was requested
    if "rejection" in str(original_path).lower():
        filename = "rejections.yml"
    else:
        filename = "titles.yml"

    # Use module-relative path (most reliable)
    path = module_dir / "data" / filename

    if not path.exists() or path.stat().st_size == 0:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            yaml.dump({"spelling": [], "alt_name": data}, file, default_flow_style=False, allow_unicode=True)
    else:
        with path.open(encoding="utf-8") as file:
            title_data = yaml.safe_load(file)
        if title_data is None:
            title_data = {"spelling": [], "alt_name": {}}
        if "alt_name" not in title_data:
            title_data["alt_name"] = {}
        for key, values in data.items():
            if key in title_data["alt_name"].values():
                continue
            if key not in title_data["alt_name"]:
                title_data["alt_name"][key] = {"variations": []}
            for value in values:
                if value not in title_data["alt_name"][key]["variations"]:
                    title_data["alt_name"][key]["variations"].append(value)
        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            yaml.dump(title_data, file, default_flow_style=False, allow_unicode=True)


def write_df_yaml(df, out_url):
    """Write a conference DataFrame to a YAML file with the right types."""
    with contextlib.suppress(KeyError):
        df = df.drop(["Country", "Venue"], axis=1)
    df["end"] = pd.to_datetime(df["end"]).dt.date
    df["start"] = pd.to_datetime(df["start"]).dt.date
    df["year"] = df["year"].astype(int)
    df["cfp"] = df["cfp"].astype(str)
    write_conference_yaml(df, out_url)
