# 🔄 Git Workflow & Deployment

## Branch Strategy

### Main Branches
- `main` - Development branch (protected)
- `gh-pages` - Production deployment (auto-generated)

### Feature Branches
- `feature/add-conference-name` - New conferences
- `fix/issue-description` - Bug fixes
- `chore/update-deps` - Maintenance tasks

### Never
- Push directly to `gh-pages` (auto-deployed)
- Force push to `main` without team agreement
- Commit without pre-commit checks

## Commit Message Standards

Follow conventional commits for clear history:

### Types
- `feat:` New conference or feature
- `fix:` Bug fix in data or code
- `chore:` Maintenance (imports, archives)
- `docs:` Documentation updates
- `test:` Test additions or fixes
- `refactor:` Code improvements

### Examples
```bash
git commit -m "feat: add PyCon US 2025"
git commit -m "fix: correct timezone for EuroPython"
git commit -m "chore: import conferences 2025-01-15"
git commit -m "chore: archive past conferences"
git commit -m "docs: update contribution guidelines"
```

### Include details when needed
```bash
git commit -m "fix: update DjangoCon Europe URL

- Changed to new conference website
- Updated social media handles
- Added extended CFP deadline"
```

## Pre-Push Checklist

**MANDATORY before pushing to main:**

```bash
# 1. Update from remote
git pull origin main

# 2. Run full validation
pixi run sort
pixi run test
pixi run pre

# 3. Test local build
pixi run serve
# Visit http://localhost:4000

# 4. Commit with checks
git add -A
git commit -m "type: description"

# 5. Push to remote
git push origin main
```

## GitHub Pages Deployment

### Automatic Deployment
- Triggers on push to `main` branch
- Builds Jekyll site via GitHub Actions
- Deploys to `gh-pages` branch
- Live at https://pythondeadlin.es in ~5 minutes

### Monitor Deployment
```bash
# Check build status
# Visit: https://github.com/[org]/python-deadlines/actions

# View deployment
# Visit: https://pythondeadlin.es

# Check for build errors
gh workflow view "Deploy to GitHub Pages"
```

### Rollback if Needed
```bash
# Find last good commit
git log --oneline -20

# Revert to good state
git revert <bad-commit-hash>
git push origin main

# Or emergency reset (coordinate with team!)
git reset --hard <good-commit-hash>
git push --force origin main
```

## Pull Request Process

For significant changes:

### 1. Create feature branch
```bash
git checkout -b feature/description
```

### 2. Make changes and test
```bash
# Edit files
pixi run sort
pixi run test
pixi run pre
```

### 3. Push and create PR
```bash
git push -u origin feature/description
gh pr create --title "Description" --body "Details"
```

### 4. PR must have
- Clear description of changes
- Test results (all passing)
- Link to related issue (if any)
- Screenshot for UI changes