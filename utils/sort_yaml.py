#!/usr/bin/env python3
# coding: utf-8

# Sort and Clean conference data.
# It writes to `"prefix"data.yml`, copy those to the conference.yml after screening.

import datetime
import pdb
import sys
import time
import urllib
from builtins import input
from pathlib import Path
from shutil import copyfile

import pytz
import requests
import yaml
from tqdm import tqdm

sys.path.append(".")
from utils import pretty_print, ordered_dump, Loader, get_schema
from date_magic import clean_dates, create_nice_date

dateformat = "%Y-%m-%d %H:%M:%S"
tba_words = ["tba", "tbd"]


def sort_by_cfp(data):
    return pytz.utc.normalize(
        datetime.datetime.strptime(data["cfp"], dateformat).replace(
            tzinfo=pytz.timezone(
                data.get("timezone", "AoE")
                .replace("AoE", "Etc/GMT+12")
                .replace("UTC+", "Etc/GMT-")
                .replace("UTC-", "Etc/GMT+")
            )
        )
    ).strftime(dateformat)


def sort_by_date_passed(data):
    right_now = datetime.datetime.utcnow().replace(microsecond=0).strftime(dateformat)
    return sort_by_cfp(data) < right_now


def order_keywords(data):
    schema = get_schema().columns.tolist()
    new_dict = {}
    for key in schema:
        if key in data:
            new_dict[key] = data[key]
    return new_dict


def split_data(data):
    conf, tba, expired = [], [], []
    for q in tqdm(data):
        if q.get(
            "end", datetime.datetime.utcnow().replace(microsecond=0).date()
        ) < datetime.datetime.utcnow().replace(
            microsecond=0
        ).date() - datetime.timedelta(
            days=37
        ):
            expired.append(q)
            continue

        q = clean_dates(q)
        q = create_nice_date(q)

        try:
            if q["cfp"].lower() in tba_words:
                tba.append(q)
            else:
                if " " not in q["cfp"]:
                    q["cfp"] += " 23:59:00"
                conf.append(q)
        except:
            print(data["cfp"].lower(), tba_words)
    return conf, tba, expired


def add_latlon(data):
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        if ("location" in q) or ("place" not in q) or ("online" in q["place"].lower()):
            continue
        else:
            url = (
                "https://nominatim.openstreetmap.org/search/"
                + urllib.parse.quote(q["place"])
                + "?format=json"
            )
            response = requests.get(url).json()
            if response:
                data[i]["location"] = {}
                data[i]["location"]["latitude"] = float(response[0]["lat"])
                data[i]["location"]["longitude"] = float(response[0]["lon"])
                time.sleep(2)
    return data


# Sort:
def sort_data(base="", prefix=""):
    url = Path(base, "_data", "conferences.yml")
    out_url = Path(base, "_data", f"{prefix}conferences.yml")
    archive = Path(base, "_data", "archive.yml")
    out_archive = Path(base, "_data", f"{prefix}archive.yml")

    with open(url, "r") as stream:
        try:
            data = yaml.load(stream, Loader=Loader)

            print("Initial Sorting:")
            for i, q in enumerate(data.copy()):
                print(q["cfp"], " - ", q["title"])
                data[i] = order_keywords(q)

            print("\n\n")

            # Geocode Data
            print("Adding Lat Lon from Place")
            data = add_latlon(data)

            # Split data by cfp
            print("Splitting conferences, tba, and archive")
            conf, tba, expired = split_data(data)

            # just sort:
            conf.sort(key=sort_by_cfp, reverse=True)
            pretty_print("Date Sorting:", conf, tba, expired)
            conf.sort(key=sort_by_date_passed)
            pretty_print(
                "Date and Passed Deadline Sorting with tba:", conf, tba, expired
            )

            with open(out_url, "w") as outfile:
                for line in ordered_dump(
                    conf + tba,
                    Dumper=yaml.SafeDumper,
                    default_flow_style=False,
                    explicit_start=True,
                ).splitlines():
                    outfile.write(line.replace("- title:", "\n- title:"))
                    outfile.write("\n")
        except yaml.YAMLError as exc:
            print(exc)

    with open(archive, "r") as stream:
        try:
            data = yaml.load(stream, Loader=Loader)

            data += expired

            data.sort(key=sort_by_cfp, reverse=True)
            data = add_latlon(data)

            pretty_print("New archive:", data)
            with open(out_archive, "w") as outfile:
                for line in ordered_dump(
                    data,
                    Dumper=yaml.SafeDumper,
                    default_flow_style=False,
                    explicit_start=True,
                ).splitlines():
                    outfile.write(line.replace("- title:", "\n- title:"))
                    outfile.write("\n")
        except yaml.YAMLError as exc:
            print(exc)


if __name__ == "__main__":
    sort_data()
