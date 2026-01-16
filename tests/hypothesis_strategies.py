"""Shared Hypothesis strategies for property-based tests.

This module provides reusable strategies for generating conference-like
test data. Import strategies from this module in topical test files.
"""

# Try to import hypothesis - strategies will be None if not available
try:
    from hypothesis import HealthCheck
    from hypothesis import assume
    from hypothesis import given
    from hypothesis import settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True

    # Conference name strategy - realistic conference names
    conference_name = st.from_regex(
        r"(Py|Django|Data|Web|Euro|US|Asia|Africa)[A-Z][a-z]{3,10}( Conference| Summit| Symposium)?",
        fullmatch=True,
    )

    # Year strategy - valid conference years
    valid_year = st.integers(min_value=1990, max_value=2050)

    # Coordinate strategy - valid lat/lon excluding special invalid values
    valid_latitude = st.floats(
        min_value=-89.99,
        max_value=89.99,
        allow_nan=False,
        allow_infinity=False,
    ).filter(
        lambda x: abs(x) > 0.001,
    )  # Exclude near-zero

    valid_longitude = st.floats(
        min_value=-179.99,
        max_value=179.99,
        allow_nan=False,
        allow_infinity=False,
    ).filter(
        lambda x: abs(x) > 0.001,
    )  # Exclude near-zero

    # URL strategy
    valid_url = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,6}/[a-z0-9/]*", fullmatch=True)

    # CFP datetime strategy
    cfp_datetime = st.from_regex(
        r"20[2-4][0-9]-[01][0-9]-[0-3][0-9] [0-2][0-9]:[0-5][0-9]:[0-5][0-9]",
        fullmatch=True,
    )

except ImportError:
    HYPOTHESIS_AVAILABLE = False
    HealthCheck = None
    assume = None
    given = None
    settings = None
    st = None
    conference_name = None
    valid_year = None
    valid_latitude = None
    valid_longitude = None
    valid_url = None
    cfp_datetime = None
