#!/usr/bin/env python3

# Sort and Clean conference data.
import contextlib
import datetime
import operator
import time
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

import pydantic
import pytz
import yaml
from logging_config import get_tqdm_logger
from tidy_conf import auto_add_sub
from tidy_conf import write_conference_yaml
from tidy_conf.date import clean_dates
from tidy_conf.latlon import add_latlon
from tidy_conf.links import check_link_availability
from tidy_conf.links import get_cache
from tidy_conf.schema import Conference
from tidy_conf.schema import get_schema
from tidy_conf.titles import tidy_titles
from tidy_conf.utils import Loader
from tqdm import tqdm

dateformat = "%Y-%m-%d %H:%M:%S"
tba_words = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]


def sort_by_cfp(data):
    """Sort by CFP date."""
    if data.cfp.lower() in tba_words:
        return data.cfp
    if " " not in data.cfp:
        data.cfp += " 23:59:00"
    timezone = data.timezone or "AoE"
    return pytz.utc.normalize(
        datetime.datetime.strptime(data.cfp, dateformat).replace(
            tzinfo=pytz.timezone(
                timezone.replace("AoE", "Etc/GMT+12").replace("UTC+", "Etc/GMT-").replace("UTC-", "Etc/GMT+"),
            ),
        ),
    ).strftime(dateformat)


def sort_by_date(data):
    """Sort by starting date."""
    return str(data.start)


def sort_by_date_passed(data):
    """Sort data by date passed."""
    right_now = datetime.datetime.now(tz=timezone.utc).replace(microsecond=0).strftime(dateformat)
    return sort_by_cfp(data) < right_now


def sort_by_name(data):
    """Sort by name."""
    return f"{data.conference} {data.year}".lower()


def order_keywords(data):
    """Order the keywords in the data."""
    schema = get_schema().columns.tolist()
    _data_flag = False
    if isinstance(data, Conference):
        data = data.dict()
        _data_flag = True

    new_dict = {}
    for key in schema:
        if key in data:
            new_dict[key] = data[key]

    if _data_flag:
        return Conference(**new_dict)
    return new_dict


def merge_duplicates(data):
    """Merge duplicates in the data."""
    filtered = []
    filtered_reduced = []
    for q in tqdm(data):
        q_reduced = f'{q.get("conference", None)} {q.get("year", None)} {q.get("place", None)}'
        if q_reduced not in filtered_reduced:
            filtered.append(q)
            filtered_reduced.append(q_reduced)
        else:
            index = filtered_reduced.index(q_reduced)
            for key, value in q.items():
                if value and key not in filtered[index]:
                    filtered[index][key] = value
                else:
                    if len(str(value)) > len(str(filtered[index][key])):
                        filtered[index][key] = value
    return filtered


def tidy_dates(data):
    """Clean dates in the data."""
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        data[i] = clean_dates(q)
        # data[i] = create_nice_date(q)
    return data


def split_data(data):
    """Split the data into conferences, tba, expired, and legacy.

    The data is split based on the `cfp` field. If the `cfp` field is in the `tba_words` list, it is considered a TBA.
    Legacy is considered anything old with the `cfp` still being TBA.
    """
    conf, tba, expired, legacy = [], [], [], []
    for q in tqdm(data):
        if q.cfp.lower() not in tba_words and " " not in q.cfp:
            q.cfp += " 23:59:00"
        if "cfp_ext" in q and " " not in q.cfp_ext:
            q.cfp_ext += " 23:59:00"
        date_today = datetime.datetime.now(tz=timezone.utc).replace(microsecond=0).date()
        # if the conference is older than 37 days, it moves off the main page
        if q.end < date_today - datetime.timedelta(days=37):
            legacy_year = (date_today - datetime.timedelta(days=7 * 365)).replace(month=1, day=1)
            if q.end < legacy_year:
                legacy.append(q)
            else:
                expired.append(q)
            continue

        try:
            if q.cfp.lower() in tba_words:
                tba.append(q)
            else:
                conf.append(q)
        except KeyError:
            pass
    return conf, tba, expired, legacy


def check_links(data):
    """Check the links in the data iteratively."""
    cache, cache_archived = get_cache()
    for i, q in tqdm(enumerate(sorted(data, key=operator.itemgetter("year"), reverse=True)), total=len(data)):
        for key in ("link", "cfp_link", "sponsor", "finaid"):
            if key in q:
                new_link = check_link_availability(q[key], q["start"], cache=cache, cache_archived=cache_archived)
                parsed_url = urlparse(new_link)
                if q[key] != new_link and parsed_url.hostname and parsed_url.hostname.endswith(".archive.org"):
                    time.sleep(0.5)
                q[key] = new_link
                data[i] = q
    return data


