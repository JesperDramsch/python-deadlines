import re

from iso3166 import countries
from tidy_conf.yaml import load_title_mappings
from tqdm import tqdm

# Build country code mappings (both directions)
# e.g., "PL" -> "Poland", "Poland" -> "PL"
COUNTRY_CODE_TO_NAME = {}
COUNTRY_NAME_TO_CODE = {}

# Custom mappings for common variations used in conference names
CUSTOM_COUNTRY_MAPPINGS = {
    "US": "USA",
    "United States": "USA",
    "United States of America": "USA",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "CZ": "Czechia",
    "Czech Republic": "Czechia",
    "NZ": "New Zealand",
    "KR": "South Korea",
    "Korea": "South Korea",
    "ZA": "South Africa",
}

# Load ISO 3166 country codes
for country in countries:
    code = country.alpha2
    name = country.name
    # Handle common name variations
    if "," in name:
        # e.g., "Korea, Republic of" -> "Korea"
        short_name = name.split(",")[0]
        COUNTRY_CODE_TO_NAME[code] = short_name
        COUNTRY_NAME_TO_CODE[short_name] = code
    else:
        COUNTRY_CODE_TO_NAME[code] = name
        COUNTRY_NAME_TO_CODE[name] = code

# Apply custom overrides
for code, name in CUSTOM_COUNTRY_MAPPINGS.items():
    COUNTRY_CODE_TO_NAME[code] = name
    if name not in COUNTRY_NAME_TO_CODE:
        COUNTRY_NAME_TO_CODE[name] = code


def tidy_titles(data):
    """Tidy up conference titles by replacing misspellings and alternative names."""
    spellings, alt_names = load_title_mappings()
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        if "conference" in q:
            low_conf = q["conference"].lower().strip()
            # Replace common misspellings
            for spelling in spellings:
                if spelling.lower() in low_conf:
                    # Find the index in the lower case string and replace it in the original string
                    index = low_conf.index(spelling.lower())
                    q["conference"] = q["conference"][:index] + spelling + q["conference"][index + len(spelling) :]

            for key, values in alt_names.items():
                global_name = values.get("global")
                variations = values.get("variations", [])
                regexes = values.get("regexes", [])

                # Match global name
                if global_name and global_name.lower().strip() == low_conf:
                    if "alt_name" not in q:
                        q["alt_name"] = global_name.strip()
                    continue

                # Match variations
                for variation in variations:
                    if (
                        (variation.lower().strip() == low_conf)
                        or (variation.lower().strip().replace(" ", "") == low_conf)
                        or (variation.lower().strip().replace("Conference", "") == low_conf)
                    ):
                        if "alt_name" not in q and q["conference"].strip() != key:
                            q["alt_name"] = q["conference"].strip()
                        q["conference"] = key.strip()
                        break

                # Match regex patterns
                for regex in regexes:
                    if re.match(regex, low_conf):
                        if "alt_name" not in q and q["conference"].strip() != key:
                            q["alt_name"] = q["conference"].strip()
                        q["conference"] = key.strip()
                        break

            data[i] = q
    return data


def expand_country_codes(name):
    """Expand country codes at the end of conference names to full country names.

    Examples
    --------
        "PyCon PL" -> "PyCon Poland"
        "PyCon DE" -> "PyCon Germany"
        "PyData Berlin" -> "PyData Berlin" (unchanged, no country code)
    """
    if not name or not isinstance(name, str):
        return name

    # Split into words
    words = name.strip().split()
    if not words:
        return name

    # Check if last word is a country code (uppercase, 2-3 letters)
    last_word = words[-1]
    if len(last_word) <= 3 and last_word.isupper() and last_word in COUNTRY_CODE_TO_NAME:
        words[-1] = COUNTRY_CODE_TO_NAME[last_word]
        return " ".join(words)

    return name


def normalize_conference_name(name: str, known_mappings: dict | None = None) -> str:
    """Normalize a single conference name to a canonical form.

    This is the single source of truth for conference name normalization.
    Both DataFrame-level normalization (tidy_df_names) and individual lookups
    should use this function to ensure consistency.

    Parameters
    ----------
    name : str
        Conference name to normalize
    known_mappings : dict, optional
        Mapping of known variations to canonical names. If None, will be loaded.

    Returns
    -------
    str
        Normalized conference name
    """
    if not name or not isinstance(name, str):
        return name if isinstance(name, str) else ""

    # Load known mappings if not provided
    if known_mappings is None:
        _, known_mappings = load_title_mappings(reverse=True)

    # Define regex patterns (same as tidy_df_names)
    regex_year = re.compile(r"\b\s*(19|20)\d{2}\s*\b")
    regex_py = re.compile(r"\b(Python|PyCon)\b")

    result = name

    # Remove years from conference names (replace with space to avoid concatenation)
    result = regex_year.sub(" ", result)

    # Add a space after Python or PyCon
    result = regex_py.sub(r" \1 ", result)

    # Replace non-word characters like +
    result = re.sub(r"[\+]", " ", result)

    # Replace the word Conference
    result = re.sub(r"\bConf\b", "Conference", result)

    # Remove extra spaces
    result = re.sub(r"\s+", " ", result)

    # Remove leading and trailing whitespace
    result = result.strip()

    # Apply known mappings FIRST (mappings may contain unexpanded country codes)
    if result in known_mappings:
        result = known_mappings[result]

    # Expand country codes to full names AFTER mappings
    # This ensures idempotency: normalize(normalize(x)) == normalize(x)
    result = expand_country_codes(result)

    # Final cleanup
    result = result.strip()

    return result


def tidy_df_names(df):
    """Tidy up the conference names in a consistent way.

    Normalizes conference names by:
    1. Removing years from names
    2. Expanding country codes to full names (e.g., "PyCon PL" -> "PyCon Poland")
    3. Normalizing spacing and punctuation
    4. Applying known mappings from titles.yml

    Uses normalize_conference_name() internally for consistency.
    """
    # Load known title mappings once for efficiency
    _, known_mappings = load_title_mappings(reverse=True)

    # Apply normalization using the shared function
    df = df.copy()
    df.loc[:, "conference"] = df["conference"].apply(
        lambda x: normalize_conference_name(x, known_mappings),
    )

    return df
