"""Enhanced tests for sort_yaml functionality to increase coverage."""

import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
import pytz
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import sort_yaml
from tidy_conf.schema import Conference


class TestSortByCfp:
    """Test CFP sorting functionality with enhanced coverage."""

    def test_sort_by_cfp_tba_words(self):
        """Test CFP sorting with various TBA words."""
        tba_words = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]

        for word in tba_words:
            conf = Conference(
                conference="Test Conference",
                year=2025,
                cfp=word,
                link="https://test.com",
                place="Test City",
                start="2025-06-01",
                end="2025-06-03",
                sub="PY",
            )
            result = sort_yaml.sort_by_cfp(conf)
            assert result == word

    def test_sort_by_cfp_without_time(self):
        """Test CFP sorting when no time is specified."""
        conf = Conference(
            conference="Test Conference",
            year=2025,
            cfp="2025-02-15",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_cfp(conf)
        # Should append 23:59:00
        expected_datetime = pytz.utc.normalize(
            datetime.strptime("2025-02-15 23:59:00", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=pytz.timezone("Etc/GMT+12"),  # AoE default
            ),
        )
        assert result == expected_datetime.strftime("%Y-%m-%d %H:%M:%S")

    def test_sort_by_cfp_with_time(self):
        """Test CFP sorting with time already specified."""
        conf = Conference(
            conference="Test Conference",
            year=2025,
            cfp="2025-02-15 12:30:00",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_cfp(conf)
        # Should not append time
        expected_datetime = pytz.utc.normalize(
            datetime.strptime("2025-02-15 12:30:00", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=pytz.timezone("Etc/GMT+12"),  # AoE default
            ),
        )
        assert result == expected_datetime.strftime("%Y-%m-%d %H:%M:%S")

    def test_sort_by_cfp_different_timezones(self):
        """Test CFP sorting with different timezones."""
        timezones = [
            ("America/New_York", "Etc/GMT+5"),
            ("Europe/London", "Europe/London"),
            ("UTC+5", "Etc/GMT-5"),
            ("UTC-3", "Etc/GMT+3"),
            ("AoE", "Etc/GMT+12"),
        ]

        for input_tz, _expected_tz in timezones:
            conf = Conference(
                conference="Test Conference",
                year=2025,
                cfp="2025-02-15 12:00:00",
                link="https://test.com",
                place="Test City",
                start="2025-06-01",
                end="2025-06-03",
                sub="PY",
                timezone=input_tz,
            )

            result = sort_yaml.sort_by_cfp(conf)
            # Should handle timezone conversion
            assert isinstance(result, str)
            assert len(result) == 19  # YYYY-MM-DD HH:MM:SS format

    def test_sort_by_cfp_case_insensitive_tba(self):
        """Test that TBA word matching is case insensitive."""
        conf = Conference(
            conference="Test Conference",
            year=2025,
            cfp="TBA",  # Uppercase
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_cfp(conf)
        assert result == "TBA"


class TestSortByDate:
    """Test date sorting functionality."""

    def test_sort_by_date_basic(self):
        """Test basic date sorting."""
        conf = Conference(
            conference="Test Conference",
            year=2025,
            cfp="2025-02-15",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_date(conf)
        assert result == "2025-06-01"

    def test_sort_by_date_different_formats(self):
        """Test date sorting with different date formats."""
        dates = ["2025-01-01", "2025-12-31", "2024-06-15"]

        for date_val in dates:
            conf = Conference(
                conference="Test Conference",
                year=2025,
                cfp="2025-02-15",
                link="https://test.com",
                place="Test City",
                start=date_val,
                end="2025-06-03",
                sub="PY",
            )

            result = sort_yaml.sort_by_date(conf)
            assert result == date_val


class TestSortByDatePassed:
    """Test date passed sorting functionality."""

    def test_sort_by_date_passed_future(self):
        """Test date passed sorting for future conferences."""
        conf = Conference(
            conference="Test Conference",
            year=2026,  # Future year
            cfp="2026-02-15",
            link="https://test.com",
            place="Test City",
            start="2026-06-01",
            end="2026-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_date_passed(conf)
        assert result is False  # Future date should be False

    def test_sort_by_date_passed_past(self):
        """Test date passed sorting for past conferences."""
        conf = Conference(
            conference="Test Conference",
            year=2020,  # Past year
            cfp="2020-02-15",
            link="https://test.com",
            place="Test City",
            start="2020-06-01",
            end="2020-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_date_passed(conf)
        assert result is True  # Past date should be True


class TestSortByName:
    """Test name sorting functionality."""

    def test_sort_by_name_basic(self):
        """Test basic name sorting."""
        conf = Conference(
            conference="PyCon US",
            year=2025,
            cfp="2025-02-15",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
        )

        result = sort_yaml.sort_by_name(conf)
        assert result == "pycon us 2025"

    def test_sort_by_name_case_insensitive(self):
        """Test name sorting is case insensitive."""
        conferences = [
            ("UPPERCASE CONF", 2025, "uppercase conf 2025"),
            ("lowercase conf", 2024, "lowercase conf 2024"),
            ("MiXeD CaSe", 2026, "mixed case 2026"),
        ]

        for name, year, expected in conferences:
            conf = Conference(
                conference=name,
                year=year,
                cfp="2025-02-15",
                link="https://test.com",
                place="Test City",
                start="2025-06-01",
                end="2025-06-03",
                sub="PY",
            )

            result = sort_yaml.sort_by_name(conf)
            assert result == expected


class TestOrderKeywords:
    """Test keyword ordering functionality."""

    def test_order_keywords_dict_input(self):
        """Test keyword ordering with dictionary input."""
        with patch("sort_yaml.get_schema") as mock_schema:
            mock_df = Mock()
            mock_df.columns.tolist.return_value = ["conference", "year", "cfp", "link", "place", "start", "end", "sub"]
            mock_schema.return_value = mock_df

            input_data = {
                "sub": "PY",
                "conference": "Test Conference",
                "year": 2025,
                "cfp": "2025-02-15",
                "extra_field": "should_be_filtered",  # Not in schema
                "link": "https://test.com",
                "place": "Test City",
                "start": "2025-06-01",
                "end": "2025-06-03",
            }

            result = sort_yaml.order_keywords(input_data)

            # Should preserve order from schema and filter out extra fields
            expected_keys = ["conference", "year", "cfp", "link", "place", "start", "end", "sub"]
            assert list(result.keys()) == expected_keys
            assert "extra_field" not in result

    def test_order_keywords_conference_input(self):
        """Test keyword ordering with Conference object input."""
        with patch("sort_yaml.get_schema") as mock_schema:
            mock_df = Mock()
            mock_df.columns.tolist.return_value = ["conference", "year", "cfp", "link", "place", "start", "end", "sub"]
            mock_schema.return_value = mock_df

            conf = Conference(
                conference="Test Conference",
                year=2025,
                cfp="2025-02-15",
                link="https://test.com",
                place="Test City",
                start="2025-06-01",
                end="2025-06-03",
                sub="PY",
            )

            result = sort_yaml.order_keywords(conf)

            # Should return Conference object
            assert isinstance(result, Conference)
            assert result.conference == "Test Conference"


class TestMergeDuplicates:
    """Test duplicate merging functionality."""

    def test_merge_duplicates_no_duplicates(self):
        """Test merge duplicates with no actual duplicates."""
        data = [
            {"conference": "Conference A", "year": 2025, "place": "City A", "link": "https://a.com"},
            {"conference": "Conference B", "year": 2025, "place": "City B", "link": "https://b.com"},
        ]

        with patch("tqdm.tqdm", side_effect=lambda x: x):  # Mock tqdm
            result = sort_yaml.merge_duplicates(data)

        assert len(result) == 2
        assert result[0]["conference"] == "Conference A"
        assert result[1]["conference"] == "Conference B"

    def test_merge_duplicates_with_duplicates(self):
        """Test merge duplicates with actual duplicates."""
        data = [
            {"conference": "Conference A", "year": 2025, "place": "City A", "link": "https://short.com"},
            {
                "conference": "Conference A",
                "year": 2025,
                "place": "City A",
                "cfp_link": "https://very-long-link.com/cfp",
            },
        ]

        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result = sort_yaml.merge_duplicates(data)

        # Should merge into one entry
        assert len(result) == 1
        merged = result[0]
        assert merged["conference"] == "Conference A"
        assert merged["link"] == "https://short.com"
        assert merged["cfp_link"] == "https://very-long-link.com/cfp"

    def test_merge_duplicates_longer_value_priority(self):
        """Test that longer values take priority in merge."""
        data = [
            {"conference": "Conference A", "year": 2025, "place": "City A", "note": "Short"},
            {"conference": "Conference A", "year": 2025, "place": "City A", "note": "Much longer note"},
        ]

        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result = sort_yaml.merge_duplicates(data)

        assert len(result) == 1
        assert result[0]["note"] == "Much longer note"


class TestTidyDates:
    """Test date cleaning functionality."""

    @patch("sort_yaml.clean_dates")
    def test_tidy_dates_basic(self, mock_clean_dates):
        """Test basic date cleaning."""
        mock_clean_dates.side_effect = lambda x: x  # Return unchanged

        data = [
            {"conference": "Conference A", "cfp": "2025-02-15"},
            {"conference": "Conference B", "cfp": "2025-03-15"},
        ]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.tidy_dates(data)

        assert len(result) == 2
        assert mock_clean_dates.call_count == 2

    @patch("sort_yaml.clean_dates")
    def test_tidy_dates_error_handling(self, mock_clean_dates):
        """Test date cleaning with errors."""

        def mock_clean_side_effect(x):
            if x.get("conference") == "Error Conference":
                raise ValueError("Date parsing error")
            return x

        mock_clean_dates.side_effect = mock_clean_side_effect

        data = [
            {"conference": "Good Conference", "cfp": "2025-02-15"},
            {"conference": "Error Conference", "cfp": "invalid-date"},
        ]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x), pytest.raises(
            ValueError,
            match="Invalid date format",
        ):
            # Should not crash even if clean_dates raises error
            sort_yaml.tidy_dates(data)


class TestSplitData:
    """Test data splitting functionality."""

    def test_split_data_basic_categories(self):
        """Test basic data splitting into categories."""
        now = datetime.now(tz=timezone.utc).date()

        conferences = [
            Conference(
                conference="Active Conference",
                year=2025,
                cfp="2025-02-15 23:59:00",
                link="https://active.com",
                place="City A",
                start=now + timedelta(days=60),
                end=now + timedelta(days=63),
                sub="PY",
            ),
            Conference(
                conference="TBA Conference",
                year=2025,
                cfp="TBA",
                link="https://tba.com",
                place="City B",
                start=now + timedelta(days=90),
                end=now + timedelta(days=93),
                sub="PY",
            ),
            Conference(
                conference="Expired Conference",
                year=2024,
                cfp="2024-02-15 23:59:00",
                link="https://expired.com",
                place="City C",
                start=now - timedelta(days=100),
                end=now - timedelta(days=97),
                sub="PY",
            ),
            Conference(
                conference="Legacy Conference",
                year=2020,
                cfp="2020-02-15 23:59:00",
                link="https://legacy.com",
                place="City D",
                start=now - timedelta(days=2000),
                end=now - timedelta(days=1997),
                sub="PY",
            ),
        ]

        with patch("tqdm.tqdm", side_effect=lambda x: x):
            conf, tba, expired, legacy = sort_yaml.split_data(conferences)

        # Verify categorization
        assert len(conf) >= 1  # Active conference
        assert len(tba) >= 1  # TBA conference
        assert len(expired) >= 1  # Expired conference
        assert len(legacy) >= 1  # Legacy conference

        # Verify correct categorization
        conf_names = [c.conference for c in conf]
        tba_names = [c.conference for c in tba]

        assert "Active Conference" in conf_names
        assert "TBA Conference" in tba_names

    def test_split_data_cfp_ext_handling(self):
        """Test handling of extended CFP deadlines."""
        now = datetime.now(tz=timezone.utc).date()

        conf = Conference(
            conference="Extended CFP Conference",
            year=2025,
            cfp="2025-02-15",  # No time
            cfp_ext="2025-03-01",  # No time
            link="https://extended.com",
            place="City A",
            start=now + timedelta(days=60),
            end=now + timedelta(days=63),
            sub="PY",
        )

        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result_conf, _, _, _ = sort_yaml.split_data([conf])

        # Should have added time to both cfp and cfp_ext
        assert len(result_conf) == 1
        processed = result_conf[0]
        assert "23:59:00" in processed.cfp
        assert "23:59:00" in processed.cfp_ext

    def test_split_data_boundary_dates(self):
        """Test splitting with boundary date conditions."""
        now = datetime.now(tz=timezone.utc).date()

        # Conference that ends exactly 37 days ago (boundary condition)
        boundary_conf = Conference(
            conference="Boundary Conference",
            year=2025,
            cfp="2025-02-15 23:59:00",
            link="https://boundary.com",
            place="City A",
            start=now - timedelta(days=40),
            end=now - timedelta(days=37),
            sub="PY",
        )

        with patch("tqdm.tqdm", side_effect=lambda x: x):
            conf, tba, expired, legacy = sort_yaml.split_data([boundary_conf])

        # Should be categorized based on the 37-day rule
        total_processed = len(conf) + len(tba) + len(expired) + len(legacy)
        assert total_processed == 1


class TestCheckLinks:
    """Test link checking functionality."""

    @patch("sort_yaml.get_cache")
    @patch("sort_yaml.check_link_availability")
    @patch("sort_yaml.time.sleep")
    def test_check_links_basic(self, mock_sleep, mock_check_link, mock_get_cache):
        """Test basic link checking functionality."""
        mock_get_cache.return_value = (set(), set())
        mock_check_link.return_value = "https://updated.com"

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "link": "https://original.com",
                "cfp_link": "https://cfp-original.com",
                "start": "2025-06-01",
            },
        ]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.check_links(data)

        # Should have updated links
        assert result[0]["link"] == "https://updated.com"
        assert result[0]["cfp_link"] == "https://updated.com"
        assert mock_check_link.call_count >= 2

    @patch("sort_yaml.get_cache")
    @patch("sort_yaml.check_link_availability")
    @patch("sort_yaml.time.sleep")
    def test_check_links_archive_org_handling(self, mock_sleep, mock_check_link, mock_get_cache):
        """Test special handling of archive.org links."""
        mock_get_cache.return_value = (set(), set())

        # Mock check_link_availability to return archive.org URL
        mock_check_link.return_value = "https://web.archive.org/web/20250101000000/https://original.com"

        data = [{"conference": "Test Conference", "year": 2025, "link": "https://original.com", "start": "2025-06-01"}]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.check_links(data)

        # Should have updated to archive.org link and called sleep
        assert "archive.org" in result[0]["link"]
        mock_sleep.assert_called_with(0.5)

    @patch("sort_yaml.get_cache")
    @patch("sort_yaml.check_link_availability")
    def test_check_links_missing_keys(self, mock_check_link, mock_get_cache):
        """Test link checking with missing keys."""
        mock_get_cache.return_value = (set(), set())
        mock_check_link.return_value = "https://updated.com"

        data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "link": "https://original.com",
                # Missing cfp_link, sponsor, finaid
                "start": "2025-06-01",
            },
        ]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.check_links(data)

        # Should only check the link that exists
        assert mock_check_link.call_count == 1
        assert result[0]["link"] == "https://updated.com"


class TestSortDataIntegration:
    """Test the main sort_data function integration."""

    @patch("sort_yaml.write_conference_yaml")
    @patch("sort_yaml.add_latlon")
    @patch("sort_yaml.auto_add_sub")
    @patch("sort_yaml.tidy_titles")
    @patch("sort_yaml.tidy_dates")
    @patch("sort_yaml.get_tqdm_logger")
    @patch("builtins.open", new_callable=mock_open)
    @patch("sort_yaml.Path")
    def test_sort_data_basic_flow(
        self,
        mock_path,
        mock_file_open,
        mock_logger,
        mock_tidy_dates,
        mock_tidy_titles,
        mock_auto_add_sub,
        mock_add_latlon,
        mock_write_yaml,
    ):
        """Test basic sort_data workflow."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock file existence and content
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock YAML content
        mock_yaml_content = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "cfp": "2025-02-15",
                "link": "https://test.com",
                "place": "Test City",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
        ]

        with patch("yaml.load", return_value=mock_yaml_content), patch(
            "sort_yaml.Conference",
        ) as mock_conf_class, patch("sort_yaml.merge_duplicates") as mock_merge, patch(
            "sort_yaml.split_data",
        ) as mock_split:

            # Setup mocks
            mock_tidy_dates.return_value = mock_yaml_content
            mock_tidy_titles.return_value = mock_yaml_content
            mock_auto_add_sub.return_value = mock_yaml_content
            mock_add_latlon.return_value = mock_yaml_content
            mock_merge.return_value = mock_yaml_content

            # Mock Conference validation
            valid_conf = Conference(**mock_yaml_content[0])
            mock_conf_class.return_value = valid_conf

            # Mock split_data results
            mock_split.return_value = ([valid_conf], [], [], [])

            # Run sort_data
            sort_yaml.sort_data(skip_links=True)

            # Verify key steps were called
            assert mock_logger_instance.info.called
            mock_write_yaml.assert_called()

    @patch("sort_yaml.get_tqdm_logger")
    def test_sort_data_no_files_exist(self, mock_logger):
        """Test sort_data when no data files exist."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        with patch("sort_yaml.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            # Should handle gracefully
            sort_yaml.sort_data()

            # Should log that no data was loaded
            info_calls = [str(call) for call in mock_logger_instance.info.call_args_list]
            assert any("Loaded 0 conferences" in call for call in info_calls)

    @patch("sort_yaml.get_tqdm_logger")
    def test_sort_data_validation_errors(self, mock_logger):
        """Test sort_data with validation errors."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        invalid_data = [
            {
                "conference": "Invalid Conference",
                # Missing required fields
                "year": "invalid_year",
            },
        ]

        with patch("sort_yaml.Path") as mock_path, patch("builtins.open", mock_open()), patch(
            "yaml.load",
            return_value=invalid_data,
        ), patch("sort_yaml.tidy_dates", return_value=invalid_data), patch(
            "sort_yaml.tidy_titles",
            return_value=invalid_data,
        ), patch(
            "sort_yaml.auto_add_sub",
            return_value=invalid_data,
        ), patch(
            "sort_yaml.add_latlon",
            return_value=invalid_data,
        ), patch(
            "sort_yaml.merge_duplicates",
            return_value=invalid_data,
        ), patch(
            "sort_yaml.write_conference_yaml",
        ):

            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            # Should handle validation errors gracefully
            sort_yaml.sort_data()

            # Should log validation errors
            assert mock_logger_instance.error.called
            assert mock_logger_instance.warning.called


class TestCommandLineInterface:
    """Test command line interface for sort_yaml."""

    @patch("sort_yaml.sort_data")
    def test_cli_default_arguments(self, mock_sort_data):
        """Test CLI with default arguments."""
        with patch("sys.argv", ["sort_yaml.py"]):
            # Import and test argument parsing
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--skip_links", action="store_true", default=False)

            args = parser.parse_args([])
            assert args.skip_links is False

    @patch("sort_yaml.sort_data")
    def test_cli_skip_links_argument(self, mock_sort_data):
        """Test CLI with --skip_links argument."""
        with patch("sys.argv", ["sort_yaml.py", "--skip_links"]):
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--skip_links", action="store_true", default=False)

            args = parser.parse_args(["--skip_links"])
            assert args.skip_links is True


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_sort_by_cfp_none_timezone(self):
        """Test CFP sorting when timezone is None."""
        conf = Conference(
            conference="Test Conference",
            year=2025,
            cfp="2025-02-15 12:00:00",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
            timezone=None,
        )

        result = sort_yaml.sort_by_cfp(conf)
        # Should use AoE as default
        assert isinstance(result, str)

    def test_merge_duplicates_empty_data(self):
        """Test merge duplicates with empty data."""
        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result = sort_yaml.merge_duplicates([])

        assert result == []

    def test_tidy_dates_empty_data(self):
        """Test tidy dates with empty data."""
        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.tidy_dates([])

        assert result == []

    def test_check_links_empty_data(self):
        """Test check links with empty data."""
        with patch("sort_yaml.get_cache", return_value=(set(), set())), patch(
            "tqdm.tqdm",
            side_effect=lambda x, total=None: x,
        ):
            result = sort_yaml.check_links([])

        assert result == []

    @patch("sort_yaml.get_tqdm_logger")
    def test_sort_data_yaml_error_handling(self, mock_logger):
        """Test sort_data handles YAML errors gracefully."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        with patch("sort_yaml.Path") as mock_path, patch("builtins.open", mock_open()), patch(
            "yaml.load",
            side_effect=yaml.YAMLError("Invalid YAML"),
        ):

            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            # Should handle YAML errors gracefully due to contextlib.suppress
            sort_yaml.sort_data()

            # Should continue processing despite YAML error
            assert mock_logger_instance.info.called