# Sort:
def sort_data(base="", prefix="", skip_links=False):
    """Sort and clean the conference data."""
    logger = get_tqdm_logger(__name__)

    # Load different data files
    current = Path(base, "_data", "conferences.yml")
    out_current = Path(base, "_data", f"{prefix}conferences.yml")
    archive = Path(base, "_data", "archive.yml")
    out_archive = Path(base, "_data", f"{prefix}archive.yml")
    legacy = Path(base, "_data", "legacy.yml")
    out_legacy = Path(base, "_data", f"{prefix}legacy.yml")

    logger.info("📊 Loading conference data files")
    data = []
    files_loaded = 0

    for url in (current, archive, legacy):
        if url.exists():
            with url.open(encoding="utf-8") as stream, contextlib.suppress(yaml.YAMLError):
                if stream:
                    file_data = yaml.load(stream, Loader=Loader)  # nosec B506 # noqa: S506
                    if file_data:
                        data += file_data
                        files_loaded += 1
                        logger.debug(f"Loaded {len(file_data)} entries from {url.name}")

    logger.info(f"📋 Loaded {len(data)} conferences from {files_loaded} files")

    from tidy_conf.schema import Conference

    logger.debug("🔧 Ordering keywords")
    for i, q in enumerate(data.copy()):
        data[i] = order_keywords(q)

    # Clean Dates
    logger.info("📅 Cleaning dates")
    data = tidy_dates(data)

    # Clean Titles
    logger.info("🏷️  Cleaning titles")
    data = tidy_titles(data)

    # Add Sub
    logger.info("🏢 Adding submission types")
    data = auto_add_sub(data)

    # Geocode Data
    logger.info("🗺️  Adding geolocation data")
    data = add_latlon(data)

    # Merge duplicates
    logger.info("🔄 Merging duplicates")
    data = merge_duplicates(data)

    # Check Links
    if not skip_links:
        logger.info("🔗 Checking link availability")
        data = check_links(data)
    else:
        logger.info("⏭️  Skipping link checking")

    for i, q in enumerate(data.copy()):
        data[i] = order_keywords(q)

    logger.info("✅ Validating conference data with Pydantic schema")
    new_data = []
    validation_errors = 0

    for q in data:
        try:
            new_data.append(Conference(**q))
        except pydantic.ValidationError as e:  # noqa: PERF203
            validation_errors += 1
            logger.error(f"❌ Validation error in conference: {e}")
            logger.debug(f"Invalid data: \n{yaml.dump(q, default_flow_style=False)}")
            continue

    if validation_errors > 0:
        logger.warning(f"⚠️  {validation_errors} conferences failed validation and were skipped")

    data = new_data
    logger.info(f"✅ {len(data)} conferences passed validation")

    # Split data by cfp
    logger.info("📂 Splitting data by CFP status")
    conf, tba, expired, legacy = split_data(data)
    logger.info(f"📊 Split results: {len(conf)} active, {len(tba)} TBA, {len(expired)} expired, {len(legacy)} legacy")

    # Sort data
    logger.info("🔄 Sorting conferences by CFP date")
    conf.sort(key=sort_by_cfp, reverse=True)
    conf.sort(key=sort_by_date_passed)
    tba.sort(key=sort_by_date, reverse=True)

    logger.info(f"💾 Writing {len(conf + tba)} active conferences to {out_current.name}")
    write_conference_yaml(conf + tba, out_current)

    expired.sort(key=sort_by_date, reverse=True)
    logger.info(f"📦 Writing {len(expired)} expired conferences to {out_archive.name}")
    write_conference_yaml(expired, out_archive)

    legacy.sort(key=sort_by_name, reverse=True)
    logger.info(f"🗂️  Writing {len(legacy)} legacy conferences to {out_legacy.name}")
    write_conference_yaml(legacy, out_legacy)

    logger.info("🎉 Conference data sorting and cleaning completed successfully")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sort and clean conference data.")
    parser.add_argument("--skip_links", action="store_true", help="Skip checking links", default=False)
    args = parser.parse_args()

    sort_data(skip_links=args.skip_links)
