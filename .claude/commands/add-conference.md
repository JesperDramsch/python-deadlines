# /add-conference

Adds a new conference to the Python Deadlines database.

## Usage
```
/add-conference <conference_name> <year>
```

## What it does
1. Creates a new conference entry in `_data/conferences.yml`
2. Validates the schema automatically
3. Adds geolocation coordinates if possible
4. Runs sorting and validation
5. Commits the changes with a conventional commit message

## Required Information
The command will prompt for:
- Conference name and year
- Conference website URL
- CFP deadline date
- Conference start and end dates
- Location (city, country)
- Submission categories (talks, workshops, tutorials)
- Optional: Social media handles, financial aid info

## Example
```
/add-conference "PyCon US" 2025
```

## Validation
The command automatically:
- Validates date formats (YYYY-MM-DD HH:mm:ss)
- Checks timezone validity
- Ensures year >= 1989
- Validates URL format (HTTPS required)
- Runs schema validation