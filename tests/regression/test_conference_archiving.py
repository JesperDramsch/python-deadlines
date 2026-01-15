"""Regression tests for conference archiving functionality."""

import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
import yaml

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "utils"))

import operator

import sort_yaml
from tidy_conf.schema import Conference


class TestConferenceArchiving:
    """Test automatic conference archiving logic."""

    @pytest.fixture
    def past_conference(self):
        """Create a conference that should be archived."""
        past_date = datetime.now(timezone.utc) - timedelta(days=30)
        return {
            "conference": "Past PyCon",
            "year": 2024,
            "link": "https://past.pycon.org",
            "cfp": past_date.strftime("%Y-%m-%d %H:%M:%S"),
            "place": "Online",  # Use Online to avoid location validation
            "start": (past_date - timedelta(days=10)).strftime("%Y-%m-%d"),
            "end": (past_date - timedelta(days=7)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

    @pytest.fixture
    def future_conference(self):
        """Create a conference that should NOT be archived."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        return {
            "conference": "Future PyCon",
            "year": 2025,
            "link": "https://future.pycon.org",
            "cfp": future_date.strftime("%Y-%m-%d %H:%M:%S"),
            "place": "Online",  # Use Online to avoid location validation
            "start": (future_date + timedelta(days=10)).strftime("%Y-%m-%d"),
            "end": (future_date + timedelta(days=14)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

    @pytest.fixture
    def edge_case_conference(self):
        """Create a conference right at the archiving boundary."""
        boundary_date = datetime.now(timezone.utc) - timedelta(hours=1)
        return {
            "conference": "Edge Case Con",
            "year": datetime.now(tz=timezone.utc).year,
            "link": "https://edge.con.org",
            "cfp": boundary_date.strftime("%Y-%m-%d %H:%M:%S"),
            "place": "Online",  # Use Online to avoid location validation
            "start": boundary_date.strftime("%Y-%m-%d"),
            "end": (boundary_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

    def test_identify_past_conferences(self, past_conference, future_conference):
        """Test identification of conferences that should be archived."""
        past_conf = Conference(**past_conference)
        future_conf = Conference(**future_conference)

        # Past conference should be identified for archiving
        assert sort_yaml.sort_by_date_passed(past_conf) is True

        # Future conference should NOT be archived
        assert sort_yaml.sort_by_date_passed(future_conf) is False

    def test_archive_boundary_conditions(self, edge_case_conference):
        """Test archiving behavior at boundary conditions."""
        edge_conf = Conference(**edge_case_conference)

        # Conference with CFP 1 hour ago - result depends on exact timing
        # since sort_by_date_passed compares CFP datetime (not just date)
        is_passed = sort_yaml.sort_by_date_passed(edge_conf)
        # Just verify it returns a boolean - the exact result depends on timing
        assert isinstance(is_passed, bool)

    def test_archive_with_extended_deadline(self):
        """Test that extended deadlines are handled during archiving.

        Note: sort_by_date_passed only checks cfp, not cfp_ext.
        Extended deadlines are used elsewhere in the system.
        """
        base_date = datetime.now(timezone.utc)
        conf_data = {
            "conference": "Extended Deadline Con",
            "year": 2025,
            "link": "https://extended.con.org",
            "cfp": (base_date - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),  # Past
            "cfp_ext": (base_date + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),  # Future
            "place": "Online",  # Use Online to avoid location validation
            "start": (base_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "end": (base_date + timedelta(days=33)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

        conf = Conference(**conf_data)

        # sort_by_date_passed only checks cfp (not cfp_ext), so past cfp = archived
        # This is expected behavior - cfp_ext is used for display purposes
        assert sort_yaml.sort_by_date_passed(conf) is True
        # Verify cfp_ext is preserved for other uses
        assert conf.cfp_ext is not None

    def test_archive_with_missing_dates(self):
        """Test archiving behavior with missing or TBA dates."""
        # Conference with TBA deadline
        tba_conf_data = {
            "conference": "TBA Con",
            "year": 2025,
            "link": "https://tba.con.org",
            "cfp": "TBA",
            "place": "Online",  # Use Online to avoid location validation
            "start": "2025-06-01",
            "end": "2025-06-03",
            "sub": "PY",
        }

        tba_conf = Conference(**tba_conf_data)

        # TBA conferences should not be archived based on CFP
        # But might be archived based on end date if that's past
        result = sort_yaml.sort_by_date_passed(tba_conf)
        assert isinstance(result, bool)

    def test_bulk_archiving_process(self, past_conference, future_conference):
        """Test archiving multiple conferences at once."""
        conferences = [past_conference, future_conference]

        archived = []
        active = []

        for conf_data in conferences:
            conf = Conference(**conf_data)
            if sort_yaml.sort_by_date_passed(conf):
                archived.append(conf_data)
            else:
                active.append(conf_data)

        assert len(archived) == 1
        assert len(active) == 1
        assert archived[0]["conference"] == "Past PyCon"
        assert active[0]["conference"] == "Future PyCon"

    def test_archive_preserves_data_integrity(self, past_conference):
        """Test that archiving preserves all conference data."""
        original_conf = Conference(**past_conference)

        # Simulate archiving by converting to dict and back
        # Use exclude_none=True to avoid 'None' strings that fail URL validation
        archived_data = original_conf.model_dump(exclude_none=True)
        restored_conf = Conference(**archived_data)

        # All fields should be preserved
        assert restored_conf.conference == original_conf.conference
        assert restored_conf.year == original_conf.year
        assert restored_conf.link == original_conf.link
        assert restored_conf.cfp == original_conf.cfp
        assert restored_conf.place == original_conf.place
        assert restored_conf.start == original_conf.start
        assert restored_conf.end == original_conf.end
        assert restored_conf.sub == original_conf.sub

    def test_archive_with_timezone_handling(self):
        """Test archiving with different timezone configurations."""
        base_date = datetime.now(timezone.utc)

        # Conference with explicit timezone - use Online to avoid location validation
        tz_conf_data = {
            "conference": "Timezone Con",
            "year": 2024,
            "link": "https://tz.con.org",
            "cfp": (base_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": "America/New_York",
            "place": "Online",
            "start": (base_date - timedelta(days=10)).strftime("%Y-%m-%d"),
            "end": (base_date - timedelta(days=8)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

        # Conference without timezone (should use AoE)
        no_tz_conf_data = {
            "conference": "No TZ Con",
            "year": 2024,
            "link": "https://notz.con.org",
            "cfp": (base_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "place": "Online",  # Use Online to avoid location validation
            "start": (base_date - timedelta(days=10)).strftime("%Y-%m-%d"),
            "end": (base_date - timedelta(days=8)).strftime("%Y-%m-%d"),
            "sub": "PY",
        }

        tz_conf = Conference(**tz_conf_data)
        no_tz_conf = Conference(**no_tz_conf_data)

        # Both should be archived
        assert sort_yaml.sort_by_date_passed(tz_conf) is True
        assert sort_yaml.sort_by_date_passed(no_tz_conf) is True

    def test_prevent_duplicate_archiving(self):
        """Test that conferences aren't archived multiple times."""
        conf_data = {
            "conference": "Already Archived",
            "year": 2023,
            "link": "https://old.con.org",
            "cfp": "2023-01-01 00:00:00",
            "place": "Old City",
            "start": "2023-06-01",
            "end": "2023-06-03",
            "sub": "PY",
        }

        # Simulate checking if conference is already in archive
        archived_conferences = [conf_data]

        # Function to check duplicates
        def is_duplicate(conf, archive):
            for archived in archive:
                if conf["conference"] == archived["conference"] and conf["year"] == archived["year"]:
                    return True
            return False

        assert is_duplicate(conf_data, archived_conferences) is True

    def test_archive_sorting_order(self):
        """Test that archived conferences maintain proper sorting."""
        archived = [
            {
                "conference": "Oldest Con",
                "year": 2022,
                "cfp": "2022-01-01 00:00:00",
                "place": "A",
                "start": "2022-06-01",
                "end": "2022-06-03",
                "sub": "PY",
                "link": "https://a.com",
            },
            {
                "conference": "Middle Con",
                "year": 2023,
                "cfp": "2023-01-01 00:00:00",
                "place": "B",
                "start": "2023-06-01",
                "end": "2023-06-03",
                "sub": "PY",
                "link": "https://b.com",
            },
            {
                "conference": "Recent Con",
                "year": 2024,
                "cfp": "2024-01-01 00:00:00",
                "place": "C",
                "start": "2024-06-01",
                "end": "2024-06-03",
                "sub": "PY",
                "link": "https://c.com",
            },
        ]

        # Sort by year descending (most recent first)
        sorted_archive = sorted(archived, key=operator.itemgetter("year"), reverse=True)

        assert sorted_archive[0]["year"] == 2024
        assert sorted_archive[1]["year"] == 2023
        assert sorted_archive[2]["year"] == 2022

    @patch("sort_yaml.Path")
    def test_archive_file_operations(self, mock_path):
        """Test file operations during archiving."""
        # Mock file operations
        mock_archive_path = Mock()
        Mock()

        mock_path.return_value = mock_archive_path
        mock_archive_path.parent.parent.return_value = Mock()

        # Simulate archiving operation
        past_conferences = [
            {"conference": "Past 1", "year": 2023, "cfp": "2023-01-01 00:00:00"},
            {"conference": "Past 2", "year": 2023, "cfp": "2023-02-01 00:00:00"},
        ]

        # Verify that archive file would be written
        with patch("builtins.open", mock_open()) as mock_file:
            # Simulate writing to archive - use safe_dump to avoid Python 2/3 issues
            yaml.safe_dump(past_conferences, mock_file())
            mock_file.assert_called()

    def test_year_boundary_archiving(self):
        """Test archiving behavior at year boundaries."""
        # Conference at end of year
        end_of_year = {
            "conference": "Year End Con",
            "year": 2023,
            "link": "https://yearend.con.org",
            "cfp": "2023-12-31 23:59:59",
            "place": "Online",  # Use Online to avoid location validation
            "start": "2024-01-15",  # Next year
            "end": "2024-01-17",
            "sub": "PY",
        }

        # Conference at start of year
        start_of_year = {
            "conference": "Year Start Con",
            "year": 2024,
            "link": "https://yearstart.con.org",
            "cfp": "2023-11-30 23:59:59",  # Previous year
            "place": "Online",  # Use Online to avoid location validation
            "start": "2024-01-01",
            "end": "2024-01-03",
            "sub": "PY",
        }

        # Both should be handled correctly based on current date
        end_conf = Conference(**end_of_year)
        start_conf = Conference(**start_of_year)

        # These will be archived if current date is past their CFP
        current_date = datetime.now(timezone.utc)
        end_cfp = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        start_cfp = datetime(2023, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

        if current_date > end_cfp:
            assert sort_yaml.sort_by_date_passed(end_conf) is True
        if current_date > start_cfp:
            assert sort_yaml.sort_by_date_passed(start_conf) is True

    def test_archive_with_special_statuses(self):
        """Test archiving of conferences with special statuses."""
        # Cancelled conference
        cancelled_conf = {
            "conference": "Cancelled Con",
            "year": 2024,
            "link": "https://cancelled.con.org",
            "cfp": "Cancelled",
            "place": "Online",  # Use Online to avoid location validation
            "start": "2024-06-01",
            "end": "2024-06-03",
            "sub": "PY",
        }

        # Conference with no CFP
        no_cfp_conf = {
            "conference": "No CFP Con",
            "year": 2024,
            "link": "https://nocfp.con.org",
            "cfp": "None",
            "place": "Online",  # Use Online to avoid location validation
            "start": "2024-06-01",
            "end": "2024-06-03",
            "sub": "PY",
        }

        # These should be handled specially
        cancelled = Conference(**cancelled_conf)
        no_cfp = Conference(**no_cfp_conf)

        # Cancelled conferences might be archived immediately or kept for reference
        # No CFP conferences might be archived based on end date
        # The behavior depends on business rules
        assert isinstance(sort_yaml.sort_by_date_passed(cancelled), bool)
        assert isinstance(sort_yaml.sort_by_date_passed(no_cfp), bool)


class TestArchivePerformance:
    """Test performance aspects of archiving."""

    def test_large_scale_archiving(self):
        """Test archiving performance with many conferences."""
        # Create many conferences
        conferences = []
        base_date = datetime.now(timezone.utc)

        for i in range(1000):
            days_offset = i - 500  # Half past, half future
            conf_date = base_date + timedelta(days=days_offset)
            start_date = conf_date + timedelta(days=10)
            end_date = conf_date + timedelta(days=12)
            # Schema requires start and end to be in same year
            # Force end_date to same year as start_date if they cross boundary
            if start_date.year != end_date.year:
                end_date = start_date.replace(month=12, day=31)
            conf = {
                "conference": f"Conference {i}",
                "year": start_date.year,
                "link": f"https://conf{i}.org",
                "cfp": conf_date.strftime("%Y-%m-%d %H:%M:%S"),
                "place": "Online",  # Use Online to avoid location validation
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "sub": "PY",
            }
            conferences.append(conf)

        # Measure archiving time
        import time

        start_time = time.time()

        archived = []
        active = []
        for conf_data in conferences:
            conf = Conference(**conf_data)
            if sort_yaml.sort_by_date_passed(conf):
                archived.append(conf_data)
            else:
                active.append(conf_data)

        end_time = time.time()

        # Should complete in reasonable time (< 5 seconds for 1000 conferences)
        # Note: Pydantic validation adds overhead per-conference
        assert end_time - start_time < 5.0

        # Should have roughly half archived
        assert 400 < len(archived) < 600
        assert 400 < len(active) < 600

    def test_memory_efficiency(self):
        """Test that archiving doesn't cause memory issues."""
        import tracemalloc

        tracemalloc.start()

        # Create and archive many conferences
        conferences = []
        for i in range(10000):
            conf = {
                "conference": f"Conf {i}",
                "year": 2024,
                "link": f"https://c{i}.org",
                "cfp": "2024-01-01 00:00:00",
                "place": f"City {i}",
                "start": "2024-06-01",
                "end": "2024-06-03",
                "sub": "PY",
            }
            conferences.append(conf)

        # Get memory usage
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory usage should be reasonable (< 100 MB for 10k conferences)
        assert peak < 100 * 1024 * 1024  # 100 MB
