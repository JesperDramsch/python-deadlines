#!/usr/bin/env python3
"""Diagnostic script to trace the conference data sync pipeline and identify breaks."""

import os
import sys
from pathlib import Path

# Change to utils directory for proper imports
os.chdir(Path(__file__).parent / "utils")
sys.path.insert(0, str(Path(__file__).parent / "utils"))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from thefuzz import fuzz  # noqa: E402
from thefuzz import process  # noqa: E402
from tidy_conf.interactive_merge import FUZZY_MATCH_THRESHOLD  # noqa: E402
from tidy_conf.interactive_merge import conference_scorer  # noqa: E402

# Import our improved functions
from tidy_conf.titles import COUNTRY_CODE_TO_NAME  # noqa: E402
from tidy_conf.titles import tidy_df_names  # noqa: E402


def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def print_subheader(title):
    print(f"\n--- {title} ---\n")


def print_df_info(df, name):
    """Print detailed DataFrame info."""
    print(f"{name}:")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {df.columns.tolist()}")
    print(f"  Index type: {type(df.index).__name__}")
    print(f"  Index values (first 5): {df.index.tolist()[:5]}")
    if "conference" in df.columns:
        print(f"  Conference values (first 5): {df['conference'].tolist()[:5]}")


# ============================================================================
# STEP 1: LOAD RAW DATA
# ============================================================================
print_header("STEP 1: LOADING RAW DATA")

# 1.1 Load YAML conferences
print_subheader("1.1 Loading conferences.yml")
with Path("../_data/conferences.yml").open(encoding="utf-8") as file:
    yaml_data = yaml.safe_load(file)

df_yml = pd.DataFrame.from_dict(yaml_data)
print(f"Loaded {len(df_yml)} conferences from YAML")
print(f"Columns: {df_yml.columns.tolist()}")
print("\nSample YAML conferences (2026):")
df_yml_2026 = df_yml[df_yml["year"] == 2026]
print(df_yml_2026[["conference", "year", "place"]].to_string())

# 1.2 Load CSV from GitHub
print_subheader("1.2 Loading 2026 CSV from GitHub")
csv_url = "https://raw.githubusercontent.com/python-organizers/conferences/main/2026.csv"
try:
    df_csv = pd.read_csv(csv_url)
    print(f"Loaded {len(df_csv)} conferences from CSV")
    print(f"Columns: {df_csv.columns.tolist()}")
    print("\nSample CSV conferences:")
    print(df_csv[["Subject", "Location"]].to_string())
except Exception as e:
    print(f"ERROR loading CSV: {e}")
    df_csv = pd.DataFrame()

# ============================================================================
# STEP 2: COLUMN MAPPING
# ============================================================================
print_header("STEP 2: COLUMN MAPPING (CSV -> Schema)")


def map_columns(df):
    """Map columns between CSV format and conference schema."""
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
    return df.rename(columns=cols)


df_csv_mapped = map_columns(df_csv.copy())
df_csv_mapped["year"] = 2026

print("After column mapping:")
print(f"Columns: {df_csv_mapped.columns.tolist()}")
print("\nConference names from CSV:")
print(df_csv_mapped[["conference", "place"]].to_string())

# ============================================================================
# STEP 3: TITLE NORMALIZATION (tidy_df_names) - MANUAL VERSION
# ============================================================================
print_header("STEP 3: TITLE NORMALIZATION (tidy_df_names)")

# Load title mappings directly from YAML file
titles_yml_path = Path("tidy_conf/data/titles.yml")
with titles_yml_path.open(encoding="utf-8") as file:
    titles_data = yaml.safe_load(file)

spellings = titles_data.get("spelling", [])
alt_names = titles_data.get("alt_name", {})

# Load rejections from rejections.yml
rejections_yml_path = Path("tidy_conf/data/rejections.yml")
with rejections_yml_path.open(encoding="utf-8") as file:
    rejections_data = yaml.safe_load(file)

rejections_alt_names = rejections_data.get("alt_name", {})
exclusions = set()
for name1, data in rejections_alt_names.items():
    variations = data.get("variations", []) if isinstance(data, dict) else []
    exclusions.update(frozenset([name1, name2]) for name2 in variations)

print(f"Loaded {len(exclusions)} rejection pairs from rejections.yml:")
for pair in sorted(exclusions, key=lambda x: min(x)):
    names = sorted(pair)
    print(f"  - '{names[0]}' <-> '{names[1]}'")

