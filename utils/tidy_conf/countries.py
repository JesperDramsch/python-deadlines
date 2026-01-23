"""Centralized country mappings for conference data processing.

This module is the SINGLE SOURCE OF TRUTH for all country-related mappings.
All other modules should import from here to ensure consistency.

Design decisions:
- We use SHORT forms (US, UK) as the canonical display format for places
- ISO 3166 alpha-3 codes (USA, GBR) are used for CSV Country column
- Conference names expand 2-letter codes to full names (PyCon US -> PyCon United States)
"""

import iso3166

# =============================================================================
# CANONICAL SHORT NAMES
# =============================================================================
# These are the preferred short names used in the 'place' field
# e.g., "San Francisco, US" or "London, UK"

CANONICAL_COUNTRY_NAMES = {
    "US": "US",  # United States - always use "US"
    "UK": "UK",  # United Kingdom - always use "UK"
    "Czechia": "Czechia",  # Not "Czech Republic"
}

# =============================================================================
# DISPLAY NAME MAPPINGS (for conference names)
# =============================================================================
# Maps country codes and variations to full display names for conference titles
# e.g., "PyCon US" -> "PyCon United States"

COUNTRY_DISPLAY_NAMES = {
    "US": "United States",
    "USA": "United States",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "CZ": "Czechia",
    "NZ": "New Zealand",
    "KR": "South Korea",
    "ZA": "South Africa",
}

# =============================================================================
# NORMALIZATION MAPPINGS
# =============================================================================
# Maps various country name formats to canonical short form
# Used when normalizing place fields during merge operations

COUNTRY_NORMALIZATION = {
    # US variations -> US
    "United States": "US",
    "United States of America": "US",
    "USA": "US",
    # UK variations -> UK
    "United Kingdom": "UK",
    "United Kingdom of Great Britain and Northern Ireland": "UK",
    "Great Britain": "UK",
    "Britain": "UK",
    "England": "UK",
    "Scotland": "UK",
    "Wales": "UK",
    "GB": "UK",
    # Czechia variations
    "Czech Republic": "Czechia",
    # Korea variations
    "Korea": "South Korea",
    "Korea, Republic of": "South Korea",
}

# =============================================================================
# ISO 3166 ALPHA-3 LOOKUP ALIASES
# =============================================================================
# Maps common country names to ISO 3166 official names for alpha-3 lookup
# The iso3166 library requires exact official names

