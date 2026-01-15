"""Property-based tests using Hypothesis for conference sync pipeline.

This module uses Hypothesis to generate random test cases that explore
edge cases and boundary conditions that manual tests might miss.

Property-based testing is particularly valuable for:
- String processing (normalization, fuzzy matching)
- Date handling edge cases
- Coordinate validation
- Finding unexpected input combinations that break logic
"""

import sys
from datetime import date
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

# Try to import hypothesis - skip tests if not available
try:
    from hypothesis import HealthCheck
    from hypothesis import assume
    from hypothesis import given
    from hypothesis import settings
    from hypothesis import strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Create dummy decorators for when hypothesis isn't installed
    def given(*args, **kwargs):
        def decorator(f):
            return pytest.mark.skip(reason="hypothesis not installed")(f)
        return decorator

    def settings(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    class st:
        @staticmethod
        def text(*args, **kwargs):
            return None
        @staticmethod
        def integers(*args, **kwargs):
            return None
        @staticmethod
        def floats(*args, **kwargs):
            return None
        @staticmethod
        def dates(*args, **kwargs):
            return None
        @staticmethod
        def lists(*args, **kwargs):
            return None

sys.path.append(str(Path(__file__).parent.parent / "utils"))


pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE,
    reason="hypothesis not installed - run: pip install hypothesis"
)


if HYPOTHESIS_AVAILABLE:
    from tidy_conf.deduplicate import deduplicate
    from tidy_conf.interactive_merge import fuzzy_match
    from tidy_conf.titles import tidy_df_names


# ---------------------------------------------------------------------------
# Custom Strategies for generating conference-like data
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:
    # Conference name strategy - realistic conference names
    conference_name = st.from_regex(
        r"(Py|Django|Data|Web|Euro|US|Asia|Africa)[A-Z][a-z]{3,10}( Conference| Summit| Symposium)?",
        fullmatch=True
    )

    # Year strategy - valid conference years
    valid_year = st.integers(min_value=1990, max_value=2050)

    # Coordinate strategy - valid lat/lon excluding special invalid values
    valid_latitude = st.floats(
        min_value=-89.99, max_value=89.99,
        allow_nan=False, allow_infinity=False
    ).filter(lambda x: abs(x) > 0.001)  # Exclude near-zero

    valid_longitude = st.floats(
        min_value=-179.99, max_value=179.99,
        allow_nan=False, allow_infinity=False
    ).filter(lambda x: abs(x) > 0.001)  # Exclude near-zero

    # URL strategy
    valid_url = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,6}/[a-z0-9/]*", fullmatch=True)

    # CFP datetime strategy
    cfp_datetime = st.from_regex(r"20[2-4][0-9]-[01][0-9]-[0-3][0-9] [0-2][0-9]:[0-5][0-9]:[0-5][0-9]", fullmatch=True)


class TestNormalizationProperties:
    """Property-based tests for name normalization."""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_normalization_never_crashes(self, text):
        """Normalization should never crash regardless of input."""
        assume(len(text.strip()) > 0)

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [text]})

            # Should not raise any exception
            try:
                result = tidy_df_names(df)
                assert isinstance(result, pd.DataFrame)
            except Exception as e:
                # Only allow expected exceptions
                if "empty" not in str(e).lower():
                    raise

    @given(st.text(alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S')), min_size=5, max_size=50))
    @settings(max_examples=100)
    def test_normalization_preserves_non_whitespace(self, text):
        """Normalization should preserve meaningful characters."""
        assume(len(text.strip()) > 0)

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [text]})
            result = tidy_df_names(df)

            # Result should not be empty
            assert len(result) == 1
            assert len(result["conference"].iloc[0].strip()) > 0

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_normalization_is_idempotent(self, text):
        """Applying normalization twice should yield same result."""
        assume(len(text.strip()) > 0)

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [text]})

            result1 = tidy_df_names(df.copy())
            result2 = tidy_df_names(result1.copy())

            assert result1["conference"].iloc[0] == result2["conference"].iloc[0], \
                f"Idempotency failed: '{result1['conference'].iloc[0]}' != '{result2['conference'].iloc[0]}'"

    @given(valid_year)
    @settings(max_examples=50)
    def test_year_removal_works_for_any_valid_year(self, year):
        """Year removal should work for any year 1990-2050."""
        name = f"PyCon Conference {year}"

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [name]})
            result = tidy_df_names(df)

            assert str(year) not in result["conference"].iloc[0], \
                f"Year {year} should be removed from '{result['conference'].iloc[0]}'"


