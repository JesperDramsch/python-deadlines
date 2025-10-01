# ⚡ Critical Operations & Safeguards

## Data Integrity Rules

### NEVER
- ❌ Edit `archive.yml` or `legacy.yml` directly (auto-managed)
- ❌ Add conferences with year < 1989 (Python's birth year)
- ❌ Use HTTP URLs - always require HTTPS
- ❌ Skip validation with `pixi run sort` after edits
- ❌ Commit without running `pixi run pre`
- ❌ Use `--no-verify` to bypass git hooks

### ALWAYS
- ✅ Validate conference data before committing
- ✅ Check for duplicates before adding new conferences
- ✅ Use IANA timezone strings (never abbreviations)
- ✅ Include coordinates to 5 decimal places max
- ✅ Test locally with `pixi run serve` before pushing
- ✅ Run link validation for new conference URLs

## Production Safety Checklist

Before ANY commit to main:
- [ ] `pixi run sort` - Data validated and sorted
- [ ] `pixi run test` - All tests passing
- [ ] `pixi run pre` - Pre-commit hooks pass
- [ ] `pixi run serve` - Site builds without errors
- [ ] No duplicate conferences introduced
- [ ] All URLs use HTTPS protocol
- [ ] Timezones are valid IANA strings

## Conference Entry Schema

### Required Fields
`conference`, `year`, `link`, `cfp`, `place`, `start`, `end`, `sub`

### Optional Fields
`cfp_link`, `cfp_ext`, `workshop_deadline`, `tutorial_deadline`, `timezone`, `sponsor`, `finaid`, `twitter`, `mastodon`, `bluesky`, `note`, `location`, `extra_places`

### Validation Constraints
- Years must be >= 1989 (Python's birth year)
- Coordinates precision: 5 decimal places max
- Date format: 'YYYY-MM-DD HH:mm:ss'
- Timezone: IANA standard timezones (defaults to AoE if omitted)
- Social media: Handles without @ symbol, full URLs for Mastodon/Bluesky
- Hybrid conferences: Use `extra_places` array for additional locations

## Data Validation Pipeline

### 1. Pydantic Validation (`utils/tidy_conf/schema.py`)
- Type checking and constraint validation
- Automatic data cleaning and normalization
- Geographic coordinate validation

### 2. Vladiate Validation (`utils/conferences/linters/`)
- Additional business rule validation
- CSV format validation for import data
- Custom validation rules via `vladiate` library

### 3. Link Validation
- Automated URL checking during sorting
- Caching mechanism to avoid redundant requests
- Configurable via `--skip_links` flag

## Common Issues

### Validation Errors
- `Year must be >= 1989`: Use valid year for Python conferences
- `Invalid timezone`: Use IANA timezone strings (e.g., 'America/New_York', not 'EST')
- `Invalid date format`: Use 'YYYY-MM-DD HH:mm:ss' format
- `Coordinate precision`: Round coordinates to 5 decimal places max

### Build Failures
- Missing dependencies: Run `pixi install` to ensure all packages installed
- Jekyll build errors: Check `_config.yml` syntax and plugin compatibility
- Ruby gem conflicts: Use `bundle install` to resolve dependencies

### Data Processing
- Link validation timeouts: Use `--skip_links` flag during development
- Encoding issues: Ensure UTF-8 encoding for conference names with special characters
- Duplicate conferences: Use `alt_name` field for conferences with name variations