print(f"Loaded {len(spellings)} spellings to check")
print(f"Loaded {len(alt_names)} alt_name mappings")

# Build reverse mappings
known_mappings = {}
for key, values in alt_names.items():
    global_name = values.get("global")
    variations_raw = values.get("variations", [])
    regexes = values.get("regexes", [])

    # Map global name and variations back to key
    if global_name:
        known_mappings[global_name] = key
    for variation in variations_raw:
        known_mappings[variation] = key
    for regex in regexes:
        known_mappings[regex] = key

print(f"Built {len(known_mappings)} reverse mappings")
print("\nReverse mappings sample:")
for k, v in list(known_mappings.items())[:15]:
    print(f"  '{k}' -> '{v}'")

# Show the country code expansion feature
print(f"Loaded {len(COUNTRY_CODE_TO_NAME)} country code mappings")
print("Sample country codes:")
for code in ["US", "DE", "PL", "AU", "AT", "UK", "JP", "KR"]:
    if code in COUNTRY_CODE_TO_NAME:
        print(f"  {code} -> {COUNTRY_CODE_TO_NAME[code]}")


# Apply tidy_df_names verbose to show before/after
def tidy_df_names_verbose(df, source_name):
    """Verbose version of tidy_df_names to show transformations."""
    original = df["conference"].copy()

    # Use the actual tidy_df_names function
    df_tidy = tidy_df_names(df.copy())

    # Show transformations
    print(f"\n{source_name} Transformations:")
    for orig, final in zip(original, df_tidy["conference"], strict=False):
        changed = " [CHANGED]" if orig != final else ""
        print(f"  '{orig}' -> '{final}'{changed}")

    return df_tidy


print_subheader("3.1 YAML Conference Names (before/after)")
df_yml_2026_tidy = tidy_df_names_verbose(df_yml_2026.copy(), "YAML")

print_subheader("3.2 CSV Conference Names (before/after)")
df_csv_tidy = tidy_df_names_verbose(df_csv_mapped.copy(), "CSV")

# ============================================================================
# STEP 4: FUZZY MATCHING ANALYSIS
# ============================================================================
print_header("STEP 4: FUZZY MATCHING ANALYSIS")

# Get unique conference names from each source
yml_names = df_yml_2026_tidy["conference"].unique().tolist()
csv_names = df_csv_tidy["conference"].unique().tolist()

print(f"YAML conference names AFTER tidy ({len(yml_names)}):")
for name in sorted(yml_names):
    print(f"  - {name}")

print(f"\nCSV conference names AFTER tidy ({len(csv_names)}):")
for name in sorted(csv_names):
    print(f"  - {name}")

print_subheader("4.1 Fuzzy Match Scores (CSV vs YAML) - Using Custom Scorer")

print(f"\nUsing FUZZY_MATCH_THRESHOLD = {FUZZY_MATCH_THRESHOLD}")
print("Custom scorer uses: token_sort_ratio, token_set_ratio, ratio, partial_ratio")

# For each CSV conference, find best match in YAML using our custom scorer
print("\nBest matches for CSV conferences in YAML:")
print("-" * 80)
match_results = []
for csv_name in csv_names:
    # Use our custom scorer
    matches = process.extract(csv_name, yml_names, scorer=conference_scorer, limit=3)

    # Handle both old (3-tuple) and new (2-tuple) formats
    if matches:
        first = matches[0]
        if len(first) == 3:
            best_match, best_score, _ = first
        else:
            best_match, best_score = first
    else:
        best_match, best_score = None, 0

    status = "EXACT" if best_score == 100 else "FUZZY" if best_score >= FUZZY_MATCH_THRESHOLD else "NO MATCH"
    match_results.append(
        {
            "csv_name": csv_name,
            "best_match": best_match,
            "score": best_score,
            "status": status,
        },
    )

    print(f"\nCSV: '{csv_name}'")
    for match_tuple in matches:
        if len(match_tuple) == 3:
            match, score, _ = match_tuple
        else:
            match, score = match_tuple

        # Check if this pair is excluded
        is_excluded = frozenset([csv_name, match]) in exclusions
        if is_excluded:
            marker = " <-- EXCLUDED (will not match)"
        elif score >= FUZZY_MATCH_THRESHOLD:
            marker = " <-- WILL MATCH"
        elif score >= 70:
            marker = " <-- NEEDS ATTENTION"
        else:
            marker = ""
        print(f"  -> YAML: '{match}' (score: {score}){marker}")

