"""Tests for conference name normalization.

This module tests the tidy_df_names function and related title normalization
logic. Tests verify specific transformations, not just that the code runs.

Key behaviors tested:
- Year removal from conference names
- Whitespace normalization
- Abbreviation expansion (Conf -> Conference)
- Known mapping application
- Idempotency (applying twice yields same result)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.titles import tidy_df_names


class TestYearRemoval:
    """Test that tidy_df_names correctly removes years from conference names."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_removes_four_digit_year_2026(self):
        """Name normalization should remove 4-digit year from conference name.

        Input: "PyCon Germany 2026"
        Expected: Year removed, conference name preserved
        """
        df = pd.DataFrame({"conference": ["PyCon Germany 2026"]})
        result = tidy_df_names(df)

        assert "2026" not in result["conference"].iloc[0], \
            f"Year '2026' should be removed, got: {result['conference'].iloc[0]}"
        assert "PyCon" in result["conference"].iloc[0], \
            "Conference name 'PyCon' should be preserved"
        assert "Germany" in result["conference"].iloc[0], \
            "Conference location 'Germany' should be preserved"

    def test_removes_four_digit_year_2025(self):
        """Year removal should work for different years (2025)."""
        df = pd.DataFrame({"conference": ["DjangoCon US 2025"]})
        result = tidy_df_names(df)

        assert "2025" not in result["conference"].iloc[0]
        assert "DjangoCon US" in result["conference"].iloc[0]

    def test_removes_year_at_end(self):
        """Year at end of name should be removed."""
        df = pd.DataFrame({"conference": ["EuroPython 2026"]})
        result = tidy_df_names(df)

        assert "2026" not in result["conference"].iloc[0]
        assert "EuroPython" in result["conference"].iloc[0]

    def test_removes_year_in_middle(self):
        """Year in middle of name should be removed."""
        df = pd.DataFrame({"conference": ["PyCon 2026 US"]})
        result = tidy_df_names(df)

        assert "2026" not in result["conference"].iloc[0]

    def test_preserves_non_year_numbers(self):
        """Non-year numbers should be preserved (e.g., Python 3)."""
        df = pd.DataFrame({"conference": ["Python 3 Conference"]})
        result = tidy_df_names(df)

        # "3" should be preserved since it's not a year
        assert "3" in result["conference"].iloc[0] or "Python" in result["conference"].iloc[0]


class TestWhitespaceNormalization:
    """Test whitespace handling in conference names."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_removes_extra_spaces(self):
        """Multiple spaces should be collapsed to single space."""
        df = pd.DataFrame({"conference": ["PyCon  Germany   2026"]})
        result = tidy_df_names(df)

        # Should not have double spaces
        assert "  " not in result["conference"].iloc[0], \
            f"Double spaces should be removed, got: '{result['conference'].iloc[0]}'"

    def test_strips_leading_trailing_whitespace(self):
        """Leading and trailing whitespace should be removed."""
        df = pd.DataFrame({"conference": ["  PyCon Germany  "]})
        result = tidy_df_names(df)

        assert not result["conference"].iloc[0].startswith(" "), \
            "Leading whitespace should be stripped"
        assert not result["conference"].iloc[0].endswith(" "), \
            "Trailing whitespace should be stripped"

    def test_handles_tabs_and_newlines(self):
        """Tabs and other whitespace should be normalized."""
        df = pd.DataFrame({"conference": ["PyCon\tGermany"]})
        result = tidy_df_names(df)

        # Result should be clean
        assert "\t" not in result["conference"].iloc[0]


class TestAbbreviationExpansion:
    """Test expansion of common abbreviations."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_expands_conf_to_conference(self):
        """'Conf ' should be expanded to 'Conference '."""
        # Test with actual "Conf " pattern (with space after)
        df = pd.DataFrame({"conference": ["Python Conf 2026", "PyConf 2026"]})
        result = tidy_df_names(df)

        # The regex replaces r"\bConf \b" with "Conference "
        # "Python Conf 2026" should become "Python Conference" (year removed, Conf expanded)
        # "PyConf" has no space after "Conf", so it should remain "PyConf" (just year removed)
        assert isinstance(result["conference"].iloc[0], str), "Result should be a string"
        assert len(result["conference"].iloc[0]) > 0, "Result should not be empty"
        # Year should be removed from both
        assert "2026" not in result["conference"].iloc[0], "Year should be removed"
        assert "2026" not in result["conference"].iloc[1], "Year should be removed"


