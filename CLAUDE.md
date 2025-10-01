# CLAUDE.md - Python Deadlines Project Configuration

<project_identity>
## Project Identity
Python Deadlines is a production Jekyll-based multilingual website that tracks Python conference CFP deadlines globally. This is a public-facing resource used by thousands of Python developers worldwide to track submission opportunities.

**Production URL**: https://pythondeadlin.es  
**Repository**: GitHub Pages deployment from gh-pages branch  
**Criticality**: High - incorrect data affects conference organizers and submitters
</project_identity>

<documentation_hub>
## 📚 Documentation System

**Core Documentation** (auto-loaded):
- `.claude/docs/adhd-support.md` - ADHD development support and energy management
- `.claude/docs/critical-operations.md` - Data integrity rules and safety checklists
- `.claude/docs/git-workflow.md` - Git workflow, branching, and deployment

**Context Documents** (reference as needed):
- `.claude/context/conference-schema.md` - Complete field reference
- `.claude/context/data-pipeline.md` - Processing workflow details
- `.claude/context/troubleshooting.md` - Common issues and solutions

**Agents** (invoke for specialized tasks):
- `.claude/agents/conference-specialist.md` - Data validation and enrichment
- `.claude/agents/qa-guardian.md` - Quality assurance and testing
</documentation_hub>

<quick_reference>
## 🚀 Quick Reference

**Most Common Commands**:
```bash
pixi run sort        # Validate and sort conference data
pixi run test-fast   # Quick test run
pixi run pre         # Pre-commit checks (MANDATORY)
pixi run serve       # Local Jekyll server
pixi run merge       # Import from external sources
```

**Adding a Conference**: Edit `_data/conferences.yml` → `pixi run sort` → `pixi run pre` → commit
**Quick Fix**: Find issue → Fix → `pixi run test-fast` → `pixi run pre` → commit
**ADHD Support**: Use TodoWrite for task tracking, see `.claude/docs/adhd-support.md`
</quick_reference>

## 🎯 Quick Start

### First Time Setup
```bash
# 1. Install dependencies
pixi install

# 2. Set up pre-commit hooks
pixi run setup-hooks

# 3. Validate existing data
pixi run sort

# 4. Start local server
pixi run serve
```

### Most Common Tasks
- **Add a conference**: Edit `_data/conferences.yml`, then run `pixi run sort`
- **Import conferences**: `pixi run merge`
- **Generate newsletter**: `pixi run newsletter`
- **Run tests**: `pixi run test`
- **Fix issues**: `pixi run pre` before committing

<project_overview>
## 📋 Project Overview

### Core Mission
Track and display Python conference Call-for-Proposal (CFP) deadlines globally with countdown timers, helping the Python community never miss submission opportunities.

### Technical Architecture
<technical_stack>
<frontend>
- **Framework**: Jekyll 4.x with GitHub Pages
- **Languages**: 9 languages via Jekyll Multiple Languages Plugin
- **Search**: Lunr.js with custom Jekyll plugin
- **Calendar**: ICS generation via Jekyll layouts
- **Maps**: Jekyll Maps plugin for geographic visualization
</frontend>

<backend>
- **Data Processing**: Python 3.11+ with Pydantic validation
- **Environment**: Pixi package manager
- **Testing**: Pytest with fixtures and mocking
- **Quality**: Pre-commit hooks, Ruff linting
- **CI/CD**: GitHub Actions with automated deployment
</backend>

<data_management>
- **Format**: YAML with strict schema validation
- **Sources**: python.org, python-organizers, manual submissions
- **Validation**: Multi-layer (Pydantic, Vladiate, custom)
- **Updates**: Weekly automated imports + continuous manual updates
</data_management>
</technical_stack>

### Production Characteristics
- **Traffic**: ~5,000 unique visitors/month
- **Data Volume**: 200+ conferences/year
- **Update Frequency**: Daily manual, weekly automated
- **SLA**: 99.9% uptime via GitHub Pages
</project_overview>

## 🚀 Claude Code Configuration

This project includes Claude Code enhancements in the `.claude/` directory:

### Available Commands
- `/add-conference` - Add a new conference with guided prompts
- `/validate-data` - Run comprehensive data validation
- `/import-conferences` - Import from external sources
- `/newsletter` - Generate newsletter content
- `/quick-fix` - Fix common issues automatically

### Hooks & Automation
- **Pre-edit validation**: Warns before editing protected files
- **Post-edit formatting**: Auto-formats Python and validates YAML
- **Command validation**: Blocks dangerous operations
- **Auto-completion**: Completes partial dates and timezones

