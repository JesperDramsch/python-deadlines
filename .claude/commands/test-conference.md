# Command: test-conference

## Purpose
Comprehensive validation and testing of a specific conference entry

## Trigger
Use when adding or modifying a conference to ensure data quality

## Workflow
Please validate the conference: $ARGUMENTS

1. **Find Conference**
   - Search in `_data/conferences.yml` by name
   - Handle partial matches with fuzzy search

2. **Schema Validation**
   - Check all required fields present
   - Validate field types and formats
   - Ensure date format YYYY-MM-DD HH:mm:ss

3. **Business Rule Validation**
   - Year >= 1989 (Python's birth)
   - CFP date before start date
   - Start date before end date
   - HTTPS URL required

4. **Data Quality Checks**
   - Valid IANA timezone
   - Coordinate precision <= 5 decimals
   - No special characters in handles
   - Valid country/city in place field

5. **External Validation**
   - Test conference URL accessibility
   - Verify CFP link if provided
   - Check social media handles exist

6. **Duplicate Detection**
   - Fuzzy match against other conferences
   - Flag potential duplicates (>80% similarity)

7. **Generate Report**
   - ✅ Valid fields
   - ⚠️ Warnings (missing optional fields)
   - ❌ Errors that must be fixed

## Success Criteria
- [ ] All required fields valid
- [ ] No business rule violations
- [ ] Conference URL accessible
- [ ] No duplicate entries
- [ ] Timezone validated
- [ ] Dates logically consistent

## Example Usage
`/test-conference PyCon US 2025`
`/test-conference EuroPython`

## Notes
- Provide specific fix suggestions for any issues found
- Include example of correct format for invalid fields
- Test both current and future years