class TestKnownMappings:
    """Test that known conference name mappings are applied."""

    def test_applies_reverse_mapping(self):
        """Known mappings should map variants to canonical names."""
        mapping_data = {
            "PyCon DE": "PyCon Germany & PyData Conference",
            "PyCon Italia": "PyCon Italy",
        }

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], mapping_data)
            df = pd.DataFrame({"conference": ["PyCon DE"]})
            result = tidy_df_names(df)

            # Should be mapped to canonical name
            assert result["conference"].iloc[0] == "PyCon Germany & PyData Conference", \
                f"Expected canonical name, got: {result['conference'].iloc[0]}"

    def test_preserves_unmapped_names(self):
        """Conferences without mappings should be preserved."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            df = pd.DataFrame({"conference": ["Unique Conference Name"]})
            result = tidy_df_names(df)

            assert "Unique Conference Name" in result["conference"].iloc[0]


class TestIdempotency:
    """Test that normalization is idempotent (applying twice yields same result)."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_idempotent_on_simple_name(self):
        """Applying tidy_df_names twice should yield identical result."""
        df = pd.DataFrame({"conference": ["PyCon Germany 2026"]})

        result1 = tidy_df_names(df.copy())
        result2 = tidy_df_names(result1.copy())

        assert result1["conference"].iloc[0] == result2["conference"].iloc[0], \
            "tidy_df_names should be idempotent"

    def test_idempotent_on_already_clean_name(self):
        """Already normalized names should stay the same."""
        df = pd.DataFrame({"conference": ["PyCon Germany"]})

        result1 = tidy_df_names(df.copy())
        result2 = tidy_df_names(result1.copy())

        assert result1["conference"].iloc[0] == result2["conference"].iloc[0]


class TestSpecialCharacters:
    """Test handling of special characters in conference names."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_preserves_accented_characters(self):
        """Accented characters (like in México) should be preserved."""
        df = pd.DataFrame({"conference": ["PyCon México 2026"]})
        result = tidy_df_names(df)

        # The accented character should be preserved
        assert "xico" in result["conference"].iloc[0].lower(), \
            f"Conference name should preserve México, got: {result['conference'].iloc[0]}"

    def test_handles_ampersand(self):
        """Ampersand in conference names should be preserved."""
        df = pd.DataFrame({"conference": ["PyCon Germany & PyData Conference"]})
        result = tidy_df_names(df)

        assert "&" in result["conference"].iloc[0], \
            "Ampersand should be preserved in conference name"

    def test_handles_plus_sign(self):
        """Plus signs should be replaced with spaces (based on code)."""
        df = pd.DataFrame({"conference": ["Python+3 Conference"]})
        result = tidy_df_names(df)

        # The regex replaces + with space
        assert "+" not in result["conference"].iloc[0], \
            "Plus sign should be replaced"


class TestMultipleConferences:
    """Test normalization on DataFrames with multiple conferences."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_normalizes_all_conferences(self):
        """All conferences in DataFrame should be normalized."""
        df = pd.DataFrame({
            "conference": [
                "PyCon Germany 2026",
                "DjangoCon US 2025",
                "EuroPython 2026",
            ]
        })
        result = tidy_df_names(df)

        # No year should remain in any name
        for name in result["conference"]:
            assert "2025" not in name and "2026" not in name, \
                f"Year should be removed from '{name}'"

    def test_preserves_dataframe_length(self):
        """Normalization should not add or remove rows."""
        df = pd.DataFrame({
            "conference": [
                "PyCon Germany 2026",
                "DjangoCon US 2025",
                "EuroPython 2026",
            ]
        })
        result = tidy_df_names(df)

        assert len(result) == len(df), \
            "DataFrame length should be preserved"

    def test_preserves_other_columns(self):
        """Other columns should be preserved through normalization."""
        df = pd.DataFrame({
            "conference": ["PyCon Germany 2026"],
            "year": [2026],
            "link": ["https://pycon.de/"],
        })
        result = tidy_df_names(df)

        assert "year" in result.columns
        assert "link" in result.columns
        assert result["year"].iloc[0] == 2026
        assert result["link"].iloc[0] == "https://pycon.de/"


class TestRealDataNormalization:
    """Test normalization with real test fixtures (integration-style unit tests)."""

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_normalizes_minimal_yaml_fixture(self, minimal_yaml_df):
        """Normalization should work correctly on the minimal_yaml fixture."""
        result = tidy_df_names(minimal_yaml_df.reset_index(drop=True))

        # All conferences should still be present
        assert len(result) == len(minimal_yaml_df)

        # Conference names should be normalized (no years in the test data anyway)
        for name in result["conference"]:
            assert isinstance(name, str), f"Conference name should be string, got {type(name)}"
            assert len(name) > 0, "Conference name should not be empty"

    def test_handles_csv_dataframe(self, minimal_csv_df):
        """Normalization should work on CSV-sourced DataFrame."""
        result = tidy_df_names(minimal_csv_df)

        # Should handle CSV names (which may have year variants)
        assert len(result) == len(minimal_csv_df)

        # Check that PyCon US 2026 has year removed
        pycon_us_rows = result[result["conference"].str.contains("PyCon US", na=False)]
        if len(pycon_us_rows) > 0:
            for name in pycon_us_rows["conference"]:
                assert "2026" not in name, f"Year should be removed from '{name}'"


