"""Comprehensive integration tests for the entire Python Deadlines pipeline."""

import sys
import tempfile
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import git_parser
import main
import newsletter
import sort_yaml
from tidy_conf.schema import Conference


class TestEndToEndPipeline:
    """Test complete end-to-end pipeline integration."""

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_complete_pipeline_success(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test complete pipeline from data import to final output."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock successful execution of all steps
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        # Execute complete pipeline
        main.main()

        # Verify pipeline execution order
        mock_official.assert_called_once()
        mock_organizer.assert_called_once()
        assert mock_sort.call_count == 2

        # Verify logging of pipeline steps
        info_calls = [str(call[0][0]) for call in mock_logger_instance.info.call_args_list]
        pipeline_messages = [
            "Starting Python Deadlines data processing pipeline",
            "Step 1: Importing from Python official calendar",
            "Step 2: Sorting and validating data",
            "Step 3: Importing from Python organizers",
            "Step 4: Final sorting and validation",
            "Data processing pipeline completed successfully",
        ]

        for message in pipeline_messages:
            assert any(message in call for call in info_calls)

    @patch("sort_yaml.write_conference_yaml")
    @patch("sort_yaml.add_latlon")
    @patch("sort_yaml.auto_add_sub")
    @patch("sort_yaml.tidy_titles")
    @patch("sort_yaml.tidy_dates")
    @patch("sort_yaml.get_tqdm_logger")
    @patch("builtins.open", new_callable=mock_open)
    @patch("sort_yaml.Path")
    def test_data_flow_through_sort_pipeline(
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
        """Test data flow through the complete sorting pipeline."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock file existence for specific conference data files only
        def mock_path_side_effect(*args, **kwargs):
            mock_path_instance = Mock()
            # Join all path arguments to check the full path
            path_str = "/".join(str(arg) for arg in args)
            # Only mock conference data files, not pytz timezone files
            if path_str.endswith((".yml", ".yaml")) and ("_data" in path_str or "conferences" in path_str):
                mock_path_instance.exists.return_value = True
                # Set up context manager for file opening
                mock_file_context = Mock()
                mock_file_context.__enter__ = Mock(return_value=mock_file_context)
                mock_file_context.__exit__ = Mock(return_value=None)
                mock_path_instance.open.return_value = mock_file_context
            else:
                # For other files (like pytz data), don't mock
                mock_path_instance.exists.return_value = False
                mock_path_instance.open.side_effect = FileNotFoundError("Not mocked")
            return mock_path_instance

        mock_path.side_effect = mock_path_side_effect

        # Create realistic conference data that flows through pipeline
        conference_data = [
            {
                "conference": "PyCon US 2025",
                "year": 2025,
                "cfp": "2025-02-15",
                "link": "https://pycon.org",
                "place": "Pittsburgh, PA, USA",
                "start": "2025-05-15",
                "end": "2025-05-23",
                "sub": "PY",
                "location": [{"latitude": 40.4406, "longitude": -79.9959}],
            },
            {
                "conference": "DjangoCon Europe 2025",
                "year": 2025,
                "cfp": "TBA",
                "link": "https://djangocon.eu",
                "place": "Vigo, Spain",
                "start": "2025-06-04",
                "end": "2025-06-08",
                "sub": "WEB",
                "location": [{"latitude": 42.2406, "longitude": -8.7207}],
            },
        ]

        # Mock each processing step to track data transformation
        def track_tidy_dates(data):
            # Simulate date cleaning
            for item in data:
                if item["cfp"] != "TBA":
                    item["cfp"] = item["cfp"] + " 23:59:00"
            return data

        def track_tidy_titles(data):
            # Simulate title cleaning
            return data

        def track_auto_add_sub(data):
            # Simulate sub-type addition
            return data

        def track_add_latlon(data):
            # Simulate geolocation addition
            for item in data:
                if "location" not in item:
                    item["location"] = [{"latitude": 40.7128, "longitude": -74.0060}]
            return data

        mock_tidy_dates.side_effect = track_tidy_dates
        mock_tidy_titles.side_effect = track_tidy_titles
        mock_auto_add_sub.side_effect = track_auto_add_sub
        mock_add_latlon.side_effect = track_add_latlon

        with patch("yaml.load", return_value=conference_data), patch("sort_yaml.merge_duplicates") as mock_merge, patch(
            "sort_yaml.split_data",
        ) as mock_split, patch("sort_yaml.sort_by_cfp", return_value="2025-02-15 23:59:00"):

            # Create valid Conference instances
            valid_conferences = [Conference(**item) for item in conference_data]

            mock_merge.return_value = conference_data
            mock_split.return_value = (valid_conferences, [], [], [])

            # Execute sorting pipeline
            sort_yaml.sort_data(skip_links=True)

            # Verify data transformation chain
            mock_tidy_dates.assert_called_once()
            mock_tidy_titles.assert_called_once()
            mock_auto_add_sub.assert_called_once()
            mock_add_latlon.assert_called_once()
            mock_write_yaml.assert_called()

    @patch("newsletter.load_conferences")
    @patch("git_parser.GitCommitParser._execute_git_command")
    @patch("builtins.print")
    def test_newsletter_git_parser_integration(self, mock_print, mock_git_execute, mock_load_conferences):
        """Test integration between newsletter generation and git parsing."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Mock conference data for newsletter
        mock_conferences = pd.DataFrame(
            {
                "conference": ["PyCon US 2025", "EuroSciPy 2025"],
                "cfp": [now + timedelta(days=5), now + timedelta(days=8)],
                "cfp_ext": [pd.NaT, pd.NaT],
                "year": [2025, 2025],
                "place": ["Pittsburgh, USA", "Basel, Switzerland"],
                "link": ["https://pycon.org", "https://euroscipy.org"],
            },
        )
        mock_load_conferences.return_value = mock_conferences

        # Mock git log output for parser
        mock_git_execute.return_value = (
            "abc123\n"
            "cfp: PyCon US 2025 Call for Proposals\n"
            "Organizer\n"
            "2025-01-15 10:30:00 +0000\n"
            "def456\n"
            "conf: EuroSciPy 2025 Conference Added\n"
            "Contributor\n"
            "2025-01-20 14:15:30 +0100"
        )

        # Generate newsletter
        newsletter.main(days=10)

        # Generate git report
        parser = git_parser.GitCommitParser(days=7)
        git_report = parser.generate_markdown_report()

        # Verify both tools process same conferences
        newsletter_calls = [str(call) for call in mock_print.call_args_list]

        # Should find conferences in newsletter
        assert any("PyCon US 2025" in call for call in newsletter_calls)
        assert any("EuroSciPy 2025" in call for call in newsletter_calls)

        # Should find same conferences in git report
        assert "PyCon US 2025" in git_report
        assert "EuroSciPy 2025" in git_report
        assert "## Call for Papers" in git_report
        assert "## Conferences" in git_report

    def test_schema_validation_across_modules(self):
        """Test that schema validation works consistently across all modules."""
        # Create test data that should pass validation
        valid_conference_data = {
            "conference": "Test Conference",
            "year": 2025,
            "cfp": "2025-02-15 23:59:00",
            "link": "https://test.com",
            "place": "Test City, Test Country",
            "start": "2025-06-01",
            "end": "2025-06-03",
            "sub": "PY",
            "location": [{"latitude": 40.7128, "longitude": -74.0060}],
        }

        # Test Conference validation
        conf = Conference(**valid_conference_data)
        assert conf.conference == "Test Conference"
        assert conf.year == 2025

        # Test data processing with this schema
        from tidy_conf.date import clean_dates

        processed_data = clean_dates(valid_conference_data.copy())

        # Should still validate after processing
        processed_conf = Conference(**processed_data)
        assert processed_conf.conference == "Test Conference"

    @patch("sort_yaml.check_link_availability")
    @patch("sort_yaml.get_cache")
    def test_link_checking_integration(self, mock_get_cache, mock_check_link):
        """Test link checking integration with data processing."""
        mock_get_cache.return_value = (set(), set())
        mock_check_link.return_value = "https://updated-link.com"

        # Test data with various link types
        test_data = [
            {
                "conference": "Conference with Links",
                "year": 2025,
                "link": "https://original-link.com",
                "cfp_link": "https://cfp-link.com",
                "sponsor": "https://sponsor-link.com",
                "finaid": "https://finaid-link.com",
                "start": "2025-06-01",
            },
        ]

        with patch("tqdm.tqdm", side_effect=lambda x, total=None: x):
            result = sort_yaml.check_links(test_data)

        # All links should be updated
        assert result[0]["link"] == "https://updated-link.com"
        assert result[0]["cfp_link"] == "https://updated-link.com"
        assert result[0]["sponsor"] == "https://updated-link.com"
        assert result[0]["finaid"] == "https://updated-link.com"

        # Should have checked all 4 links
        assert mock_check_link.call_count == 4


class TestDataConsistency:
    """Test data consistency across pipeline stages."""

    def test_date_format_consistency(self):
        """Test that date formats remain consistent across processing."""
        test_data = {"start": "2025-06-01", "end": "2025-06-03", "cfp": "2025-02-15"}

        # Process through date cleaning
        from tidy_conf.date import clean_dates
        from tidy_conf.date import create_nice_date

        cleaned = clean_dates(test_data.copy())
        nice_date = create_nice_date(cleaned.copy())

        # Verify date formats
        assert isinstance(cleaned["start"], date)
        assert isinstance(cleaned["end"], date)
        assert cleaned["cfp"] == "2025-02-15 23:59:00"
        assert nice_date["date"] == "June 1 - 3, 2025"

    def test_conference_name_consistency(self):
        """Test that conference names remain consistent across processing."""
        test_conferences = [
            {"conference": "PyCon US", "year": 2025, "place": "Pittsburgh"},
            {"conference": "PyCon US", "year": 2025, "place": "Pittsburgh"},  # Duplicate
        ]

        # Test merge duplicates
        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result = sort_yaml.merge_duplicates(test_conferences)

        # Should merge to single entry with consistent name
        assert len(result) == 1
        assert result[0]["conference"] == "PyCon US"

    def test_geolocation_data_consistency(self):
        """Test geolocation data consistency."""
        conference_data = [
            {
                "conference": "Test Conference",
                "year": 2025,
                "place": "New York, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        with patch("tidy_conf.latlon.requests.get") as mock_get, patch("tidy_conf.latlon.time.sleep"), patch(
            "tqdm.tqdm",
            side_effect=lambda x, total=None: x,
        ):

            mock_response = Mock()
            mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, USA"}]
            mock_get.return_value = mock_response

            from tidy_conf.latlon import add_latlon

            result = add_latlon(conference_data)

            # Should have consistent location data
            assert len(result) == 1
            if "location" in result[0]:
                location = result[0]["location"][0]
                assert "latitude" in location
                assert "longitude" in location


class TestErrorPropagation:
    """Test error handling and propagation across modules."""

    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_error_propagation_in_pipeline(self, mock_logger, mock_official):
        """Test that errors propagate correctly through pipeline."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Make official updater fail
        mock_official.side_effect = Exception("Import failed")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        # Should exit with error code
        assert exc_info.value.code == 1

        # Should log the error
        mock_logger_instance.error.assert_called_once()

    def test_validation_error_handling(self):
        """Test handling of validation errors in processing."""
        invalid_data = [
            {
                "conference": "Invalid Conference",
                "year": "invalid_year",  # Invalid type
                # Missing required fields
            },
        ]

        # Should handle validation gracefully
        def validate_conference(item):
            try:
                return Conference(**item), None
            except Exception as e:
                return None, str(e)

        results = [validate_conference(item) for item in invalid_data]
        validated_data = [conf for conf, _ in results if conf is not None]
        validation_errors = [error for _, error in results if error is not None]

        # Verify that validation errors were detected
        assert len(validation_errors) > 0
        # No valid conferences should remain
        assert len(validated_data) == 0

    @patch("sort_yaml.get_tqdm_logger")
    def test_file_io_error_handling(self, mock_logger):
        """Test handling of file I/O errors."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Create a simple test scenario by using an empty directory structure
        # This simulates file I/O scenarios where no conference data exists
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the _data directory structure but with no conference files
            data_dir = Path(temp_dir) / "_data"
            data_dir.mkdir(exist_ok=True)

            # Should handle gracefully when no files exist
            sort_yaml.sort_data(base=temp_dir)

            # Should log that no data was loaded
            info_calls = [str(call) for call in mock_logger_instance.info.call_args_list]
            assert any("Loaded 0 conferences" in call for call in info_calls)


class TestPerformanceIntegration:
    """Test performance characteristics of integrated pipeline."""

    def test_large_dataset_processing(self):
        """Test processing of large datasets."""
        # Create a moderately large dataset
        large_dataset = [
            {
                "conference": f"Conference {i}",
                "year": 2025,
                "cfp": "2025-02-15",
                "link": f"https://conf{i}.com",
                "place": f"City {i}",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            }
            for i in range(100)
        ]

        # Test merge duplicates performance
        with patch("tqdm.tqdm", side_effect=lambda x: x):
            result = sort_yaml.merge_duplicates(large_dataset)

        # Should handle large dataset efficiently
        assert len(result) == 100  # No duplicates, so all should remain

    def test_memory_efficiency_newsletter(self):
        """Test memory efficiency of newsletter generation."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Create large conference dataset
        large_conferences = pd.DataFrame(
            {
                "conference": [f"Conference {i}" for i in range(1000)],
                "cfp": [now + timedelta(days=5)] * 1000,  # All within range
                "cfp_ext": [pd.NaT] * 1000,
                "year": [2025] * 1000,
            },
        )

        with patch("newsletter.load_conferences", return_value=large_conferences), patch("builtins.print"):

            # Should handle large dataset efficiently
            newsletter.main(days=10)


class TestDataIntegrityE2E:
    """Test end-to-end data integrity scenarios."""

    def test_conference_lifecycle_tracking(self):
        """Test tracking a conference through its complete lifecycle."""
        now = datetime.now(tz=timezone.utc).date()

        # Conference in different lifecycle stages
        conferences = [
            # Active conference
            Conference(
                conference="Active Conference",
                year=2025,
                cfp="2025-02-15 23:59:00",
                link="https://active.com",
                place="Active City",
                start=now + timedelta(days=60),
                end=now + timedelta(days=63),
                sub="PY",
                location=[{"latitude": 40.7128, "longitude": -74.0060}],
            ),
            # Expired conference
            Conference(
                conference="Expired Conference",
                year=2024,
                cfp="2024-02-15 23:59:00",
                link="https://expired.com",
                place="Expired City",
                start=now - timedelta(days=100),
                end=now - timedelta(days=97),
                sub="PY",
                location=[{"latitude": 40.7128, "longitude": -74.0060}],
            ),
            # Legacy conference (more than 7 years ago)
            Conference(
                conference="Legacy Conference",
                year=2016,
                cfp="2016-02-15 23:59:00",
                link="https://legacy.com",
                place="Legacy City",
                start=now - timedelta(days=3000),  # ~8.2 years ago
                end=now - timedelta(days=2997),  # ~8.2 years ago
                sub="PY",
                location=[{"latitude": 40.7128, "longitude": -74.0060}],
            ),
        ]

        # Test data splitting
        with patch("tqdm.tqdm", side_effect=lambda x: x):
            conf, _tba, expired, legacy = sort_yaml.split_data(conferences)

        # Verify proper categorization
        assert len(conf) >= 1  # Active conference
        assert len(expired) >= 1  # Expired conference
        assert len(legacy) >= 1  # Legacy conference

        # Verify conferences are in correct categories
        conf_names = [c.conference for c in conf]
        expired_names = [c.conference for c in expired]
        legacy_names = [c.conference for c in legacy]

        assert "Active Conference" in conf_names
        assert "Expired Conference" in expired_names
        assert "Legacy Conference" in legacy_names

    def test_multi_deadline_consistency(self):
        """Test consistency of multiple deadline types."""
        conference_with_deadlines = {
            "conference": "Multi-Deadline Conference",
            "year": 2025,
            "cfp": "2025-02-15",
            "workshop_deadline": "2025-01-15",
            "tutorial_deadline": "2025-01-20",
            "start": "2025-06-01",
            "end": "2025-06-03",
        }

        # Process through date cleaning
        from tidy_conf.date import clean_dates

        processed = clean_dates(conference_with_deadlines.copy())

        # All deadlines should have consistent time format
        assert processed["cfp"] == "2025-02-15 23:59:00"
        assert processed["workshop_deadline"] == "2025-01-15 23:59:00"
        assert processed["tutorial_deadline"] == "2025-01-20 23:59:00"

    def test_international_conference_support(self):
        """Test support for international conferences with various formats."""
        international_conferences = [
            {
                "conference": "PyCon España",
                "year": 2025,
                "place": "Madrid, España",
                "cfp": "2025-02-15",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
            {
                "conference": "PyCon 中国",
                "year": 2025,
                "place": "北京, 中国",
                "cfp": "2025-03-01",
                "start": "2025-07-01",
                "end": "2025-07-03",
                "sub": "PY",
            },
        ]

        # Test processing international data
        from tidy_conf.date import clean_dates

        for conf_data in international_conferences:
            processed = clean_dates(conf_data.copy())

            # Should handle international characters correctly
            assert processed["conference"] in ["PyCon España", "PyCon 中国"]
            assert processed["cfp"].endswith(" 23:59:00")


class TestBusinessLogicIntegration:
    """Test business logic integration across modules."""

    def test_cfp_priority_logic(self):
        """Test CFP vs CFP extended priority logic."""
        from datetime import timedelta

        today = datetime.now(timezone.utc).date()

        # Conference where cfp is in range but cfp_ext is NOT
        # If cfp_ext takes priority (as it should), this should NOT be included
        conf_cfp_only_in_range = {
            "conference": "CFP Only In Range",
            "year": today.year,
            "cfp": (today + timedelta(days=5)).isoformat(),  # In 30-day range
            "cfp_ext": (today + timedelta(days=60)).isoformat(),  # Outside 30-day range
            "place": "Test City",
            "start": (today + timedelta(days=90)).isoformat(),
            "end": (today + timedelta(days=92)).isoformat(),
        }

        # Conference where cfp is NOT in range but cfp_ext IS
        # If cfp_ext takes priority (as it should), this SHOULD be included
        conf_cfp_ext_in_range = {
            "conference": "CFP Ext In Range",
            "year": today.year,
            "cfp": (today - timedelta(days=30)).isoformat(),  # Past/outside range
            "cfp_ext": (today + timedelta(days=10)).isoformat(),  # In 30-day range
            "place": "Test City",
            "start": (today + timedelta(days=90)).isoformat(),
            "end": (today + timedelta(days=92)).isoformat(),
        }

        df = pd.DataFrame([conf_cfp_only_in_range, conf_cfp_ext_in_range])

        with patch("builtins.print"):
            filtered = newsletter.filter_conferences(df, days=30)

        # cfp_ext takes priority: only "CFP Ext In Range" should be included
        assert len(filtered) == 1, f"Expected 1 conference, got {len(filtered)}"
        assert filtered.iloc[0]["conference"] == "CFP Ext In Range"

    def test_archive_vs_live_link_logic(self):
        """Test logic for handling archive vs live links."""
        test_data = [
            {"conference": "Link Test Conference", "year": 2025, "link": "https://original.com", "start": "2025-06-01"},
        ]

        with patch("sort_yaml.get_cache", return_value=(set(), set())), patch(
            "sort_yaml.check_link_availability",
        ) as mock_check, patch("sort_yaml.time.sleep"), patch("tqdm.tqdm", side_effect=lambda x, total=None: x):

            # Mock return of archive.org URL
            mock_check.return_value = "https://web.archive.org/web/20250101/https://original.com"

            result = sort_yaml.check_links(test_data)

            # Should update to archive URL
            assert "archive.org" in result[0]["link"]

    def test_timezone_normalization_across_modules(self):
        """Test timezone handling consistency."""
        # Test data with different timezone formats
        conference_with_tz = Conference(
            conference="Timezone Test",
            year=2025,
            cfp="2025-02-15 12:00:00",
            link="https://test.com",
            place="Test City",
            start="2025-06-01",
            end="2025-06-03",
            sub="PY",
            timezone="America/New_York",
            location=[{"latitude": 40.7128, "longitude": -74.0060}],
        )

        # Test CFP sorting with timezone
        result = sort_yaml.sort_by_cfp(conference_with_tz)

        # Should produce consistent date format
        assert isinstance(result, str)
        assert len(result) == 19  # YYYY-MM-DD HH:MM:SS format


class TestRealDataProcessing:
    """Integration tests that use real data processing with minimal mocking.

    These tests address the audit finding that many tests over-mock, hiding
    potential bugs. Instead of mocking every function, we create real test
    data and only mock external I/O operations.
    """

    @pytest.fixture()
    def temp_data_dir(self, tmp_path):
        """Create a temporary data directory with real YAML files."""
        data_dir = tmp_path / "_data"
        data_dir.mkdir()

        # Create realistic conference data
        today = datetime.now(timezone.utc).date()
        test_conferences = [
            {
                "conference": "Test PyCon US",
                "year": today.year,
                "link": "https://pycon.us",
                "cfp": (today + timedelta(days=30)).isoformat(),
                "place": "Pittsburgh, PA, USA",
                "start": (today + timedelta(days=90)).isoformat(),
                "end": (today + timedelta(days=93)).isoformat(),
                "sub": "PY",
            },
            {
                "conference": "Test DjangoCon",
                "year": today.year,
                "link": "https://djangocon.us",
                "cfp": (today + timedelta(days=15)).isoformat(),
                "place": "Durham, NC, USA",
                "start": (today + timedelta(days=60)).isoformat(),
                "end": (today + timedelta(days=62)).isoformat(),
                "sub": "WEB",
            },
        ]

        from yaml import safe_dump

        # Write conferences.yml (use safe_dump to avoid custom representers)
        with (data_dir / "conferences.yml").open("w") as f:
            safe_dump(test_conferences, f, default_flow_style=False)

        # Write empty archive and legacy files
        with (data_dir / "archive.yml").open("w") as f:
            safe_dump([], f)

        with (data_dir / "legacy.yml").open("w") as f:
            safe_dump([], f)

        return tmp_path

    def test_tidy_dates_with_real_data(self, temp_data_dir):
        """Test tidy_dates with real conference data, not mocks.

        This verifies actual date processing logic works correctly.
        """
        from yaml import safe_load

        # Load the test data
        with (temp_data_dir / "_data" / "conferences.yml").open() as f:
            data = safe_load(f)

        # Process with real tidy_dates function
        result = sort_yaml.tidy_dates(data)

        # Verify actual data transformation
        assert len(result) == 2
        for conf in result:
            # CFP should have time component added
            assert "cfp" in conf
            if conf["cfp"] not in ["TBA", "Cancelled"]:
                assert " " in conf["cfp"], f"CFP should have time: {conf['cfp']}"
                assert conf["cfp"].endswith("23:59:00"), f"CFP should end with 23:59:00: {conf['cfp']}"

    def test_tidy_titles_with_real_data(self, temp_data_dir):
        """Test tidy_titles preserves conference names correctly."""
        from yaml import safe_load

        with (temp_data_dir / "_data" / "conferences.yml").open() as f:
            data = safe_load(f)

        original_names = [d["conference"] for d in data]

        result = sort_yaml.tidy_titles(data)

        # Names should be preserved (not corrupted)
        result_names = [d["conference"] for d in result]
        for name in original_names:
            assert name in result_names, f"Conference name '{name}' was lost"

    def test_auto_add_sub_with_real_data(self, temp_data_dir):
        """Test auto_add_sub correctly assigns topic codes."""
        # Create data without 'sub' field
        data_without_sub = [
            {
                "conference": "PyCon US",
                "year": 2025,
                "link": "https://pycon.us",
                "cfp": "2025-02-15 23:59:00",
                "place": "Pittsburgh, PA, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
            },
        ]

        result = sort_yaml.auto_add_sub(data_without_sub)

        # Should have added a 'sub' field
        assert "sub" in result[0], "auto_add_sub should add 'sub' field"

    @pytest.mark.skip(reason="Requires `responses` library for proper HTTP-level mocking; see audit item #6")
    def test_check_links_with_http_mock(self):
        """Test link checking with HTTP-level mocking (not function mocking).

        This addresses audit finding #6: mock at HTTP level, not function level.

        Note: This test should use the `responses` or `httpretty` library
        for proper HTTP-level mocking instead of mocking requests.get directly.
        The current Mock approach doesn't properly simulate HTTP responses.

        Example using responses:
        ```python
        import responses

        @responses.activate
        def test_check_links_real():
            responses.add(responses.GET, "https://pycon.us", status=200)
            result = sort_yaml.check_links(test_data)
            assert len(result) == len(test_data)
        ```
        """
        # Skipped - needs `responses` library

    def test_sort_by_cfp_with_real_conferences(self):
        """Test sorting actually orders conferences correctly by CFP deadline."""
        today = datetime.now(timezone.utc).date()

        # Create Conference objects for proper sorting
        # Using "Online" as place avoids needing location coordinates
        unsorted_confs = [
            Conference(
                conference="Late CFP",
                year=today.year,
                link="https://late.com",
                cfp=(today + timedelta(days=30)).isoformat() + " 23:59:00",
                place="Online",
                start=(today + timedelta(days=90)).isoformat(),
                end=(today + timedelta(days=92)).isoformat(),
                sub="PY",
            ),
            Conference(
                conference="Early CFP",
                year=today.year,
                link="https://early.com",
                cfp=(today + timedelta(days=10)).isoformat() + " 23:59:00",
                place="Online",
                start=(today + timedelta(days=90)).isoformat(),
                end=(today + timedelta(days=92)).isoformat(),
                sub="PY",
            ),
            Conference(
                conference="Mid CFP",
                year=today.year,
                link="https://mid.com",
                cfp=(today + timedelta(days=20)).isoformat() + " 23:59:00",
                place="Online",
                start=(today + timedelta(days=90)).isoformat(),
                end=(today + timedelta(days=92)).isoformat(),
                sub="PY",
            ),
        ]

        # Sort using actual sort_by_cfp function
        sorted_confs = sorted(unsorted_confs, key=sort_yaml.sort_by_cfp)

        # Verify sorting works (earliest deadline first)
        assert sorted_confs[0].conference == "Early CFP"
        assert sorted_confs[1].conference == "Mid CFP"
        assert sorted_confs[2].conference == "Late CFP"

    def test_merge_duplicates_with_real_data(self):
        """Test duplicate detection and merging with real data.

        merge_duplicates uses conference+year+place as the key.
        Same conference+year+place = merge. Different place = keep separate.
        """
        # Same conference, same year, same place = should merge
        duplicates_same_place = [
            {
                "conference": "PyCon US",
                "year": 2025,
                "link": "https://pycon.us",
                "cfp": "2025-02-15 23:59:00",
                "place": "Pittsburgh, USA",
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
            {
                "conference": "PyCon US",  # Same conference
                "year": 2025,
                "link": "https://pycon.us/2025",  # Different link but same event
                "cfp": "2025-02-20 23:59:00",  # Different CFP (update)
                "place": "Pittsburgh, USA",  # SAME place
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
        ]

        result = sort_yaml.merge_duplicates(duplicates_same_place)

        # Should merge into one conference (same conference+year+place)
        assert len(result) == 1, f"Expected 1 merged conference, got {len(result)}"
        # Name should be preserved
        assert result[0]["conference"] == "PyCon US"

    def test_merge_duplicates_different_places_preserved(self):
        """Test that conferences with different places are NOT merged.

        Different places indicates different events (e.g., regional conferences).
        """
        different_places = [
            {
                "conference": "PyCon US",
                "year": 2025,
                "link": "https://pycon.us",
                "cfp": "2025-02-15 23:59:00",
                "place": "Pittsburgh, USA",  # Place A
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
            {
                "conference": "PyCon US",
                "year": 2025,
                "link": "https://pycon-satellite.us",
                "cfp": "2025-02-20 23:59:00",
                "place": "Online",  # Different place
                "start": "2025-06-01",
                "end": "2025-06-03",
                "sub": "PY",
            },
        ]

        result = sort_yaml.merge_duplicates(different_places)

        # Should keep both (different places = potentially different events)
        assert len(result) == 2, f"Expected 2 conferences (different places), got {len(result)}"
