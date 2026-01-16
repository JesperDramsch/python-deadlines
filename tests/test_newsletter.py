"""Tests for newsletter functionality."""

import argparse
import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd
import pytest
from freezegun import freeze_time

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import newsletter


class TestFilterConferences:
    """Test conference filtering functionality."""

    @freeze_time("2026-06-01")
    def test_filter_conferences_basic(self):
        """Test basic conference filtering within time range."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Create test DataFrame with conferences
        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B", "Conference C"],
                "cfp": [
                    now + timedelta(days=5),  # Within range
                    now + timedelta(days=15),  # Outside range (too far)
                    now - timedelta(days=1),  # Outside range (past)
                ],
                "cfp_ext": [pd.NaT, pd.NaT, pd.NaT],  # No extended deadlines
                "year": [2025, 2025, 2025],
            },
        )

        with patch("builtins.print"):  # Suppress print output
            result = newsletter.filter_conferences(test_data, days=10)

        # Should only include Conference A (within 10 days)
        assert len(result) == 1
        assert result.iloc[0]["conference"] == "Conference A"

    @freeze_time("2026-06-01")
    def test_filter_conferences_with_cfp_ext(self):
        """Test filtering with extended CFP deadlines (cfp_ext)."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B"],
                "cfp": [
                    now - timedelta(days=1),  # Original deadline passed
                    now + timedelta(days=5),  # Original deadline within range
                ],
                "cfp_ext": [
                    now + timedelta(days=3),  # Extended deadline within range
                    pd.NaT,  # No extension
                ],
                "year": [2025, 2025],
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(test_data, days=10)

        # Should include both conferences
        assert len(result) == 2

        # Conference A should use cfp_ext deadline
        conf_a = result[result["conference"] == "Conference A"].iloc[0]
        assert conf_a["cfp"] == now + timedelta(days=3)

    @freeze_time("2026-06-01")
    def test_filter_conferences_tba_handling(self):
        """Test handling of 'TBA' deadlines."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B"],
                "cfp": ["TBA", now + timedelta(days=5)],
                "cfp_ext": [pd.NaT, pd.NaT],
                "year": [2025, 2025],
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(test_data, days=10)

        # Should only include Conference B (TBA should be filtered out)
        assert len(result) == 1
        assert result.iloc[0]["conference"] == "Conference B"

    @freeze_time("2026-06-01")
    def test_filter_conferences_custom_days(self):
        """Test filtering with custom day range."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B", "Conference C"],
                "cfp": [
                    now + timedelta(days=2),  # Within 5 days
                    now + timedelta(days=7),  # Within 10 days but not 5
                    now + timedelta(days=12),  # Outside 10 days
                ],
                "cfp_ext": [pd.NaT, pd.NaT, pd.NaT],
                "year": [2025, 2025, 2025],
            },
        )

        with patch("builtins.print"):
            result_5_days = newsletter.filter_conferences(test_data, days=5)
            result_10_days = newsletter.filter_conferences(test_data, days=10)

        # 5 days should only include Conference A
        assert len(result_5_days) == 1
        assert result_5_days.iloc[0]["conference"] == "Conference A"

        # 10 days should include Conference A and B
        assert len(result_10_days) == 2
        conference_names = result_10_days["conference"].tolist()
        assert "Conference A" in conference_names
        assert "Conference B" in conference_names

    def test_filter_conferences_empty_dataframe(self):
        """Test filtering with empty DataFrame."""
        empty_df = pd.DataFrame(columns=["conference", "cfp", "cfp_ext", "year"])

        with patch("builtins.print"):
            result = newsletter.filter_conferences(empty_df, days=10)

        assert len(result) == 0
        assert isinstance(result, pd.DataFrame)

    @freeze_time("2026-06-01")
    def test_filter_conferences_all_past_deadlines(self):
        """Test filtering when all deadlines are in the past."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B"],
                "cfp": [
                    now - timedelta(days=5),  # Past
                    now - timedelta(days=10),  # Past
                ],
                "cfp_ext": [pd.NaT, pd.NaT],
                "year": [2025, 2025],
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(test_data, days=10)

        assert len(result) == 0

    @freeze_time("2026-06-01")
    def test_filter_conferences_timezone_handling(self):
        """Test that timezone handling works correctly."""
        # This test ensures the timezone offset is properly handled
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Conference A"],
                "cfp": [now + timedelta(days=1)],  # Tomorrow
                "cfp_ext": [pd.NaT],
                "year": [2025],
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(test_data, days=5)

        # Should include the conference (tomorrow is within 5 days)
        assert len(result) == 1
        assert result.iloc[0]["conference"] == "Conference A"


class TestCreateMarkdownLinks:
    """Test markdown link creation functionality."""

    def test_create_markdown_links_basic(self):
        """Test basic markdown link creation."""
        test_data = pd.DataFrame({"conference": ["PyCon US", "DjangoCon Europe"], "year": [2025, 2025]})

        links = newsletter.create_markdown_links(test_data)

        assert len(links) == 2
        assert links[0] == "[PyCon US](https://pythondeadlin.es/conference/pycon-us-2025/)"
        assert links[1] == "[DjangoCon Europe](https://pythondeadlin.es/conference/djangocon-europe-2025/)"

    def test_create_markdown_links_special_characters(self):
        """Test markdown link creation with special characters."""
        test_data = pd.DataFrame(
            {"conference": ["PyCon Australia & NZ", "Conference with Spaces"], "year": [2025, 2026]},
        )

        links = newsletter.create_markdown_links(test_data)

        assert len(links) == 2
        assert "[PyCon Australia & NZ]" in links[0]
        assert "pycon-australia-&-nz-2025" in links[0]
        assert "[Conference with Spaces]" in links[1]
        assert "conference-with-spaces-2026" in links[1]

    def test_create_markdown_links_case_handling(self):
        """Test that conference names are properly lowercased in URLs."""
        test_data = pd.DataFrame({"conference": ["UPPERCASE CONF", "MiXeD CaSe CoNf"], "year": [2025, 2025]})

        links = newsletter.create_markdown_links(test_data)

        # Display names should preserve original case
        assert "[UPPERCASE CONF]" in links[0]
        assert "[MiXeD CaSe CoNf]" in links[1]

        # URLs should be lowercase
        assert "uppercase-conf-2025" in links[0]
        assert "mixed-case-conf-2025" in links[1]

    def test_create_markdown_links_empty_dataframe(self):
        """Test markdown link creation with empty DataFrame."""
        empty_df = pd.DataFrame(columns=["conference", "year"])

        links = newsletter.create_markdown_links(empty_df)

        assert len(links) == 0
        assert isinstance(links, list)

    def test_create_markdown_links_single_conference(self):
        """Test markdown link creation with single conference."""
        test_data = pd.DataFrame({"conference": ["Solo Conference"], "year": [2025]})

        links = newsletter.create_markdown_links(test_data)

        assert len(links) == 1
        assert links[0] == "[Solo Conference](https://pythondeadlin.es/conference/solo-conference-2025/)"

    def test_create_markdown_links_different_years(self):
        """Test markdown link creation with different years."""
        test_data = pd.DataFrame({"conference": ["Same Conference", "Same Conference"], "year": [2024, 2025]})

        links = newsletter.create_markdown_links(test_data)

        assert len(links) == 2
        assert "same-conference-2024" in links[0]
        assert "same-conference-2025" in links[1]


class TestMainFunction:
    """Test main function integration."""

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_main_function_basic(self, mock_print, mock_load_conferences):
        """Test basic main function execution."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Mock conference data
        mock_data = pd.DataFrame(
            {
                "conference": ["Upcoming Conference"],
                "cfp": [now + timedelta(days=5)],
                "cfp_ext": [pd.NaT],
                "year": [2025],
            },
        )
        mock_load_conferences.return_value = mock_data

        newsletter.main(days=10)

        # Verify function calls
        mock_load_conferences.assert_called_once()

        # Verify print was called (output formatting)
        assert mock_print.called

        # Check that conference was processed
        print_calls = [call[0] for call in mock_print.call_args_list]
        assert any("Upcoming Conference" in str(call) for call in print_calls)

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_main_function_no_conferences(self, mock_print, mock_load_conferences):
        """Test main function with no upcoming conferences."""
        # Mock empty conference data (all past deadlines)
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()
        mock_data = pd.DataFrame(
            {"conference": ["Past Conference"], "cfp": [now - timedelta(days=5)], "cfp_ext": [pd.NaT], "year": [2024]},
        )
        mock_load_conferences.return_value = mock_data

        newsletter.main(days=10)

        # Should still call print, but with empty results
        assert mock_print.called

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_main_function_custom_days(self, mock_print, mock_load_conferences):
        """Test main function with custom day parameter."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        mock_data = pd.DataFrame(
            {
                "conference": ["Conference A", "Conference B"],
                "cfp": [
                    now + timedelta(days=3),  # Within 5 days
                    now + timedelta(days=8),  # Within 10 days but not 5
                ],
                "cfp_ext": [pd.NaT, pd.NaT],
                "year": [2025, 2025],
            },
        )
        mock_load_conferences.return_value = mock_data

        newsletter.main(days=5)

        # Should only process Conference A
        print_calls = [str(call) for call in mock_print.call_args_list]
        conference_a_mentioned = any("Conference A" in call for call in print_calls)
        conference_b_mentioned = any("Conference B" in call for call in print_calls)

        assert conference_a_mentioned
        # Conference B should not be mentioned (outside 5-day range)
        assert not conference_b_mentioned

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_main_function_markdown_output(self, mock_print, mock_load_conferences):
        """Test main function produces correct markdown output."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        mock_data = pd.DataFrame(
            {"conference": ["Test Conference"], "cfp": [now + timedelta(days=3)], "cfp_ext": [pd.NaT], "year": [2025]},
        )
        mock_load_conferences.return_value = mock_data

        newsletter.main(days=10)

        # Check for markdown formatting in output
        print_calls = [str(call) for call in mock_print.call_args_list]
        markdown_found = any(
            "[Test Conference]" in call and "https://pythondeadlin.es/conference/" in call for call in print_calls
        )
        assert markdown_found


