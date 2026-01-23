"""Tests for the centralized country mappings module.

This module tests that all country mapping functionality is consistent
and that the single source of truth (countries.py) works correctly.
"""

import pytest


class TestCountryDisplayNames:
    """Test that country codes expand to correct display names."""

    def test_us_expands_to_united_states(self):
        """US should expand to 'United States', NOT 'United States of America'."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("US") == "United States"

    def test_usa_expands_to_united_states(self):
        """USA should expand to 'United States'."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("USA") == "United States"

    def test_uk_expands_to_united_kingdom(self):
        """UK should expand to 'United Kingdom'."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("UK") == "United Kingdom"

    def test_gb_expands_to_united_kingdom(self):
        """GB should expand to 'United Kingdom'."""
        from tidy_conf.countries import get_country_display_name

        assert get_country_display_name("GB") == "United Kingdom"

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

    def test_pycon_us_expands_correctly(self):
        """PyCon US should expand to 'PyCon United States'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon US")
        assert result == "PyCon United States"
        # Most importantly, it should NOT contain "of America"
        assert "of America" not in result

    def test_pycon_uk_expands_correctly(self):
        """PyCon UK should expand to 'PyCon United Kingdom'."""
        from tidy_conf.titles import expand_country_codes

        result = expand_country_codes("PyCon UK")
        assert result == "PyCon United Kingdom"

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

    def test_us_maps_to_united_states(self):
        """COUNTRY_CODE_TO_NAME['US'] should be 'United States'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["US"] == "United States"
        # NOT "United States of America"
        assert "of America" not in COUNTRY_CODE_TO_NAME["US"]

    def test_uk_maps_to_united_kingdom(self):
        """COUNTRY_CODE_TO_NAME['UK'] should be 'United Kingdom'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["UK"] == "United Kingdom"

    def test_usa_maps_to_united_states(self):
        """COUNTRY_CODE_TO_NAME['USA'] should be 'United States'."""
        from tidy_conf.countries import COUNTRY_CODE_TO_NAME

        assert COUNTRY_CODE_TO_NAME["USA"] == "United States"


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

    def test_normalize_conference_name_us_not_expanded_to_full(self):
        """normalize_conference_name should not expand US to 'United States of America'."""
        from tidy_conf.titles import normalize_conference_name

        result = normalize_conference_name("PyCon US")
        assert "of America" not in result

    def test_place_with_us_not_expanded(self):
        """A place ending with 'US' or 'USA' should normalize correctly."""
        from tidy_conf.countries import normalize_country_name

        # Direct normalization
        assert normalize_country_name("USA") == "US"

        # After normalization, it should stay as "US"
        result = normalize_country_name("US")
        assert result == "US"
        assert "of America" not in result
