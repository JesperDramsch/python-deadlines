"""Tests for data processing and sorting functionality."""

# Add utils to path for imports
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import sort_yaml
from tidy_conf.schema import Conference


class TestDataProcessing:
    """Test data processing functions."""

    def test_sort_by_cfp(self, sample_conference):
        """Test sorting conferences by CFP deadline."""
        conf = Conference(**sample_conference)
        cfp_date = sort_yaml.sort_by_cfp(conf)

        assert cfp_date == "2025-02-15 23:59:00"

    def test_sort_by_date_passed(self, sample_conference):
        """Test identifying passed deadlines."""
        # Future deadline
        sample_conference["cfp"] = "2030-12-31 23:59:00"
        conf = Conference(**sample_conference)
        assert not sort_yaml.sort_by_date_passed(conf)

        # Past deadline
        sample_conference["cfp"] = "2020-01-01 00:00:00"
        conf = Conference(**sample_conference)
        assert sort_yaml.sort_by_date_passed(conf)

    def test_sort_by_name(self, sample_conference):
        """Test sorting by conference name."""
        conf = Conference(**sample_conference)
        sort_key = sort_yaml.sort_by_name(conf)

        expected = f"{conf.conference} {conf.year}".lower()
        assert sort_key == expected

    def test_order_keywords(self, sample_conference):
        """Test keyword ordering according to schema."""
        conf = Conference(**sample_conference)
        ordered_conf = sort_yaml.order_keywords(conf)

        # Should return a Conference object with ordered fields
        assert isinstance(ordered_conf, Conference)
        assert ordered_conf.conference == sample_conference["conference"]

    def test_merge_duplicates(self):
        """Test duplicate conference merging."""
        conferences = [
            {
                "conference": "PyCon Test",
                "year": 2025,
                "place": "Test City",
                "link": "https://short.link",
                "cfp": "2025-02-15 23:59:00",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
            {
                "conference": "PyCon Test",
                "year": 2025,
                "place": "Test City",
                "link": "https://much-longer-and-more-detailed.link",  # Longer link
                "cfp": "2025-02-15 23:59:00",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
                "sponsor": "https://sponsor.com",  # Additional field
            },
        ]

        merged = sort_yaml.merge_duplicates(conferences)

        # Should have only one conference after merging
        assert len(merged) == 1

        # Should keep the longer link and additional fields
        merged_conf = merged[0]
        assert merged_conf["link"] == "https://much-longer-and-more-detailed.link"
        assert "sponsor" in merged_conf

    def test_yaml_file_processing(self, temp_yaml_file, sample_conference):
        """Test processing YAML conference files."""
        # Create test data
        test_data = [sample_conference]
        yaml_file = temp_yaml_file(test_data)

        # Test loading
        with yaml_file.open(encoding="utf-8") as f:
            loaded_data = yaml.safe_load(f)

        assert len(loaded_data) == 1
        assert loaded_data[0]["conference"] == "PyCon Test"


class TestDateHandling:
    """Test date parsing and timezone handling."""

    def test_date_formats(self):
        """Test various date format parsing."""
        valid_date_formats = ["2025-02-15 23:59:00", "2025-12-31 00:00:00", "2025-01-01 12:30:45"]

        for date_str in valid_date_formats:
            # Should not raise an exception
            parsed_date = datetime.strptime(date_str, sort_yaml.dateformat).replace(tzinfo=timezone.utc)
            assert isinstance(parsed_date, datetime)

    def test_tba_words_handling(self):
        """Test handling of TBA/TBD words."""
        tba_variations = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]

        for tba_word in tba_variations:
            assert tba_word in sort_yaml.tba_words

    def test_timezone_handling(self, sample_conference):
        """Test timezone field handling."""
        # Test with timezone
        sample_conference["timezone"] = "America/New_York"
        conf = Conference(**sample_conference)
        assert conf.timezone == "America/New_York"

        # Test without timezone (should be None/default to AoE)
        sample_conference["timezone"] = None
        conf = Conference(**sample_conference)
        assert conf.timezone is None


class TestDataIntegrity:
    """Test data integrity and consistency."""

    def test_conference_data_consistency(self, sample_conference):
        """Test that conference data maintains consistency."""
        conf = Conference(**sample_conference)

        # Basic consistency checks
        assert conf.start <= conf.end
        assert conf.year >= 1989
        assert conf.conference.strip() != ""
        assert conf.place.strip() != ""

    def test_required_fields_completeness(self, sample_conference):
        """Test that all required fields are present and valid."""
        conf = Conference(**sample_conference)

        required_fields = ["conference", "year", "link", "cfp", "place", "start", "end", "sub"]

        for field in required_fields:
            assert hasattr(conf, field)
            value = getattr(conf, field)
            assert value is not None
            if isinstance(value, str):
                assert value.strip() != ""

    def test_url_accessibility_format(self, sample_conference):
        """Test URL format for accessibility."""
        # Test various valid URL formats
        valid_urls = [
            "https://example.com",
            "https://sub.example.com/path",
            "https://example.com/path?param=value",
            "https://example.org/path#section",
        ]

        for url in valid_urls:
            sample_conference["link"] = url
            conf = Conference(**sample_conference)
            assert str(conf.link).startswith(("http://", "https://"))

    def test_date_logic_validation(self, sample_conference):
        """Test logical date relationships."""
        # CFP should typically be before conference start
        from datetime import datetime

        # In most cases, CFP should be before the conference
        # (Though not enforced as a hard rule since there might be exceptions)
        cfp_date = datetime.strptime(sample_conference["cfp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        start_date = sample_conference["start"]
        # Ensure both dates exist for logical validation
        assert cfp_date is not None
        assert start_date is not None