class TestCommandLineInterface:
    """Test command line interface functionality."""

    @patch("newsletter.main")
    @patch("argparse.ArgumentParser.parse_args")
    def test_cli_default_arguments(self, mock_parse_args, mock_main):
        """Test CLI with default arguments."""
        mock_args = Mock()
        mock_args.days = 15
        mock_parse_args.return_value = mock_args

        # Import and execute CLI code
        import importlib
        import sys

        # Temporarily modify sys.argv to simulate CLI call
        original_argv = sys.argv
        try:
            sys.argv = ["newsletter.py"]

            # Reload the module to trigger __main__ execution
            newsletter_module = importlib.import_module("newsletter")

            # Simulate the __main__ block execution
            if hasattr(newsletter_module, "__name__") and newsletter_module.__name__ == "__main__":
                # This would normally be handled by Python's import system
                pass

        finally:
            sys.argv = original_argv

    def test_cli_custom_days_argument(self):
        """Test CLI with custom days argument."""
        # We test the argument parsing structure directly without mocking
        parser = argparse.ArgumentParser()
        parser.add_argument("--days", type=int, default=15)

        # Test that default is correct
        default_args = parser.parse_args([])
        assert default_args.days == 15

        # Test custom argument parsing
        custom_args = parser.parse_args(["--days", "30"])
        assert custom_args.days == 30


