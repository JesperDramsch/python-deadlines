# 🧠 ADHD Development Support

## TodoWrite Integration
Use TodoWrite proactively for task tracking and ADHD support:
- Break complex tasks into smaller steps automatically
- Track one task as `in_progress` at a time for focus
- Get break reminders based on time tracking
- Celebrate completed tasks for dopamine hits

## Task Breakdown Strategy
When working on this codebase:
1. **Conference Data Tasks**: Break into validate → edit → sort → test → commit phases
2. **Import Tasks**: Source selection → fetch → parse → merge → validate phases  
3. **Bug Fixes**: Reproduce → isolate → fix → test → verify phases

## Focus Patterns for Common Tasks

### Adding a Conference (10-15 min)
1. ✏️ Edit `_data/conferences.yml` (3 min)
2. 🌍 Add timezone via timezonefinder (2 min)
3. 📍 Add coordinates if missing (2 min)
4. ✅ Run `pixi run sort` (1 min)
5. 🧪 Run `pixi run test-fast` (1 min)
6. 📝 Commit with `pixi run pre` (2 min)

### Import & Merge (20-30 min)
1. 📥 Run `pixi run merge` (5 min)
2. 👀 Review import results (5 min)
3. 🔍 Check for duplicates (3 min)
4. 🛠️ Fix any issues (5 min)
5. ✅ Validate with `pixi run sort` (2 min)
6. 📝 Commit changes (3 min)

### Quick Bug Fix (5-10 min)
1. 🐛 Reproduce the issue (2 min)
2. 🔍 Find problematic data (2 min)
3. ✏️ Apply fix (2 min)
4. 🧪 Test fix (1 min)
5. 📝 Commit (2 min)

## Energy Management

### High Energy Tasks (morning/peak focus)
- Complex data imports and merging
- Debugging validation errors
- Writing new import scripts
- Major refactoring

### Medium Energy Tasks (afternoon)
- Adding new conferences
- Updating existing data
- Running test suites
- Reviewing PRs

### Low Energy Tasks (end of day/tired)
- Fix typos in conference names
- Update conference URLs to HTTPS
- Archive old conferences
- Run automated validations
- Check upcoming deadlines

## Quick Wins Board
- ✨ Fix a typo in conference data (2 min)
- 🎯 Validate one conference URL (3 min)
- 🚀 Add missing timezone to a conference (5 min)
- 📍 Add coordinates to a conference (5 min)
- 🧪 Run fast tests: `pixi run test-fast` (1 min)
- 🔒 Change HTTP to HTTPS in a URL (1 min)
- 📅 Check this week's deadlines (2 min)
- 🏃 Run `pixi run sort` for validation (2 min)

## Break Reminders & Rewards
- **30 min**: Mini-break - stand and stretch (2 min) 
- **45 min**: Water break - hydrate and move (5 min)
- **60 min**: Proper break - walk or rest eyes (10 min)
- **After 3 tasks**: Celebration break! You earned it! 🎉