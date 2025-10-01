# /validate-data

Runs comprehensive validation on conference data files.

## Usage
```
/validate-data [--fix] [--check-links]
```

## Options
- `--fix`: Automatically fix common issues
- `--check-links`: Validate all conference URLs (slow)

## What it does
1. **Schema Validation**
   - Validates all entries in `_data/conferences.yml`
   - Checks required fields presence
   - Validates date formats and ranges
   - Ensures timezone validity

2. **Data Integrity**
   - Checks for duplicate conferences
   - Validates coordinate precision
   - Ensures consistent naming

3. **Link Validation** (if --check-links)
   - Verifies all conference URLs are accessible
   - Checks for HTTPS usage
   - Reports broken links

4. **Auto-fixes** (if --fix)
   - Sorts conferences by date
   - Fixes coordinate precision
   - Normalizes date formats
   - Moves past conferences to archive

## Output
- Validation report with errors and warnings
- Suggested fixes for common issues
- Summary of data quality metrics

## Example
```
/validate-data --fix
```