# ============================================================================
# STEP 5: IDENTIFY PROBLEM CASES
# ============================================================================
print_header("STEP 5: PROBLEM CASES ANALYSIS")

print_subheader(
    f"5.1 Conferences that SHOULD match but DON'T (score < {FUZZY_MATCH_THRESHOLD})",
)
no_match = [r for r in match_results if r["score"] < FUZZY_MATCH_THRESHOLD]
if no_match:
    for r in no_match:
        print("\n*** PROBLEM: CSV conference has no YAML match ***")
        print(f"CSV: '{r['csv_name']}'")
        print(f"  Best YAML match: '{r['best_match']}' (score: {r['score']})")

        # Analyze why they don't match
        csv_n = r["csv_name"]
        yml_n = r["best_match"]

        # Different fuzzy scoring methods
        print("\n  Detailed similarity scores:")
        print(f"    - ratio: {fuzz.ratio(csv_n, yml_n)}")
        print(f"    - partial_ratio: {fuzz.partial_ratio(csv_n, yml_n)}")
        print(f"    - token_sort_ratio: {fuzz.token_sort_ratio(csv_n, yml_n)}")
        print(f"    - token_set_ratio: {fuzz.token_set_ratio(csv_n, yml_n)}")

        # Check what the original names were
        print("\n  Original names before tidy:")
        csv_orig = df_csv_mapped[
            df_csv_mapped["conference"].str.contains(
                csv_n.split()[0],
                case=False,
                na=False,
            )
        ]["conference"].values
        yml_orig = df_yml_2026[
            df_yml_2026["conference"].str.contains(
                yml_n.split()[0],
                case=False,
                na=False,
            )
        ]["conference"].values
        print(f"    CSV original: {csv_orig}")
        print(f"    YAML original: {yml_orig}")
else:
    print("All CSV conferences have matches >= 90% in YAML")

print_subheader("5.2 Conferences in YAML without CSV match")
yml_in_csv = set()
for r in match_results:
    if r["score"] >= FUZZY_MATCH_THRESHOLD:
        yml_in_csv.add(r["best_match"])

yml_no_csv = set(yml_names) - yml_in_csv
if yml_no_csv:
    print("YAML conferences with no CSV equivalent:")
    for name in sorted(yml_no_csv):
        # Find best CSV match using custom scorer
        matches = process.extract(name, csv_names, scorer=conference_scorer, limit=1)
        if matches:
            first = matches[0]
            best_match, score = (first[0], first[1]) if len(first) >= 2 else (first, 0)
            print(f"  '{name}' -> closest CSV: '{best_match}' (score: {score})")
        else:
            print(f"  '{name}' -> no CSV data")

print_subheader("5.3 Checking Title Mappings Coverage")

# Check if problematic names are in the mappings
print("\nChecking if problem cases are covered in titles.yml:")
for r in no_match:
    csv_name = r["csv_name"]
    yml_name = r["best_match"]

    # Check if either name is in the mappings
    csv_in_mappings = csv_name in known_mappings
    yml_in_mappings = yml_name in known_mappings

    print(f"\n'{csv_name}':")
    print(f"  - In reverse mappings: {csv_in_mappings}")
    if csv_in_mappings:
        print(f"    -> maps to: '{known_mappings[csv_name]}'")

    print(f"'{yml_name}':")
    print(f"  - In reverse mappings: {yml_in_mappings}")
    if yml_in_mappings:
        print(f"    -> maps to: '{known_mappings[yml_name]}'")

# ============================================================================
# STEP 6: SIMULATE fuzzy_match() DATA FLOW
# ============================================================================
print_header("STEP 6: DATA FLOW SIMULATION")

# This simulates exactly what fuzzy_match() does
print("Simulating fuzzy_match() function behavior...")

# Step 1: Set up DataFrames like fuzzy_match does
df_yml_for_match = df_yml_2026_tidy.copy()
df_csv_for_match = df_csv_tidy.copy()

# Set index for remote dataframe
df_csv_for_match = df_csv_for_match.set_index("conference", drop=False)
df_csv_for_match.index.rename("title_match", inplace=True)

