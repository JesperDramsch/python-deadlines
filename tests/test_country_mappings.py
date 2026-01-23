"""Tests for the centralized country mappings module.

This module tests that all country mapping functionality is consistent
and that the single source of truth (countries.py) works correctly.
"""

import pytest


class TestCountryDisplayNames:
    """Test that country codes map to correct display names."""

    def test_us_stays_as_us(self):
        """US should stay as 'US' in conference names."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("US") == "US"

    def test_usa_becomes_us(self):
        """USA should become 'US' in conference names."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("USA") == "US"

    def test_uk_stays_as_uk(self):
        """UK should stay as 'UK' in conference names."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("UK") == "UK"

    def test_gb_becomes_uk(self):
        """GB should become 'UK' in conference names."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("GB") == "UK"

    def test_cz_expands_to_czechia(self):
        """CZ should expand to 'Czechia'."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("CZ") == "Czechia"

    def test_standard_codes_expand_via_iso(self):
        """Standard ISO codes should expand to country names."""
        from tidy_conf.countries import get_country_display_name

        # These should use ISO 3166 lookup
        assert get_country_display_name("DE") == "Germany"
        assert get_country_display_name("FR") == "France"
        assert get_country_display_name("PL") == "Poland"
        assert get_country_display_name("JP") == "Japan"


class TestCountryNormalization:
    """Test that country names normalize to canonical short forms."""

    def test_normalize_us_variations(self):
        """All US variations should normalize to 'US'."""
        from tidy_conf.countries import normalize_country_name

        assert normalize_country_name("United States") == "US"
        assert normalize_country_name("United States of America") == "US"
        assert normalize_country_name("USA") == "US"
        assert normalize_country_name("US") == "US"

    def test_normalize_uk_variations(self):
        """All UK variations should normalize to 'UK'."""
        from tidy_conf.countries import normalize_country_name

        assert normalize_country_name("United Kingdom") == "UK"
        assert normalize_country_name("Great Britain") == "UK"
        assert normalize_country_name("England") == "UK"
        assert normalize_country_name("UK") == "UK"
        assert normalize_country_name("GB") == "UK"

    def test_normalize_czechia_variations(self):
        """Czech variations should normalize to 'Czechia'."""
        from tidy_conf.countries import normalize_country_name

        assert normalize_country_name("Czech Republic") == "Czechia"
        assert normalize_country_name("Czechia") == "Czechia"

    def test_normalize_preserves_unknown(self):
        """Unknown countries should be preserved."""
        from tidy_conf.countries import normalize_country_name

        assert normalize_country_name("Germany") == "Germany"
        assert normalize_country_name("Japan") == "Japan"


class TestAlpha3Lookup:
    """Test ISO 3166 alpha-3 code lookup."""

    def test_us_variations_return_usa_code(self):
        """All US variations should return alpha-3 code 'USA'."""
        from tidy_conf.countries import get_country_alpha3

        assert get_country_alpha3("US") == "USA"
        assert get_country_alpha3("USA") == "USA"
        assert get_country_alpha3("United States") == "USA"
        assert get_country_alpha3("United States of America") == "USA"

    def test_uk_variations_return_gbr_code(self):
        """All UK variations should return alpha-3 code 'GBR'."""
        from tidy_conf.countries import get_country_alpha3

        assert get_country_alpha3("UK") == "GBR"
        assert get_country_alpha3("United Kingdom") == "GBR"
        assert get_country_alpha3("England") == "GBR"

    def test_standard_countries(self):
        """Standard country names should return correct alpha-3 codes."""
        from tidy_conf.countries import get_country_alpha3

        assert get_country_alpha3("Germany") == "DEU"
        assert get_country_alpha3("France") == "FRA"
        assert get_country_alpha3("Japan") == "JPN"

    def test_preserves_unknown_countries(self):
        """Unknown countries should be preserved, not lost."""
        from tidy_conf.countries import get_country_alpha3

        assert get_country_alpha3("Atlantis") == "Atlantis"
        assert get_country_alpha3("Unknown Place") == "Unknown Place"

    def test_handles_empty_input(self):
        """Empty input should return empty string."""
        from tidy_conf.countries import get_country_alpha3

        assert get_country_alpha3("") == ""
        assert get_country_alpha3(None) == ""
        assert get_country_alpha3("   ") == ""


class TestConferenceNameExpansion:
    """Test that conference names with country codes expand correctly."""

    def test_pycon_us_stays_as_us(self):
        """PyCon US should stay as 'PyCon US'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon US")
        assert result == "PyCon US"

    def test_pycon_uk_stays_as_uk(self):
        """PyCon UK should stay as 'PyCon UK'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon UK")
        assert result == "PyCon UK"

    def test_pycon_pl_expands_correctly(self):
        """PyCon PL should expand to 'PyCon Poland'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon PL")
        assert result == "PyCon Poland"

    def test_pycon_de_expands_correctly(self):
        """PyCon DE should expand to 'PyCon Germany'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon DE")
        assert result == "PyCon Germany"

    def test_expansion_is_idempotent(self):
        """Expanding twice should give the same result."""
        from tidy_conf.titles import expand_country_codes

        once = expand_country_codes("PyCon US")
        twice = expand_country_codes(once)
        assert once == twice


class TestCountryCodeToNameMapping:
    """Test the COUNTRY_CODE_TO_NAME mapping is correctly built."""

    def test_us_maps_to_us(self):
        """COUNTRY_CODE_TO_NAME['US'] should be 'US'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["US"] == "US"

    def test_uk_maps_to_uk(self):
        """COUNTRY_CODE_TO_NAME['UK'] should be 'UK'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["UK"] == "UK"

    def test_usa_maps_to_us(self):
        """COUNTRY_CODE_TO_NAME['USA'] should be 'US'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["USA"] == "US"

    def test_de_maps_to_germany(self):
        """COUNTRY_CODE_TO_NAME['DE'] should be 'Germany'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["DE"] == "Germany"


class TestMergeReplacementsConsistency:
    """Test that the merge replacements use the centralized mappings."""

    def test_interactive_merge_uses_country_normalization(self):
        """interactive_merge.py should use COUNTRY_NORMALIZATION."""
        from tidy_conf.countries import COUNTRY_NORMALIZATION

        # These should all be in COUNTRY_NORMALIZATION
        assert "United States of America" in COUNTRY_NORMALIZATION
        assert "United Kingdom" in COUNTRY_NORMALIZATION
        assert "Czech Republic" in COUNTRY_NORMALIZATION

        # And map to the correct canonical forms
        assert COUNTRY_NORMALIZATION["United States of America"] == "US"
        assert COUNTRY_NORMALIZATION["United Kingdom"] == "UK"
        assert COUNTRY_NORMALIZATION["Czech Republic"] == "Czechia"


class TestRegressionUSExpansion:
    """Regression tests to prevent US -> United States of America bug."""

    def test_normalize_conference_name_us_stays_as_us(self):
        """normalize_conference_name should keep US as 'US'."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("PyCon US")
        assert result == "PyCon US"
        assert "United States" not in result

    def test_pycon_de_expands_to_germany(self):
        """PyCon DE should expand to 'PyCon Germany'."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("PyCon DE")
        assert result == "PyCon Germany"

    def test_place_with_us_not_expanded(self):
        """A place ending with 'US' or 'USA' should normalize correctly."""
        from tidy_conf.countries import normalize_country_name

        # Direct normalization
        assert normalize_country_name("USA") == "US"

        # After normalization, it should stay as "US"
        result = normalize_country_name("US")
        assert result == "US"