ISO_COUNTRY_ALIASES = {
    # United States variations
    "USA": "UNITED STATES OF AMERICA",
    "US": "UNITED STATES OF AMERICA",
    "UNITED STATES": "UNITED STATES OF AMERICA",
    # United Kingdom variations
    "UK": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "UNITED KINGDOM": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "GREAT BRITAIN": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "BRITAIN": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "ENGLAND": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "SCOTLAND": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "WALES": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    "NORTHERN IRELAND": "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND",
    # Other common variations
    "CZECHIA": "CZECHIA",
    "CZECH REPUBLIC": "CZECHIA",
    "KOREA": "KOREA, REPUBLIC OF",
    "SOUTH KOREA": "KOREA, REPUBLIC OF",
    "RUSSIA": "RUSSIAN FEDERATION",
    "VIETNAM": "VIET NAM",
    "TAIWAN": "TAIWAN, PROVINCE OF CHINA",
    "IRAN": "IRAN, ISLAMIC REPUBLIC OF",
    "SYRIA": "SYRIAN ARAB REPUBLIC",
    "BOLIVIA": "BOLIVIA, PLURINATIONAL STATE OF",
    "VENEZUELA": "VENEZUELA, BOLIVARIAN REPUBLIC OF",
    "TANZANIA": "TANZANIA, UNITED REPUBLIC OF",
    "MOLDOVA": "MOLDOVA, REPUBLIC OF",
    "LAOS": "LAO PEOPLE'S DEMOCRATIC REPUBLIC",
    "PALESTINE": "PALESTINE, STATE OF",
    "THE NETHERLANDS": "NETHERLANDS",
    "HOLLAND": "NETHERLANDS",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def normalize_country_name(country: str) -> str:
    """Normalize a country name to its canonical short form.

    Parameters
    ----------
    country : str
        Country name to normalize (e.g., "United States of America", "USA", "US")

    Returns
    -------
    str
        Canonical short form (e.g., "US", "UK", "Czechia")
    """
    if not country or not isinstance(country, str):
        return country if isinstance(country, str) else ""

    country = country.strip()

    # Check if it's already canonical
    if country in CANONICAL_COUNTRY_NAMES:
        return country

    # Try normalization mapping
    if country in COUNTRY_NORMALIZATION:
        return COUNTRY_NORMALIZATION[country]

    # Try case-insensitive normalization
    country_upper = country.upper()
    for key, value in COUNTRY_NORMALIZATION.items():
        if key.upper() == country_upper:
            return value

    return country


def get_country_display_name(code: str) -> str:
    """Get the full display name for a country code.

    Used for expanding country codes in conference names.

    Parameters
    ----------
    code : str
        Country code (e.g., "US", "UK", "DE")

    Returns
    -------
    str
        Full display name (e.g., "United States", "United Kingdom", "Germany")
    """
    if not code or not isinstance(code, str):
        return code if isinstance(code, str) else ""

    code = code.strip()

    # Check custom display names first
    if code in COUNTRY_DISPLAY_NAMES:
        return COUNTRY_DISPLAY_NAMES[code]

    # Fall back to ISO 3166 lookup
    try:
        country = iso3166.countries.get(code)
        if country:
            name = country.name
            # Handle comma-separated names like "Korea, Republic of"
            if "," in name:
                return name.split(",")[0]
            return name
    except (KeyError, AttributeError):
        pass

    return code


def get_country_alpha3(country_name: str) -> str:
    """Get ISO 3166-1 alpha-3 country code from a country name.

    Parameters
    ----------
    country_name : str
        The country name to look up (e.g., "United States", "USA", "Germany")

    Returns
    -------
    str
        ISO 3166-1 alpha-3 code if found (e.g., "USA", "DEU"),
        otherwise returns the original country name to preserve data
    """
    if not country_name or not isinstance(country_name, str):
        return ""

    name_upper = country_name.strip().upper()

    if not name_upper:
        return ""

    # Try direct lookup first
    country = iso3166.countries_by_name.get(name_upper)
    if country:
        return country.alpha3

    # Try lookup using aliases
    if name_upper in ISO_COUNTRY_ALIASES:
        aliased_name = ISO_COUNTRY_ALIASES[name_upper]
        country = iso3166.countries_by_name.get(aliased_name)
        if country:
            return country.alpha3

    # Fallback: return original country name to preserve data
    return country_name.strip()


# =============================================================================
# BUILD COUNTRY CODE MAPPINGS
# =============================================================================
# These dictionaries are used by titles.py for conference name expansion

COUNTRY_CODE_TO_NAME = {}
COUNTRY_NAME_TO_CODE = {}


def _build_country_mappings():
    """Build the country code mappings from ISO 3166 and custom overrides."""
    global COUNTRY_CODE_TO_NAME, COUNTRY_NAME_TO_CODE

    # First, load ISO 3166 country codes
    for country in iso3166.countries:
        code = country.alpha2
        name = country.name
        # Handle common name variations (e.g., "Korea, Republic of" -> "Korea")
        if "," in name:
            short_name = name.split(",")[0]
            COUNTRY_CODE_TO_NAME[code] = short_name
            COUNTRY_NAME_TO_CODE[short_name] = code
        else:
            COUNTRY_CODE_TO_NAME[code] = name
            COUNTRY_NAME_TO_CODE[name] = code

    # Apply custom overrides from COUNTRY_DISPLAY_NAMES
    # This ensures codes like "US" map to "United States" not "United States of America"
    for code, name in COUNTRY_DISPLAY_NAMES.items():
        COUNTRY_CODE_TO_NAME[code] = name
        if name not in COUNTRY_NAME_TO_CODE:
            COUNTRY_NAME_TO_CODE[name] = code

    # Also add entries for common variations pointing to canonical codes
    for variation, canonical in COUNTRY_NORMALIZATION.items():
        if variation not in COUNTRY_CODE_TO_NAME:
            # Map variations to their display names via canonical form
            if canonical in COUNTRY_CODE_TO_NAME:
                COUNTRY_CODE_TO_NAME[variation] = COUNTRY_CODE_TO_NAME[canonical]


# Build mappings on module import
_build_country_mappings()