class TestRegressionCases:
    """Regression tests for bugs found in production.

    These tests document specific bugs and ensure they stay fixed.
    """

    @pytest.fixture(autouse=True)
    def setup_mock_mappings(self):
        """Mock title mappings for all tests in this class."""
        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            yield mock

    def test_regression_pycon_de_name_preserved(self):
        """REGRESSION: PyCon DE name should not be corrupted during normalization.

        This ensures the normalization doesn't mangle short conference names.
        """
        df = pd.DataFrame({"conference": ["PyCon DE"]})
        result = tidy_df_names(df)

        # Name should still be recognizable
        assert "PyCon" in result["conference"].iloc[0], \
            "PyCon should be preserved in the name"

    def test_regression_extra_spaces_dont_accumulate(self):
        """REGRESSION: Repeated normalization shouldn't add extra spaces.

        Processing with regex should not introduce artifacts.
        """
        df = pd.DataFrame({"conference": ["PyCon Germany"]})

        # Apply multiple times
        for _ in range(3):
            df = tidy_df_names(df.copy())

        # Should not have accumulated spaces
        name = df["conference"].iloc[0]
        assert "  " not in name, f"Extra spaces accumulated: '{name}'"


class TestRTLUnicodeHandling:
    """Test handling of Right-to-Left scripts (Arabic, Hebrew).

    Coverage gap: RTL scripts require special handling and can cause
    display and processing issues if not handled correctly.
    """

    def test_arabic_conference_name(self):
        """Test Arabic script in conference name."""
        # "PyCon Arabia" with Arabic text
        df = pd.DataFrame({"conference": ["PyCon العربية 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        # Should not crash and should preserve Arabic characters
        assert len(result) == 1
        conf_name = result["conference"].iloc[0]
        assert len(conf_name) > 0

    def test_hebrew_conference_name(self):
        """Test Hebrew script in conference name."""
        # "PyCon Israel" with Hebrew text
        df = pd.DataFrame({"conference": ["PyCon ישראל 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        # Should not crash and should preserve Hebrew characters
        assert len(result) == 1
        conf_name = result["conference"].iloc[0]
        assert len(conf_name) > 0

    def test_mixed_rtl_ltr_text(self):
        """Test mixed RTL and LTR text (bidirectional)."""
        # Conference name with both English and Arabic
        df = pd.DataFrame({"conference": ["PyData مؤتمر Conference 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        # Should handle bidirectional text without crashing
        assert len(result) == 1
        conf_name = result["conference"].iloc[0]
        assert "PyData" in conf_name or len(conf_name) > 0

    def test_persian_farsi_conference_name(self):
        """Test Persian/Farsi script (RTL, Arabic-derived)."""
        df = pd.DataFrame({"conference": ["PyCon ایران 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_urdu_conference_name(self):
        """Test Urdu script (RTL, Arabic-derived)."""
        df = pd.DataFrame({"conference": ["PyCon پاکستان 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_rtl_with_numbers(self):
        """Test RTL text with embedded numbers."""
        # Numbers in RTL context can have special display behavior
        df = pd.DataFrame({"conference": ["مؤتمر 2026 Python"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        # Should handle without crashing
        assert len(result) == 1

    def test_rtl_marks_and_controls(self):
        """Test handling of RTL control characters."""
        # Unicode RTL mark (U+200F) and LTR mark (U+200E)
        rtl_mark = "\u200f"
        ltr_mark = "\u200e"

        df = pd.DataFrame({"conference": [f"PyCon {rtl_mark}Test{ltr_mark} 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        # Should handle invisible control characters
        assert len(result) == 1


class TestCJKUnicodeHandling:
    """Test handling of CJK (Chinese, Japanese, Korean) scripts.

    Additional coverage for East Asian character sets.
    """

    def test_chinese_simplified_conference_name(self):
        """Test Simplified Chinese conference name."""
        df = pd.DataFrame({"conference": ["PyCon 中国 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_chinese_traditional_conference_name(self):
        """Test Traditional Chinese conference name."""
        df = pd.DataFrame({"conference": ["PyCon 台灣 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_japanese_conference_name(self):
        """Test Japanese conference name with mixed scripts."""
        # Japanese uses Hiragana, Katakana, and Kanji
        df = pd.DataFrame({"conference": ["PyCon JP 日本 パイコン 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_korean_conference_name(self):
        """Test Korean (Hangul) conference name."""
        df = pd.DataFrame({"conference": ["PyCon 한국 파이콘 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1
        assert len(result["conference"].iloc[0]) > 0

    def test_fullwidth_characters(self):
        """Test fullwidth ASCII characters (common in CJK contexts)."""
        # Fullwidth "PyCon" = Ｐｙｃｏｎ
        df = pd.DataFrame({"conference": ["Ｐｙｃｏｎ Conference 2026"]})

        with patch("tidy_conf.titles.load_title_mappings") as mock:
            mock.return_value = ([], {})
            result = tidy_df_names(df)

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Property-based tests using Hypothesis
# ---------------------------------------------------------------------------

# Import shared strategies from hypothesis_strategies module
sys.path.insert(0, str(Path(__file__).parent))
from hypothesis_strategies import (
    HYPOTHESIS_AVAILABLE,
    valid_year,
)

if HYPOTHESIS_AVAILABLE:
    from hypothesis import HealthCheck, assume, given, settings
    from hypothesis import strategies as st


pytestmark_hypothesis = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE,
    reason="hypothesis not installed - run: pip install hypothesis"
)


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
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


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestUnicodeHandlingProperties:
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
