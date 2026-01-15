"""Input validation and merge tracking for conference data sync pipeline.

This module provides:
1. Input validation for DataFrames before merging
2. MergeReport class for tracking all merge operations
3. Clear error messages when data is malformed
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Required columns for conference data
REQUIRED_COLUMNS = ["conference", "year", "start", "end"]
OPTIONAL_COLUMNS = [
    "link",
    "cfp",
    "cfp_ext",
    "cfp_link",
    "place",
    "sub",
    "sponsor",
    "finaid",
    "tutorial_deadline",
    "workshop_deadline",
    "timezone",
    "alt_name",
    "note",
    "twitter",
    "mastodon",
    "bluesky",
    "location",
    "extra_places",
]
ALL_KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


@dataclass
class MergeRecord:
    """Record of a single merge operation."""

    yaml_name: str
    remote_name: str
    match_score: int
    match_type: str  # "exact", "fuzzy", "excluded", "no_match"
    action: str  # "merged", "kept_yaml", "kept_remote", "dropped"
    year: int
    before_values: dict = field(default_factory=dict)
    after_values: dict = field(default_factory=dict)
    conflict_resolutions: list = field(default_factory=list)


@dataclass
class MergeReport:
    """Comprehensive report of all merge operations.

    This class tracks:
    - All match attempts (successful and failed)
    - Data preservation (nothing silently dropped)
    - Conflict resolutions
    - Before/after states
    """

    source_yaml_count: int = 0
    source_remote_count: int = 0
    exact_matches: int = 0
    fuzzy_matches: int = 0
    excluded_matches: int = 0
    no_matches: int = 0
    total_output: int = 0
    records: list = field(default_factory=list)
    dropped_conferences: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def add_record(self, record: MergeRecord) -> None:
        """Add a merge record and update counters."""
        self.records.append(record)

        if record.match_type == "exact":
            self.exact_matches += 1
        elif record.match_type == "fuzzy":
            self.fuzzy_matches += 1
        elif record.match_type == "excluded":
            self.excluded_matches += 1
        elif record.match_type == "no_match":
            self.no_matches += 1

        if record.action == "dropped":
            self.dropped_conferences.append(
                {"yaml_name": record.yaml_name, "remote_name": record.remote_name, "year": record.year}
            )

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(message)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        logger.error(message)

    def summary(self) -> str:
        """Generate a summary of the merge operation."""
        lines = [
            "=" * 60,
            "MERGE REPORT SUMMARY",
            "=" * 60,
            f"Input YAML conferences:    {self.source_yaml_count}",
            f"Input Remote conferences:  {self.source_remote_count}",
            "-" * 60,
            f"Exact matches:             {self.exact_matches}",
            f"Fuzzy matches:             {self.fuzzy_matches}",
            f"Excluded (false positive): {self.excluded_matches}",
            f"No matches:                {self.no_matches}",
            "-" * 60,
            f"Total output conferences:  {self.total_output}",
            f"Dropped conferences:       {len(self.dropped_conferences)}",
            f"Warnings:                  {len(self.warnings)}",
            f"Errors:                    {len(self.errors)}",
            "=" * 60,
        ]

        if self.dropped_conferences:
            lines.append("\nDROPPED CONFERENCES (DATA LOSS):")
            for dropped in self.dropped_conferences:
                lines.append(f"  - {dropped['yaml_name']} / {dropped['remote_name']} ({dropped['year']})")

        if self.warnings:
            lines.append("\nWARNINGS:")
            for warning in self.warnings[:10]:  # Show first 10
                lines.append(f"  - {warning}")
            if len(self.warnings) > 10:
                lines.append(f"  ... and {len(self.warnings) - 10} more warnings")

        if self.errors:
            lines.append("\nERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)

    def validate_no_data_loss(self) -> bool:
        """Check that no conferences were silently dropped.

        Returns True if all input conferences are accounted for in output.
        """
        expected_total = max(self.source_yaml_count, self.source_remote_count)
        if self.total_output < expected_total:
            self.add_error(
                f"Data loss detected: expected at least {expected_total} conferences, "
                f"got {self.total_output}. {len(self.dropped_conferences)} dropped."
            )
            return False
        return True


def validate_dataframe(
    df: pd.DataFrame, source_name: str, required_columns: Optional[list] = None
) -> tuple[bool, list[str]]:
    """Validate a DataFrame has expected columns and data types.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate
    source_name : str
        Name of the data source (for error messages)
    required_columns : list, optional
        List of required column names. Defaults to REQUIRED_COLUMNS

    Returns
    -------
    tuple[bool, list[str]]
        (is_valid, list of error messages)
    """
    errors = []
    if required_columns is None:
        required_columns = REQUIRED_COLUMNS

    # Check if DataFrame is empty
    if df is None:
        errors.append(f"{source_name}: DataFrame is None")
        return False, errors

    if df.empty:
        errors.append(f"{source_name}: DataFrame is empty")
        return False, errors

    # Check required columns exist
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"{source_name}: Missing required columns: {missing_columns}")
        errors.append(f"{source_name}: Available columns: {df.columns.tolist()}")

    # Check 'conference' column data type
    if "conference" in df.columns:
        non_string_conferences = df[~df["conference"].apply(lambda x: isinstance(x, str))]
        if not non_string_conferences.empty:
            errors.append(
                f"{source_name}: {len(non_string_conferences)} conference names are not strings: "
                f"{non_string_conferences['conference'].head().tolist()}"
            )

        # Check for empty conference names
        empty_conferences = df[df["conference"].apply(lambda x: not x or (isinstance(x, str) and not x.strip()))]
        if not empty_conferences.empty:
            errors.append(f"{source_name}: {len(empty_conferences)} conference names are empty")

    # Check 'year' column data type
    if "year" in df.columns:
        try:
            years = pd.to_numeric(df["year"], errors="coerce")
            invalid_years = df[years.isna()]
            if not invalid_years.empty:
                errors.append(f"{source_name}: {len(invalid_years)} rows have invalid year values")
        except Exception as e:
            errors.append(f"{source_name}: Error validating year column: {e}")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_merge_inputs(
    df_yaml: pd.DataFrame, df_remote: pd.DataFrame, report: Optional[MergeReport] = None
) -> tuple[bool, MergeReport]:
    """Validate both DataFrames before merging.

    Parameters
    ----------
    df_yaml : pd.DataFrame
        YAML source DataFrame (source of truth)
    df_remote : pd.DataFrame
        Remote source DataFrame (CSV or ICS)
    report : MergeReport, optional
        Existing report to update. Creates new if None

    Returns
    -------
    tuple[bool, MergeReport]
        (all_valid, updated report)
    """
    if report is None:
        report = MergeReport()

    all_errors = []

    # Validate YAML DataFrame
    yaml_valid, yaml_errors = validate_dataframe(df_yaml, "YAML")
    all_errors.extend(yaml_errors)
    if not df_yaml.empty:
        report.source_yaml_count = len(df_yaml)

    # Validate remote DataFrame
    remote_valid, remote_errors = validate_dataframe(df_remote, "Remote")
    all_errors.extend(remote_errors)
    if not df_remote.empty:
        report.source_remote_count = len(df_remote)

    # Log all errors
    for error in all_errors:
        report.add_error(error)

    all_valid = yaml_valid and remote_valid
    if not all_valid:
        logger.error(f"Input validation failed with {len(all_errors)} errors")
        for error in all_errors:
            logger.error(f"  {error}")

    return all_valid, report


def ensure_conference_strings(df: pd.DataFrame, source_name: str = "DataFrame") -> pd.DataFrame:
    """Ensure all conference names are strings.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to process
    source_name : str
        Name for logging purposes

    Returns
    -------
    pd.DataFrame
        DataFrame with conference names as strings
    """
    if "conference" not in df.columns:
        return df

    df = df.copy()

    for idx in df.index:
        val = df.at[idx, "conference"]
        if not isinstance(val, str):
            if pd.notna(val):
                df.at[idx, "conference"] = str(val).strip()
                logger.debug(f"{source_name}: Converted conference[{idx}] to string: {val} -> {df.at[idx, 'conference']}")
            else:
                df.at[idx, "conference"] = f"Unknown_Conference_{idx}"
                logger.warning(f"{source_name}: Replaced null conference[{idx}] with placeholder")

    return df


def log_dataframe_state(df: pd.DataFrame, label: str, show_sample: bool = True) -> None:
    """Log the current state of a DataFrame for debugging.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to log
    label : str
        Label for the log output
    show_sample : bool
        Whether to show sample data
    """
    logger.info(f"{label}: shape={df.shape}, columns={df.columns.tolist()}")
    logger.debug(f"{label}: index type={type(df.index)}, index values={df.index.tolist()[:5]}...")

    if show_sample and not df.empty and "conference" in df.columns:
        logger.debug(f"{label}: conference sample: {df['conference'].head().tolist()}")
