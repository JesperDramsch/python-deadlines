
import datetime


dateformat = "%Y-%m-%d %H:%M:%S"
tba_words = ["tba", "tbd"]


def clean_dates(data):
    
    # Clean Up Dates
    for dates in ["start", "end"]:
            if isinstance(data[dates], str):
                data[dates] = datetime.datetime.strptime(data[dates], dateformat.split(" ")[0]).date()
    
    # Make deadlines 
    for datetimes in ["cfp", "workshop_deadline", "tutorial_deadline"]:
            if datetimes in data and data[datetimes].lower() not in tba_words:
                try:
                    tmp_time = datetime.datetime.strptime(data[datetimes], dateformat.split(" ")[0])
                    if tmp_time.hour == 0 and tmp_time.minute == 0:
                        tmp_time += datetime.timedelta(hours=23, minutes=59)
                    data[datetimes] = tmp_time.strftime(dateformat)
                except ValueError:
                    continue

    return data

def suffix(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')


def create_nice_date(data):
    if "date" in data and data["date"]:
        return data
    
    try:
        start = datetime.datetime.strptime(data["start"], dateformat.split(" ")[0])
        end = datetime.datetime.strptime(data["end"], dateformat.split(" ")[0])
    except TypeError:
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

    return data


