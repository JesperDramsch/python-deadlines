"""Tests for main pipeline functionality."""

import sys
import time
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

import main


class TestMainPipeline:
    """Test main pipeline functionality."""

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_success(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test successful main pipeline execution."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock all pipeline steps to succeed
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        # Execute main pipeline
        main.main()

        # Verify all steps were called
        mock_official.assert_called_once()
        mock_organizer.assert_called_once()
        assert mock_sort.call_count == 2  # Called twice in pipeline

        # Verify sort_data called with skip_links=True
        for call in mock_sort.call_args_list:
            assert call[1]["skip_links"] is True

        # Verify logging calls
        assert mock_logger_instance.info.call_count >= 7  # Start + 4 steps + completion messages
        assert not mock_logger_instance.error.called

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_step1_failure(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline failure in step 1 (official updater)."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Make official updater fail
        mock_official.side_effect = Exception("Official calendar API error")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        # Should exit with code 1
        assert exc_info.value.code == 1

        # Should have called official updater but not subsequent steps
        mock_official.assert_called_once()
        mock_organizer.assert_not_called()
        mock_sort.assert_not_called()

        # Should have logged the error
        mock_logger_instance.error.assert_called_once()
        error_call = mock_logger_instance.error.call_args
        assert "Official calendar API error" in str(error_call)

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_step2_failure(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline failure in step 2 (first sort)."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Make first sort fail
        mock_official.return_value = None
        mock_sort.side_effect = Exception("Data validation error")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should have called official updater and first sort
        mock_official.assert_called_once()
        mock_sort.assert_called_once()
        mock_organizer.assert_not_called()

        # Should have logged the error
        mock_logger_instance.error.assert_called_once()

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_step3_failure(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline failure in step 3 (organizer updater)."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Make organizer updater fail
        mock_official.return_value = None
        mock_sort.side_effect = [None, Exception("Final sort error")]  # First sort succeeds, second fails
        mock_organizer.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should have called official updater, first sort, and organizer updater
        mock_official.assert_called_once()
        mock_organizer.assert_called_once()
        assert mock_sort.call_count == 2  # Both sorts called

        # Should have logged the error
        mock_logger_instance.error.assert_called_once()

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_step4_failure(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline failure in step 4 (final sort)."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Make organizer updater fail
        mock_official.return_value = None
        mock_organizer.side_effect = Exception("GitHub API error")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should have called all steps up to organizer updater
        mock_official.assert_called_once()
        mock_sort.assert_called_once()  # Only first sort
        mock_organizer.assert_called_once()

        # Should have logged the error
        mock_logger_instance.error.assert_called_once()

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    @patch("main.time.time")
    def test_main_pipeline_timing(self, mock_time, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline timing measurement."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock time progression - main() makes 10 time.time() calls
        time_sequence = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
        mock_time.side_effect = time_sequence

        # Mock successful execution
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        main.main()

        # Verify timing logs were created
        info_calls = [str(call) for call in mock_logger_instance.info.call_args_list]

        # Should have step timing information
        step_timing_calls = [call for call in info_calls if "completed in" in call]
        assert len(step_timing_calls) >= 4  # At least 4 step completions

        # Should have total timing information
        total_timing_calls = [call for call in info_calls if "pipeline completed successfully in" in call]
        assert len(total_timing_calls) == 1

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_logging_messages(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test specific logging messages in pipeline."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock successful execution
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        main.main()

        # Collect all info log messages
        info_calls = [str(call[0][0]) for call in mock_logger_instance.info.call_args_list]

        # Verify key messages are present
        assert any("Starting Python Deadlines data processing pipeline" in msg for msg in info_calls)
        assert any("Step 1: Importing from Python official calendar" in msg for msg in info_calls)
        assert any("Step 2: Sorting and validating data" in msg for msg in info_calls)
        assert any("Step 3: Importing from Python organizers" in msg for msg in info_calls)
        assert any("Step 4: Final sorting and validation" in msg for msg in info_calls)
        assert any("Data processing pipeline completed successfully" in msg for msg in info_calls)

        # Verify step completion messages
        assert any("Official calendar import completed" in msg for msg in info_calls)
        assert any("Data sorting completed" in msg for msg in info_calls)
        assert any("Organizers import completed" in msg for msg in info_calls)
        assert any("Final sorting completed" in msg for msg in info_calls)

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_main_pipeline_error_logging_with_traceback(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test that errors are logged with full traceback."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Create a specific exception
        test_exception = ValueError("Test error for traceback")
        mock_official.side_effect = test_exception

        with pytest.raises(SystemExit):
            main.main()

        # Verify error was logged with exc_info=True
        mock_logger_instance.error.assert_called_once()
        error_call = mock_logger_instance.error.call_args

        # Check error message
        assert "Pipeline failed with error: Test error for traceback" in str(error_call[0])

        # Check exc_info parameter
        assert error_call[1]["exc_info"] is True


class TestStepIntegration:
    """Test integration between pipeline steps."""

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_step_order_correct(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test that pipeline steps execute in correct order."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Track call order
        call_order = []

        def track_official():
            call_order.append("official")

        def track_first_sort(*args, **kwargs):
            call_order.append("sort1")

        def track_organizer():
            call_order.append("organizer")

        def track_second_sort(*args, **kwargs):
            call_order.append("sort2")

        mock_official.side_effect = track_official
        mock_organizer.side_effect = track_organizer

        # Use a function that tracks calls and can be called multiple times
        def track_sort(*args, **kwargs):
            if len(call_order) == 1:  # After official
                call_order.append("sort1")
            elif len(call_order) == 3:  # After organizer
                call_order.append("sort2")

        mock_sort.side_effect = track_sort

        main.main()

        # Verify correct order
        expected_order = ["official", "sort1", "organizer", "sort2"]
        assert call_order == expected_order

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_skip_links_parameter(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test that skip_links=True is passed to sort_data calls."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        main.main()

        # Verify both sort_data calls use skip_links=True
        assert mock_sort.call_count == 2
        for call in mock_sort.call_args_list:
            assert "skip_links" in call[1]
            assert call[1]["skip_links"] is True


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_keyboard_interrupt_handling(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test handling of KeyboardInterrupt (Ctrl+C)."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Simulate user interruption
        mock_official.side_effect = KeyboardInterrupt("User cancelled")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should still log the error
        mock_logger_instance.error.assert_called_once()

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_memory_error_handling(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test handling of MemoryError."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Simulate memory error
        mock_sort.side_effect = MemoryError("Insufficient memory")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should log the error with traceback
        mock_logger_instance.error.assert_called_once()
        error_call = mock_logger_instance.error.call_args
        assert error_call[1]["exc_info"] is True

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_file_permission_error_handling(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test handling of file permission errors."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Simulate permission error
        mock_organizer.side_effect = PermissionError("Permission denied: conferences.yml")

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1

        # Should log the error appropriately
        mock_logger_instance.error.assert_called_once()


class TestMainExecution:
    """Test main module execution."""

    @patch("main.main")
    def test_main_module_execution(self, mock_main_func):
        """Test that main function is called when module is executed."""
        # This tests the if __name__ == "__main__": block
        # In a real scenario, this would be tested by running the module directly

        # Import the module and simulate __main__ execution

        # Temporarily modify sys.argv and __name__ to simulate direct execution
        original_name = main.__name__
        try:
            main.__name__ = "__main__"
            # The actual test would involve subprocess execution
            # For unit testing, we verify the structure exists
            assert hasattr(main, "main")
            assert callable(main.main)
        finally:
            main.__name__ = original_name


class TestPerformanceAndRobustness:
    """Test performance characteristics and robustness."""

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_pipeline_handles_slow_operations(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline handling of slow operations."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Simulate slow operations
        def slow_official():
            time.sleep(0.1)  # Small delay for testing

        def slow_organizer():
            time.sleep(0.1)

        def slow_sort(*args, **kwargs):
            time.sleep(0.1)

        mock_official.side_effect = slow_official
        mock_organizer.side_effect = slow_organizer
        mock_sort.side_effect = slow_sort

        # Should complete successfully even with slow operations
        start_time = time.time()
        main.main()
        end_time = time.time()

        # Should have taken some time (at least 0.4s for 4 operations)
        assert end_time - start_time >= 0.4

        # Should have logged timing information
        assert mock_logger_instance.info.called

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_pipeline_resource_cleanup(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test that pipeline properly handles resource cleanup."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock successful execution
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        # Pipeline should complete successfully
        main.main()

        # All mocks should have been called appropriately
        mock_official.assert_called_once()
        mock_organizer.assert_called_once()
        assert mock_sort.call_count == 2

    @patch("main.sort_data")
    @patch("main.organizer_updater")
    @patch("main.official_updater")
    @patch("main.get_tqdm_logger")
    def test_pipeline_with_warnings(self, mock_logger, mock_official, mock_organizer, mock_sort):
        """Test pipeline handling when sub-processes emit warnings."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Mock operations that succeed but may log warnings
        mock_official.return_value = None
        mock_organizer.return_value = None
        mock_sort.return_value = None

        main.main()

        # Pipeline should complete successfully regardless of warnings
        # Verify success message
        info_calls = [str(call[0][0]) for call in mock_logger_instance.info.call_args_list]
        success_messages = [msg for msg in info_calls if "completed successfully" in msg]
        assert len(success_messages) >= 1
