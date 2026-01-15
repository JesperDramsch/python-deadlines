"""Tests for YAML file integrity and data consistency."""

# Add utils to path for imports
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.schema import Conference


class TestYAMLIntegrity:
    """Test YAML file integrity and structure."""

    @pytest.fixture()
    def data_files(self):
        """Get paths to data files."""
        project_root = Path(__file__).parent.parent
        return {
            "conferences": project_root / "_data" / "conferences.yml",
            "archive": project_root / "_data" / "archive.yml",
            "legacy": project_root / "_data" / "legacy.yml",
            "types": project_root / "_data" / "types.yml",
        }

    def test_yaml_files_parseable(self, data_files):
        """Test that all YAML data files can be parsed."""
        for name, file_path in data_files.items():
            if file_path.exists():
                with file_path.open(encoding="utf-8") as f:
                    try:
                        data = yaml.safe_load(f)
                        assert data is not None, f"{name} file is empty or invalid"
                        if name != "types":
                            assert isinstance(data, list), f"{name} should contain a list"
                    except yaml.YAMLError as e:
                        pytest.fail(f"YAML parsing error in {name}: {e}")

    def test_conferences_schema_compliance(self, data_files):
        """Test that conference entries comply with schema."""
        conferences_file = data_files["conferences"]
        if not conferences_file.exists():
            pytest.skip("conferences.yml not found")

        with conferences_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        def validate_conference(i, conf_data):
            try:
                Conference(**conf_data)
                return None
            except Exception as e:
                return f"Conference {i} ({conf_data.get('conference', 'Unknown')}): {e}"

        errors = [error for i, conf_data in enumerate(conferences) if (error := validate_conference(i, conf_data))]

        if errors:
            pytest.fail("Schema validation errors:\n" + "\n".join(errors[:10]))  # Show first 10 errors

    def test_archive_schema_compliance(self, data_files):
        """Test that archived entries comply with schema."""
        archive_file = data_files["archive"]
        if not archive_file.exists():
            pytest.skip("archive.yml not found")

        with archive_file.open(encoding="utf-8") as f:
            archived_conferences = yaml.safe_load(f)

        def validate_archived_conference(i, conf_data):
            try:
                Conference(**conf_data)
                return None
            except Exception as e:
                return f"Archived conference {i}: {e}"

        errors = [
            error
            for i, conf_data in enumerate(archived_conferences[:50])  # Test first 50 to avoid timeout
            if (error := validate_archived_conference(i, conf_data))
        ]

        if errors:
            pytest.fail("Archive schema validation errors:\n" + "\n".join(errors[:10]))

    def test_no_duplicate_conferences(self, data_files):
        """Test that there are no duplicate conferences in active list."""
        conferences_file = data_files["conferences"]
        if not conferences_file.exists():
            pytest.skip("conferences.yml not found")

        with conferences_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        seen_conferences = set()
        duplicates = []

        for conf in conferences:
            # Create unique key from conference name, year, and place
            key = (conf.get("conference", "").lower().strip(), conf.get("year"), conf.get("place", "").lower().strip())

            if key in seen_conferences:
                duplicates.append(f"{conf.get('conference')} {conf.get('year')} - {conf.get('place')}")
            else:
                seen_conferences.add(key)

        if duplicates:
            pytest.fail("Duplicate conferences found:\n" + "\n".join(duplicates))

    def test_conference_types_validity(self, data_files):
        """Test that all conferences use valid types."""
        conferences_file = data_files["conferences"]
        types_file = data_files["types"]

        if not conferences_file.exists() or not types_file.exists():
            pytest.skip("Required data files not found")

        # Load valid types
        with types_file.open(encoding="utf-8") as f:
            types_data = yaml.safe_load(f)

        valid_types = {type_info["sub"] for type_info in types_data}

        # Check conferences
        with conferences_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        invalid_types = []
        for conf in conferences:
            conf_type = conf.get("sub")
            if conf_type:
                # Handle comma-separated types like "PY,DATA"
                individual_types = [t.strip() for t in conf_type.split(",")]
                invalid_types.extend(
                    f"{conf.get('conference')} uses invalid type: {individual_type} (from {conf_type})"
                    for individual_type in individual_types
                    if individual_type not in valid_types
                )

        if invalid_types:
            pytest.fail("Invalid conference types:\n" + "\n".join(invalid_types[:10]))

    def test_future_conferences_only(self, data_files):
        """Test that conferences.yml contains only future conferences."""
        conferences_file = data_files["conferences"]
        if not conferences_file.exists():
            pytest.skip("conferences.yml not found")

        with conferences_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        current_year = datetime.now(tz=timezone.utc).year
        past_conferences = []

        for conf in conferences:
            conf_year = conf.get("year")
            if conf_year and conf_year < current_year - 1:  # Allow some buffer for year-end
                past_conferences.append(f"{conf.get('conference')} {conf_year}")

        if past_conferences:
            pytest.fail("Past conferences should be archived:\n" + "\n".join(past_conferences[:10]))