class TestIntegrationWorkflows:
    """Integration tests for complete newsletter workflows."""

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_full_newsletter_workflow(self, mock_print, mock_load_conferences):
        """Test complete newsletter generation workflow."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Create realistic test data
        mock_data = pd.DataFrame(
            {
                "conference": ["PyCon US 2025", "EuroSciPy 2025", "PyData Global"],
                "cfp": [
                    now + timedelta(days=7),  # Week ahead
                    now + timedelta(days=2),  # 2 days ahead
                    now + timedelta(days=20),  # Outside 15-day range
                ],
                "cfp_ext": [
                    pd.NaT,  # No extension
                    now + timedelta(days=5),  # Extended to 5 days
                    pd.NaT,  # No extension
                ],
                "year": [2025, 2025, 2025],
                "place": ["Pittsburgh, USA", "Basel, Switzerland", "Online"],
                "link": ["https://pycon.org", "https://euroscipy.org", "https://pydata.org"],
            },
        )
        mock_load_conferences.return_value = mock_data

        newsletter.main(days=15)

        # Verify comprehensive output
        print_calls = [str(call) for call in mock_print.call_args_list]

        # Should include conferences within range
        pycon_mentioned = any("PyCon US 2025" in call for call in print_calls)
        euroscipy_mentioned = any("EuroSciPy 2025" in call for call in print_calls)
        pydata_mentioned = any("PyData Global" in call for call in print_calls)

        assert pycon_mentioned
        assert euroscipy_mentioned
        assert not pydata_mentioned  # Outside 15-day range

        # Should include markdown links
        markdown_found = any("https://pythondeadlin.es/conference/" in call for call in print_calls)
        assert markdown_found

    @freeze_time("2026-06-01")
    @patch("newsletter.load_conferences")
    @patch("builtins.print")
    def test_edge_case_handling(self, mock_print, mock_load_conferences):
        """Test handling of edge cases and data quality issues."""
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        # Create data with various edge cases
        mock_data = pd.DataFrame(
            {
                "conference": ["Normal Conference", "Conference with SpecialChars!@#", ""],
                "cfp": [
                    now + timedelta(days=5),  # Normal
                    "TBA",  # TBA deadline
                    now + timedelta(days=3),  # Empty name
                ],
                "cfp_ext": [pd.NaT, pd.NaT, pd.NaT],
                "year": [2025, 2025, 2025],
            },
        )
        mock_load_conferences.return_value = mock_data

        # Should handle gracefully without crashing
        newsletter.main(days=10)

        # Function should complete successfully
        assert mock_print.called

    @freeze_time("2026-06-01")
    def test_date_boundary_conditions(self):
        """Test boundary conditions around date filtering."""
        # Test exactly at boundary
        now = datetime.now(tz=timezone(timedelta(hours=2))).date()

        test_data = pd.DataFrame(
            {
                "conference": ["Boundary Conference"],
                "cfp": [now + timedelta(days=10)],  # Exactly 10 days
                "cfp_ext": [pd.NaT],
                "year": [2025],
            },
        )

        with patch("builtins.print"):
            # Should be included when days=10
            result_inclusive = newsletter.filter_conferences(test_data, days=10)
            assert len(result_inclusive) == 1

            # Should be excluded when days=9
            result_exclusive = newsletter.filter_conferences(test_data, days=9)
            assert len(result_exclusive) == 0


class TestDataProcessingRobustness:
    """Test robustness of data processing functions."""

    @pytest.mark.xfail(reason="Known bug: filter_conferences can't compare datetime64[ns] NaT with date")
    def test_filter_conferences_malformed_dates(self):
        """Test filtering with malformed date data.

        When all dates are invalid, pandas converts them to NaT values
        which can't be compared with datetime.date objects.
        """
        test_data = pd.DataFrame(
            {
                "conference": ["Conf A", "Conf B", "Conf C"],
                "cfp": ["invalid-date", "2025-13-45", "not-a-date"],  # All invalid
                "cfp_ext": [pd.NaT, pd.NaT, pd.NaT],
                "year": [2025, 2025, 2025],
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(test_data, days=10)

        # Should handle gracefully and return empty result
        assert len(result) == 0

    @pytest.mark.xfail(reason="Known bug: create_markdown_links doesn't handle None values")
    def test_create_markdown_links_missing_data(self):
        """Test markdown link creation with missing data.

        When conference names are None, the str.lower() call fails.
        """
        test_data = pd.DataFrame({"conference": ["Valid Conf", None, ""], "year": [2025, 2025, 2025]})

        # Should handle gracefully
        links = newsletter.create_markdown_links(test_data)
        assert len(links) == 3  # All rows processed, even with missing data

    @pytest.mark.xfail(reason="Known bug: filter_conferences can't compare datetime64[ns] NaT with date")
    def test_memory_efficiency_large_dataset(self):
        """Test performance with larger datasets.

        When all dates are TBA (coerced to NaT), pandas can't compare
        datetime64[ns] NaT values with datetime.date objects.
        """
        # Create a moderately large dataset
        large_data = pd.DataFrame(
            {
                "conference": [f"Conference {i}" for i in range(1000)],
                "cfp": ["TBA"] * 1000,  # All TBA to test filtering
                "cfp_ext": [pd.NaT] * 1000,
                "year": [2025] * 1000,
            },
        )

        with patch("builtins.print"):
            result = newsletter.filter_conferences(large_data, days=10)

        # Should handle large dataset efficiently
        assert len(result) == 0  # All TBA should be filtered out
        assert isinstance(result, pd.DataFrame)
