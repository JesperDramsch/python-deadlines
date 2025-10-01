# /quick-fix

Quick fixes for common issues in the Python Deadlines project.

## Usage
```
/quick-fix <issue-type>
```

## Available Fixes

### `dates`
Fixes date-related issues:
- Invalid date formats
- Missing timezones
- Past CFP deadlines
- Conference date inconsistencies

### `links`
Fixes URL-related issues:
- HTTP → HTTPS upgrades
- Broken link replacements
- Missing CFP links
- Trailing slash normalization

### `coordinates`
Fixes geolocation issues:
- Missing coordinates lookup
- Precision normalization (5 decimals)
- Invalid coordinate ranges

### `duplicates`
Removes duplicate conferences:
- Fuzzy name matching
- Same conference different years
- Merge duplicate entries

### `formatting`
Fixes formatting issues:
- YAML syntax errors
- Indentation problems
- Quote normalization
- Sort order

### `social`
Fixes social media handles:
- Remove @ symbols
- Validate handles
- Convert to full URLs (Mastodon/Bluesky)

## Examples
```
/quick-fix dates
/quick-fix links
/quick-fix all
```

## Safety
- Creates backup before changes
- Shows diff before applying
- Validates after each fix
- Can be reverted with git