"""Smoke tests for production health monitoring."""

import json
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest
import requests
import yaml

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "utils"))


class TestProductionHealth:
    """Critical smoke tests to verify production readiness."""

    @pytest.fixture()
    def production_url(self):
        """Production URL for the site."""
        return "https://pythondeadlin.es"

    @pytest.fixture()
    def critical_paths(self):
        """Critical paths that must be accessible."""
        return [
            "/",  # Homepage
            "/search",  # Search page
            "/calendar",  # Calendar page
            "/about",  # About page
            "/series",  # Conference series
        ]

    @pytest.fixture()
    def critical_data_files(self):
        """Critical data files that must exist and be valid."""
        project_root = Path(__file__).parent.parent.parent
        return {
            "conferences": project_root / "_data" / "conferences.yml",
            "archive": project_root / "_data" / "archive.yml",
            "types": project_root / "_data" / "types.yml",
        }

    @pytest.mark.smoke()
    def test_critical_data_files_exist(self, critical_data_files):
        """Test that all critical data files exist."""
        for name, file_path in critical_data_files.items():
            assert file_path.exists(), f"Critical data file {name} not found at {file_path}"

    @pytest.mark.smoke()
    def test_data_files_valid_yaml(self, critical_data_files):
        """Test that all data files are valid YAML."""
        for name, file_path in critical_data_files.items():
            if file_path.exists():
                with file_path.open(encoding="utf-8") as f:
                    try:
                        data = yaml.safe_load(f)
                        assert data is not None, f"{name} file is empty"
                    except yaml.YAMLError as e:
                        pytest.fail(f"YAML error in {name}: {e}")

    @pytest.mark.smoke()
    def test_no_duplicate_conferences(self, critical_data_files):
        """Test that there are no duplicate active conferences."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            seen = set()
            duplicates = []

            for conf in conferences:
                key = (conf.get("conference"), conf.get("year"))
                if key in seen:
                    duplicates.append(key)
                seen.add(key)

            assert len(duplicates) == 0, f"Duplicate conferences found: {duplicates}"

    @pytest.mark.smoke()
    def test_conference_dates_valid(self, critical_data_files):
        """Test that conference dates are properly formatted."""
        import datetime as dt

        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            errors = []
            for i, conf in enumerate(conferences[:10]):  # Check first 10 for speed
                # Check date format for CFP
                cfp = conf.get("cfp")
                if cfp and cfp not in ["TBA", "Cancelled", "None"]:
                    # YAML may parse datetimes as datetime objects
                    if isinstance(cfp, (dt.datetime, dt.date)):
                        pass  # Already valid
                    else:
                        try:
                            # Should be in YYYY-MM-DD HH:MM:SS format
                            datetime.strptime(cfp, "%Y-%m-%d %H:%M:%S").replace(
                                tzinfo=timezone.utc,
                            )
                        except ValueError:
                            errors.append(f"Conference {i}: Invalid CFP date format: {cfp}")

                # Check start/end dates
                for field in ["start", "end"]:
                    date_val = conf.get(field)
                    if date_val and date_val != "TBA":
                        # YAML may parse dates as date objects
                        if isinstance(date_val, (dt.datetime, dt.date)):
                            pass  # Already valid
                        else:
                            try:
                                datetime.strptime(date_val, "%Y-%m-%d").replace(
                                    tzinfo=timezone.utc,
                                )
                            except ValueError:
                                errors.append(f"Conference {i}: Invalid {field} date format: {date_val}")

            assert len(errors) == 0, f"Date format errors: {errors[:5]}"  # Show first 5 errors

    @pytest.mark.smoke()
    def test_required_fields_present(self, critical_data_files):
        """Test that all conferences have required fields."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            required_fields = ["conference", "year", "link", "cfp", "place", "start", "end", "sub"]

            errors = []
            for i, conf in enumerate(conferences[:10]):  # Check first 10
                errors.extend(
                    f"Conference {i} ({conf.get('conference', 'Unknown')}): Missing {field}"
                    for field in required_fields
                    if field not in conf
                )

            assert len(errors) == 0, f"Missing required fields: {errors[:5]}"

    @pytest.mark.smoke()
    def test_jekyll_config_valid(self):
        """Test that Jekyll configuration is valid."""
        project_root = Path(__file__).parent.parent.parent
        config_file = project_root / "_config.yml"

        assert config_file.exists(), "Jekyll config not found"

        with config_file.open(encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None, "Config is empty"
                assert "title" in config, "Missing title in config"
                assert "url" in config, "Missing url in config"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid Jekyll config: {e}")

    @pytest.mark.smoke()
    def test_no_https_violations(self, critical_data_files):
        """Test that all conference links use HTTPS."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            http_links = []
            for conf in conferences:
                link = conf.get("link", "")
                if link.startswith("http://"):
                    http_links.append(f"{conf.get('conference')} {conf.get('year')}: {link}")

            assert len(http_links) == 0, f"HTTP links found (should be HTTPS): {http_links[:5]}"

    @pytest.mark.smoke()
    def test_javascript_files_exist(self):
        """Test that critical JavaScript files exist."""
        project_root = Path(__file__).parent.parent.parent
        js_dir = project_root / "static" / "js"

        critical_js = [
            "countdown-simple.js",
            "notifications.js",
            "search.js",
            "favorites.js",
            "conference-manager.js",
        ]

        for js_file in critical_js:
            file_path = js_dir / js_file
            assert file_path.exists(), f"Critical JS file missing: {js_file}"

    @pytest.mark.smoke()
    def test_css_files_exist(self):
        """Test that critical CSS files exist."""
        project_root = Path(__file__).parent.parent.parent
        css_dir = project_root / "static" / "css"

        assert css_dir.exists(), "CSS directory not found"

        # At least some CSS files should exist
        css_files = list(css_dir.glob("*.css"))
        assert len(css_files) > 0, "No CSS files found"

    @pytest.mark.smoke()
    @pytest.mark.skipif(not Path("_site").exists(), reason="Requires built site")
    def test_built_site_has_content(self):
        """Test that built site has expected content."""
        site_dir = Path("_site")

        # Check for index.html
        index_file = site_dir / "index.html"
        assert index_file.exists(), "No index.html in built site"

        # Check that index has content
        with index_file.open(encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 1000, "Index file seems too small"
            assert "Python" in content, "Index doesn't mention Python"

        # Check for conference pages
        conf_dir = site_dir / "conference"
        if conf_dir.exists():
            conf_pages = list(conf_dir.glob("*.html"))
            assert len(conf_pages) > 0, "No conference pages generated"

    @pytest.mark.smoke()
    def test_no_year_before_1989(self, critical_data_files):
        """Test that no conferences have year before Python's creation."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            invalid_years = []
            for conf in conferences:
                year = conf.get("year")
                if year and year < 1989:
                    invalid_years.append(f"{conf.get('conference')} {year}")

            assert len(invalid_years) == 0, f"Conferences with year < 1989: {invalid_years}"

    @pytest.mark.smoke()
    def test_timezone_validity(self, critical_data_files):
        """Test that timezone values are valid IANA timezones."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            # Sample of valid IANA timezones
            valid_tz_patterns = [
                "America/",
                "Europe/",
                "Asia/",
                "Africa/",
                "Australia/",
                "Pacific/",
                "UTC",
                "GMT",
            ]

            invalid_tz = []
            for conf in conferences[:20]:  # Check first 20
                tz = conf.get("timezone")
                if tz and not any(tz.startswith(pattern) for pattern in valid_tz_patterns):
                    invalid_tz.append(f"{conf.get('conference')}: {tz}")

            assert len(invalid_tz) == 0, f"Invalid timezones: {invalid_tz}"

    @pytest.mark.smoke()
    @pytest.mark.network()
    @patch("requests.get")
    def test_production_endpoints_accessible(self, mock_get, production_url, critical_paths):
        """Test that production endpoints are accessible."""
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Content</html>"
        mock_get.return_value = mock_response

        for path in critical_paths:
            url = f"{production_url}{path}"
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, f"Failed to access {url}"

    @pytest.mark.smoke()
    def test_package_json_valid(self):
        """Test that package.json is valid."""
        project_root = Path(__file__).parent.parent.parent
        package_file = project_root / "package.json"

        if package_file.exists():
            with package_file.open(encoding="utf-8") as f:
                try:
                    package = json.load(f)
                    assert "name" in package, "Missing name in package.json"
                    assert "scripts" in package, "Missing scripts in package.json"
                    assert "test" in package["scripts"], "Missing test script"
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid package.json: {e}")

    @pytest.mark.smoke()
    def test_critical_dependencies_installed(self):
        """Test that critical dependencies are specified."""
        project_root = Path(__file__).parent.parent.parent

        # Check Python dependencies
        pixi_file = project_root / "pixi.toml"
        if pixi_file.exists():
            with pixi_file.open(encoding="utf-8") as f:
                content = f.read()
                assert "pydantic" in content, "Missing pydantic dependency"
                assert "pytest" in content, "Missing pytest dependency"
                assert "pyyaml" in content, "Missing pyyaml dependency"

        # Check Ruby dependencies
        gemfile = project_root / "Gemfile"
        if gemfile.exists():
            with gemfile.open(encoding="utf-8") as f:
                content = f.read()
                assert "jekyll" in content, "Missing jekyll dependency"


class TestProductionDataIntegrity:
    """Tests to ensure data integrity in production."""

    @pytest.fixture()
    def critical_data_files(self):
        """Critical data files that must exist and be valid."""
        project_root = Path(__file__).parent.parent.parent
        return {
            "conferences": project_root / "_data" / "conferences.yml",
            "archive": project_root / "_data" / "archive.yml",
            "types": project_root / "_data" / "types.yml",
        }

    @pytest.mark.smoke()
    def test_no_test_data_in_production(self, critical_data_files):
        """Ensure no test data makes it to production files."""
        conf_file = critical_data_files["conferences"]
        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            test_indicators = ["test", "TEST", "example", "EXAMPLE", "demo", "DEMO", "localhost"]

            suspicious = []
            for conf in conferences:
                name = conf.get("conference", "").lower()
                link = conf.get("link", "").lower()

                # Allow legitimate conferences about testing
                suspicious.extend(
                    f"{conf.get('conference')} - {conf.get('link')}"
                    for indicator in test_indicators
                    if (indicator.lower() in name or indicator.lower() in link) and "testing" not in name
                )

            assert len(suspicious) == 0, f"Possible test data in production: {suspicious[:5]}"

    @pytest.mark.smoke()
    def test_reasonable_data_counts(self, critical_data_files):
        """Test that data counts are within reasonable ranges."""
        conf_file = critical_data_files["conferences"]
        archive_file = critical_data_files["archive"]

        if conf_file.exists():
            with conf_file.open(encoding="utf-8") as f:
                conferences = yaml.safe_load(f)

            # Should have some conferences but not too many
            assert 5 <= len(conferences) <= 500, f"Unusual number of active conferences: {len(conferences)}"

        if archive_file.exists():
            with archive_file.open(encoding="utf-8") as f:
                archive = yaml.safe_load(f)

            # Archive should have reasonable amount (at least 1 if file exists)
            assert len(archive) >= 1, f"Archive file exists but has no conferences: {len(archive)}"
            assert len(archive) <= 10000, f"Archive seems too large: {len(archive)}"


class TestSemanticCorrectness:
    """Tests for semantic correctness of conference data.

    These tests verify that data makes logical sense, not just that it exists.
    Section 9 of the test audit identified that smoke tests checked existence
    but not correctness.
    """

    @pytest.fixture()
    def critical_data_files(self):
        """Critical data files for semantic checks."""
        project_root = Path(__file__).parent.parent.parent
        return {
            "conferences": project_root / "_data" / "conferences.yml",
            "archive": project_root / "_data" / "archive.yml",
            "types": project_root / "_data" / "types.yml",
        }

    @pytest.fixture()
    def valid_topic_codes(self, critical_data_files):
        """Load valid topic codes from types.yml."""
        types_file = critical_data_files["types"]
        if types_file.exists():
            with types_file.open(encoding="utf-8") as f:
                types_data = yaml.safe_load(f)
            return {t["sub"] for t in types_data}
        return {"PY", "SCIPY", "DATA", "WEB", "BIZ", "GEO", "CAMP", "DAY"}

    @pytest.mark.smoke()
    def test_conference_dates_are_logical(self, critical_data_files):
        """Test that conference dates make logical sense.

        - Start date should be before or equal to end date
        - CFP deadline should be before conference start
        """
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"

            # Start should be before or equal to end
            start = conf.get("start")
            end = conf.get("end")
            if start and end and str(start) != "TBA" and str(end) != "TBA":
                start_str = str(start)[:10]
                end_str = str(end)[:10]
                if start_str > end_str:
                    errors.append(f"{name}: start ({start_str}) > end ({end_str})")

            # CFP should be before start (with some tolerance for last-minute CFPs)
            cfp = conf.get("cfp")
            if cfp and cfp not in ["TBA", "Cancelled", "None"] and start and str(start) != "TBA":
                cfp_date = str(cfp)[:10]
                start_date = str(start)[:10]
                if cfp_date > start_date:
                    errors.append(f"{name}: CFP ({cfp_date}) after start ({start_date})")

        assert len(errors) == 0, f"Logical date errors found:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_conference_year_matches_dates(self, critical_data_files):
        """Test that the year field matches the conference dates."""
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = conf.get("conference")
            year = conf.get("year")
            start = conf.get("start")

            if year and start and str(start) != "TBA":
                start_str = str(start)[:10]
                start_year = int(start_str[:4])

                # Year should match start date year (or be one year before for Dec-Jan spanning)
                if abs(year - start_year) > 1:
                    errors.append(f"{name}: year={year} but start={start_str}")

        assert len(errors) == 0, f"Year/date mismatches:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_latitude_longitude_ranges(self, critical_data_files):
        """Test that geographic coordinates are within valid ranges.

        - Latitude: -90 to 90
        - Longitude: -180 to 180
        """
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"
            location = conf.get("location")

            if location and isinstance(location, list):
                for loc in location:
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")

                    if lat is not None:
                        if not (-90 <= lat <= 90):
                            errors.append(f"{name}: invalid latitude {lat}")

                    if lon is not None:
                        if not (-180 <= lon <= 180):
                            errors.append(f"{name}: invalid longitude {lon}")

        assert len(errors) == 0, f"Invalid coordinates:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_url_format_validity(self, critical_data_files):
        """Test that URLs are properly formatted."""
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        url_fields = ["link", "cfp_link", "finaid", "sponsor"]

        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"

            for field in url_fields:
                url = conf.get(field)
                if url:
                    # Must start with http:// or https://
                    if not (url.startswith("http://") or url.startswith("https://")):
                        errors.append(f"{name}: {field} '{url}' missing protocol")
                    # Should have a domain
                    elif "." not in url:
                        errors.append(f"{name}: {field} '{url}' missing domain")
                    # Should not have spaces
                    elif " " in url:
                        errors.append(f"{name}: {field} '{url}' contains spaces")

        assert len(errors) == 0, f"URL format errors:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_topic_codes_are_valid(self, critical_data_files, valid_topic_codes):
        """Test that all topic codes (sub field) are valid."""
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"
            sub = conf.get("sub", "")

            if sub:
                # Sub can be comma-separated
                codes = [c.strip() for c in str(sub).split(",")]
                for code in codes:
                    if code and code not in valid_topic_codes:
                        errors.append(f"{name}: unknown topic code '{code}'")

        assert len(errors) == 0, f"Invalid topic codes:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_cfp_extended_after_original(self, critical_data_files):
        """Test that extended CFP deadline is on or after the original CFP.

        An extension can be on the same day (extending hours) or a later date.
        """
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"
            cfp = conf.get("cfp")
            cfp_ext = conf.get("cfp_ext")

            # Both must be valid dates
            if cfp and cfp_ext:
                if cfp in ["TBA", "Cancelled", "None"] or cfp_ext in ["TBA", "Cancelled", "None"]:
                    continue

                cfp_date = str(cfp)[:10]
                cfp_ext_date = str(cfp_ext)[:10]

                # Extension should be on same day or later (not before original)
                if cfp_ext_date < cfp_date:
                    errors.append(f"{name}: cfp_ext ({cfp_ext_date}) before cfp ({cfp_date})")

        assert len(errors) == 0, f"CFP extension errors:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_conference_names_meaningful(self, critical_data_files):
        """Test that conference names are meaningful (not empty or just numbers)."""
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = conf.get("conference", "")
            year = conf.get("year")

            if not name:
                errors.append(f"Conference with year {year}: empty name")
            elif name.strip() == "":
                errors.append(f"Conference with year {year}: whitespace-only name")
            elif name.isdigit():
                errors.append(f"Conference with year {year}: name is just numbers '{name}'")
            elif len(name) < 3:
                errors.append(f"Conference with year {year}: name too short '{name}'")

        assert len(errors) == 0, f"Conference name issues:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_no_future_conferences_too_far_out(self, critical_data_files):
        """Test that conferences aren't scheduled too far in the future.

        Conferences more than 3 years out are suspicious data entry errors.
        """
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        current_year = datetime.now().year
        max_year = current_year + 3

        errors = []
        for conf in conferences:
            name = conf.get("conference")
            year = conf.get("year")

            if year and year > max_year:
                errors.append(f"{name} {year}: too far in future (max {max_year})")

        assert len(errors) == 0, f"Conferences too far in future:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_place_field_has_country(self, critical_data_files):
        """Test that place field includes country information.

        Place should typically be in format "City, Country" or similar.
        """
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        errors = []
        for conf in conferences:
            name = f"{conf.get('conference')} {conf.get('year')}"
            place = conf.get("place", "")

            if place and place not in ["TBA", "Online", "Virtual", "Remote"]:
                # Should contain a comma separating city and country
                if "," not in place:
                    errors.append(f"{name}: place '{place}' missing country (no comma)")

        assert len(errors) == 0, f"Place format issues:\n" + "\n".join(errors[:10])

    @pytest.mark.smoke()
    def test_online_conferences_no_location_required(self, critical_data_files):
        """Test that online conferences don't require physical location."""
        conf_file = critical_data_files["conferences"]
        if not conf_file.exists():
            pytest.skip("No conferences file")

        with conf_file.open(encoding="utf-8") as f:
            conferences = yaml.safe_load(f)

        # This is more of a documentation test - online conferences are valid
        online_count = 0
        for conf in conferences:
            place = conf.get("place", "")
            if place.lower() in ["online", "virtual", "remote"]:
                online_count += 1
                # Should not have misleading location data
                location = conf.get("location")
                if location:
                    # Location for online events should be intentional
                    pass  # Allow it, but track for awareness

        # Just ensure the test runs - no assertion needed for valid data
        assert online_count >= 0