class TestDataConsistency:
    """Test data consistency across files."""

    @pytest.fixture()
    def all_conference_data(self):
        """Load all conference data."""
        project_root = Path(__file__).parent.parent
        data = {}

        for file_name in ["conferences.yml", "archive.yml", "legacy.yml"]:
            file_path = project_root / "_data" / file_name
            if file_path.exists():
                with file_path.open(encoding="utf-8") as f:
                    data[file_name] = yaml.safe_load(f)

        return data

    def test_url_consistency(self, all_conference_data):
        """Test URL format consistency."""
        all_conferences = []
        for file_data in all_conference_data.values():
            if file_data:
                all_conferences.extend(file_data)

        url_errors = []
        for conf in all_conferences[:100]:  # Test subset to avoid timeout
            for url_field in ["link", "cfp_link", "sponsor", "finaid"]:
                url = conf.get(url_field)
                if url and isinstance(url, str) and not url.startswith(("http://", "https://")):
                    url_errors.append(f"{conf.get('conference')}: Invalid {url_field} - {url}")

        if url_errors:
            pytest.fail("URL format errors:\n" + "\n".join(url_errors[:10]))

    def test_date_format_consistency(self, all_conference_data):
        """Test date format consistency."""
        all_conferences = []
        for file_data in all_conference_data.values():
            if file_data:
                all_conferences.extend(file_data)

        date_errors = []
        date_format = "%Y-%m-%d %H:%M:%S"

        for conf in all_conferences[:100]:  # Test subset
            for date_field in ["cfp", "cfp_ext", "workshop_deadline", "tutorial_deadline"]:
                date_str = conf.get(date_field)
                if date_str and isinstance(date_str, str) and date_str not in ["TBA", "None", "Cancelled"]:
                    try:
                        datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
                    except ValueError:
                        date_errors.append(f"{conf.get('conference')}: Invalid {date_field} format - {date_str}")

        if date_errors:
            pytest.fail("Date format errors:\n" + "\n".join(date_errors[:10]))

    def test_geographic_data_consistency(self, all_conference_data):
        """Test geographic data consistency."""
        all_conferences = []
        for file_data in all_conference_data.values():
            if file_data:
                all_conferences.extend(file_data)

        geo_errors = []
        for conf in all_conferences[:100]:  # Test subset
            location_data = conf.get("location")
            if location_data:
                if not isinstance(location_data, list):
                    geo_errors.append(f"{conf.get('conference')}: location should be a list")
                    continue

                for loc in location_data:
                    if not isinstance(loc, dict):
                        geo_errors.append(f"{conf.get('conference')}: location items should be objects")
                        continue

                    lat = loc.get("latitude")
                    lon = loc.get("longitude")

                    if lat is not None and (lat < -90 or lat > 90):
                        geo_errors.append(f"{conf.get('conference')}: Invalid latitude {lat}")

                    if lon is not None and (lon < -180 or lon > 180):
                        geo_errors.append(f"{conf.get('conference')}: Invalid longitude {lon}")

        if geo_errors:
            pytest.fail("Geographic data errors:\n" + "\n".join(geo_errors[:10]))
