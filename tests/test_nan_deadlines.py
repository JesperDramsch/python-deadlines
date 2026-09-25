"""Tests guarding against pandas NaN leaking into deadline fields as "nan".

A missing CFP in a DataFrame becomes the string "nan" after astype(str) and was
written to conferences.yml as `cfp: nan`. The writer and the schema both map it
to TBA (cfp) or drop it (optional deadlines) instead.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.date import clean_dates
from tidy_conf.schema import Conference
from tidy_conf.yaml import write_df_yaml


class TestSchemaNanDeadlines:
    """The schema replaces NaN deadlines instead of rejecting the conference."""

    @pytest.mark.parametrize("missing", [float("nan"), "nan", "NaN", " nan ", ""])
    def test_cfp_nan_becomes_tba(self, sample_conference, missing):
        conf = Conference(**{**sample_conference, "cfp": missing})
        assert conf.cfp == "TBA"

    @pytest.mark.parametrize("field", ["cfp_ext", "workshop_deadline", "tutorial_deadline"])
    @pytest.mark.parametrize("missing", [float("nan"), "nan"])
    def test_optional_deadline_nan_becomes_none(self, sample_conference, field, missing):
        conf = Conference(**{**sample_conference, field: missing})
        assert getattr(conf, field) is None
        assert field not in conf.model_dump(exclude_none=True)

    @pytest.mark.parametrize("value", ["TBA", "tbd", "None", "Cancelled", "n/a", "2025-02-15", "2025-02-15 23:59:00"])
    def test_legitimate_cfp_values_unchanged(self, sample_conference, value):
        assert Conference(**{**sample_conference, "cfp": value}).cfp == value


class TestWriteDfYamlNan:
    """write_df_yaml never writes `cfp: nan`."""

    def test_missing_cfp_written_as_tba(self, tmp_path, sample_conference):
        rows = [
            {**sample_conference, "cfp": float("nan")},
            {**sample_conference, "conference": "PyCon Other", "cfp": None},
            {**sample_conference, "conference": "PyCon Dated"},
        ]
        out = tmp_path / "conferences.yml"

        write_df_yaml(pd.DataFrame(rows), out)

        written = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert [c["cfp"] for c in written] == ["TBA", "TBA", "2025-02-15 23:59:00"]
        assert "nan" not in out.read_text(encoding="utf-8")


class TestDeadlineSanity:
    """Deadlines must be real calendar dates, and blank optional deadlines must not crash the sort."""

    @pytest.mark.parametrize("value", ["2026-02-30", "2026-13-01 23:59:00", "2026-02-15 25:00:00"])
    def test_impossible_deadline_rejected(self, sample_conference, value):
        with pytest.raises(ValidationError):
            Conference(**{**sample_conference, "cfp": value})

    @pytest.mark.parametrize("value", ["2026-02-28", "2024-02-29 23:59:00"])
    def test_real_deadline_accepted(self, sample_conference, value):
        assert Conference(**{**sample_conference, "cfp": value}).cfp == value

    def test_clean_dates_skips_blank_optional_deadline(self):
        """`cfp_ext:` with no value loads as None and previously raised AttributeError."""
        data = {"start": "2026-06-01", "end": "2026-06-03", "cfp": "2026-02-15", "cfp_ext": None}

        cleaned = clean_dates(data)

        assert cleaned["cfp"] == "2026-02-15 23:59:00"
        assert cleaned["cfp_ext"] is None
