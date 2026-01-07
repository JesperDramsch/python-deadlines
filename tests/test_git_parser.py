"""Tests for git_parser functionality."""

import subprocess  # noqa: S404 # Required for testing git functionality
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from git_parser import ConventionalCommit
from git_parser import GitCommitParser
from git_parser import parse_arguments


class TestConventionalCommit:
    """Test ConventionalCommit dataclass functionality."""

    def test_commit_initialization(self):
        """Test basic commit object creation."""
        commit = ConventionalCommit(
            hash="abc123",
            prefix="cfp",
            message="PyCon US 2025",
            author="Test Author",
            date=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert commit.hash == "abc123"
        assert commit.prefix == "cfp"
        assert commit.message == "PyCon US 2025"
        assert commit.author == "Test Author"
        assert commit.date.year == 2025

    def test_generate_url(self):
        """Test URL generation with various conference names."""
        commit = ConventionalCommit(
            hash="abc123",
            prefix="cfp",
            message="PyCon US 2025",
            author="Test Author",
            date=datetime(2025, 1, 15, tzinfo=timezone.utc),
        )

        url = commit.generate_url()
        expected_url = "https://pythondeadlin.es/conference/pycon-us-2025"
        assert url == expected_url

    def test_generate_url_special_characters(self):
        """Test URL generation with special characters."""
        commit = ConventionalCommit(
            hash="def456",
            prefix="conf",
            message="PyCon Australia & New Zealand",
            author="Test Author",
            date=datetime(2025, 2, 20, tzinfo=timezone.utc),
        )

        url = commit.generate_url()
        assert "https://pythondeadlin.es/conference/" in url
        assert "pycon" in url.lower()
        # Should handle special characters properly
        assert "&" not in url or "%26" in url

    def test_to_markdown(self):
        """Test markdown formatting."""
        commit = ConventionalCommit(
            hash="ghi789",
            prefix="cfp",
            message="DjangoCon Europe",
            author="Test Author",
            date=datetime(2025, 3, 10, tzinfo=timezone.utc),
        )

        markdown = commit.to_markdown()
        assert "[2025-03-10]" in markdown
        assert "[DjangoCon Europe]" in markdown
        assert "https://pythondeadlin.es/conference/" in markdown

    def test_to_markdown_formatting(self):
        """Test proper markdown link formatting."""
        commit = ConventionalCommit(
            hash="jkl012",
            prefix="conf",
            message="PyData Global",
            author="Test Author",
            date=datetime(2025, 4, 5, tzinfo=timezone.utc),
        )

        markdown = commit.to_markdown()
        # Should be in format: - [date] [title](url)
        assert markdown.startswith("- [2025-04-05]")
        assert "[PyData Global](" in markdown
        assert markdown.endswith(")")


class TestGitCommitParser:
    """Test GitCommitParser functionality."""

    def test_parser_initialization_defaults(self):
        """Test parser initialization with default values."""
        parser = GitCommitParser()

        assert parser.repo_path == "."
        assert parser.prefixes == ["cfp", "conf"]
        assert parser.days is None

    def test_parser_initialization_custom(self):
        """Test parser initialization with custom values."""
        parser = GitCommitParser(repo_path="/custom/path", prefixes=["event", "workshop"], days=30)

        assert parser.repo_path == "/custom/path"
        assert parser.prefixes == ["event", "workshop"]
        assert parser.days == 30

    def test_parse_commit_message_cfp(self):
        """Test parsing valid CFP commit message."""
        parser = GitCommitParser()

        commit = parser.parse_commit_message(
            commit_hash="abc123",
            message="cfp: PyCon US 2025",
            author="John Doe",
            date_str="2025-01-15 10:30:00 +0000",
        )

        assert commit is not None
        assert commit.hash == "abc123"
        assert commit.prefix == "cfp"
        assert commit.message == "PyCon US 2025"
        assert commit.author == "John Doe"
        assert commit.date.year == 2025

    def test_parse_commit_message_conf(self):
        """Test parsing valid conference commit message."""
        parser = GitCommitParser()

        commit = parser.parse_commit_message(
            commit_hash="def456",
            message="conf: EuroSciPy 2025",
            author="Jane Smith",
            date_str="2025-02-20 14:15:30 +0100",
        )

        assert commit is not None
        assert commit.hash == "def456"
        assert commit.prefix == "conf"
        assert commit.message == "EuroSciPy 2025"
        assert commit.author == "Jane Smith"
        assert commit.date.day == 20

    def test_parse_commit_message_invalid_prefix(self):
        """Test parsing commit message with invalid prefix."""
        parser = GitCommitParser()

        commit = parser.parse_commit_message(
            commit_hash="ghi789",
            message="fix: Bug fix for deadline parsing",
            author="Developer",
            date_str="2025-03-10 09:00:00 +0000",
        )

        assert commit is None

    def test_parse_commit_message_case_insensitive(self):
        """Test parsing commit message with different case."""
        parser = GitCommitParser()

        commit = parser.parse_commit_message(
            commit_hash="jkl012",
            message="CFP: PyCon India 2025",
            author="Contributor",
            date_str="2025-04-05 16:45:00 +0530",
        )

        assert commit is not None
        assert commit.prefix == "cfp"  # Should be normalized to lowercase
        assert commit.message == "PyCon India 2025"

    def test_parse_commit_message_custom_prefix(self):
        """Test parsing with custom prefixes."""
        parser = GitCommitParser(prefixes=["event", "workshop"])

        commit = parser.parse_commit_message(
            commit_hash="mno345",
            message="event: PyLadies Workshop",
            author="Organizer",
            date_str="2025-05-12 11:00:00 +0000",
        )

        assert commit is not None
        assert commit.prefix == "event"
        assert commit.message == "PyLadies Workshop"

    @patch("git_parser.subprocess.run")
    def test_execute_git_command_success(self, mock_run):
        """Test successful git command execution."""
        mock_result = Mock()
        mock_result.stdout = "commit abc123\nAuthor: Test\n"
        mock_run.return_value = mock_result

        parser = GitCommitParser(repo_path="/test/repo")
        result = parser._execute_git_command(["log", "--oneline"])

        mock_run.assert_called_once_with(
            ["git", "log", "--oneline"],
            cwd="/test/repo",
            capture_output=True,
            text=True,
            check=True,
        )
        assert result == "commit abc123\nAuthor: Test"

    @patch("git_parser.subprocess.run")
    def test_execute_git_command_failure(self, mock_run):
        """Test git command execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        parser = GitCommitParser()

        with pytest.raises(subprocess.CalledProcessError):
            parser._execute_git_command(["log"])

    @patch.object(GitCommitParser, "_execute_git_command")
    def test_get_conventional_commits(self, mock_execute):
        """Test getting conventional commits from git log."""
        mock_execute.return_value = (
            "abc123\n"
            "cfp: PyCon US 2025\n"
            "John Doe\n"
            "2025-01-15 10:30:00 +0000\n"
            "def456\n"
            "conf: DjangoCon Europe\n"
            "Jane Smith\n"
            "2025-02-20 14:15:30 +0100"
        )

        parser = GitCommitParser()
        commits = parser.get_conventional_commits()

        assert len(commits) == 2
        assert commits[0].hash == "abc123"
        assert commits[0].prefix == "cfp"
        assert commits[0].message == "PyCon US 2025"
        assert commits[1].hash == "def456"
        assert commits[1].prefix == "conf"
        assert commits[1].message == "DjangoCon Europe"

    @patch.object(GitCommitParser, "_execute_git_command")
    def test_get_conventional_commits_with_days(self, mock_execute):
        """Test getting commits with day limitation."""
        mock_execute.return_value = ""

        parser = GitCommitParser(days=7)
        parser.get_conventional_commits()

        # Should call git with --since parameter
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0][0]
        assert "--since" in call_args

    @patch.object(GitCommitParser, "_execute_git_command")
    def test_get_conventional_commits_mixed_valid_invalid(self, mock_execute):
        """Test filtering out invalid commits."""
        mock_execute.return_value = (
            "abc123\n"
            "cfp: Valid CFP\n"
            "Author1\n"
            "2025-01-15 10:30:00 +0000\n"
            "def456\n"
            "fix: Invalid commit\n"
            "Author2\n"
            "2025-01-16 10:30:00 +0000\n"
            "ghi789\n"
            "conf: Valid Conference\n"
            "Author3\n"
            "2025-01-17 10:30:00 +0000"
        )

        parser = GitCommitParser()
        commits = parser.get_conventional_commits()

        assert len(commits) == 2
        assert commits[0].message == "Valid CFP"
        assert commits[1].message == "Valid Conference"

    def test_generate_link_list_empty(self):
        """Test link list generation with empty list."""
        parser = GitCommitParser()
        result = parser._generate_link_list([])
        assert result == ""

    def test_generate_link_list_single(self):
        """Test link list generation with single item."""
        parser = GitCommitParser()
        commit = ConventionalCommit(
            hash="abc123",
            prefix="cfp",
            message="PyCon",
            author="Author",
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        result = parser._generate_link_list([commit])
        expected = "[PyCon](https://pythondeadlin.es/conference/pycon)"
        assert result == expected

    def test_generate_link_list_two(self):
        """Test link list generation with two items."""
        parser = GitCommitParser()
        commits = [
            ConventionalCommit("abc", "cfp", "PyCon", "Author", datetime(2025, 1, 1, tzinfo=timezone.utc)),
            ConventionalCommit("def", "cfp", "DjangoCon", "Author", datetime(2025, 1, 2, tzinfo=timezone.utc)),
        ]

        result = parser._generate_link_list(commits)
        assert " and " in result
        assert "[PyCon]" in result
        assert "[DjangoCon]" in result

    def test_generate_link_list_three_or_more(self):
        """Test link list generation with three or more items (Oxford comma)."""
        parser = GitCommitParser()
        commits = [
            ConventionalCommit("abc", "cfp", "PyCon", "Author", datetime(2025, 1, 1, tzinfo=timezone.utc)),
            ConventionalCommit("def", "cfp", "DjangoCon", "Author", datetime(2025, 1, 2, tzinfo=timezone.utc)),
            ConventionalCommit("ghi", "cfp", "PyData", "Author", datetime(2025, 1, 3, tzinfo=timezone.utc)),
        ]

        result = parser._generate_link_list(commits)
        assert ", and " in result  # Oxford comma
        assert "[PyCon]" in result
        assert "[DjangoCon]" in result
        assert "[PyData]" in result

    @patch.object(GitCommitParser, "get_conventional_commits")
    def test_generate_markdown_report_empty(self, mock_get_commits):
        """Test markdown report generation with no commits."""
        mock_get_commits.return_value = []

        parser = GitCommitParser()
        report = parser.generate_markdown_report()

        assert report == ""

    @patch.object(GitCommitParser, "get_conventional_commits")
    def test_generate_markdown_report_cfp_only(self, mock_get_commits):
        """Test markdown report generation with CFP commits only."""
        commits = [
            ConventionalCommit("abc123", "cfp", "PyCon US 2025", "Author", datetime(2025, 1, 15, tzinfo=timezone.utc)),
        ]
        mock_get_commits.return_value = commits

        parser = GitCommitParser()
        report = parser.generate_markdown_report()

        assert "## Call for Papers" in report
        assert "## Conferences" not in report
        assert "## Summary" in report
        assert "[PyCon US 2025]" in report
        assert "new CFPs for" in report

    @patch.object(GitCommitParser, "get_conventional_commits")
    def test_generate_markdown_report_conf_only(self, mock_get_commits):
        """Test markdown report generation with conference commits only."""
        commits = [
            ConventionalCommit(
                "def456",
                "conf",
                "EuroSciPy 2025",
                "Author",
                datetime(2025, 2, 20, tzinfo=timezone.utc),
            ),
        ]
        mock_get_commits.return_value = commits

        parser = GitCommitParser()
        report = parser.generate_markdown_report()

        assert "## Conferences" in report
        assert "## Call for Papers" not in report
        assert "## Summary" in report
        assert "[EuroSciPy 2025]" in report
        assert "these conferences" in report

    @patch.object(GitCommitParser, "get_conventional_commits")
    def test_generate_markdown_report_mixed(self, mock_get_commits):
        """Test markdown report generation with mixed commit types."""
        commits = [
            ConventionalCommit("abc123", "cfp", "PyCon US 2025", "Author1", datetime(2025, 1, 15, tzinfo=timezone.utc)),
            ConventionalCommit(
                "def456",
                "conf",
                "EuroSciPy 2025",
                "Author2",
                datetime(2025, 2, 20, tzinfo=timezone.utc),
            ),
            ConventionalCommit(
                "ghi789",
                "cfp",
                "DjangoCon Europe",
                "Author3",
                datetime(2025, 1, 10, tzinfo=timezone.utc),
            ),
        ]
        mock_get_commits.return_value = commits

        parser = GitCommitParser()
        report = parser.generate_markdown_report()

        assert "## Call for Papers" in report
        assert "## Conferences" in report
        assert "## Summary" in report
        assert "these conferences" in report
        assert "new CFPs for" in report
        assert " and " in report  # Should connect both parts

    @patch.object(GitCommitParser, "get_conventional_commits")
    def test_generate_markdown_report_chronological_sorting(self, mock_get_commits):
        """Test that commits are sorted chronologically within groups."""
        commits = [
            ConventionalCommit("abc123", "cfp", "Earlier CFP", "Author", datetime(2025, 1, 10, tzinfo=timezone.utc)),
            ConventionalCommit("def456", "cfp", "Later CFP", "Author", datetime(2025, 1, 20, tzinfo=timezone.utc)),
        ]
        mock_get_commits.return_value = commits

        parser = GitCommitParser()
        report = parser.generate_markdown_report()

        # Should be sorted in reverse chronological order (most recent first)
        later_pos = report.find("Later CFP")
        earlier_pos = report.find("Earlier CFP")
        assert later_pos < earlier_pos


class TestArgumentParsing:
    """Test command line argument parsing."""

    @patch("git_parser.argparse.ArgumentParser.parse_args")
    def test_parse_arguments_defaults(self, mock_parse_args):
        """Test argument parsing with defaults."""
        mock_args = Mock()
        mock_args.days = 15
        mock_args.repo = "."
        mock_parse_args.return_value = mock_args

        args = parse_arguments()

        assert args.days == 15
        assert args.repo == "."

    @patch("git_parser.argparse.ArgumentParser.parse_args")
    def test_parse_arguments_custom(self, mock_parse_args):
        """Test argument parsing with custom values."""
        mock_args = Mock()
        mock_args.days = 30
        mock_args.repo = "/custom/path"
        mock_parse_args.return_value = mock_args

        args = parse_arguments()

        assert args.days == 30
        assert args.repo == "/custom/path"


class TestMainFunction:
    """Test main function integration."""

    @patch("git_parser.parse_arguments")
    @patch("git_parser.GitCommitParser")
    @patch("builtins.print")
    def test_main_success(self, mock_print, mock_parser_class, mock_parse_args):
        """Test successful main function execution."""
        # Setup mocks
        mock_args = Mock()
        mock_args.days = 15
        mock_args.repo = "."
        mock_parse_args.return_value = mock_args

        mock_parser = Mock()
        mock_parser.generate_markdown_report.return_value = "Test Report"
        mock_parser_class.return_value = mock_parser

        # Import and call main
        from git_parser import main

        main()

        # Verify calls
        mock_parser_class.assert_called_once_with(repo_path=".", days=15)
        mock_parser.generate_markdown_report.assert_called_once()
        mock_print.assert_called_once_with("Test Report")

    @patch("git_parser.parse_arguments")
    @patch("git_parser.GitCommitParser")
    @patch("builtins.print")
    def test_main_subprocess_error(self, mock_print, mock_parser_class, mock_parse_args):
        """Test main function with subprocess error."""
        # Setup mocks
        mock_args = Mock()
        mock_args.days = 15
        mock_args.repo = "."
        mock_parse_args.return_value = mock_args

        mock_parser = Mock()
        mock_parser.generate_markdown_report.side_effect = subprocess.CalledProcessError(1, "git")
        mock_parser_class.return_value = mock_parser

        # Import and call main
        from git_parser import main

        main()

        # Should print error message
        mock_print.assert_called_once_with(
            "Error: Failed to analyze git repository. Please ensure you're in a valid git repository.",
        )


class TestIntegration:
    """Integration tests for complete workflows."""

    @patch.object(GitCommitParser, "_execute_git_command")
    def test_full_workflow_integration(self, mock_execute):
        """Test complete workflow from git log to markdown report."""
        # Mock git log output with realistic data
        mock_execute.return_value = (
            "a1b2c3d4\n"
            "cfp: PyCon US 2025 Call for Proposals\n"
            "John Organizer\n"
            "2025-01-15 10:30:00 +0000\n"
            "e5f6g7h8\n"
            "conf: EuroSciPy 2025 Conference Announcement\n"
            "Jane Conference\n"
            "2025-01-20 14:15:30 +0100\n"
            "i9j0k1l2\n"
            "cfp: PyData Global CFP Extended\n"
            "Data Organizer\n"
            "2025-01-10 09:00:00 +0000"
        )

        parser = GitCommitParser(days=30)
        report = parser.generate_markdown_report()

        # Verify complete report structure
        assert "## Call for Papers" in report
        assert "## Conferences" in report
        assert "## Summary" in report

        # Verify content
        assert "PyCon US 2025" in report
        assert "EuroSciPy 2025" in report
        assert "PyData Global" in report

        # Verify markdown formatting
        assert "[2025-01-15]" in report
        assert "[2025-01-20]" in report
        assert "[2025-01-10]" in report

        # Verify URLs
        assert "https://pythondeadlin.es/conference/" in report

        # Verify summary logic
        assert "these conferences" in report
        assert "new CFPs for" in report

    def test_edge_cases_and_robustness(self):
        """Test parser robustness with edge cases."""
        parser = GitCommitParser()

        # Test with empty message
        commit = parser.parse_commit_message("abc", "", "Author", "2025-01-01 00:00:00 +0000")
        assert commit is None

        # Test with whitespace in message
        commit = parser.parse_commit_message(
            "def",
            "  cfp:   Spaced Conference Name  ",
            "Author",
            "2025-01-01 00:00:00 +0000",
        )
        assert commit is not None
        assert commit.message == "Spaced Conference Name"

        # Test with special characters in conference name
        commit = parser.parse_commit_message(
            "ghi",
            "conf: Conference with & Special * Characters!",
            "Author",
            "2025-01-01 00:00:00 +0000",
        )
        assert commit is not None
        url = commit.generate_url()
        assert "https://pythondeadlin.es/conference/" in url


class TestCommitFormatVerification:
    """Test parsing accuracy for various commit message formats.

    Section 10 of the test audit identified that tests verify commits are
    parsed, but don't verify the regex patterns work correctly for real
    commit messages from actual usage.
    """

    def test_parse_various_commit_formats(self):
        """Test parsing different commit message formats from real usage."""
        parser = GitCommitParser()

        test_cases = [
            # (message, expected_prefix, expected_content)
            ("cfp: Add PyCon US 2025", "cfp", "Add PyCon US 2025"),
            ("conf: DjangoCon Europe 2025", "conf", "DjangoCon Europe 2025"),
            ("CFP: Fix deadline for EuroPython", "cfp", "Fix deadline for EuroPython"),
            ("CONF: PyData Berlin announcement", "conf", "PyData Berlin announcement"),
            ("Cfp: Mixed case prefix", "cfp", "Mixed case prefix"),
            ("Merge pull request #123", None, None),  # Should not parse
            ("fix: Bug fix for deadline parsing", None, None),  # Wrong prefix
            ("feat: Add new feature", None, None),  # Wrong prefix
            ("chore: Update dependencies", None, None),  # Wrong prefix
            ("docs: Update README", None, None),  # Wrong prefix
        ]

        for msg, expected_prefix, expected_content in test_cases:
            result = parser.parse_commit_message(
                commit_hash="test123",
                message=msg,
                author="Test Author",
                date_str="2025-01-15 10:30:00 +0000",
            )

            if expected_prefix is not None:
                assert result is not None, f"Expected to parse '{msg}' but got None"
                assert (
                    result.prefix == expected_prefix
                ), f"Expected prefix '{expected_prefix}' for '{msg}', got '{result.prefix}'"
                assert (
                    result.message == expected_content
                ), f"Expected content '{expected_content}' for '{msg}', got '{result.message}'"
            else:
                assert result is None, f"Expected '{msg}' to NOT parse but got {result}"

    def test_commit_message_edge_cases(self):
        """Test edge cases in commit message parsing."""
        parser = GitCommitParser()

        # Colon without space - the regex uses \s* so this IS valid
        result = parser.parse_commit_message("abc123", "cfp:NoSpace", "Author", "2025-01-01 00:00:00 +0000")
        assert result is not None, "Colon without space should parse (regex allows \\s*)"
        assert result.message == "NoSpace"

        # Multiple colons
        result = parser.parse_commit_message(
            "abc123", "cfp: PyCon US: Call for Papers", "Author", "2025-01-01 00:00:00 +0000",
        )
        assert result is not None
        assert result.message == "PyCon US: Call for Papers"

        # Leading whitespace in message
        result = parser.parse_commit_message("abc123", "   cfp: Whitespace test", "Author", "2025-01-01 00:00:00 +0000")
        assert result is not None
        assert result.message == "Whitespace test"

        # Trailing whitespace in message
        result = parser.parse_commit_message(
            "abc123", "cfp: Trailing whitespace   ", "Author", "2025-01-01 00:00:00 +0000",
        )
        assert result is not None
        assert result.message == "Trailing whitespace"

        # Empty content after prefix
        result = parser.parse_commit_message("abc123", "cfp: ", "Author", "2025-01-01 00:00:00 +0000")
        assert result is None, "Should not parse empty content"

        # Just prefix with colon
        result = parser.parse_commit_message("abc123", "cfp:", "Author", "2025-01-01 00:00:00 +0000")
        assert result is None, "Should not parse just prefix"

    def test_special_characters_in_conference_names(self):
        """Test parsing and URL generation for conference names with special characters.

        Note: urllib.parse.quote() uses safe='/' by default, so '/' is NOT encoded.
        """
        parser = GitCommitParser()

        special_cases = [
            ("cfp: PyCon US & Canada", "pycon-us-%26-canada"),
            ("conf: PyData 2025 (Berlin)", "pydata-2025-%28berlin%29"),
            ("cfp: EuroSciPy #1 Conference", "euroscipy-%231-conference"),
            ("conf: Python-Day@Munich", "python-day%40munich"),
            ("cfp: Test/Event", "test/event"),  # '/' is in default safe chars, not encoded
        ]

        for message, expected_url_part in special_cases:
            result = parser.parse_commit_message("test123", message, "Author", "2025-01-01 00:00:00 +0000")
            assert result is not None, f"Failed to parse '{message}'"
            url = result.generate_url()
            assert expected_url_part in url, f"Expected '{expected_url_part}' in URL for '{message}', got '{url}'"

    def test_unicode_in_conference_names(self):
        """Test handling of Unicode characters in conference names."""
        parser = GitCommitParser()

        unicode_cases = [
            "cfp: PyCon España 2025",
            "conf: Python日本 Summit",
            "cfp: PyConFr Café Edition",
            "conf: München Python Day",
        ]

        for message in unicode_cases:
            result = parser.parse_commit_message("test123", message, "Author", "2025-01-01 00:00:00 +0000")
            assert result is not None, f"Failed to parse Unicode message: '{message}'"
            url = result.generate_url()
            assert "https://pythondeadlin.es/conference/" in url

    def test_date_parsing_various_timezones(self):
        """Test date parsing with various timezone formats."""
        parser = GitCommitParser()

        timezone_cases = [
            ("2025-01-15 10:30:00 +0000", 2025, 1, 15, 10, 30),  # UTC
            ("2025-06-20 14:15:30 +0100", 2025, 6, 20, 14, 15),  # CET
            ("2025-03-10 09:00:00 -0500", 2025, 3, 10, 9, 0),  # EST
            ("2025-08-25 16:45:00 +0530", 2025, 8, 25, 16, 45),  # IST
            ("2025-12-31 23:59:59 +1200", 2025, 12, 31, 23, 59),  # NZST
        ]

        for date_str, year, month, day, hour, minute in timezone_cases:
            result = parser.parse_commit_message("test123", "cfp: Test Conference", "Author", date_str)
            assert result is not None, f"Failed to parse date: {date_str}"
            assert result.date.year == year
            assert result.date.month == month
            assert result.date.day == day
            assert result.date.hour == hour
            assert result.date.minute == minute

    def test_markdown_output_format_correctness(self):
        """Test that markdown output format is correct and parseable."""
        parser = GitCommitParser()

        result = parser.parse_commit_message(
            "abc123",
            "cfp: PyCon US 2025",
            "John Doe",
            "2025-03-15 14:30:00 +0000",
        )

        markdown = result.to_markdown()

        # Verify markdown format: - [date] [title](url)
        assert markdown.startswith("- ["), "Should start with '- ['"
        assert "2025-03-15" in markdown, "Should contain the date"
        assert "[PyCon US 2025]" in markdown, "Should contain the title in brackets"
        assert "(https://pythondeadlin.es/conference/" in markdown, "Should contain URL in parentheses"
        assert markdown.endswith(")"), "Should end with ')'"

        # Verify it's valid markdown link format
        import re

        link_pattern = r"\[.+\]\(https://[^)]+\)"
        assert re.search(link_pattern, markdown), "Should contain valid markdown link"

    def test_url_generation_consistency(self):
        """Test that URL generation is consistent and deterministic."""
        parser = GitCommitParser()

        # Same input should produce same URL
        result1 = parser.parse_commit_message("abc123", "cfp: PyCon US 2025", "Author", "2025-01-15 10:30:00 +0000")
        result2 = parser.parse_commit_message(
            "def456", "cfp: PyCon US 2025", "Different Author", "2025-01-16 10:30:00 +0000",
        )

        assert result1.generate_url() == result2.generate_url(), "Same conference name should generate same URL"

        # Different case should produce same URL (lowercase)
        result3 = parser.parse_commit_message("ghi789", "cfp: PYCON US 2025", "Author", "2025-01-17 10:30:00 +0000")
        # Note: The message preserves case, but URL should be lowercase
        url3 = result3.generate_url()
        assert "pycon" in url3.lower()

    def test_custom_prefixes_parsing(self):
        """Test parsing with custom prefix configurations."""
        # Custom prefixes for different use cases
        custom_parser = GitCommitParser(prefixes=["event", "workshop", "meetup"])

        valid_cases = [
            ("event: Python Day Berlin", "event", "Python Day Berlin"),
            ("workshop: Django Girls Workshop", "workshop", "Django Girls Workshop"),
            ("meetup: Monthly Python Meetup", "meetup", "Monthly Python Meetup"),
            ("WORKSHOP: Advanced Flask", "workshop", "Advanced Flask"),
        ]

        invalid_for_custom = [
            "cfp: PyCon US 2025",  # Not in custom prefixes
            "conf: DjangoCon",  # Not in custom prefixes
        ]

        for msg, expected_prefix, expected_content in valid_cases:
            result = custom_parser.parse_commit_message("test", msg, "Author", "2025-01-01 00:00:00 +0000")
            assert result is not None, f"Custom parser should parse '{msg}'"
            assert result.prefix == expected_prefix
            assert result.message == expected_content

        for msg in invalid_for_custom:
            result = custom_parser.parse_commit_message("test", msg, "Author", "2025-01-01 00:00:00 +0000")
            assert result is None, f"Custom parser should NOT parse '{msg}'"

    def test_real_world_commit_messages(self):
        """Test with realistic commit messages from actual repository history."""
        parser = GitCommitParser()

        real_world_messages = [
            # Typical CFP announcements
            ("cfp: PyCon US 2025 Call for Proposals now open", "cfp", "PyCon US 2025 Call for Proposals now open"),
            ("cfp: Extended deadline for EuroPython 2025", "cfp", "Extended deadline for EuroPython 2025"),
            ("cfp: PyData Global - last chance to submit", "cfp", "PyData Global - last chance to submit"),
            # Conference announcements
            ("conf: DjangoCon US 2025 announced", "conf", "DjangoCon US 2025 announced"),
            ("conf: Added PyConDE & PyData Berlin 2025", "conf", "Added PyConDE & PyData Berlin 2025"),
            ("conf: Update PyCon APAC schedule", "conf", "Update PyCon APAC schedule"),
            # Messages that should NOT be parsed
            ("Update README with new conference links", None, None),
            ("Fix typo in EuroPython CFP deadline", None, None),
            ("Merge branch 'feature/add-pycon-2025'", None, None),
            ('Revert "cfp: PyCon US 2025"', None, None),  # Revert shouldn't match
            ("[skip ci] cfp: Test commit", None, None),  # Skip CI prefix
        ]

        for msg, expected_prefix, expected_content in real_world_messages:
            result = parser.parse_commit_message("test123", msg, "Contributor", "2025-01-15 12:00:00 +0000")

            if expected_prefix is not None:
                assert result is not None, f"Should parse: '{msg}'"
                assert result.prefix == expected_prefix
                assert result.message == expected_content
            else:
                assert result is None, f"Should NOT parse: '{msg}'"