### Context Documents
Auto-loaded context in `.claude/context/`:
- `conference-schema.md` - Complete field reference
- `data-pipeline.md` - Processing workflow details
- `troubleshooting.md` - Common issues and solutions

## 🛠️ Key Development Commands

### Python Environment Setup
```bash
# Initialize pixi environment
pixi install

# Activate environment
pixi shell
```

### Core Data Management
```bash
# Sort conference data and validate entries
pixi run sort

# Sort and validate with link checking
pixi run links

# Import from external sources and process
pixi run merge

# Generate newsletter content
pixi run newsletter
```

### Jekyll Site Development
```bash
# Install Ruby dependencies
bundle install

# Serve site locally
pixi run serve
# OR
bundler exec jekyll serve

# Build with performance profiling
pixi run profile
# OR
bundler exec jekyll build --profile
```

### Code Quality and Testing
```bash
# Set up pre-commit hooks (run once after pixi install)
pixi run setup-hooks

# Run all pre-commit hooks (MANDATORY before committing)
pixi run pre

# Run all tests
pixi run test

# Run tests with coverage report
pixi run test-cov

# Run tests until first failure (fast feedback)
pixi run test-fast

# Lint Python code
ruff check utils/
ruff format utils/

# Validate conference data
python utils/conferences/linters/validate.py
```

<critical_operations>
## ⚡ Critical Operations Summary

**NEVER**: Edit archive.yml, add pre-1989 conferences, use HTTP URLs, skip validation
**ALWAYS**: Validate data, check duplicates, use IANA timezones, test locally first

**Pre-commit checklist**: `pixi run sort` → `pixi run test` → `pixi run pre` → `pixi run serve`

📖 See `.claude/docs/critical-operations.md` for complete safeguards
</critical_operations>

## Architecture and Data Structure

### Core Data Files
- `_data/conferences.yml` - Active conferences with CFP deadlines
- `_data/archive.yml` - Past conferences (auto-managed)
- `_data/legacy.yml` - Historical conference data (auto-managed)
- `_data/types.yml` - Conference categories (PY, SCIPY, DATA, WEB, BIZ, GEO, etc.)

### Conference Entry Schema
Required fields: `conference`, `year`, `link`, `cfp`, `place`, `start`, `end`, `sub`  
Optional: `cfp_link`, `cfp_ext`, `workshop_deadline`, `tutorial_deadline`, `timezone`, `sponsor`, `finaid`, `twitter`, `mastodon`, `bluesky`, `note`, `location`, `extra_places`

