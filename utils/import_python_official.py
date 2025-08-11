import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import pandas as pd
import requests
from icalendar import Calendar
from logging_config import get_tqdm_logger
from tidy_conf import fuzzy_match
from tidy_conf import load_conferences
from tidy_conf import merge_conferences
from tidy_conf.date import create_nice_date
from tidy_conf.deduplicate import deduplicate
from tidy_conf.titles import tidy_df_names
from tidy_conf.utils import fill_missing_required
from tidy_conf.yaml import load_title_mappings
from tidy_conf.yaml import write_df_yaml

logger = get_tqdm_logger(__name__)


def ics_to_dataframe() -> pd.DataFrame:
    """Parse an .ics file and return a DataFrame with the event data.

    Returns
    -------
        pd.DataFrame: DataFrame containing parsed conference events

    Raises
    ------
        ConnectionError: If unable to fetch the calendar data
        ValueError: If calendar data is invalid
    """
    calendar_url = (
        "https://www.google.com/calendar/ical/j7gov1cmnqr9tvg14k621j7t5c@group.calendar.google.com/public/basic.ics"
    )

    # Validate URL scheme for security
    if not calendar_url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are allowed for security")

    logger.info(f"Fetching calendar data from: {calendar_url}")

    try:
        response = requests.get(calendar_url, timeout=30)
        response.raise_for_status()
        calendar_data = response.content

        if not calendar_data:
            raise ValueError("Empty calendar data received")

        calendar = Calendar.from_ical(calendar_data)
        logger.info(f"Successfully parsed calendar data ({len(calendar_data)} bytes)")

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch calendar data: {e}")
        raise ConnectionError(f"Unable to fetch calendar from {calendar_url}: {e}") from e
    except Exception as e:
        logger.error(f"Failed to parse calendar data: {e}")
        raise ValueError(f"Invalid calendar data: {e}") from e

    link_desc = re.compile(r".*<a .*?href=\"? ?((?:https|http):\/\/[\w\.\/\-\?= ]+)\"?.*?>(.*?)[#0-9 ]*<\/?a>.*")

    # Initialize a list to hold event data
    event_data = []
    processed_events = 0
    skipped_events = 0

    # Iterate over each event in the Calendar
    for component in calendar.walk():
        if component.name == "VEVENT":
            try:
                # Extract event details with error checking
                conference = str(component.get("summary", "Unknown Conference"))

                # Safely extract dates
                dtstart = component.get("dtstart")
                dtend = component.get("dtend")

                if not dtstart or not dtend:
                    logger.warning(f"Skipping event '{conference}' - missing date information")
                    skipped_events += 1
                    continue

                start = dtstart.dt
                end = dtend.dt - timedelta(days=1)

                # If the event is all day, the date might be of type 'date' (instead of 'datetime')
                # Adjust format accordingly
                start = start.strftime("%Y-%m-%d")
                end = end.strftime("%Y-%m-%d")
                year = int(start[:4])

            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"Skipping event due to date parsing error: {e}")
                skipped_events += 1
                continue

            # Process description and extract links
            try:
                raw_description = str(component.get("description", ""))
                if not raw_description:
                    logger.warning(f"Event '{conference}' has no description, skipping link extraction")
                    link = ""
                else:
                    # Clean HTML entities and format description
                    description = re.sub(
                        r"(?:\\s|&nbsp;|\\|\'|<br />|<br>|</[^a][^>]*>|<[^a/][^>]*>)+",
                        " ",
                        "<a "
                        + "<a ".join(
                            raw_description.replace("\n", "")
                            .replace(
                                """, '"')
                            .replace(""",
                                '"',
                            )
                            .replace("&amp;", "&")
                            .replace("&quot;", '"')
                            .replace("&apos;", "'")
                            .replace("&lt;", "<")
                            .replace("&gt;", ">")
                            .split("<a ")[1:],
                        ),
                    )

                    # Extract link and conference name from description
                    m = re.match(link_desc, description)
                    if m:
                        link = m.group(1).strip()
                        conference2 = m.group(2).strip()
                        if conference2:
                            conference = conference2
                    else:
                        logger.debug(f"No link found in description for '{conference}'")
                        link = ""

            except Exception as e:
                logger.warning(f"Error processing description for '{conference}': {e}")
                link = ""

            location = str(component.get("location", ""))

            # Append this event's details to the list
            event_data.append([conference, year, "TBA", start, end, link, location])
            processed_events += 1

    # Log processing summary
    logger.info(f"Calendar processing complete: {processed_events} events processed, {skipped_events} skipped")

    # Convert the list into a pandas DataFrame
    df = pd.DataFrame(event_data, columns=["conference", "year", "cfp", "start", "end", "link", "place"])

    if df.empty:
        logger.warning("No events were successfully processed from calendar")
        return df

    # Strip whitespace from applicable columns
    try:
        df_obj = df.select_dtypes("object")
        df[df_obj.columns] = df_obj.apply(lambda x: x.str.strip())
        logger.info(f"Created DataFrame with {len(df)} conference entries")
    except Exception as e:
        logger.error(f"Error cleaning DataFrame: {e}")

    return df


