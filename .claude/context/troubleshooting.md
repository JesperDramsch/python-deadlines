# Troubleshooting Guide

## Quick Fixes

### 🔴 Build Failures

#### Jekyll build error
```bash
# Clear Jekyll cache
rm -rf _site .jekyll-cache

# Reinstall dependencies
bundle install

# Build with verbose output
bundle exec jekyll build --verbose
```

#### Pixi environment issues
```bash
# Clear pixi cache
pixi clean

# Reinstall environment
rm -rf .pixi pixi.lock
pixi install
```

### 🟡 Validation Errors

#### "Year must be >= 1989"
- Python was created in 1989
- Use current or future years only
- Check for typos in year field

#### "Invalid timezone"
```python
# Valid examples
timezone: "America/New_York"  # ✅
timezone: "Europe/Berlin"     # ✅
timezone: "AoE"               # ✅ (Anywhere on Earth)

# Invalid examples
timezone: "EST"               # ❌ Use full IANA name
timezone: "UTC+5"             # ❌ Use region/city format
```

#### "Invalid date format"
```yaml
# Correct formats
cfp: '2025-01-15 23:59:59'  # ✅ Full datetime
start: '2025-05-15'          # ✅ Date only

# Wrong formats
cfp: '01/15/2025'            # ❌ Use YYYY-MM-DD
cfp: '2025-1-15'             # ❌ Use two digits
```

### 🟢 Data Issues

#### Duplicate conferences
```bash
# Find duplicates
python -c "
from utils.tidy_conf.deduplicate import find_duplicates
import yaml
data = yaml.safe_load(open('_data/conferences.yml'))
dupes = find_duplicates(data)
for d in dupes: print(d)
"

# Auto-fix duplicates
pixi run sort --fix-duplicates
```

#### Missing coordinates
```bash
# Add coordinates for all entries
python utils/sort_yaml.py --add-coordinates

# Manual coordinate lookup
# Visit: https://nominatim.openstreetmap.org
```

#### Broken links
```bash
# Check all links
pixi run links

# Skip link checking (development)
pixi run sort --skip-links

# Update specific conference URL
python -c "
import yaml
data = yaml.safe_load(open('_data/conferences.yml'))
# Update conference URL
for conf in data:
    if conf['conference'] == 'CONFERENCE_NAME':
        conf['link'] = 'https://new-url.com'
yaml.dump(data, open('_data/conferences.yml', 'w'))
"
```

## Common Error Messages

### Import Errors

#### "ModuleNotFoundError: No module named 'X'"
```bash
# Ensure you're in pixi environment
pixi shell

# Or install missing module
pixi add package_name
```

#### "requests.exceptions.SSLError"
```python
# Temporary workaround (NOT for production)
import requests
response = requests.get(url, verify=False)

# Better solution: Update certificates
pip install --upgrade certifi
```

### Git Issues

#### "Pre-commit hook failed"
```bash
# See what failed
pixi run pre

# Fix Python formatting
ruff format utils/
ruff check --fix utils/

# Fix YAML formatting
# Manual indentation fix required
```

#### "Merge conflicts in conferences.yml"
```bash
# Strategy: Accept both, then deduplicate
git checkout --theirs _data/conferences.yml
git add _data/conferences.yml
pixi run sort  # This will deduplicate
git add _data/conferences.yml
git commit
```

## Performance Issues

### Slow Processing

#### Optimize geocoding
```python
# Use cache
export GEOCODING_CACHE=true
pixi run sort

# Skip geocoding
pixi run sort --skip-geocoding
```

#### Optimize link checking
```python
# Parallel link checking
export LINK_CHECK_PARALLEL=10
pixi run links

# Skip link checking
pixi run sort --skip-links
```

### Memory Issues

#### Large conference files
```bash
# Process in chunks
python utils/conferences/scripts/split.py
# Process each chunk
pixi run sort --file _data/conferences_chunk1.yml
# Merge back
python utils/conferences/scripts/merge.py
```

## Testing Issues

### Test Failures

#### "Test data not found"
```bash
# Ensure test fixtures exist
ls tests/fixtures/
# Create if missing
mkdir -p tests/fixtures
cp _data/conferences.yml tests/fixtures/test_conferences.yml
```

#### "Assertion failed"
```bash
# Run specific test with verbose output
pytest tests/test_schema_validation.py -xvs

# Debug with pdb
pytest tests/test_schema_validation.py --pdb
```

### Coverage Issues

#### Low test coverage
```bash
# Generate coverage report
pixi run test-cov

# See uncovered lines
coverage report -m

# Generate HTML report
coverage html
open htmlcov/index.html
```

## Debug Tools

### Logging

#### Enable debug logging
```python
# In Python scripts
import logging
logging.basicConfig(level=logging.DEBUG)

# Via command line
python utils/sort_yaml.py --log-level DEBUG
```

#### Log to file
```python
# utils/logging_config.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
```

### Profiling

#### Performance profiling
```bash
# Profile Jekyll build
pixi run profile

# Profile Python scripts
python -m cProfile -s cumulative utils/sort_yaml.py
```

#### Memory profiling
```bash
# Install memory profiler
pip install memory_profiler

# Profile memory usage
python -m memory_profiler utils/sort_yaml.py
```

## Recovery Procedures

### Restore from Backup

#### Git recovery
```bash
# View history
git log --oneline _data/conferences.yml

# Restore specific version
git checkout <commit-hash> -- _data/conferences.yml

# Or restore from yesterday
git checkout @{yesterday} -- _data/conferences.yml
```

#### Manual backup
```bash
# Create backup
cp _data/conferences.yml _data/conferences.yml.backup

# Restore backup
cp _data/conferences.yml.backup _data/conferences.yml
```

### Reset Environment

#### Full reset
```bash
# Clean everything
git clean -fdx
rm -rf .pixi pixi.lock
rm -rf _site .jekyll-cache
rm -rf node_modules

# Reinstall
pixi install
bundle install
pixi run setup-hooks
```

## Getting Help

### Resources
1. Check existing issues: https://github.com/python-organizers/conferences/issues
2. Review documentation: `README.md`, `CONTRIBUTING.md`
3. Search error messages in codebase
4. Check CI/CD logs for similar failures

### Debug Information to Collect
When reporting issues, include:
```bash
# Environment info
pixi --version
python --version
ruby --version
bundle --version

# Error context
git status
git diff
tail -50 debug.log

# System info
uname -a  # Linux/Mac
systeminfo  # Windows
```