"""Pytest configuration and fixtures for Python Deadlines tests."""

import pytest
import yaml


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
            yaml.dump(data, f, default_flow_style=False)
        return str(yaml_file)

    return _create_yaml_file


@pytest.fixture()
def sample_csv_data():
    """Sample CSV data for import testing."""
    return """Conference Name,Year,Website,CFP Deadline,Location,Start Date,End Date,Type
PyCon Test,2025,https://test.pycon.org,2025-02-15 23:59:00,"Test City, Test Country",2025-06-01,2025-06-03,PY
Django Test,2025,https://test.django.org,2025-03-01 23:59:00,"Another City, Test Country",2025-07-01,2025-07-03,WEB"""