def main(year=None, base="") -> bool:
    """Import Python conferences from a Google Calendar .ics file.

    Args:
        year: Target year for filtering (defaults to current year)
        base: Base path for file operations

    Returns
    -------
        bool: True if import was successful, False otherwise
    """
    logger.info("Starting Python Official calendar import")

    # If no year is provided, use the current year
    if year is None:
        year = datetime.now(tz=timezone.utc).year

    logger.info(f"Importing conferences for year: {year}")

    try:
        # Create the necessary files if they don't exist
        _data_path = Path(base, "_data")
        _tmp_path = Path(base, ".tmp")
        _tmp_path.mkdir(exist_ok=True, parents=True)
        _data_path.mkdir(exist_ok=True, parents=True)
        target_file = Path(_data_path, "conferences.yml")
        cache_file = Path(_tmp_path, ".conferences_ics.csv")

        logger.info(f"Using data path: {_data_path}")
        logger.info(f"Using cache file: {cache_file}")

        # Load the existing conference data
        logger.info("Loading existing conference data")
        df_yml = load_conferences()
        df_new = pd.DataFrame(columns=df_yml.columns)

        # Parse your .ics file and only use future events in the current year
        logger.info("Parsing ICS calendar data")
        df_ics = ics_to_dataframe()

        if df_ics.empty:
            logger.warning("No conference data retrieved from calendar")
            return False

    except Exception as e:
        logger.error(f"Failed to initialize import process: {e}")
        return False

    # Load old ics dataframe from cached data
    try:
        # Load the old ics dataframe from cache
        logger.info("Loading cached ICS data")
        df_ics_old = pd.read_csv(cache_file, na_values=None, keep_default_na=False)
        logger.info(f"Loaded {len(df_ics_old)} cached entries")
    except FileNotFoundError:
        logger.info("No cache file found, starting fresh")
        df_ics_old = pd.DataFrame(columns=df_ics.columns)
    except Exception as e:
        logger.error(f"Error loading cache file: {e}")
        df_ics_old = pd.DataFrame(columns=df_ics.columns)

    try:
        # Load and apply the title mappings, remove years from conference names
        logger.info("Applying title mappings and cleaning data")
        df_ics = tidy_df_names(df_ics)

        # Store the new ics dataframe to cache
        df_cache = df_ics.copy()

        # Get the difference between the old and new dataframes
        df_diff = pd.concat([df_ics_old, df_ics]).drop_duplicates(keep=False)

        # Deduplicate the new dataframe
        df_ics = deduplicate(df_diff, "conference")

        if df_ics.empty:
            logger.info("No new conferences found in official Python source.")
            return True  # Not an error, just no new data

    except Exception as e:
        logger.error(f"Error processing conference data: {e}")
        return False

    try:
        _, reverse_titles = load_title_mappings(reverse=False)

        # Fuzzy match the new data with the existing data
        logger.info(f"Starting fuzzy matching for years {year} to {year + 9}")
        processed_years = 0

        for y in range(year, year + 10):
            # Skip years that are not in the new data
            if df_ics.loc[df_ics["year"] == y].empty or df_yml[df_yml["year"] == y].empty:
                # Concatenate the new data with the existing data
                df_new = pd.concat(
                    [df_new, df_yml[df_yml["year"] == y], df_ics.loc[df_ics["year"] == y]],
                    ignore_index=True,
                )
                continue

        df_merged, df_remote = fuzzy_match(df_yml[df_yml["year"] == y], df_ics.loc[df_ics["year"] == y])
        df_merged["year"] = year
        diff_idx = df_merged.index.difference(df_remote.index)
        df_missing = df_merged.loc[diff_idx, :].sort_values("start")
        df_merged = df_merged.drop(["conference"], axis=1)
        df_merged = deduplicate(df_merged)
        df_remote = deduplicate(df_remote)
        df_merged = merge_conferences(df_merged, df_remote)

        # Concatenate the new data with the existing data
        df_new = pd.concat([df_new, df_merged], ignore_index=True)
        for _index, row in df_missing.iterrows():

            reverse_title_data = reverse_titles.get(row["conference"])
            if reverse_title_data is None:
                reverse_title = f"{row['conference']} {row['year']}"
            else:
                # Get the first variation from the reverse title data
                reverse_title_data = reverse_title_data.get("variations")
                if reverse_title_data:
                    reverse_title = f"{reverse_title_data[0]} {row['year']}"
                else:
                    reverse_title = f"{row['conference']} {row['year']}"

            dates = f'{create_nice_date(row)["date"]} ({row["timezone"] if isinstance(row["timezone"], str) else "UTC"}'
            link = f'<a href="{row["link"]}">{row["conference"]}</a>'
            out = f""" * name of the event: {reverse_title}
 * type of event: conference
 * focus on Python: yes
 * approximate number of attendees: Unknown
 * location (incl. country): {row["place"]}
 * dates/times/recurrence (incl. time zone): {dates})
 * HTML link using the format <a href="http://url/">name of the event</a>: {link}"""
            with Path("missing_conferences.txt").open("a") as f:
                f.write(out + "\n\n")
            Path(".tmp").mkdir(exist_ok=True, parents=True)
            with Path(".tmp", f"{reverse_title}.ics".lower().replace(" ", "-")).open("w") as f:
                f.write(
                    f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:{reverse_title}
DTSTART;VALUE=DATE:{row["start"].strftime("%Y%m%d")}
DTEND;VALUE=DATE:{row["end"].strftime("%Y%m%d")}
DESCRIPTION:<a href="{row.link}">{ reverse_title }</a>
LOCATION:{ row.place }
END:VEVENT
END:VCALENDAR""",
                )
            processed_years += 1

        logger.info(f"Fuzzy matching complete: processed {processed_years} years")

        # Fill in missing required fields
        logger.info("Filling missing required fields")
        df_new = fill_missing_required(df_new)

        # Write the new data to the YAML file
        logger.info(f"Writing {len(df_new)} conference entries to {target_file}")
        write_df_yaml(df_new, target_file)

        # Save the new dataframe to cache
        logger.info(f"Saving cache to {cache_file}")
        df_cache.to_csv(cache_file, index=False)

        logger.info("Python Official calendar import completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during fuzzy matching and data processing: {e}")
        return False


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Import Python conferences from official calendar")
    parser.add_argument("--year", type=int, help="Year to import (defaults to current year)")
    parser.add_argument("--base", type=str, default="", help="Base path for data files")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level",
    )

    args = parser.parse_args()

    # Set up logging
    from logging_config import setup_logging

    setup_logging(level=args.log_level)

    # Run the import
    success = main(year=args.year, base=args.base)

    if not success:
        logger.error("Import failed")
        sys.exit(1)

    logger.info("Import completed successfully")
