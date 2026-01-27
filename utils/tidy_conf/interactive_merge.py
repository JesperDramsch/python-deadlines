"""Interactive merge module for conference data synchronization.

Merge Strategy:
- YAML is the source of truth for existing conferences
- Remote data (CSV/ICS) enriches YAML with new information
- Conflicts are resolved by preferring YAML values, with user prompts for ambiguous cases
- All operations are logged to MergeReport for tracking and debugging
"""

import contextlib
import logging
from collections import defaultdict

import pandas as pd
from thefuzz import fuzz
from thefuzz import process

try:
    from tidy_conf.countries import COUNTRY_NORMALIZATION
    from tidy_conf.countries import PLACE_COUNTRY_NORMALIZATION
    from tidy_conf.countries import normalize_place
    from tidy_conf.schema import get_schema
    from tidy_conf.titles import tidy_df_names
    from tidy_conf.utils import query_yes_no
    from tidy_conf.validation import MergeRecord
    from tidy_conf.validation import MergeReport
    from tidy_conf.validation import ensure_conference_strings
    from tidy_conf.validation import log_dataframe_state
    from tidy_conf.validation import validate_merge_inputs
    from tidy_conf.yaml import load_title_mappings
    from tidy_conf.yaml import update_title_mappings
except ImportError:
    from .countries import COUNTRY_NORMALIZATION
    from .countries import normalize_place
    from .schema import get_schema
    from .titles import tidy_df_names
    from .utils import query_yes_no
    from .validation import MergeRecord
    from .validation import MergeReport
    from .validation import ensure_conference_strings
    from .validation import log_dataframe_state
    from .validation import validate_merge_inputs
    from .yaml import load_title_mappings
    from .yaml import update_title_mappings

# Configuration for fuzzy matching
FUZZY_MATCH_THRESHOLD = 90  # Minimum score to consider a fuzzy match
EXACT_MATCH_THRESHOLD = 100  # Score for exact matches

# Merge strategy configuration
MERGE_STRATEGY = {
    "source_of_truth": "yaml",  # YAML is authoritative for existing data
    "remote_enriches": True,  # Remote data can add new fields
    "prefer_non_tba": True,  # Prefer actual values over TBA/TBD
    "log_conflicts": True,  # Log all conflict resolutions
}


def is_placeholder_value(value) -> bool:
    """Check if a value is a placeholder (TBA, TBD, None, empty).

    Parameters
    ----------
    value : Any
        Value to check for placeholder status

    Returns
    -------
    bool
        True if value is a placeholder, False otherwise
    """
    if pd.isna(value):
        return True
    if not isinstance(value, str):
        return False
    stripped = str(value).strip().upper()
    return stripped in ("TBA", "TBD", "NONE", "N/A", "") or not stripped


def resolve_conflict(
    yaml_val,
    remote_val,
    column: str,
    conference: str,
    logger,
) -> tuple:
    """Resolve a conflict between YAML and remote values.

    Strategy:
    1. If one is a placeholder, use the other
    2. If YAML has a value, prefer it (source of truth)
    3. Log the resolution for debugging

    Parameters
    ----------
    yaml_val : Any
        Value from YAML source (source of truth)
    remote_val : Any
        Value from remote source (CSV/ICS)
    column : str
        Column name where conflict occurs
    conference : str
        Conference name for logging
    logger : logging.Logger
        Logger instance for debug output

    Returns
    -------
    tuple[Any, str]
        (resolved value, resolution reason)
    """
    yaml_is_placeholder = is_placeholder_value(yaml_val)
    remote_is_placeholder = is_placeholder_value(remote_val)

    # If both are placeholders, use YAML (source of truth)
    if yaml_is_placeholder and remote_is_placeholder:
        return yaml_val, "both_placeholder"

    # If YAML is placeholder but remote has value, use remote
    if yaml_is_placeholder and not remote_is_placeholder:
        if MERGE_STRATEGY["log_conflicts"]:
            logger.debug(
                f"Conflict [{conference}][{column}]: Using remote '{remote_val}' (YAML was placeholder)",
            )
        return remote_val, "yaml_placeholder"

    # If remote is placeholder but YAML has value, use YAML
    if not yaml_is_placeholder and remote_is_placeholder:
        return yaml_val, "remote_placeholder"

    # Both have values - prefer YAML as source of truth
    if yaml_val == remote_val:
        return yaml_val, "equal"

    # Values differ - log and use YAML (or prompt user)
    if MERGE_STRATEGY["log_conflicts"]:
        logger.info(
            f"Conflict [{conference}][{column}]: YAML='{yaml_val}' vs Remote='{remote_val}' -> keeping YAML",
        )
    return yaml_val, "yaml_preferred"


