import re
from datetime import date
from pathlib import Path
from typing import Annotated

import pandas as pd
import yaml
from pydantic import BaseModel
from pydantic import HttpUrl
from pydantic import condate
from pydantic import confloat
from pydantic import conint
from pydantic import constr
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator

DatetimeString = Annotated[str, constr(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")]
PythonYear = Annotated[int, conint(ge=1989, le=3000)]
PythonDate = Annotated[date, condate(gt=date.fromisoformat("1989-01-01"))]
LatitudeFloat = Annotated[float, confloat(ge=-90, le=90)]
LongitudeFloat = Annotated[float, confloat(ge=-180, le=180)]


class Location(BaseModel):
    title: str | None = None
    latitude: LatitudeFloat
    longitude: LongitudeFloat

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if not v:
            raise ValueError("Location title is required")
        return v

    @model_validator(mode="after")
    def validate_latitude_longitude(self):
        msg = ""
        lat_round = round(self.latitude * 100000) / 100000
        lon_round = round(self.longitude * 100000) / 100000

        if lat_round == 0 and lon_round == 0:
            msg = f"Invalid latitude ({self.latitude}) or longitude ({self.longitude}), because it's the default 0, 0"
        elif lat_round == 44.93796 and lon_round == 7.54012:
            msg = f"Invalid latitude ({self.latitude}) or longitude ({self.longitude}) because it's 'None'"
        elif lat_round == 43.59047 and lon_round == 3.85951:
            msg = f"Invalid latitude ({self.latitude}) or longitude ({self.longitude}) because it's 'Online'"

        if msg:
            raise ValueError(msg)
        return self


class Conference(BaseModel):
    conference: str
    alt_name: str | None = None
    year: PythonYear
    link: HttpUrl
    cfp_link: HttpUrl | None = None
    cfp: DatetimeString
    cfp_ext: DatetimeString | None = None
    workshop_deadline: DatetimeString | None = None
    tutorial_deadline: DatetimeString | None = None
    timezone: str | None = None
    place: str
    extra_places: list[str] | None = None
    start: PythonDate
    end: PythonDate
    sponsor: HttpUrl | None = None
    finaid: HttpUrl | None = None
    twitter: str | None = None
    mastodon: HttpUrl | None = None
    bluesky: str | None = None
    youtube: HttpUrl | None = None
    sub: str
    note: str | None = None
    location: list[Location] | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start.year != self.end.year:
            raise ValueError("Are you sure this is a multi-year conference?")
        return self

    @model_validator(mode="after")
    def validate_years(self):
        if self.start > self.end:
            raise ValueError("The start date must be before the end date")
        return self

    @model_validator(mode="after")
    def validate_location_if_not_online(self):
        if "online" not in self.place.lower() and not self.location:
            raise ValueError("Location is required for in-person conferences")
        return self

    @field_validator("sub")
    @classmethod
    def validate_sub(cls, v):
        # open the _data/type.yml file and check if the submission type is valid
        with Path("_data", "types.yml").open(encoding="utf-8") as file:
            valid_types = [entry["sub"] for entry in yaml.safe_load(file)]

        for x in v.split(","):
            if x not in valid_types:
                raise ValueError("Invalid submission type")
        return v

    @field_validator("twitter")
    @classmethod
    def validate_twitter(cls, v):
        if v and v.startswith("@"):
            return v[1:]  # Remove the @ symbol
        return v

    @field_validator("conference")
    @classmethod
    def validate_title(cls, v):
        if v:
            # Remove years from the title
            return re.sub(r"\b(19|20)\d{2}\b", "", v).strip()
        return v

    @field_serializer("link", "cfp_link", "sponsor", "finaid", "mastodon", "youtube")
    def ser_url(self, value):
        return str(value)


def get_schema():
    """Load the schema from the schema.yml file and return it as a DataFrame.

    This is used to determine the order of and accepted keys in a conference item.
    """
    with Path("utils", "schema.yml").open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # Convert the YAML data to a Pandas DataFrame
    return pd.DataFrame.from_dict(data).drop(index=0)
