"""Pytest configuration and fixtures for Python Deadlines tests.

This module provides shared fixtures for testing the conference synchronization
pipeline. Fixtures use real data structures and only mock external I/O boundaries
(network, file system) following testing best practices.

Note: Shared Hypothesis strategies are in hypothesis_strategies.py - import
them directly in test files that need property-based testing.
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
import yaml

# ---------------------------------------------------------------------------
# Hypothesis Configuration for CI/Dev/Debug profiles
# ---------------------------------------------------------------------------

try:
    from hypothesis import Phase, settings

    # CI profile: More thorough testing, no time limit
    settings.register_profile("ci", max_examples=200, deadline=None)

    # Dev profile: Balanced speed and coverage
    settings.register_profile("dev", max_examples=50, deadline=200)

    # Debug profile: Minimal examples for fast iteration
    settings.register_profile("debug", max_examples=10, phases=[Phase.generate])

    # Load dev profile by default (can be overridden with --hypothesis-profile)
    settings.load_profile("dev")

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Path constants for test data
# ---------------------------------------------------------------------------
TEST_DATA_DIR = Path(__file__).parent / "test_data"


# ---------------------------------------------------------------------------
# DataFrame Fixtures - Real data for testing core logic
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_yaml_df():
    """Load minimal test YAML as DataFrame for fuzzy matching tests.

    This fixture provides a real DataFrame from YAML data to test
    core matching and merge logic without mocking.
    """
    yaml_path = TEST_DATA_DIR / "minimal_yaml.yml"
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    df = pd.DataFrame(data)
    return df.set_index("conference", drop=False)


@pytest.fixture()
def minimal_csv_df():
    """Load minimal test CSV as DataFrame for fuzzy matching tests.

    Uses CSV format with name variants to test matching against YAML.
    """
    csv_path = TEST_DATA_DIR / "minimal_csv.csv"
    df = pd.read_csv(csv_path)

    # Map CSV columns to match expected conference schema
    column_mapping = {
        "Subject": "conference",
        "Start Date": "start",
        "End Date": "end",
        "Location": "place",
        "Description": "link",
    }
    df = df.rename(columns=column_mapping)

    # Extract year from start date
    df["start"] = pd.to_datetime(df["start"])
    df["year"] = df["start"].dt.year
    df["start"] = df["start"].dt.date
    df["end"] = pd.to_datetime(df["end"]).dt.date

    return df


@pytest.fixture()
def edge_cases_df():
    """Load edge case test data as DataFrame.

    Contains conferences with:
    - TBA CFP dates
    - Online conferences (no location)
    - Extra places (multiple venues)
    - Special characters in names (México)
    - Workshop/tutorial deadlines
    """
    yaml_path = TEST_DATA_DIR / "edge_cases.yml"
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return pd.DataFrame(data)


@pytest.fixture()
def merge_conflicts_df():
    """Load test data with merge conflicts for conflict resolution testing.

    Contains conferences where YAML and CSV have conflicting values
    to verify merge strategy and logging.
    """
    yaml_path = TEST_DATA_DIR / "merge_conflicts.yml"
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Mock Fixtures - Mock ONLY external I/O boundaries
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_title_mappings():
    """Mock the title mappings file I/O to avoid file system dependencies.

    This mocks the file loading/writing operations but NOT the core
    matching logic. Use this when you need to test fuzzy_match without
    actual title mapping files.

    The fuzzy_match function calls load_title_mappings from multiple locations:
    - tidy_conf.interactive_merge.load_title_mappings
    - tidy_conf.titles.load_title_mappings (via tidy_df_names)

    It also calls update_title_mappings which writes to files.
    """
    with (
        patch("tidy_conf.interactive_merge.load_title_mappings") as mock_load1,
        patch("tidy_conf.titles.load_title_mappings") as mock_load2,
        patch("tidy_conf.interactive_merge.update_title_mappings") as mock_update,
    ):
        # Return empty mappings (list, dict) for both load calls
        mock_load1.return_value = ([], {})
        mock_load2.return_value = ([], {})
        mock_update.return_value = None
        yield {
            "load_interactive": mock_load1,
            "load_titles": mock_load2,
            "update": mock_update,
        }


@pytest.fixture()
def mock_title_mappings_with_data():
    """Mock title mappings with realistic mapping data.

    Includes known mappings like:
    - PyCon DE -> PyCon Germany & PyData Conference
    - PyCon Italia -> PyCon Italy
    """
    mapping_data = {
        "PyCon DE": "PyCon Germany & PyData Conference",
        "PyCon DE & PyData": "PyCon Germany & PyData Conference",
        "PyCon Italia": "PyCon Italy",
        "EuroPython Conference": "EuroPython",
        "PyCon US 2026": "PyCon US",
    }

    with (
        patch("tidy_conf.interactive_merge.load_title_mappings") as mock_load1,
        patch("tidy_conf.titles.load_title_mappings") as mock_load2,
        patch("tidy_conf.interactive_merge.update_title_mappings") as mock_update,
    ):
        # For interactive_merge, return empty rejections
        mock_load1.return_value = ([], {})

        # For titles (reverse=True), return the mapping data
        def load_with_reverse(reverse=False, path=None):
            if reverse:
                return ([], mapping_data)
            return ([], {})

        mock_load2.side_effect = load_with_reverse
        mock_update.return_value = None
        yield {
            "load_interactive": mock_load1,
            "load_titles": mock_load2,
            "update": mock_update,
            "mappings": mapping_data,
        }


@pytest.fixture()
def mock_user_accepts_all():
    """Mock user input to accept all fuzzy match prompts.

    Use this when testing the happy path where user confirms matches.
    """
    with patch("builtins.input", return_value="y"):
        yield


@pytest.fixture()
def mock_user_rejects_all():
    """Mock user input to reject all fuzzy match prompts.

    Use this when testing that rejections are handled correctly.
    """
    with patch("builtins.input", return_value="n"):
        yield


@pytest.fixture()
def mock_schema(tmp_path):
    """Mock the schema loading to use test data directory.

    Also mocks the types.yml loading for sub validation.
    """
    types_data = [
        {"sub": "PY", "name": "Python"},
        {"sub": "DATA", "name": "Data Science"},
        {"sub": "WEB", "name": "Web"},
        {"sub": "SCIPY", "name": "Scientific Python"},
        {"sub": "BIZ", "name": "Business"},
        {"sub": "GEO", "name": "Geospatial"},
        {"sub": "CAMP", "name": "Camp"},
        {"sub": "DAY", "name": "Day"},
    ]

    # Create types.yml in tmp_path
    types_path = tmp_path / "_data"
    types_path.mkdir(parents=True, exist_ok=True)
    with (types_path / "types.yml").open("w") as f:
        yaml.safe_dump(types_data, f)

    return types_path


# ---------------------------------------------------------------------------
# Sample Data Fixtures - Individual conference dictionaries
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_conference():
    """Sample valid conference data for testing."""
    return {
        "conference": "PyCon Test",
        "year": 2025,
        "link": "https://test.pycon.org",
        "cfp": "2025-02-15 23:59:00",
        "place": "Test City, Test Country",
        "start": "2025-06-01",
        "end": "2025-06-03",
        "sub": "PY",
        "timezone": "America/New_York",
        "location": [
            {
                "title": "PyCon Test 2025",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        ],
    }


@pytest.fixture()
def invalid_conference():
    """Sample invalid conference data for testing validation."""
    return {
        "conference": "Invalid Conf",
        "year": 1988,  # Before Python existed
        "link": "not-a-url",
        "cfp": "invalid-date",
        "place": "",  # Empty required field
        "start": "2025-06-03",
        "end": "2025-06-01",  # End before start
        "sub": "INVALID",
    }


@pytest.fixture()
def temp_yaml_file(tmp_path):
    """Create a temporary YAML file for testing."""

    def _create_yaml_file(data):
        yaml_file = tmp_path / "test_conferences.yml"
        with yaml_file.open("w", encoding="utf-8") as f:
            # Use safe_dump to avoid Python 2/3 dict representer issues
            yaml.safe_dump(data, f, default_flow_style=False)
        return str(yaml_file)

    return _create_yaml_file


@pytest.fixture()
def online_conference():
    """Sample online conference data for testing."""
    return {
        "conference": "PyConf Online",
        "year": 2025,
        "link": "https://online.pyconf.org",
        "cfp": "2025-02-15 23:59:00",
        "place": "Online",
        "start": "2025-06-01",
        "end": "2025-06-03",
        "sub": "PY",
        "timezone": "UTC",
    }


@pytest.fixture()
def sample_conferences(sample_conference):
    """Multiple conferences with known merge behavior.

    Includes:
    - Original conference
    - Different conference (EuroSciPy)
    - Duplicate of original with different deadline (tests conflict resolution)
    """
    return [
        sample_conference,
        {
            **sample_conference,
            "conference": "EuroSciPy 2025",
            "cfp": "2025-03-01 23:59:00",
            "link": "https://euroscipy.org",
            "place": "Basel, Switzerland",
        },
        {
            **sample_conference,
            "conference": "PyCon Test",  # Same name = duplicate!
            "cfp": "2025-01-20 23:59:00",  # Different deadline
            "link": "https://test.pycon.org/updated",  # Different link
        },
    ]


@pytest.fixture()
def sample_csv_data():
    """Sample CSV data for import testing."""
    return """Conference Name,Year,Website,CFP Deadline,Location,Start Date,End Date,Type
PyCon Test,2025,https://test.pycon.org,2025-02-15 23:59:00,"Test City, Test Country",2025-06-01,2025-06-03,PY
Django Test,2025,https://test.django.org,2025-03-01 23:59:00,"Another City, Test Country",2025-07-01,2025-07-03,WEB"""