def conference_scorer(s1: str, s2: str) -> int:
    """Custom scorer optimized for conference name matching.

    Uses a combination of scoring strategies:
    1. token_sort_ratio: Good for same words in different order
    2. token_set_ratio: Good when one name has extra words
    3. partial_ratio: Good for substring matches

    Parameters
    ----------
    s1 : str
        First conference name to compare
    s2 : str
        Second conference name to compare

    Returns
    -------
    int
        Maximum similarity score from all strategies (0-100)
    """
    # Normalize case for comparison
    s1_lower = s1.lower().strip()
    s2_lower = s2.lower().strip()

    # Calculate different similarity scores
    scores = [
        fuzz.token_sort_ratio(s1_lower, s2_lower),
        fuzz.token_set_ratio(s1_lower, s2_lower),
        fuzz.ratio(s1_lower, s2_lower),
    ]

    # For short names, also try partial matching
    if len(s1_lower) < 20 or len(s2_lower) < 20:
        scores.append(fuzz.partial_ratio(s1_lower, s2_lower))

    return max(scores)


def fuzzy_match(
    df_yml: pd.DataFrame,
    df_remote: pd.DataFrame,
    report: MergeReport | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, MergeReport]:
    """Fuzzy merge conferences from two pandas dataframes on title.

    Loads known mappings from a YAML file and uses them to harmonise conference titles.
    Updates those when we find a Fuzzy match.

    Keeps temporary track of rejections to avoid asking the same question multiple
    times. Also respects explicit exclusions from titles.yml to prevent known
    false-positive matches (e.g., PyCon Austria vs PyCon Australia).

    Parameters
    ----------
    df_yml : pd.DataFrame
        YAML source DataFrame (source of truth)
    df_remote : pd.DataFrame
        Remote source DataFrame (CSV or ICS)
    report : MergeReport, optional
        Merge report for tracking operations

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame, MergeReport]
        (merged DataFrame, remote DataFrame, merge report)
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"Starting fuzzy_match with df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}",
    )

    # Initialize or update merge report
    if report is None:
        report = MergeReport()

    # Validate inputs before proceeding
    inputs_valid, report = validate_merge_inputs(df_yml, df_remote, report)
    if not inputs_valid:
        logger.warning("Input validation failed, attempting to continue with warnings")
        # Don't raise - try to continue and track issues

    # Ensure conference names are strings
    df_yml = ensure_conference_strings(df_yml, "YAML")
    df_remote = ensure_conference_strings(df_remote, "Remote")

    # Tidy conference names
    df_yml = tidy_df_names(df_yml)
    df_remote = tidy_df_names(df_remote)

    # Log state after tidying
    log_dataframe_state(df_yml, "df_yml after tidy_df_names")
    log_dataframe_state(df_remote, "df_remote after tidy_df_names")

    logger.debug(
        f"After tidy_df_names - df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}",
    )
    logger.debug(f"df_yml columns: {df_yml.columns.tolist()}")
    logger.debug(f"df_remote columns: {df_remote.columns.tolist()}")

    # Load rejections (pairs that should never match)
    _, known_rejections = load_title_mappings(
        path="utils/tidy_conf/data/rejections.yml",
    )

    # Convert rejections to frozenset pairs for fast lookup
    # Format: {name1: {variations: [name2, name3]}, ...}
    all_exclusions = set()
    for name1, data in known_rejections.items():
        variations = data.get("variations", []) if isinstance(data, dict) else []
        all_exclusions.update(frozenset([name1, name2]) for name2 in variations)

    logger.debug(f"Loaded {len(all_exclusions)} rejection pairs from rejections.yml")

    new_mappings = defaultdict(list)
    new_rejections = defaultdict(list)

    # Set index for remote dataframe
    df_remote = df_remote.set_index("conference", drop=False)
    df_remote.index.rename("title_match", inplace=True)

    df = df_yml.copy()

    # Get closest match for titles using our custom scorer
    df["title_match"] = df["conference"].apply(
        lambda x: process.extract(
            x,
            df_remote["conference"],
            scorer=conference_scorer,
            limit=1,
        ),
    )

    # Helper function to check if a pair is excluded (permanent or session-based)
    def is_excluded(name1, name2):
        """Check if two conference names are in the combined exclusion list."""
        return frozenset([name1, name2]) in all_exclusions

    # Process matches and track in report
    for i, row in df.iterrows():
        if isinstance(row["title_match"], str):
            continue
        if not row["title_match"]:
            continue

        # Handle both 2-tuple and 3-tuple results from process.extract
        match_result = row["title_match"][0]
        if len(match_result) == 3:
            title, prob, _ = match_result
        else:
            title, prob = match_result

        conference_name = row["conference"]
        year = row.get("year", 0)

        # Create merge record for tracking
        record = MergeRecord(
            yaml_name=conference_name,
            remote_name=title,
            match_score=prob,
            match_type="pending",
            action="pending",
            year=int(year) if pd.notna(year) else 0,
        )

        # Check if this pair is excluded (either permanent from titles.yml or session-based)
        if is_excluded(conference_name, title):
            logger.info(
                f"Excluded match: '{conference_name}' and '{title}' are in exclusion list",
            )
            df.at[i, "title_match"] = conference_name  # Use original name, not index
            record.match_type = "excluded"
            record.action = "kept_yaml"
        elif prob >= EXACT_MATCH_THRESHOLD:
            logger.debug(
                f"Exact match: '{conference_name}' -> '{title}' (score: {prob})",
            )
            df.at[i, "title_match"] = title
            record.match_type = "exact"
            record.action = "merged"
        elif prob >= FUZZY_MATCH_THRESHOLD:
            # Prompt user for fuzzy matches that aren't excluded
            logger.info(
                f"Fuzzy match candidate: '{conference_name}' -> '{title}' (score: {prob})",
            )
            if not query_yes_no(
                f"Do '{row['conference']}' and '{title}' match? (y/n): ",
            ):
                new_rejections[title].append(conference_name)
                new_rejections[conference_name].append(title)
                df.at[i, "title_match"] = conference_name  # Use original name, not index
                record.match_type = "fuzzy"
                record.action = "kept_yaml"
            else:
                new_mappings[conference_name].append(title)
                df.at[i, "title_match"] = title
                record.match_type = "fuzzy"
                record.action = "merged"
        else:
            logger.debug(
                f"No match: '{conference_name}' (best: '{title}', score: {prob})",
            )
            df.at[i, "title_match"] = conference_name  # Use original name, not index
            record.match_type = "no_match"
            record.action = "kept_yaml"

        # Add record to report
        report.add_record(record)

    # Update mappings and rejections
    update_title_mappings(new_mappings)
    update_title_mappings(new_rejections, path="utils/tidy_conf/data/rejections.yml")

    # Ensure all title_match values are strings (not lists from process.extract)
    for i, row in df.iterrows():
        if not isinstance(row["title_match"], str):
            # Fall back to original conference name
            original_name = row.get("conference", str(i))
            df.at[i, "title_match"] = original_name if isinstance(original_name, str) else str(i)
            logger.debug(
                f"Converted title_match[{i}] to string: {df.at[i, 'title_match']}",
            )

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
        logger.warning(
            f"Found {len(integer_indices)} integer indices in df_new: {integer_indices[:5]}...",
        )

    # Fill missing CFPs with "TBA"
    df_new.loc[df_new["cfp"].isna(), "cfp"] = "TBA"

    # Update report with final counts
    report.total_output = len(df_new)

    # Check for data loss
    if not report.validate_no_data_loss():
        logger.warning("Potential data loss detected - check merge report for details")

    logger.info("fuzzy_match completed successfully")
    logger.info(
        f"Merge summary: {report.exact_matches} exact, {report.fuzzy_matches} fuzzy, "
        f"{report.excluded_matches} excluded, {report.no_matches} no match",
    )

    return df_new, df_remote, report


def merge_conferences(
    df_yml: pd.DataFrame,
    df_remote: pd.DataFrame,
    report: MergeReport | None = None,
) -> pd.DataFrame:
    """Merge two dataframes on title and interactively resolve conflicts.

    Merge Strategy (defined by MERGE_STRATEGY):
    - YAML is the source of truth for existing conferences
    - Remote data enriches YAML with new or missing information
    - Non-TBA values are preferred over TBA/TBD placeholders
    - Conflicts are logged and can be resolved interactively

    Parameters
    ----------
    df_yml : pd.DataFrame
        YAML source DataFrame (source of truth)
    df_remote : pd.DataFrame
        Remote source DataFrame
    report : MergeReport, optional
        Merge report for tracking operations

    Returns
    -------
    pd.DataFrame
        Merged DataFrame
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"Starting merge_conferences with df_yml shape: {df_yml.shape}, df_remote shape: {df_remote.shape}",
    )

    # Initialize report if not provided
    if report is None:
        report = MergeReport()
        report.source_yaml_count = len(df_yml)
        report.source_remote_count = len(df_remote)

    # Data validation before merge
    logger.debug(f"df_yml columns: {df_yml.columns.tolist()}")
    logger.debug(f"df_remote columns: {df_remote.columns.tolist()}")
    logger.debug(
        f"df_yml index: {df_yml.index.tolist()[:5]}...",
    )  # Show first 5 indices
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

    # Use centralized country normalization mappings
    # This ensures consistency with the rest of the codebase
    # Note: For place fields, we use normalize_place() which uses PLACE_COUNTRY_NORMALIZATION
    # For other fields, we use COUNTRY_NORMALIZATION (substring replacement)
    replacements = COUNTRY_NORMALIZATION

    logger.info("Performing pandas merge on 'title_match'")
    df_merge = pd.merge(
        left=df_yml,
        right=df_remote,
        how="outer",
        on="title_match",
        validate="one_to_one",
    )
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
            logger.error(
                f"Conference name is not a string: {type(conference_name)} = {conference_name}",
            )
            conference_name = str(conference_name)

        df_new.loc[i, "conference"] = conference_name
        logger.debug(f"Set conference[{i}] = {conference_name}")
        for column in columns:
            cx, cy = column + "_x", column + "_y"
            # print(i,cx,cy,cx in df_merge.columns and cy in df_merge.columns,column in df_merge.columns,)
            if cx in df_merge.columns and cy in df_merge.columns:
                rx, ry = row[cx], row[cy]
                # For place fields, use the dedicated normalize_place function
                # This prevents the "US of America" bug (substring replacement issues)
                if column == "place":
                    if isinstance(rx, str):
                        rx = normalize_place(rx)
                    if isinstance(ry, str):
                        ry = normalize_place(ry)
                else:
                    # For other columns, use substring replacement
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
                elif type(rx) is not type(ry):
                    # Use non-string on different types
                    if str(rx).strip() == str(ry).strip():
                        if isinstance(rx, str):
                            df_new.loc[i, column] = ry
                            rx = ry
                        elif isinstance(ry, str):
                            df_new.loc[i, column] = rx
                            ry = rx
                    else:
                        if query_yes_no(
                            f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?",
                        ):
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

                        # Check if the cfp_ext columns exist before accessing them
                        # These columns may not exist if one dataframe doesn't have cfp_ext
                        cfp_ext_x = row.get("cfp_ext_x") if "cfp_ext_x" in row.index else None
                        cfp_ext_y = row.get("cfp_ext_y") if "cfp_ext_y" in row.index else None

                        # Check if the cfp_ext is the same and if so update the cfp
                        if cfp_ext_x is not None and rx + cfp_time_x == cfp_ext_x:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if cfp_ext_y is not None and ry + cfp_time_y == cfp_ext_y:
                            df_new.loc[i, "cfp"] = rx + cfp_time_x
                            df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                            continue
                        if cfp_ext_y is not None and rx + cfp_time_x == cfp_ext_y:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if cfp_ext_x is not None and ry + cfp_time_y == cfp_ext_x:
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
                        if query_yes_no(
                            f"For {i} in column '{column}' would you prefer '{ryy}' or keep '{rxx}'?",
                        ):
                            df_new.loc[i, column] = ryy
                        else:
                            df_new.loc[i, column] = rxx
                else:
                    # For everything else give a choice
                    if query_yes_no(
                        f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?",
                    ):
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
    invalid_conferences = df_new[
        ~df_new["conference"].apply(
            lambda x: isinstance(x, str) and len(str(x).strip()) > 0,
        )
    ]
    if not invalid_conferences.empty:
        logger.error(
            f"Found {len(invalid_conferences)} rows with invalid conference names:",
        )
        for idx, row in invalid_conferences.iterrows():
            logger.error(
                f"  Row {idx}: conference = {row['conference']} (type: {type(row['conference'])})",
            )

    # Check for null conference names
    null_conferences = df_new[df_new["conference"].isna()]
    if not null_conferences.empty:
        logger.error(f"Found {len(null_conferences)} rows with null conference names")

    logger.info("Merge validation completed")
    return df_new
