# /import-conferences

Imports conference data from external sources.

## Usage
```
/import-conferences [--source <source>] [--year <year>]
```

## Options
- `--source`: Specify import source (official, organizers, all)
- `--year`: Import only for specific year

## Sources
1. **Python Official** (python.org)
   - Google Calendar ICS feed
   - Official Python events

2. **Python Organizers** (GitHub)
   - Community-maintained CSV files
   - Broader conference coverage

## What it does
1. Fetches data from external sources
2. Parses and normalizes conference information
3. Performs fuzzy matching to avoid duplicates
4. Merges with existing data intelligently
5. Validates all imported entries
6. Generates import report

## Merge Strategy
- Uses fuzzy matching (thefuzz library)
- Prioritizes existing data over imports
- Preserves manual edits
- Adds missing fields from imports

## Example
```
/import-conferences --source official --year 2025
```

## Post-import
After import, always:
1. Review the changes with `git diff`
2. Run `/validate-data` to ensure consistency
3. Test the site locally with `pixi run serve`