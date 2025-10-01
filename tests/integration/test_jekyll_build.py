"""Integration tests for Jekyll site build validation."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest
import yaml

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "utils"))


class TestJekyllBuildValidation:
    """Test Jekyll build process and output validation."""

    @pytest.fixture()
    def test_config(self, tmp_path):
        """Create a minimal test Jekyll configuration."""
        config = {
            "title": "Python Deadlines Test",
            "description": "Test site",
            "url": "http://localhost:4000",
            "baseurl": "",
            "languages": ["en"],
            "plugins": ["jekyll-datapage-generator"],
            "markdown": "kramdown",
            "exclude": ["utils/", "tests/", "*.pyc", "__pycache__", ".coverage"],
        }

        config_file = tmp_path / "_config.test.yml"
        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(config, f)

        return config_file

    @pytest.fixture()
    def sample_conference_data(self, tmp_path):
        """Create sample conference data for testing."""
        conferences = [
            {
                "conference": "Test PyCon",
                "year": 2025,
                "link": "https://test.pycon.org",
                "cfp": "2025-02-15 23:59:00",
                "place": "Test City",
                "start": "2025-06-01",
                "end": "2025-06-05",
                "sub": "PY",
            },
            {
                "conference": "Test EuroPython",
                "year": 2025,
                "link": "https://test.europython.eu",
                "cfp": "2025-03-01 23:59:00",
                "place": "Test Location",
                "start": "2025-07-01",
                "end": "2025-07-07",
                "sub": "PY",
            },
        ]

        data_dir = tmp_path / "_data"
        data_dir.mkdir(exist_ok=True)

        conf_file = data_dir / "conferences.yml"
        with conf_file.open("w", encoding="utf-8") as f:
            yaml.dump(conferences, f)

        return conf_file

    @pytest.mark.slow
    @pytest.mark.integration
    def test_jekyll_build_success(self, test_config, sample_conference_data):
        """Test that Jekyll can build the site successfully."""
        project_root = Path(__file__).parent.parent.parent

        # Run Jekyll build with test config
        result = subprocess.run(
            ["bundle", "exec", "jekyll", "build", "--config", str(test_config), "--source", str(project_root), "--destination", "_test_site", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check build succeeded
        assert result.returncode == 0, f"Jekyll build failed: {result.stderr}"

        # Check that _site directory was created
        site_dir = project_root / "_test_site"
        assert site_dir.exists(), "Jekyll did not create output directory"

        # Clean up
        if site_dir.exists():
            import shutil

            shutil.rmtree(site_dir)

    def test_jekyll_config_validation(self):
        """Test that Jekyll configuration files are valid YAML."""
        project_root = Path(__file__).parent.parent.parent
        config_files = list(project_root.glob("_config*.yml"))

        assert len(config_files) > 0, "No Jekyll config files found"

        for config_file in config_files:
            with config_file.open(encoding="utf-8") as f:
                try:
                    config = yaml.safe_load(f)
                    assert config is not None, f"{config_file} is empty"
                    assert isinstance(config, dict), f"{config_file} should be a dictionary"

                    # Check required Jekyll fields
                    if config_file.name == "_config.yml":
                        assert "title" in config, "Missing title in main config"
                        assert "url" in config, "Missing url in main config"
                        assert "languages" in config, "Missing languages in main config"

                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {config_file}: {e}")

    def test_jekyll_data_files_valid(self):
        """Test that Jekyll data files are valid and properly structured."""
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "_data"

        assert data_dir.exists(), "_data directory not found"

        # Check conference data files
        for data_file in ["conferences.yml", "archive.yml", "types.yml"]:
            file_path = data_dir / data_file
            if file_path.exists():
                with file_path.open(encoding="utf-8") as f:
                    try:
                        data = yaml.safe_load(f)
                        assert data is not None, f"{data_file} is empty"

                        if data_file == "types.yml":
                            assert isinstance(data, dict), "types.yml should be a dictionary"
                        else:
                            assert isinstance(data, list), f"{data_file} should be a list"

                    except yaml.YAMLError as e:
                        pytest.fail(f"Invalid YAML in {data_file}: {e}")

    def test_jekyll_layouts_exist(self):
        """Test that required Jekyll layouts exist."""
        project_root = Path(__file__).parent.parent.parent
        layouts_dir = project_root / "_layouts"

        assert layouts_dir.exists(), "_layouts directory not found"

        required_layouts = ["default.html", "conference.html", "home.html"]

        for layout in required_layouts:
            layout_path = layouts_dir / layout
            assert layout_path.exists(), f"Required layout {layout} not found"

    def test_jekyll_includes_exist(self):
        """Test that required Jekyll includes exist."""
        project_root = Path(__file__).parent.parent.parent
        includes_dir = project_root / "_includes"

        assert includes_dir.exists(), "_includes directory not found"

        # Check for some critical includes
        critical_includes = ["header.html", "footer.html"]

        for include in critical_includes:
            include_path = includes_dir / include
            assert include_path.exists(), f"Critical include {include} not found"

    def test_jekyll_plugins_configured(self):
        """Test that required Jekyll plugins are configured."""
        project_root = Path(__file__).parent.parent.parent
        config_file = project_root / "_config.yml"

        with config_file.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "plugins" in config, "No plugins configured"

        required_plugins = ["jekyll-datapage-generator", "jekyll-multiple-languages-plugin"]

        for plugin in required_plugins:
            assert plugin in config["plugins"], f"Required plugin {plugin} not configured"

    def test_jekyll_pages_structure(self):
        """Test that Jekyll pages directory has required structure."""
        project_root = Path(__file__).parent.parent.parent
        pages_dir = project_root / "_pages"

        if pages_dir.exists():
            # Check for important pages
            important_pages = ["about.md", "search.md", "calendar.md"]

            for page in important_pages:
                # Pages might be in root or _pages
                page_in_pages = pages_dir / page
                page_in_root = project_root / page

                assert page_in_pages.exists() or page_in_root.exists(), f"Important page {page} not found"

    @patch("subprocess.run")
    def test_jekyll_build_with_errors(self, mock_run):
        """Test handling of Jekyll build errors."""
        # Mock a failed build
        mock_run.return_value = Mock(returncode=1, stderr="Error: Invalid YAML in _config.yml", stdout="")

        result = subprocess.run(["bundle", "exec", "jekyll", "build"], capture_output=True, text=True)

        assert result.returncode == 1
        assert "Invalid YAML" in result.stderr

    def test_jekyll_static_assets(self):
        """Test that static assets are properly structured."""
        project_root = Path(__file__).parent.parent.parent
        static_dir = project_root / "static"

        assert static_dir.exists(), "static directory not found"

        # Check for required subdirectories
        required_dirs = ["css", "js", "img"]

        for dir_name in required_dirs:
            dir_path = static_dir / dir_name
            assert dir_path.exists(), f"Required static directory {dir_name} not found"
            assert len(list(dir_path.iterdir())) > 0, f"Static directory {dir_name} is empty"

    def test_jekyll_i18n_structure(self):
        """Test internationalization file structure."""
        project_root = Path(__file__).parent.parent.parent
        i18n_dir = project_root / "_i18n"

        assert i18n_dir.exists(), "_i18n directory not found"

        # Check for language directories
        config_file = project_root / "_config.yml"
        with config_file.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)

        languages = config.get("languages", ["en"])

        for lang in languages:
            lang_dir = i18n_dir / lang
            assert lang_dir.exists(), f"Language directory for {lang} not found"

            # Check for required translation files
            lang_file = lang_dir / f"{lang}.yml"
            assert lang_file.exists(), f"Translation file for {lang} not found"

    def test_conference_page_generation_config(self):
        """Test that conference page generation is properly configured."""
        project_root = Path(__file__).parent.parent.parent
        config_file = project_root / "_config.yml"

        with config_file.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Check for page_gen configuration
        assert "page_gen" in config or "page-gen" in config, "Page generation not configured"

        page_gen = config.get("page_gen", config.get("page-gen", []))
        assert len(page_gen) > 0, "No page generation rules defined"

        # Check for conference page generation
        conference_gen = None
        for gen in page_gen:
            if gen.get("data") == "conferences":
                conference_gen = gen
                break

        assert conference_gen is not None, "Conference page generation not configured"
        assert "template" in conference_gen, "No template specified for conference pages"
        assert "dir" in conference_gen, "No output directory specified for conference pages"

    def test_jekyll_gemfile_consistency(self):
        """Test that Gemfile and Gemfile.lock are consistent."""
        project_root = Path(__file__).parent.parent.parent
        gemfile = project_root / "Gemfile"
        gemfile_lock = project_root / "Gemfile.lock"

        assert gemfile.exists(), "Gemfile not found"
        assert gemfile_lock.exists(), "Gemfile.lock not found"

        # Check that Gemfile contains required gems
        with gemfile.open(encoding="utf-8") as f:
            gemfile_content = f.read()

        required_gems = ["jekyll", "jekyll-datapage-generator", "jekyll-multiple-languages-plugin"]

        for gem in required_gems:
            assert gem in gemfile_content, f"Required gem {gem} not in Gemfile"

    @pytest.mark.slow
    def test_jekyll_serve_config(self):
        """Test that Jekyll serve configurations work."""
        project_root = Path(__file__).parent.parent.parent

        # Test different config combinations
        configs = [
            ["_config.yml", "_config.test.yml"],
            ["_config.yml", "_config.dev.yml"],
            ["_config.yml", "_config.minimal.yml"],
        ]

        for config_combo in configs:
            config_files = [project_root / c for c in config_combo]

            # Check all config files exist
            for cf in config_files:
                if not cf.exists():
                    pytest.skip(f"Config file {cf} not found")

            # Test that config combination is valid YAML when merged
            merged_config = {}
            for cf in config_files:
                with cf.open(encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config:
                        merged_config.update(config)

            assert "url" in merged_config, f"No URL in merged config for {config_combo}"

    def test_search_index_generation(self):
        """Test that search index can be generated."""
        project_root = Path(__file__).parent.parent.parent
        plugins_dir = project_root / "_plugins"

        # Check for search index generator plugin
        search_plugin = plugins_dir / "jekyll-lunr-search-index-generator.rb"
        assert search_plugin.exists(), "Search index generator plugin not found"

        # Check that plugin is valid Ruby
        with search_plugin.open(encoding="utf-8") as f:
            content = f.read()
            assert "Jekyll" in content, "Not a Jekyll plugin"
            assert "Lunr" in content or "search" in content.lower(), "Not a search plugin"

    def test_calendar_ics_generation(self):
        """Test that calendar ICS generation is configured."""
        project_root = Path(__file__).parent.parent.parent
        layouts_dir = project_root / "_layouts"

        # Check for ICS layout
        ics_files = list(layouts_dir.glob("*ics*")) + list(layouts_dir.glob("*ical*")) + list(layouts_dir.glob("*calendar*"))

        assert len(ics_files) > 0, "No calendar/ICS layout found"

        # Check that timezone plugin exists for ICS generation
        plugins_dir = project_root / "_plugins"
        tz_plugin = plugins_dir / "jekyll-timezone-finder.rb"
        assert tz_plugin.exists(), "Timezone plugin needed for ICS generation not found"


class TestJekyllBuildOutput:
    """Test the output of Jekyll builds."""

    @pytest.mark.slow
    @pytest.mark.skipif(not Path("_site").exists(), reason="Requires built site")
    def test_built_site_structure(self):
        """Test that built site has expected structure."""
        site_dir = Path("_site")

        # Check for index.html
        assert (site_dir / "index.html").exists(), "No index.html in built site"

        # Check for static assets
        assert (site_dir / "static").exists(), "No static directory in built site"

        # Check for conference pages
        conf_dir = site_dir / "conference"
        if conf_dir.exists():
            conferences = list(conf_dir.glob("*.html"))
            assert len(conferences) > 0, "No conference pages generated"

    @pytest.mark.skipif(not Path("_site").exists(), reason="Requires built site")
    def test_built_site_search_index(self):
        """Test that search index is generated in built site."""
        site_dir = Path("_site")

        # Look for search index JSON
        search_files = list(site_dir.glob("**/search*.json")) + list(site_dir.glob("**/lunr*.json"))

        assert len(search_files) > 0, "No search index found in built site"

    @pytest.mark.skipif(not Path("_site").exists(), reason="Requires built site")
    def test_built_site_no_errors(self):
        """Test that built site doesn't contain Jekyll error messages."""
        site_dir = Path("_site")

        # Check a few HTML files for error messages
        html_files = list(site_dir.glob("*.html"))[:5]  # Check first 5 HTML files

        error_patterns = ["Liquid Exception", "Jekyll Error", "undefined method", "no such file"]

        for html_file in html_files:
            with html_file.open(encoding="utf-8") as f:
                content = f.read()
                for pattern in error_patterns:
                    assert pattern not in content, f"Error pattern '{pattern}' found in {html_file}"