import contextlib
import logging
from collections import defaultdict

import pandas as pd
from thefuzz import process

try:
    from tidy_conf.schema import get_schema
    from tidy_conf.titles import tidy_df_names
    from tidy_conf.utils import query_yes_no
    from tidy_conf.yaml import load_title_mappings
    from tidy_conf.yaml import update_title_mappings
except ImportError:
    from .schema import get_schema
    from .titles import tidy_df_names
    from .utils import query_yes_no
    from .yaml import load_title_mappings
    from .yaml import update_title_mappings


def fuzzy_match(df_yml, df_remote):
    """Fuzzy merge conferences from two pandas dataframes on title.

    Loads known mappings from a YAML file and uses them to harmonise conference titles.
    Updates those when we find a Fuzzy match.

    Keeps temporary track of rejections to avoid asking the same question multiple
    times.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting fuzzy_match with df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}")

    df_yml = tidy_df_names(df_yml)
    df_remote = tidy_df_names(df_remote)

    logger.debug(f"After tidy_df_names - df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}")
    logger.debug(f"df_yml columns: {df_yml.columns.tolist()}")
    logger.debug(f"df_remote columns: {df_remote.columns.tolist()}")

    _, known_rejections = load_title_mappings(path="utils/tidy_conf/data/.tmp/rejections.yml")

    new_mappings = defaultdict(list)
    new_rejections = defaultdict(list)

    # Set index for remote dataframe
    df_remote = df_remote.set_index("conference", drop=False)
    df_remote.index.rename("title_match", inplace=True)

    df = df_yml.copy()

    # Get closest match for titles
    df["title_match"] = df["conference"].apply(
        lambda x: process.extract(x, df_remote["conference"], limit=1),
    )

    # Process matches
    for i, row in df.iterrows():
        if isinstance(row["title_match"], str):
            continue
        if not row["title_match"]:
            continue

        title, prob, _ = row["title_match"][0]
        if prob == 100:
            df.at[i, "title_match"] = title
        elif prob >= 90:
            if (title in known_rejections and i in known_rejections[title]) or (
                i in known_rejections and title in known_rejections[i]
            ):
                df.at[i, "title_match"] = i
            else:
                if not query_yes_no(f"Do '{row['conference']}' and '{title}' match? (y/n): "):
                    new_rejections[title].append(i)
                    new_rejections[i].append(title)
                    df.at[i, "title_match"] = i
                else:
                    new_mappings[i].append(title)
                    df.at[i, "title_match"] = title
        else:
            df.at[i, "title_match"] = i

    # Update mappings and rejections
    update_title_mappings(new_mappings)
    update_title_mappings(new_rejections, path="utils/tidy_conf/data/.tmp/rejections.yml")

    # Ensure all title_match values are strings (not lists from process.extract)
    for i, row in df.iterrows():
        if not isinstance(row["title_match"], str):
            df.at[i, "title_match"] = str(i)
            logger.debug(f"Converted title_match[{i}] to string: {df.at[i, 'title_match']}")

    # Combine dataframes
    logger.info("Combining dataframes using title_match index")
    df.set_index("title_match", inplace=True)
    logger.debug(f"df index after set_index: {df.index.tolist()[:5]}...")

    df_new = df.combine_first(df_remote)
    logger.info(f"Combined dataframe shape: {df_new.shape}")
    logger.debug(f"df_new index: {df_new.index.tolist()[:5]}...")

    # Validate that the index contains actual conference names, not integers
    integer_indices = [idx for idx in df_new.index if isinstance(idx, int)]
    if integer_indices:
        logger.warning(f"Found {len(integer_indices)} integer indices in df_new: {integer_indices[:5]}...")

    # Fill missing CFPs with "TBA"
    df_new.loc[df_new["cfp"].isna(), "cfp"] = "TBA"

    logger.info("fuzzy_match completed successfully")
    return df_new, df_remote


def merge_conferences(df_yml, df_remote):
    """Merge two dataframes on title and interactively resolve conflicts."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting merge_conferences with df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}")

    # Data validation before merge
    logger.debug(f"df_yml columns: {df_yml.columns.tolist()}")
    logger.debug(f"df_remote columns: {df_remote.columns.tolist()}")
    logger.debug(f"df_yml index: {df_yml.index.tolist()[:5]}...")  # Show first 5 indices
    logger.debug(f"df_remote index: {df_remote.index.tolist()[:5]}...")

    df_new = get_schema()
    columns = df_new.columns.tolist()
    logger.debug(f"Schema columns: {columns}")

    with contextlib.suppress(KeyError):
        logger.debug("Dropping 'conference' column from df_yml")
        df_yml = df_yml.drop(["conference"], axis=1)
    with contextlib.suppress(KeyError):
        logger.debug("Dropping 'conference' column from df_remote")
        df_remote = df_remote.drop(["conference"], axis=1)

    replacements = {
        "United States of America": "USA",
        "United Kingdom": "UK",
        "Czech Republic": "Czechia",
    }

    logger.info("Performing pandas merge on 'title_match'")
    df_merge = pd.merge(left=df_yml, right=df_remote, how="outer", on="title_match", validate="one_to_one")
    logger.info(f"Merge completed. df_merge shape: {df_merge.shape}")
    logger.debug(f"df_merge columns: {df_merge.columns.tolist()}")
    logger.debug(f"df_merge index: {df_merge.index.tolist()[:5]}...")

    for i, row in df_merge.iterrows():
        # Use the actual conference name from title_match index, not the row index
        conference_name = df_merge.index.name if hasattr(df_merge.index, "name") and df_merge.index.name else i
        if hasattr(row, "name") and row.name:
            conference_name = row.name
            logger.debug(f"Using row.name for conference: {conference_name}")
        elif "title_match" in row and pd.notna(row["title_match"]):
            conference_name = row["title_match"]
            logger.debug(f"Using title_match for conference: {conference_name}")
        else:
            logger.warning(f"Falling back to index {i} for conference name")
            conference_name = i

        # Validate conference name is a string
        if not isinstance(conference_name, str):
            logger.error(f"Conference name is not a string: {type(conference_name)} = {conference_name}")
            conference_name = str(conference_name)

        df_new.loc[i, "conference"] = conference_name
        logger.debug(f"Set conference[{i}] = {conference_name}")
        for column in columns:
            cx, cy = column + "_x", column + "_y"
            # print(i,cx,cy,cx in df_merge.columns and cy in df_merge.columns,column in df_merge.columns,)
            if cx in df_merge.columns and cy in df_merge.columns:
                rx, ry = row[cx], row[cy]
                for orig, replacement in replacements.items():
                    if isinstance(rx, str):
                        rx = rx.replace(orig, replacement)
                    if isinstance(ry, str):
                        ry = ry.replace(orig, replacement)
                # Prefer my sponsor info if exists
                if column == "sponsor" and not pd.isnull(rx):
                    ry = rx
                # Some text processing
                if isinstance(rx, str) and isinstance(ry, str):
                    # Remove whitespaces
                    rx, ry = str.strip(rx), str.strip(ry)
                    # Look at strings with extra information
                    if rx.split(" ")[0] == ry.split(" ")[0] and rx.split(" ")[-1] == ry.split(" ")[-1]:
                        if len(ry) > len(rx):
                            df_new.loc[i, column] = rx
                            ry = rx
                        else:
                            df_new.loc[i, column] = ry
                            rx = ry
                    # Partial strings such as CFP
                    if rx.startswith(ry):
                        ry = rx
                    elif ry.startswith(rx):
                        rx = ry
                    if rx.endswith(ry):
                        rx = ry
                    elif ry.endswith(rx):
                        ry = rx
                if rx == ry:
                    # When both are equal just assign
                    df_new.loc[i, column] = rx
                elif pd.isnull(rx) and ry:
                    # If one is empty use the other
                    df_new.loc[i, column] = ry
                elif rx and pd.isnull(ry):
                    # If one is empty use the other
                    df_new.loc[i, column] = rx
                elif type(rx) != type(ry):
                    # Use non-string on different types
                    if str(rx).strip() == str(ry).strip():
                        if isinstance(rx, str):
                            df_new.loc[i, column] = ry
                            rx = ry
                        elif isinstance(ry, str):
                            df_new.loc[i, column] = rx
                            ry = rx
                    else:
                        if query_yes_no(f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?"):
                            df_new.loc[i, column] = ry
                        else:
                            df_new.loc[i, column] = rx
                elif column == "cfp_ext":
                    # Skip cfp_ext
                    continue
                elif column == "cfp" and rx != ry:
                    if "TBA" in rx:
                        df_new.loc[i, column] = ry
                    elif "TBA" in ry:
                        df_new.loc[i, column] = rx
                    else:
                        # Extract a time signature from the cfp
                        cfp_time_x = cfp_time_y = ""
                        if " " in rx and " " not in ry:
                            cfp_time_y = " " + rx.split(" ")[1]
                        elif " " not in rx and " " in ry:
                            cfp_time_x = " " + ry.split(" ")[1]

                        # Check if the cfp_ext is the same and if so update the cfp
                        if rx + cfp_time_x == row["cfp_ext_x"]:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if ry + cfp_time_y == row["cfp_ext_y"]:
                            df_new.loc[i, "cfp"] = rx + cfp_time_x
                            df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                            continue
                        if rx + cfp_time_x == row["cfp_ext_y"]:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if ry + cfp_time_y == row["cfp_ext_x"]:
                            df_new.loc[i, "cfp"] = rx + cfp_time_x
                            df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                            continue
                        # Give a choice
                        if query_yes_no(
                            (
                                f"For {i} in column '{column}' would you prefer "
                                f"'{ry + cfp_time_y}' or keep '{rx + cfp_time_x}'?"
                            ),
                        ):
                            df_new.loc[i, column] = ry + cfp_time_y
                        else:
                            # Check if it's an extension of the deadline and update both
                            if query_yes_no("Is this an extension?"):
                                rrx, rry = int(rx.replace("-", "").split(" ")[0]), int(
                                    ry.replace("-", "").split(" ")[0],
                                )
                                if rrx < rry:
                                    df_new.loc[i, "cfp"] = rx + cfp_time_x
                                    df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                                else:
                                    df_new.loc[i, "cfp"] = ry + cfp_time_y
                                    df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            else:
                                df_new.loc[i, column] = rx + cfp_time_x
                elif column == "place" and rx != ry:
                    # Special Place stuff
                    rxx = ", ".join((rx.split(",")[0].strip(), rx.split(",")[-1].strip())) if "," in rx else rx
                    ryy = ", ".join((ry.split(",")[0].strip(), ry.split(",")[-1].strip())) if "," in ry else ry

                    # Chill on the TBA
                    if rxx == ryy or rxx in ["TBD", "TBA", "None"]:
                        df_new.loc[i, column] = ryy
                    elif ryy in ["TBD", "TBA", "None"]:
                        df_new.loc[i, column] = rxx
                    elif rx in ry:
                        # If one is a substring of the other use the longer one
                        df_new.loc[i, column] = ry
                    elif ry in rx:
                        df_new.loc[i, column] = rx
                    elif rxx in ryy:
                        df_new.loc[i, column] = ryy
                    elif ryy in rxx:
                        df_new.loc[i, column] = rxx
                    else:
                        if query_yes_no(f"For {i} in column '{column}' would you prefer '{ryy}' or keep '{rxx}'?"):
                            df_new.loc[i, column] = ryy
                        else:
                            df_new.loc[i, column] = rxx
                else:
                    # For everything else give a choice
                    if query_yes_no(f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?"):
                        df_new.loc[i, column] = ry
                    else:
                        df_new.loc[i, column] = rx
            elif column in df_merge.columns:
                # Sorry for this code, it's the new Pandas "non-empty merge" stuff...
                df_new[column] = (
                    df_new[column].copy()
                    if df_merge[column].empty
                    else (
                        df_merge[column].copy()
                        if df_new[column].empty
                        else df_new[column].combine_first(df_merge[column])
                    )
                )

    # Fill in missing CFPs with TBA
    df_new.loc[df_new.cfp.isna(), "cfp"] = "TBA"

    # Final validation before returning
    logger.info(f"Merge completed. Final df_new shape: {df_new.shape}")
    logger.debug(f"Final df_new columns: {df_new.columns.tolist()}")

    # Validate conference names
    invalid_conferences = df_new[~df_new["conference"].apply(lambda x: isinstance(x, str) and len(str(x).strip()) > 0)]
    if not invalid_conferences.empty:
        logger.error(f"Found {len(invalid_conferences)} rows with invalid conference names:")
        for idx, row in invalid_conferences.iterrows():
            logger.error(f"  Row {idx}: conference = {row['conference']} (type: {type(row['conference'])})")

    # Check for null conference names
    null_conferences = df_new[df_new["conference"].isna()]
    if not null_conferences.empty:
        logger.error(f"Found {len(null_conferences)} rows with null conference names")

    logger.info("Merge validation completed")
    return df_new
