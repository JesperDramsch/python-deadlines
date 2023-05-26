from datetime import datetime
import pandas as pd
import urllib
import yaml
import sys
from thefuzz import process, fuzz
from pathlib import Path

sys.path.append(".")
from utils import ordered_dump, get_schema, query_yes_no


def load_remote(year):
    template = "https://raw.githubusercontent.com/python-organizers/conferences/main/{year}.csv"
    url = template.format(year=year)

    # Read data and rename columns
    df = pd.read_csv(url)
    df = map_columns(df)

    # Only return valid cfps
    # return df.dropna(subset=['cfp'])
    return df


def load_yml():
    schema = get_schema()

    # Load the YAML file
    with open("_data/conferences.yml", "r") as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    with open("_data/archive.yml", "r") as file:
        archive = yaml.load(file, Loader=yaml.FullLoader)

    # Convert the YAML data to a Pandas DataFrame
    return pd.concat(
        [schema, pd.DataFrame.from_dict(data), pd.DataFrame.from_dict(archive)],
        ignore_index=True,
    ).set_index("title", drop=False)


def map_columns(df, reverse=False):
    cols = {
        "Subject": "title",
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


def fuzzy_match(df_yml, df_remote):
    # Make Title the index
    df_remote = df_remote.set_index("title", drop=False)
    df_remote.index.rename("title_match", inplace=True)
    known_mappings = {"SciPy US": "SciPy"}

    df = df_yml.copy()

    # Get closest match for titles
    df["title_match"] = df["title"].apply(lambda x: process.extract(x, df_remote["title"], limit=1))

    for key, value in known_mappings.items():
        if key in df["title"].values:
            df.loc[df["title"] == key, "title_match"] = value

    # Get first match if it's over 90
    for i, row in df.copy().iterrows():
        if isinstance(row["title_match"], str):
            continue
        title, prob, _ = row["title_match"][0]
        if prob == 100:
            title = title
        elif prob >= 70:
            if not query_yes_no(f"Do '{row['title']}' and '{title}' match? (y/n): "):
                # Code for non-matching case
                title = i
        else:
            title = i
        df.loc[i, "title_match"] = title

    df.set_index("title_match", inplace=True)
    print(df)
    # Update missing data in existing records
    df_new = df.combine_first(df_remote)

    df_new.loc[df_new["cfp"].isna(), "cfp"] = "TBA"

    print(df_new, df_remote)

    return df_new, df_remote


def interactive_merge(df_yml, df_remote):
    df_new = get_schema()
    columns = df_new.columns.tolist()

    try:
        df_yml = df_yml.drop(["title"], axis=1)
    except:
        pass
    try:
        df_remote = df_remote.drop(["title"], axis=1)
    except:
        pass

    replacements = {"United States of America": "USA",
                    "United States": "USA",
                    "United Kingdom": "UK",
                    "www.": ""}

    df_merge = pd.merge(left=df_yml, right=df_remote, how="outer", on="title_match", validate="one_to_one")
    for i, row in df_merge.iterrows():
        df_new.loc[i, "title"] = i
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
                if column == "sponsor":
                    if not pd.isnull(rx):
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
                    if "Online" in [rx, ry]:
                        ry, rx = "Online", "Online"
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
                        if query_yes_no(
                            f"For {i} in column '{column}' would you prefer '{rx}' or keep '{ry}'?"
                        ):
                            df_new.loc[i, column] = rx
                        else:
                            df_new.loc[i, column] = ry
                elif column == "cfp" and rx != ry:
                    # Special CFP stuff
                    if " " in rx and " " not in ry:
                        cfp_time_x = ""
                        cfp_time_y = " " + rx.split(" ")[1]
                    elif " " not in rx and " " in ry:
                        cfp_time_x = " " + ry.split(" ")[1]
                        cfp_time_y = ""
                    if query_yes_no(
                        f"For {i} in column '{column}' would you prefer '{rx+ cfp_time_x}' or keep '{ry+cfp_time_y}'?"
                    ):
                        df_new.loc[i, column] = rx + cfp_time_x
                    else:
                        df_new.loc[i, column] = ry + cfp_time_y
                else:
                    # For everything else give a choice
                    if query_yes_no(f"For {i} in column '{column}' would you prefer '{rx}' or keep '{ry}'?"):
                        df_new.loc[i, column] = rx
                    else:
                        df_new.loc[i, column] = ry
            elif column in df_merge.columns:
                df_new[column] = df_merge[column]

    df_new.loc[df_new.cfp.isna(), "cfp"] = "TBA"
    return df_new


def fill_missing_required(df):
    required = [
        "title",
        "year",
        "link",
        "cfp",
        "timezone",
        "place",
        "start",
        "end",
        "sub",
    ]

    for i, row in df.copy().iterrows():
        for keyword in required:
            if pd.isna(row[keyword]):
                user_input = input(
                    f"What's the value of '{keyword}' for conference '{row['title']}' check {row['link']} ?: "
                )
                if user_input != "":
                    df.loc[i, keyword] = user_input
    return df


def write_yaml(df, out_url):
    try:
        df = df.drop(["Country", "Venue"], axis=1)
    except KeyError:
        pass
    df["end"] = pd.to_datetime(df["end"]).dt.date
    df["start"] = pd.to_datetime(df["start"]).dt.date
    df["year"] = df["year"].astype(int)
    df["cfp"] = df["cfp"].astype(str)
    with open(out_url, "w") as outfile:
        for line in ordered_dump(
            [{k: v for k, v in record.items() if pd.notnull(v)} for record in df.to_dict(orient="records")],
            Dumper=yaml.SafeDumper,
            default_flow_style=False,
            explicit_start=True,
        ).splitlines():
            outfile.write(line.replace("- title:", "\n- title:"))
            outfile.write("\n")


def write_csv(df, year, csv_location):
    df["cfp"] = df["cfp"].str.slice(stop=10).str.replace("TBA", "")
    df["tutorial_deadline"] = df["tutorial_deadline"].str.slice(stop=10).str.replace("TBA", "")
    df = map_columns(df, reverse=True)
    for y in range(year, datetime.now().year + 10):
        if y in df["year"].unique():
            df.loc[
                df["year"] == y,
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
                ],
            ].fillna("").astype(str).sort_values(by="Start Date").to_csv(Path(csv_location, f"{y}.csv"), index=False)


def main(year=None, base=""):
    target_file = Path(base, "_data", "conferences.yml")
    csv_location = Path(base, "utils", "conferences")

    if year is None:
        year = datetime.now().year

    df_yml = load_yml()
    df_new = pd.DataFrame(columns=df_yml.columns)
    df_csv = pd.DataFrame(columns=df_yml.columns)

    for y in range(year, datetime.now().year + 10):
        try:
            df = load_remote(year=y)
        except urllib.error.HTTPError:
            break

        df_merged, df_remote = fuzzy_match(df_yml[df_yml["year"] == y], df)
        df_merged["year"] = y
        df_merged = df_merged.drop(["title"], axis=1)
        df_merged = interactive_merge(df_merged, df_remote)

        df_new = pd.concat([df_new, df_merged], ignore_index=True)

        # merged, _ = fuzzy_match(df, df_yml[df_yml["year"] == y])
        # df_csv = pd.concat([df_csv, merged], ignore_index=True)

    df_new = fill_missing_required(df_new)

    write_yaml(df_new, target_file)
    # write_csv(df_csv, year, csv_location)


if __name__ == "__main__":
    main()
