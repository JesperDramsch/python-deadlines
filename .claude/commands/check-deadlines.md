# Command: check-deadlines

## Purpose
List all conferences with CFP deadlines approaching in the specified timeframe

## Trigger
Use when needing to see upcoming CFP deadlines or generate alerts

## Workflow
Please check for conferences with deadlines in next $ARGUMENTS days (default: 7):

1. Load `_data/conferences.yml`
2. Parse all CFP dates (use `cfp_ext` if available, else `cfp`)
3. Filter conferences with deadlines in the specified window
4. Sort by days remaining (closest first)
5. Display formatted list with:
   - Days remaining
   - Conference name and year
   - CFP deadline date/time
   - Conference URL
   - Note if using extended deadline

## Success Criteria
- [ ] All upcoming deadlines identified
- [ ] Sorted by urgency (closest first)
- [ ] Clear display of time remaining
- [ ] Extended deadlines highlighted
- [ ] No past deadlines shown

## Example Usage
`/check-deadlines 7` - Shows deadlines in next week
`/check-deadlines 30` - Shows deadlines in next month
`/check-deadlines 1` - Shows deadlines tomorrow

## Notes
- Account for timezones when calculating days remaining
- Highlight any deadlines within 48 hours in red
- Include workshop/tutorial deadlines if approaching