import re
import sys
import urllib
from datetime import datetime
from datetime import timezone
from pathlib import Path

import iso3166
import pandas as pd

sys.path.append(".")
from tidy_conf import fuzzy_match
from tidy_conf import load_conferences
from tidy_conf import merge_conferences
from tidy_conf.deduplicate import deduplicate
from tidy_conf.schema import get_schema
from tidy_conf.utils import fill_missing_required
from tidy_conf.yaml import load_title_mappings
from tidy_conf.yaml import write_df_yaml


def load_remote(year):
    url = f"https://raw.githubusercontent.com/python-organizers/conferences/main/{year}.csv"

    # Read data and rename columns
    df = pd.read_csv(url)
    df = map_columns(df)

    # Only return valid cfps
    # return df.dropna(subset=['cfp'])
    return df


def map_columns(df, reverse=False):
    """Map columns to the schema."""
    cols = {
        "Subject": "conference",
        "Start Date": "start",
        "End Date": "end",
        "Tutorial Deadline": "tutorial_deadline",
        "Talk Deadline": "cfp",
        "Website URL": "link",
        "Proposal URL": "cfp_link",
        "Sponsorship URL": "sponsor",
    }

    df["place"] = df["Location"]

    if reverse:
        cols = {v: k for k, v in cols.items()}

    return df.rename(columns=cols)


def write_csv(df, year, csv_location):
    """Write the CSV files for the conferences."""
    from logging_config import get_tqdm_logger

    logger = get_tqdm_logger(__name__)

    logger.info(f"Starting write_csv for year {year} with df shape: {df.shape}")
    logger.debug(f"write_csv input columns: {df.columns.tolist()}")

    # Validate conference names before processing
    invalid_conferences = df[~df["conference"].apply(lambda x: isinstance(x, str) and len(str(x).strip()) > 0)]
    if not invalid_conferences.empty:
        logger.error(f"Found {len(invalid_conferences)} rows with invalid conference names in write_csv:")
        for idx, row in invalid_conferences.iterrows():
            logger.error(f"  Row {idx}: conference = {row['conference']} (type: {type(row['conference'])})")
        # Fix invalid conference names
        df.loc[invalid_conferences.index, "conference"] = df.loc[invalid_conferences.index, "conference"].apply(
            lambda x: str(x) if pd.notna(x) else f"Conference_{invalid_conferences.index}",
        )

    df["cfp"] = df["cfp"].str.slice(stop=10).str.replace(r"\b(TBA|None)\b", "", regex=True)
    df["tutorial_deadline"] = (
        df["tutorial_deadline"].fillna("").apply(str).str.slice(stop=10).str.replace(r"\b(TBA|None)\b", "", regex=True)
    )
    df = map_columns(df, reverse=True)
    logger.debug(f"After map_columns, df shape: {df.shape}")

    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        if y in df["year"].unique():
            # Extract and prepare data for this year
            df_year_subset = df.loc[df["year"] == y]
            logger.debug(f"Year {y} subset shape: {df_year_subset.shape}")

            csv_data = (
                df_year_subset[
                    [
                        "Subject",
                        "Start Date",
                        "End Date",
                        "Location",
                        "Country",
                        "Venue",
                        "Tutorial Deadline",
                        "Talk Deadline",
                        "Website URL",
                        "Proposal URL",
                        "Sponsorship URL",
                    ]
                ]
                .fillna("")
                .astype(str)
                .sort_values(by=["Start Date", "End Date", "Subject"])
            )

            logger.debug(f"Writing CSV for year {y} with {len(csv_data)} conferences")
            logger.debug(f"Sample conference names: {csv_data['Subject'].head().tolist()}")

            csv_data.to_csv(Path(csv_location, f"{y}.csv"), index=False)
            logger.info(f"Successfully wrote {Path(csv_location, f'{y}.csv')}")