**Validation Constraints**:
- Years must be >= 1989 (Python's birth year)
- Coordinates precision: 5 decimal places max
- Date format: 'YYYY-MM-DD HH:mm:ss'
- Timezone: IANA standard timezones (defaults to AoE if omitted)
- Social media: Handles without @ symbol, full URLs for Mastodon/Bluesky
- Hybrid conferences: Use `extra_places` array for additional locations

### Python Utilities (`utils/`)
- `sort_yaml.py` - Main data processing and validation
- `main.py` - Orchestrates data import and sorting
- `import_python_official.py` - Imports from python.org
- `import_python_organizers.py` - Imports from organizers
- `newsletter.py` - Generates newsletter content
- `git_parser.py` - Git integration for tracking changes
- `tidy_conf/` - Modular data cleaning and validation library

### Jekyll Structure
- `_layouts/` - Page templates including calendar ICS generators
- `_includes/` - Reusable components and JavaScript modules
- `_pages/` - Static pages (about, search, map, etc.)
- `_plugins/` - Custom Jekyll plugins for timezone handling and search
- `_i18n/` - Translation files for 9 supported languages
- `static/` - CSS, JS, images, and fonts

### Custom Jekyll Plugins (`_plugins/`)
- `jekyll-timezone-finder.rb` - Converts conference times to UTC for ICS calendars and handles timezone validation
- `jekyll-lunr-search-index-generator.rb` - Generates search indexes for the multilingual site search functionality
- `jekyll-ics-wrap-lines-filter.rb` - Formats calendar (.ics) files with proper line wrapping per RFC standards

## Data Management Workflow

1. **Adding Conferences**: Edit `_data/conferences.yml` directly or use import scripts
2. **Validation**: Run `pixi run sort` to validate schema and clean data
3. **Link Checking**: Use `pixi run links` to verify conference URLs
4. **Auto-archiving**: Old conferences automatically move to archive during sorting
5. **Location Data**: Coordinates added automatically via geolocation services

## Data Import and Processing

### Automated Import Sources
- **Python Official** (`import_python_official.py`): Imports from Google Calendar ICS feed
  - Source: `j7gov1cmnqr9tvg14k621j7t5c@group.calendar.google.com`
  - Parses ICS events into conference format
- **Python Organizers** (`import_python_organizers.py`): Imports from GitHub CSV
  - Source: `python-organizers/conferences` repository
  - Fetches yearly CSV files for current and future years

### Data Processing Pipeline
1. **Fuzzy Matching**: Uses `thefuzz` library to match similar conference names
2. **Deduplication**: Intelligent merging of conferences from multiple sources
3. **Schema Validation**: Pydantic validation with automatic field population
4. **Geographic Enhancement**: Auto-adds coordinates via geolocation APIs
5. **Link Validation**: Optional URL checking with caching mechanism

### Newsletter Generation
- **Filter Logic**: Conferences with CFPs closing within 10 days
- **Extended Deadlines**: Prioritizes `cfp_ext` over `cfp` when available
- **Git Integration**: Uses conventional commits to track newsletter changes

### Archive Management
- **Auto-archiving**: Past conferences moved to `_data/archive.yml` during sort
- **Schema Consistency**: Archived entries maintain same format as active ones
- **Historical Tracking**: Git parser creates structured commit messages for changes

## Multi-language Support

- Translation managed via Crowdin (crowdin.yml)
- Jekyll Multiple Languages Plugin handles routing
- Language files in `_i18n/[lang]/` directories
- Supported: en, es, de, fr, pt-br, zh-cn, hi, id, ru

## 📁 Project Structure

### Core Files
```
_data/
├── conferences.yml      # Active conferences (MAIN DATA FILE)
├── archive.yml         # Past conferences (auto-managed)
├── legacy.yml          # Historical data
└── types.yml          # Conference categories

utils/
├── sort_yaml.py        # Main processing script
├── main.py            # Import orchestrator
├── import_*.py        # Import scripts
├── newsletter.py      # Newsletter generator
└── tidy_conf/         # Validation library

.claude/
├── settings.json      # Claude Code configuration
├── commands/         # Custom slash commands
├── scripts/          # Hook scripts
└── context/          # Auto-loaded documentation
```

### Important Files for Conference Management

- `utils/schema.yml` - Pydantic schema definition
- `utils/tidy_conf/schema.py` - Python validation classes
- `utils/conferences/linters/validate.py` - Data validation script
- `ruff.toml` - Python linting configuration
- `.claude/settings.json` - Claude Code behavior configuration

## Data Validation Pipeline

The project uses a multi-layered validation approach:

1. **Pydantic Validation** (`utils/tidy_conf/schema.py`):
   - Type checking and constraint validation
   - Automatic data cleaning and normalization
   - Geographic coordinate validation

2. **Vladiate Validation** (`utils/conferences/linters/`):
   - Additional business rule validation
   - CSV format validation for import data
   - Custom validation rules via `vladiate` library

3. **Link Validation**:
   - Automated URL checking during sorting
   - Caching mechanism to avoid redundant requests
   - Configurable via `--skip_links` flag

## Deployment Notes

- Site builds automatically on push to main branch
- GitHub Pages serves from gh-pages branch
- Calendar feeds (.ics) generated from Jekyll layouts
- Search index built via custom Jekyll plugin
- Map integration uses Jekyll Maps plugin

## Contributing Guidelines

### Code Contributions

1. **MANDATORY Pre-Commit Checks**:
   - Install pre-commit hooks: `pixi run setup-hooks`
   - Always run `pixi run pre` before committing
   - All tests must pass: `pixi run test`
   - Never bypass quality checks with `--no-verify`

2. **Code Quality Requirements**:
   - Add type hints to all functions
   - Include comprehensive error handling with logging
   - Write tests for new functionality
   - Use security best practices (HTTPS, input validation)
   - Follow established logging patterns

3. **Testing Standards**:
   - Use pytest fixtures for test data
   - Mock external dependencies (HTTP, file I/O)
   - Test both success and failure scenarios
   - Maintain test coverage for critical functions

### Conference Data Changes

- Conference data changes go to `_data/conferences.yml`
- Run validation scripts before committing: `pixi run sort`
- Use timezone finder tool for accurate timezone data
- Include geolocation coordinates when possible
- Follow existing YAML formatting patterns
- Test changes with `pixi run pre` before committing

## Troubleshooting

### Common Issues

**Validation Errors**:
- `Year must be >= 1989`: Use valid year for Python conferences
- `Invalid timezone`: Use IANA timezone strings (e.g., 'America/New_York', not 'EST')
- `Invalid date format`: Use 'YYYY-MM-DD HH:mm:ss' format
- `Coordinate precision`: Round coordinates to 5 decimal places max

**Build Failures**:
- Missing dependencies: Run `pixi install` to ensure all packages installed
- Jekyll build errors: Check `_config.yml` syntax and plugin compatibility
- Ruby gem conflicts: Use `bundle install` to resolve dependencies

**Data Processing**:
- Link validation timeouts: Use `--skip_links` flag during development
- Encoding issues: Ensure UTF-8 encoding for conference names with special characters
- Duplicate conferences: Use `alt_name` field for conferences with name variations

**Code Quality Issues**:
- Pre-commit hook failures: Run `pixi run pre` to see specific issues, fix each one individually
- Type annotation errors: Add proper type hints using modern syntax (`str | None`, not `Optional[str]`)
- Linting errors: Fix code issues rather than suppressing with `# noqa`
- Test failures: Ensure all tests pass with `pixi run test` before committing
- Import errors in tests: Check that `utils/` is properly added to Python path in test files

**Timezone Handling**:
- Default timezone is AoE (Anywhere on Earth) if omitted
- Use https://timezonefinder.michelfe.it/ for accurate timezone lookup
- Test timezone conversions in calendar exports (.ics files)

## Testing Infrastructure

The project includes comprehensive testing and quality assurance:

### Test Suite
- **Schema Validation Tests**: Validate Pydantic models and conference data structure
- **Data Processing Tests**: Test sorting, merging, and data transformation logic
- **Import Function Tests**: Test data import from external sources with mocking
- **YAML Integrity Tests**: Validate actual conference data files for consistency

### Pre-commit Hooks
- Automatically validate conference data schema on commit
- Format Python code with Ruff
- Check YAML syntax and formatting
- Validate CSV import data

### Logging Infrastructure
- Structured logging throughout import and processing scripts
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- Detailed error messages for troubleshooting data import issues

### Running Tests
```bash
# Run all tests
pixi run test

# Run with coverage report
pixi run test-cov

# Fast feedback (stop on first failure)
pixi run test-fast
```

## Performance Optimizations

The project includes responsible performance optimizations that improve processing speed while respecting external API rate limits and policies.

### Key Performance Features

1. **Smart Geocoding Caching**:
   - Persistent cache for geocoding results to avoid repeat API calls
   - Intelligent deduplication of place names before API requests
   - Respects OpenStreetMap Nominatim rate limits (1 request per second)
   - Reduces geocoding time by 70-90% for subsequent runs

2. **Parallel Processing**:
   - CPU-bound operations (date processing, validation) run in parallel
   - Thread pool for I/O-bound operations
   - Process pool for computation-intensive tasks
   - Maintains thread safety and error handling

3. **Efficient Algorithms**:
   - Hash-based duplicate detection (O(n) instead of O(n²))
   - Smart data structures for faster lookups
   - Pre-calculated date ranges for splitting logic
   - Optimized sorting with multiple keys

4. **Link Checking Optimizations**:
   - URL deduplication before checking
   - Persistent cache for link validation results
   - Respects website rate limits and robots.txt
   - Falls back gracefully on errors

### Performance Modules

- `utils/performance_optimized.py` - Core optimization functions
- `utils/sort_yaml_responsible.py` - Performance-optimized sorting pipeline
- `tests/test_performance_optimizations.py` - Performance optimization tests

### Usage

```bash
# Use performance-optimized processing
python utils/sort_yaml_responsible.py

# With custom log level for debugging
python utils/sort_yaml_responsible.py --log-level DEBUG

# Skip link checking for faster processing during development
python utils/sort_yaml_responsible.py --skip_links
```

### Performance Guidelines

**DO**:
- Use smart caching to reduce external API calls
- Implement parallel processing for CPU-bound operations
- Deduplicate requests before making external calls
- Use efficient data structures and algorithms

**DON'T**:
- Violate external API rate limits (always respect 1 req/sec for Nominatim)
- Make excessive parallel requests to external services
- Bypass caching mechanisms to "force refresh" data
- Remove intentional delays that prevent service bans

## Code Quality Standards

This project enforces high code quality standards through automated tooling and established practices.

### Mandatory Pre-Commit Requirements

**CRITICAL**: All changes must pass pre-commit hooks before committing:

```bash
# Run ALL pre-commit checks (MANDATORY before any commit)
pixi run pre
```

### Code Quality Expectations

1. **Type Hints Required**:
   - All function parameters and return values must have type hints
   - Use modern Python syntax: `str | None` instead of `Optional[str]`
   - Import types from `typing` when needed

2. **Error Handling Standards**:
   - Use structured exception handling with specific exception types
   - Return `bool` values for success/failure in utility functions
   - Provide meaningful error messages with context
   - Log errors with appropriate severity levels

3. **Security Requirements**:
   - Use `requests` library instead of `urllib` for HTTP requests
   - Validate URL schemes (require HTTPS for external sources)
   - Sanitize all user inputs and external data
   - Never commit secrets or credentials

4. **Testing Requirements**:
   - All new features must include comprehensive tests
   - Use pytest fixtures for consistent test data
   - Mock external dependencies (HTTP requests, file I/O)
   - Maintain test coverage for critical data processing functions

5. **Logging Standards**:
   - Use structured logging throughout data processing scripts
   - Import loggers via: `from logging_config import get_logger`
   - Log at appropriate levels: DEBUG, INFO, WARNING, ERROR
   - Include contextual information in log messages

### Development Workflow

1. **Setup** (First time):
   ```bash
   pixi install
   pixi run setup-hooks  # Install pre-commit hooks
   ```

2. **Making Changes**:
   ```bash
   # Make your code changes
   # Write/update tests for your changes
   pixi run test          # Verify tests pass
   pixi run pre           # MANDATORY: Run all quality checks
   git add .
   git commit -m "your commit message"
   ```

3. **Pre-Commit Hook Failures**:
   - Never use `--no-verify` to skip pre-commit hooks
   - Never use `# noqa` to suppress linting errors (fix the code instead)
   - Address all reported issues before committing

### Error Handling Patterns

**Data Processing Scripts**:
```python
def process_data() -> bool:
    """Process conference data with proper error handling.
    
    Returns:
        bool: True if processing succeeded, False otherwise
    """
    logger = get_logger(__name__)
    
    try:
        # Processing logic here
        logger.info("Data processing completed successfully")
        return True
    except SpecificException as e:
        logger.error(f"Specific error occurred: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
        return False
```

**HTTP Requests**:
```python
import requests

def fetch_data(url: str) -> str | None:
    """Fetch data from URL with security validation.
    
    Returns:
        str | None: Response content or None on failure
    """
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are allowed")
        
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None
```

### Testing Patterns

**Use Fixtures for Test Data**:
```python
@pytest.fixture
def sample_conference():
    return {
        "conference": "PyCon Test",
        "year": 2025,
        "link": "https://example.com",
        # ... other required fields
    }
```

**Mock External Dependencies**:
```python
@patch('requests.get')
def test_http_function(mock_get, sample_data):
    mock_get.return_value.content = sample_data
    result = function_under_test()
    assert result is not None
```


## ⚠️ Critical Guidelines

### DO ✅
- Run `pixi run pre` before EVERY commit
- Use `pixi run sort` after editing conference data
- Validate URLs are HTTPS before adding
- Check timezone validity with IANA database
- Test locally with `pixi run serve` before pushing
- Use existing patterns and conventions
- Follow the schema strictly

### DON'T ❌
- Skip pre-commit hooks with `--no-verify`
- Use `# noqa` to suppress linting errors
- Add conferences with year < 1989
- Use HTTP URLs (always HTTPS)
- Commit without running tests
- Create duplicate conference entries
- Modify archive.yml manually (auto-managed)

## 📚 Additional Resources

### External Tools
- [Timezone Finder](https://timezonefinder.michelfe.it/) - Find IANA timezones
- [Nominatim](https://nominatim.openstreetmap.org) - Geocoding service
- [ICS Validator](https://icalendar.org/validator.html) - Calendar feed validation

### Related Repositories
- [Python Organizers](https://github.com/python-organizers/conferences) - Conference CSV data
- [Python.org Events](https://www.python.org/events/) - Official Python events

### Getting Help
- GitHub Issues: Report bugs and request features
- Contributing: See `CONTRIBUTING.md` for guidelines
- Translation: See `TRANSLATION.md` for localization help

## 🔄 Automated Workflows

### GitHub Actions
- **Weekly Import**: Mondays at 00:00 UTC
- **Data Validation**: On every push
- **Site Build**: On merge to main
- **Newsletter Draft**: Weekly on Fridays

### Pre-commit Hooks
Installed via `pixi run setup-hooks`:
1. Python formatting (ruff)
2. YAML validation
3. Schema validation
4. Conference data sorting
5. Link checking (optional)
