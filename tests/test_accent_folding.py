"""Tests for accent-insensitive conference name matching.

Names from different sources disagree on diacritics ("PyCon Panamá" vs
"PyCon Panama", "PyDay México" vs "PyDay Mexico"). Matching should treat
these as the same conference while stored names keep their original spelling.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.interactive_merge import conference_scorer
from tidy_conf.interactive_merge import fuzzy_match
from tidy_conf.interactive_merge import is_identical_name
from tidy_conf.interactive_merge import merge_conferences
from tidy_conf.titles import tidy_df_names
from tidy_conf.titles import tidy_titles
from tidy_conf.utils import fold_name
from tidy_conf.utils import strip_accents
from tidy_conf.yaml import load_title_mappings

ACCENTED_PAIRS = [
    ("PyCon Panamá", "PyCon Panama"),
    ("PyDay México", "PyDay Mexico"),
    ("PyCon España", "PyCon Espana"),
    ("PyCon Medellín", "PyCon Medellin"),
    ("Pythoncamp Rügen", "Pythoncamp Rugen"),
    ("PyDay Boyacá", "PyDay Boyaca"),
]


class TestStripAccents:
    """strip_accents removes diacritics but keeps case and other characters."""

    @pytest.mark.parametrize(("accented", "plain"), ACCENTED_PAIRS)
    def test_removes_diacritics(self, accented, plain):
        assert strip_accents(accented) == plain

    def test_preserves_case_and_punctuation(self):
        assert strip_accents("PyDay México: CDMX") == "PyDay Mexico: CDMX"

    def test_plain_ascii_unchanged(self):
        assert strip_accents("PyCon US") == "PyCon US"

    def test_decomposed_input_matches_composed(self):
        """NFD input ("e" + combining acute) folds the same as NFC ("é")."""
        decomposed = "PyDay México"
        assert strip_accents(decomposed) == "PyDay Mexico"

    def test_non_latin_scripts_preserved(self):
        """Scripts without combining marks must survive untouched."""
        assert strip_accents("PyCon 中国") == "PyCon 中国"


class TestFoldName:
    """fold_name produces a comparison key: no accents, casefolded, single spaces."""

    @pytest.mark.parametrize(("accented", "plain"), ACCENTED_PAIRS)
    def test_accented_and_plain_fold_equal(self, accented, plain):
        assert fold_name(accented) == fold_name(plain)

    def test_collapses_whitespace_and_case(self):
        assert fold_name("  PyDay   MÉXICO ") == "pyday mexico"


class TestMergeMatching:
    """Merge helpers treat accent-only differences as identical names."""

    @pytest.mark.parametrize(("accented", "plain"), ACCENTED_PAIRS)
    def test_is_identical_name_ignores_accents(self, accented, plain):
        assert is_identical_name(accented, plain)

    @pytest.mark.parametrize(("accented", "plain"), ACCENTED_PAIRS)
    def test_scorer_gives_full_score(self, accented, plain):
        assert conference_scorer(accented, plain) == 100

    def test_different_conferences_still_distinct(self):
        """Folding must not make genuinely different names identical."""
        assert not is_identical_name("PyCon Panamá", "PyCon Paraguay")
        assert not is_identical_name("PyCon Africa", "PyCon South Africa")


class TestTitleMappings:
    """titles.yml variations match regardless of accents."""

    def test_reverse_mapping_contains_unaccented_variation(self):
        """The real titles.yml lists "PyDay México"; the plain form must map too."""
        _, reverse = load_title_mappings(reverse=True)
        assert reverse.get("PyDay México") == "PyDay Mexico"
        assert reverse.get("PyDay Mexico: CDMX") == "PyDay Mexico"

    def test_tidy_df_names_maps_unaccented_variant(self):
        mapping = {"PyDay México": "PyDay Mexico", "PyDay Mexico": "PyDay Mexico"}
        with patch("tidy_conf.titles.load_title_mappings", return_value=([], mapping)):
            result = tidy_df_names(pd.DataFrame({"conference": ["PyDay México"]}))
        assert result["conference"].iloc[0] == "PyDay Mexico"

    def test_tidy_titles_matches_accent_variant(self):
        """A variation listed without accents matches an accented input, and vice versa."""
        alt_names = {
            "PyCon Panama": {"global": None, "variations": ["PyCon Panama City"], "regexes": []},
            "PyDay Mexico": {"global": None, "variations": ["PyDay México"], "regexes": []},
        }
        data = [{"conference": "PyCon Panamá City"}, {"conference": "PyDay Mexico"}]
        with patch("tidy_conf.titles.load_title_mappings", return_value=([], alt_names)):
            result = tidy_titles(data)
        assert result[0]["conference"] == "PyCon Panama"
        assert result[0]["alt_name"] == "PyCon Panamá City"
        assert result[1]["conference"] == "PyDay Mexico"
        assert "alt_name" not in result[1]

    def test_tidy_titles_matches_variation_without_conference(self):
        """The "Conference"-stripped comparison works (it was dead code before)."""
        alt_names = {"PyCon Foo": {"global": None, "variations": ["Foo Conference"], "regexes": []}}
        with patch("tidy_conf.titles.load_title_mappings", return_value=([], alt_names)):
            result = tidy_titles([{"conference": "Foo"}])
        assert result[0]["conference"] == "PyCon Foo"
        assert result[0]["alt_name"] == "Foo"

    def test_tidy_df_names_falls_back_to_accent_free_lookup(self):
        """A mapping keyed by the accent-free spelling must still catch the accented input."""
        mapping = {"PyDay Mexico": "PyDay Mexico"}
        with patch("tidy_conf.titles.load_title_mappings", return_value=([], mapping)):
            result = tidy_df_names(pd.DataFrame({"conference": ["PyDay México"]}))
        assert result["conference"].iloc[0] == "PyDay Mexico"


class TestMergeKeepsYamlSpelling:
    """An accent-only match merges without prompting but must keep the YAML spelling.

    The importers drop the YAML "conference" column and take the name from the
    merged index, so keying the remote row under its own spelling would rename
    the conference and trip the bot's data-loss guard.
    """

    def _frames(self):
        base = {
            "year": [2026],
            "cfp": ["2026-09-18 23:59:00"],
            "link": ["https://pycon.pa/2026/"],
            "start": ["2026-10-22"],
            "end": ["2026-10-23"],
        }
        df_yml = pd.DataFrame({"conference": ["PyCon Panamá"], "place": ["Panama City, Panamá"], **base})
        df_remote = pd.DataFrame({"conference": ["PyCon Panama"], "place": ["Panama City, Panama"], **base})
        return df_yml, df_remote

    def test_fuzzy_match_keys_remote_row_by_yaml_name(self):
        df_yml, df_remote = self._frames()
        with (
            patch("tidy_conf.interactive_merge.load_title_mappings", return_value=([], {})),
            patch("tidy_conf.titles.load_title_mappings", return_value=([], {})),
            patch("tidy_conf.interactive_merge.update_title_mappings") as mock_update,
            patch("tidy_conf.interactive_merge.query_yes_no", side_effect=AssertionError("must not prompt")),
        ):
            matched, remote, report = fuzzy_match(df_yml, df_remote)

        assert matched.index.tolist() == ["PyCon Panamá"]
        assert remote.index.tolist() == ["PyCon Panamá"]
        assert report.records[0].action == "merged"
        # The remote spelling is recorded as a variation of the YAML name
        mock_update.assert_any_call({"PyCon Panamá": ["PyCon Panama"]})

    def test_merged_conference_keeps_yaml_name(self):
        df_yml, df_remote = self._frames()
        with (
            patch("tidy_conf.interactive_merge.load_title_mappings", return_value=([], {})),
            patch("tidy_conf.titles.load_title_mappings", return_value=([], {})),
            patch("tidy_conf.interactive_merge.update_title_mappings"),
        ):
            matched, remote, _report = fuzzy_match(df_yml, df_remote)

        # Both importers drop the conference column and rely on the index
        matched = matched.drop(columns=["conference"])
        schema = pd.DataFrame(columns=["conference", "year", "cfp", "link", "place", "start", "end", "sub"])
        with (
            patch("tidy_conf.interactive_merge.get_schema", return_value=schema),
            patch("tidy_conf.interactive_merge.query_yes_no", return_value=False),
        ):
            result = merge_conferences(matched, remote)

        assert result["conference"].tolist() == ["PyCon Panamá"]