def main(year=None, base=""):
    """Import Python conferences from a csv file Github."""
    from logging_config import get_tqdm_logger

    # Setup tqdm-compatible logging for this module
    logger = get_tqdm_logger(__name__)
    logger.info("🚀 Starting import_python_organizers main function")

    # If no year is provided, use the current year
    if year is None:
        year = datetime.now(tz=timezone.utc).year

    logger.info(f"Processing conferences for year: {year}")

    # Load current conferences
    _data_path = Path(base, "_data")
    _utils_path = Path(base, "utils")
    _tmp_path = Path(base, ".tmp")
    _tmp_path.mkdir(exist_ok=True, parents=True)
    _data_path.mkdir(exist_ok=True, parents=True)
    target_file = Path(_data_path, "conferences.yml")
    csv_location = Path(_utils_path, "conferences")
    cache_file = Path(_tmp_path, ".conferences_py_orgs.csv")

    # Load the existing conference data
    df_yml = load_conferences()
    df_schema = get_schema()
    df_new = pd.DataFrame(columns=df_schema.columns)
    df_csv_raw = pd.DataFrame(columns=df_schema.columns)

    # Parse your csv file and iterate through year by year
    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        try:
            df = deduplicate(load_remote(year=y), "conference")
            df["year"] = y
        except urllib.error.HTTPError:
            break
        df_csv_raw = pd.concat([df_csv_raw, df], ignore_index=True)

    # Load old csv dataframe from cached data
    # try:
    #     df_csv_old = pd.read_csv(cache_file)
    # except FileNotFoundError:
    #     df_csv_old = pd.DataFrame(columns=df_csv_raw.columns)

    # Create a copy for processing with standardized names
    df_csv_standardized = df_csv_raw.copy()

    # Load and apply the title mappings
    _, known_mappings = load_title_mappings(reverse=True)
    df_csv_standardized["conference"] = (
        df_csv_standardized["conference"]
        .replace(re.compile(r"\b\s+(19|20)\d{2}\s*\b"), "", regex=True)
        .replace(known_mappings)
    )

    # Store the new csv dataframe to cache (with original names)
    df_cache = df_csv_raw.copy()

    # Get the difference between the old and new dataframes
    # _ = pd.concat([df_csv_old, df_csv_raw]).drop_duplicates(keep=False)

    # Deduplicate the new dataframe (with standardized names for merging)
    df_csv_for_merge = deduplicate(df_csv_standardized, "conference")

    if df_csv_for_merge.empty:
        print("No new conferences found in Python organiser source.")
        return

    # Process year by year
    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        if df_csv_for_merge.loc[df_csv_for_merge["year"] == y].empty or df_yml[df_yml["year"] == y].empty:
            # Concatenate the new data with the existing data
            df_new = pd.concat(
                [df_new, df_yml[df_yml["year"] == y], df_csv_for_merge.loc[df_csv_for_merge["year"] == y]],
                ignore_index=True,
            )
            continue

        logger.info(f"Processing year {y} merge operations")
        df_yml_year = df_yml[df_yml["year"] == y]
        df_csv_year = df_csv_for_merge.loc[df_csv_for_merge["year"] == y]
        logger.debug(f"Year {y}: df_yml_year shape: {df_yml_year.shape}, df_csv_year shape: {df_csv_year.shape}")

        df_merged, df_remote = fuzzy_match(df_yml_year, df_csv_year)
        logger.info(f"Fuzzy match completed for year {y}. df_merged shape: {df_merged.shape}")

        df_merged["year"] = y
        df_merged = df_merged.drop(["conference"], axis=1)
        logger.debug(f"After dropping conference column: {df_merged.shape}")

        df_merged = deduplicate(df_merged)
        df_remote = deduplicate(df_remote)
        logger.debug(f"After deduplication - df_merged: {df_merged.shape}, df_remote: {df_remote.shape}")

        df_merged = merge_conferences(df_merged, df_remote)
        logger.info(f"Merge conferences completed for year {y}. Final shape: {df_merged.shape}")

        df_new = pd.concat([df_new, df_merged], ignore_index=True)

    # Fill in missing required fields
    df_new = fill_missing_required(df_new)

    # Write the new data to the YAML file
    write_df_yaml(df_new, target_file)

    # Prepare CSV output with original names
    df_csv_output = df_csv_raw.copy()

    # Map from the standardized data back to original
    mapping_dict = {}
    for idx, row in df_csv_raw.iterrows():
        standardized_conf = re.sub(r"\b\s+(19|20)\d{2}\s*\b", "", row["conference"])
        if standardized_conf in known_mappings:
            standardized_conf = known_mappings[standardized_conf]
        mapping_key = (standardized_conf, row["year"])
        mapping_dict[mapping_key] = idx

    # Update the CSV output with information from the merged data
    for _, row in df_new.iterrows():
        key = (row["conference"], row["year"])
        if key in mapping_dict:
            original_idx = mapping_dict[key]
            # Update only fields that were potentially enriched during merge
            for col in ["start", "end", "cfp", "link", "cfp_link", "sponsor", "finaid"]:
                if col in row and pd.notna(row[col]):
                    df_csv_output.at[original_idx, col] = row[col]

    # Write the CSV with original names
    df_csv_output.loc[:, "Location"] = df_csv_output.place
    try:
        df_csv_output.loc[:, "Country"] = (
            df_csv_output.place.str.split(",")
            .str[-1]
            .str.strip()
            .apply(lambda x: iso3166.countries_by_name.get(x.upper(), iso3166.Country("", "", "", "", "")).alpha3)
        )
    except AttributeError as e:
        df_csv_output.loc[:, "Country"] = ""
        print(f"Error: Country iso3 not found for {df_csv_output.place} - {e}")

    write_csv(df_csv_output, year, csv_location)

    # Save the new dataframe to cache
    df_cache.to_csv(cache_file, index=False)


if __name__ == "__main__":
    # Make argparse to get year and base

    import argparse

    parser = argparse.ArgumentParser(description="Import Python Organizers")
    parser.add_argument("--year", type=int, help="Year to import")

    main(year=parser.parse_args().year)