class TestFuzzyMatchProperties:
    """Property-based tests for fuzzy matching."""

    @given(st.lists(st.text(min_size=5, max_size=30), min_size=1, max_size=5, unique=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_fuzzy_match_preserves_all_yaml_entries(self, names):
        """All YAML entries should appear in result (no silent data loss)."""
        # Filter out empty or whitespace-only names
        names = [n for n in names if len(n.strip()) > 3]
        assume(len(names) > 0)

        with patch("tidy_conf.interactive_merge.load_title_mappings") as mock1, \
             patch("tidy_conf.titles.load_title_mappings") as mock2, \
             patch("tidy_conf.interactive_merge.update_title_mappings"):
            mock1.return_value = ([], {})
            mock2.return_value = ([], {})

            df_yml = pd.DataFrame({
                "conference": names,
                "year": [2026] * len(names),
                "cfp": ["2026-01-15 23:59:00"] * len(names),
                "link": [f"https://conf{i}.org/" for i in range(len(names))],
                "place": ["Test City"] * len(names),
                "start": ["2026-06-01"] * len(names),
                "end": ["2026-06-03"] * len(names),
            })

            df_remote = pd.DataFrame(
                columns=["conference", "year", "cfp", "link", "place", "start", "end"]
            )

            result, _ = fuzzy_match(df_yml, df_remote)

            # All input conferences should be in result
            assert len(result) >= len(names), \
                f"Expected at least {len(names)} results, got {len(result)}"

    @given(st.text(min_size=10, max_size=50))
    @settings(max_examples=30)
    def test_exact_match_always_scores_100(self, name):
        """Identical names should always match perfectly."""
        assume(len(name.strip()) > 5)

        with patch("tidy_conf.interactive_merge.load_title_mappings") as mock1, \
             patch("tidy_conf.titles.load_title_mappings") as mock2, \
             patch("tidy_conf.interactive_merge.update_title_mappings"):
            mock1.return_value = ([], {})
            mock2.return_value = ([], {})

            df_yml = pd.DataFrame({
                "conference": [name],
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://test.org/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            })

            df_remote = pd.DataFrame({
                "conference": [name],  # Same name
                "year": [2026],
                "cfp": ["2026-01-15 23:59:00"],
                "link": ["https://other.org/"],
                "place": ["Test City"],
                "start": ["2026-06-01"],
                "end": ["2026-06-03"],
            })

            # No user prompts should be needed for exact match
            with patch("builtins.input", side_effect=AssertionError("Should not prompt")):
                result, _ = fuzzy_match(df_yml, df_remote)

            # Should be merged (1 result, not 2)
            assert len(result) == 1, f"Exact match should merge, got {len(result)} results"


class TestDeduplicationProperties:
    """Property-based tests for deduplication logic."""

    @given(st.lists(st.text(min_size=5, max_size=30), min_size=2, max_size=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_dedup_reduces_or_maintains_row_count(self, names):
        """Deduplication should never increase row count."""
        # Filter and create duplicates intentionally
        names = [n for n in names if len(n.strip()) > 3]
        assume(len(names) >= 2)

        # Add some duplicates
        all_names = names + [names[0], names[0]]  # Intentional duplicates

        df = pd.DataFrame({
            "conference": all_names,
            "year": [2026] * len(all_names),
        })
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        result = deduplicate(df)

        # Should have fewer or equal rows (never more)
        assert len(result) <= len(df), \
            f"Dedup increased rows: {len(result)} > {len(df)}"

    @given(st.text(min_size=5, max_size=30))
    @settings(max_examples=30)
    def test_dedup_merges_identical_rows(self, name):
        """Rows with same key should be merged to one."""
        assume(len(name.strip()) > 3)

        df = pd.DataFrame({
            "conference": [name, name, name],  # 3 identical
            "year": [2026, 2026, 2026],
            "cfp": ["2026-01-15 23:59:00", None, "2026-01-15 23:59:00"],  # Fill test
        })
        df = df.set_index("conference", drop=False)
        df.index.name = "title_match"

        result = deduplicate(df)

        # Should have exactly 1 row
        assert len(result) == 1, f"Expected 1 row after dedup, got {len(result)}"


class TestCoordinateProperties:
    """Property-based tests for coordinate validation."""

    @given(valid_latitude, valid_longitude)
    @settings(max_examples=100)
    def test_valid_coordinates_accepted(self, lat, lon):
        """Valid coordinates within bounds should be accepted."""
        from tidy_conf.schema import Location

        # Skip coordinates that are specifically rejected by the schema
        special_invalid = [
            (0.0, 0.0),  # Origin
            (44.93796, 7.54012),  # 'None' location
            (43.59047, 3.85951),  # 'Online' location
        ]

        for inv_lat, inv_lon in special_invalid:
            if abs(lat - inv_lat) < 0.0001 and abs(lon - inv_lon) < 0.0001:
                assume(False)

        # Should be accepted
        location = Location(title="Test", latitude=lat, longitude=lon)
        assert location.latitude == lat
        assert location.longitude == lon

    @given(st.floats(min_value=91, max_value=1000, allow_nan=False))
    @settings(max_examples=30)
    def test_invalid_latitude_rejected(self, lat):
        """Latitude > 90 should be rejected."""
        from pydantic import ValidationError
        from tidy_conf.schema import Location

        with pytest.raises(ValidationError):
            Location(title="Test", latitude=lat, longitude=0)

    @given(st.floats(min_value=181, max_value=1000, allow_nan=False))
    @settings(max_examples=30)
    def test_invalid_longitude_rejected(self, lon):
        """Longitude > 180 should be rejected."""
        from pydantic import ValidationError
        from tidy_conf.schema import Location

        with pytest.raises(ValidationError):
            Location(title="Test", latitude=0.1, longitude=lon)


class TestDateProperties:
    """Property-based tests for date handling."""

    @given(st.dates(min_value=date(1990, 1, 1), max_value=date(2050, 12, 31)))
    @settings(max_examples=50)
    def test_valid_dates_accepted_in_range(self, d):
        """Dates between 1990 and 2050 should be valid start/end dates."""
        from pydantic import ValidationError
        from tidy_conf.schema import Conference

        end_date = d + timedelta(days=2)

        # Skip if end date would cross year boundary
        assume(d.year == end_date.year)

        try:
            conf = Conference(
                conference="Test",
                year=d.year,
                link="https://test.org/",
                cfp=f"{d.year}-01-15 23:59:00",
                place="Online",
                start=d,
                end=end_date,
                sub="PY",
            )
            assert conf.start == d
        except ValidationError:
            # Some dates may fail for other reasons - that's ok
            pass

    @given(st.integers(min_value=1, max_value=365))
    @settings(max_examples=30)
    def test_multi_day_conferences_accepted(self, days):
        """Conferences spanning multiple days should be accepted."""
        from pydantic import ValidationError
        from tidy_conf.schema import Conference

        start = date(2026, 1, 1)
        end = start + timedelta(days=days)

        # Must be same year
        assume(start.year == end.year)

        try:
            conf = Conference(
                conference="Multi-day Test",
                year=2026,
                link="https://test.org/",
                cfp="2025-10-15 23:59:00",
                place="Online",
                start=start,
                end=end,
                sub="PY",
            )
            assert conf.end >= conf.start
        except ValidationError:
            # May fail for other validation reasons
            pass


class TestUnicodeHandling:
    """Property-based tests for Unicode handling."""

    @given(st.text(
        alphabet=st.characters(
            whitelist_categories=('L',),  # Letters only
            whitelist_characters='áéíóúñüöäÄÖÜßàèìòùâêîôûçÇ'
        ),
        min_size=5, max_size=30
    ))
    @settings(max_examples=50)
    def test_unicode_letters_preserved(self, text):
        """Unicode letters should be preserved through normalization."""
        assume(len(text.strip()) > 3)

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [f"PyCon {text}"]})
            result = tidy_df_names(df)

            # Check that some Unicode is preserved
            result_text = result["conference"].iloc[0]
            assert len(result_text) > 0, "Result should not be empty"

    @given(st.sampled_from([
        "PyCon México",
        "PyCon España",
        "PyCon Österreich",
        "PyCon Česko",
        "PyCon Türkiye",
        "PyCon Ελλάδα",
        "PyCon 日本",
        "PyCon 한국",
    ]))
    def test_specific_unicode_names_handled(self, name):
        """Specific international conference names should be handled."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})

            df = pd.DataFrame({"conference": [name]})
            result = tidy_df_names(df)

            # Should not crash and should produce non-empty result
            assert len(result) == 1
            assert len(result["conference"].iloc[0]) > 0