print("\nAfter setting up indexes:")
print_df_info(df_yml_for_match, "df_yml_for_match")
print()
print_df_info(df_csv_for_match, "df_csv_for_match")

# Step 2: Apply fuzzy matching like the real function using our custom scorer
df_test = df_yml_for_match.copy()
df_test["title_match"] = df_test["conference"].apply(
    lambda x: process.extract(
        x,
        df_csv_for_match["conference"],
        scorer=conference_scorer,
        limit=1,
    ),
)

print_subheader("6.1 Fuzzy Match Raw Results (Using Custom Scorer)")

print("\nWhat fuzzy_match() would produce:")
for _i, row in df_test.iterrows():
    if row["title_match"]:
        match_tuple = row["title_match"][0]
        title, prob = (match_tuple[0], match_tuple[1]) if len(match_tuple) >= 2 else (match_tuple, 0)
        conference_name = row["conference"]

        # Check exclusions first
        is_pair_excluded = frozenset([conference_name, title]) in exclusions

        if is_pair_excluded:
            status = f"EXCLUDED -> title_match = '{conference_name}' (exclusion rule applied)"
            resolved = conference_name
        elif prob == 100:
            status = f"EXACT -> title_match = '{title}'"
            resolved = title
        elif prob >= FUZZY_MATCH_THRESHOLD:
            status = f"FUZZY (>={FUZZY_MATCH_THRESHOLD}) -> Would prompt user, assuming 'yes'"
            resolved = title
        else:
            status = f"NO MATCH (<{FUZZY_MATCH_THRESHOLD}) -> title_match = '{conference_name}' (original)"
            resolved = conference_name
        print(f"  YAML '{conference_name}' -> CSV '{title}' (score: {prob})")
        print(f"     Resolution: {status}")

# ============================================================================
# STEP 7: IDENTIFY THE FIRST BREAK
# ============================================================================
print_header("STEP 7: FIRST BREAK POINT IDENTIFIED")

if no_match:
    print("*** FIRST BREAK POINT: FUZZY MATCHING FAILS ***")
    print(
        "\nThe pipeline breaks at fuzzy_match() because these conferences don't match:",
    )
    for r in no_match:
        print(f"\n  CSV: '{r['csv_name']}'")
        print(f"  YAML: '{r['best_match']}'")
        print(f"  Similarity: {r['score']}% (threshold is {FUZZY_MATCH_THRESHOLD}%)")

    print("\n*** ROOT CAUSE ANALYSIS ***")
    for r in no_match:
        csv_name = r["csv_name"]
        yml_name = r["best_match"]

        # What would need to be in titles.yml to fix this
        print(f"\n1. The name '{csv_name}' from CSV")
        print(f"   should map to '{yml_name}' in YAML")

        # Check if there's a global name involved
        if yml_name in known_mappings:
            print(f"   Note: '{yml_name}' already maps to '{known_mappings[yml_name]}'")
        else:
            print(f"   Note: '{yml_name}' is NOT in any mapping")

        # Suggest fix
        print("\n   SUGGESTED FIX - Add to titles.yml:")
        print(f"   {yml_name}:")
        print("     variations:")
        print(f"       - {csv_name}")
else:
    print("No major breaks detected in fuzzy matching phase.")
    print("All CSV conferences match YAML conferences with >= 90% similarity.")

# ============================================================================
# STEP 8: SUMMARY
# ============================================================================
print_header("STEP 8: SUMMARY AND NEXT STEPS")

exact_matches = len([r for r in match_results if r["score"] == 100])
fuzzy_matches = len(
    [r for r in match_results if FUZZY_MATCH_THRESHOLD <= r["score"] < 100],
)
no_matches = len([r for r in match_results if r["score"] < FUZZY_MATCH_THRESHOLD])

print("Match Statistics:")
print(f"  - Exact matches (100%): {exact_matches}")
print(f"  - Fuzzy matches (90-99%): {fuzzy_matches}")
print(f"  - No matches (<90%): {no_matches}")
print(f"  - Total CSV conferences: {len(csv_names)}")
print(f"  - Total YAML conferences: {len(yml_names)}")

if no_matches > 0:
    print(f"\n*** {no_matches} CONFERENCES WILL BE LOST IN SYNC ***")
    print("These need mappings added to titles.yml")

print("\nDiagnostic complete.")
