import datetime

dateformat = "%Y-%m-%d %H:%M:%S"
tba_words = ["tba", "tbd", "cancelled"]


def clean_dates(data):
    """Clean dates in the data.

    This function makes sure `start` and `end` dates are in the correct format.
    Then we go through the deadlines and make sure they contain a time signature.
    """
    # Clean Up Dates
    for dates in ["start", "end"]:
        if isinstance(data[dates], str):
            data[dates] = (
                datetime.datetime.strptime(data[dates], dateformat.split(" ")[0])
                .replace(tzinfo=datetime.timezone.utc)
                .date()
            )

    # Make deadlines
    for datetimes in ["cfp", "workshop_deadline", "tutorial_deadline"]:
        if datetimes not in data:
            # Check if we have this key
            continue
        if isinstance(data[datetimes], datetime.datetime):
            # If it's a datetime make it a string, because of timezones
            data[datetimes] = data[datetimes].strftime(dateformat)
        elif isinstance(data[datetimes], datetime.date):
            # If it's a date make it a string, because of timezones
            data[datetimes] = data[datetimes].strftime(dateformat.split(" ")[0])
        if data[datetimes].lower() not in tba_words:
            try:
                tmp_time = datetime.datetime.strptime(data[datetimes], dateformat.split(" ")[0]).replace(
                    tzinfo=datetime.timezone.utc,
                )
                if tmp_time.hour == 0 and tmp_time.minute == 0:
                    tmp_time += datetime.timedelta(hours=23, minutes=59)
                data[datetimes] = tmp_time.strftime(dateformat)
            except ValueError:
                continue

        if datetimes != "cfp" and data[datetimes] == data["cfp"]:
            # If the deadline is equal to the cfp, we don't need to add it
            # to the list of deadlines

            del data[datetimes]
            continue

    return data


def suffix(d):
    """Date utility to add ordinal suffix to a number."""
    return "th" if 11 <= (d % 100) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")


def create_nice_date(data):
    """Create a nice date string for the conference.

    This overwrites the written `date` field with a more human-readable preferred date.
    """
    try:
        # Handle string dates
        if isinstance(data["start"], str):
            start = datetime.datetime.strptime(data["start"], dateformat.split(" ")[0]).replace(
                tzinfo=datetime.timezone.utc,
            )
        else:
            # Assume it's already a date object
            start = data["start"]

        if isinstance(data["end"], str):
            end = datetime.datetime.strptime(data["end"], dateformat.split(" ")[0]).replace(
                tzinfo=datetime.timezone.utc,
            )
        else:
            # Assume it's already a date object
            end = data["end"]
    except (TypeError, ValueError):
        start = data["start"]
        end = data["end"]

    if start == end:
        tmp_date = start.strftime("%B %d, %Y")

        data["date"] = tmp_date[:-6] + suffix(start.day) + tmp_date[-6:]
    elif start.month == end.month:
        tmp_date = start.strftime("%B %d, %Y")

        data["date"] = tmp_date[:-6] + " - " + end.strftime("%d") + tmp_date[-6:]
    elif start.year == end.year:
        tmp_date = start.strftime("%B %d, %Y")
        data["date"] = tmp_date[:-6] + " - " + end.strftime("%B %d") + tmp_date[-6:]
    else:
        data["date"] = start.strftime("%B %d, %Y") + " - " + end.strftime("%B %d, %Y")

    data["date"] = data["date"].replace(" 0", " ")

    return data
