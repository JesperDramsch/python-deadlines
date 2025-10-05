import sys
import time
from urllib import parse as urllib_parse

import requests
from tqdm import tqdm

try:
    sys.path.append("..")
    from logging_config import get_tqdm_logger
except ImportError:
    from ..logging_config import get_tqdm_logger  # noqa: TID252

# Constants
GEOCODING_SLEEP_TIME = 2  # Seconds to sleep between geocoding requests (respects rate limits)


def add_latlon(data: list[dict]) -> list[dict]:
    """Add latitude and longitude to the data.

    Parameters
    ----------
    data : list[dict]
        List of conference dictionaries to add geolocation data to

    Returns
    -------
    list[dict]
        List with added latitude and longitude information
    """
    logger = get_tqdm_logger(__name__)

    # Cache for locations
    cache = {}
    # Copy of data for unlocated conferences
    data_copy = []

    logger.debug(f"Processing geolocation for {len(data)} conferences")

    # Go through the data and check if the location is already in the cache
    for i, q in tqdm(enumerate(data), total=len(data)):
        if ("place" not in q) or ("online" in q["place"].lower()):
            # Ignore online conferences
            continue
        if "location" in q:
            # If location is already present, add it to the cache
            cache[q["place"]] = q["location"][0]
            # continue
        else:
            # Add to the copy if location is not present for speed
            data_copy.append((i, q))

    # Go through the copy and get the latitude and longitude
    for i, q in tqdm(data_copy):
        # Get a shorter location
        try:
            q["place"] = q["place"].split(",")[0].strip() + ", " + q["place"].split(",")[-1].strip()
        except IndexError:
            logger.error(f"IndexError processing place: {q['place']}")

        # Check if the location is already in the cache
        places = [q["place"]]
        if "extra_places" in q:
            places += q["extra_places"]

        new_location = []
        for place in places:
            place = place.strip()
            # Skip online places in extra_places too
            if "online" in place.lower():
                continue
            if place in cache and cache[place] is not None:
                new_location += [
                    {
                        "title": f'{q["conference"]} {q["year"]}',
                        "latitude": cache[place]["latitude"],
                        "longitude": cache[place]["longitude"],
                    },
                ]

            else:
                headers = {"User-Agent": "Pythondeadlin.es Location Search/0.1 (https://pythondeadlin.es)"}
                # Get the location from Openstreetmaps
                url = "https://nominatim.openstreetmap.org/search" + "?format=json&q=" + urllib_parse.quote(place)
                response = requests.get(url, timeout=10, headers=headers)

                if response:
                    try:
                        response_json = response.json()
                        new_location += [
                            {
                                "title": f'{q["conference"]} {q["year"]}',
                                "latitude": float(response_json[0]["lat"]),
                                "longitude": float(response_json[0]["lon"]),
                            },
                        ]
                        cache[place] = new_location[-1]
                    except (IndexError, ValueError, KeyError) as e:
                        cache[place] = None
                        logger.warning(f"Error processing response from OpenStreetMap for {place}: {e}")
                    time.sleep(GEOCODING_SLEEP_TIME)
                else:
                    cache[place] = None
                    logger.warning(f"No response from OpenStreetMap for {q['place']}")
        else:
            if new_location:
                data[i]["location"] = new_location
    return data
