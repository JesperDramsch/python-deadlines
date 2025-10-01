# CI/CD Optimization Strategy

## Overview

This document explains the GitHub Actions optimization strategy implemented to reduce CI costs while maintaining code quality.

## Problem Statement

- Full test suites (Frontend, E2E, Python) run on every PR, even for simple data changes
- E2E tests with multiple browsers (Chromium, Firefox, WebKit) are expensive
- Conference data updates (90% of PRs) don't affect code functionality
- Unnecessary test runs increase CI costs and slow down PR reviews

## Solution: Smart Test Runner

The `smart-test-runner.yml` workflow intelligently determines which tests to run based on file changes.

### How It Works

1. **Change Detection**: Uses `dorny/paths-filter` to categorize changed files
2. **Strategy Selection**: Determines optimal test strategy based on changes
3. **Conditional Execution**: Only runs necessary test suites
4. **Cost Transparency**: Comments on PRs with test strategy and savings

### Test Strategies

| Strategy | When Applied | Tests Run | Time Saved |
|----------|--------------|-----------|------------|
| `data-validation-only` | Only YAML data files changed | Data validation, duplicate check | ~15-20 min |
| `full-frontend` | JS or template files changed | Unit, E2E, visual regression | 0 min |
| `python-only` | Python utils changed | Python tests, data validation | ~10 min |
| `jekyll-build` | Jekyll config/plugins changed | Build test only | ~15 min |
| `minimal` | Documentation/config changes | Basic validation | ~20 min |

## File Categories

### Frontend Tests Required
- `static/js/**/*.js` (except minified)
- `tests/frontend/**`
- `package.json`, `package-lock.json`
- `jest.config.js`

### E2E Tests Required
- All frontend files
- `_layouts/**`, `_includes/**`, `_pages/**`
- `tests/e2e/**`
- `playwright.config.js`

### Python Tests Required
- `utils/**/*.py`
- `tests/python/**`
- `pixi.toml`, `pyproject.toml`

### Data-Only (No Code Tests)
- `_data/*.yml`
- `_i18n/**/*.yml`
- Translation files

## Implementation Details

### 1. Existing Workflows (Unchanged)

These workflows already have path filters:

- **frontend-tests.yml**: Only runs on JS changes
- **e2e-tests.yml**: Only runs on frontend/template changes
- **pr-sort.yml**: Only runs on conference data changes

### 2. New Smart Test Runner

The `smart-test-runner.yml` provides:

- Centralized change detection
- Intelligent test selection
- PR comments with test strategy
- Cost savings tracking

### 3. Usage

#### For Pull Requests

```yaml
# Automatically triggered on PR
# Bot comments with:
# - Detected changes
# - Selected test strategy
# - Estimated time/cost savings
```

#### Manual Override

```yaml
# Run specific workflows manually if needed
workflow_dispatch:
  inputs:
    force-all-tests:
      description: 'Run all tests regardless of changes'
      type: boolean
      default: false
```

## Cost Savings Analysis

### Typical PR Distribution

- 60% - Conference data updates
- 20% - Frontend code changes
- 10% - Python utility updates
- 10% - Documentation/config

### Estimated Monthly Savings

Assuming 100 PRs/month:

| PR Type | Count | Old Time | New Time | Saved |
|---------|-------|----------|----------|-------|
| Data only | 60 | 20 min | 2 min | 18 hrs |
| Frontend | 20 | 20 min | 20 min | 0 hrs |
| Python | 10 | 20 min | 5 min | 2.5 hrs |
| Docs | 10 | 20 min | 1 min | 3 hrs |
| **Total** | **100** | **33 hrs** | **9.5 hrs** | **23.5 hrs** |

**Monthly savings: ~70% reduction in CI time**

## Migration Guide

### Phase 1: Testing (Current)

1. Deploy `smart-test-runner.yml` alongside existing workflows
2. Monitor PR comments to verify correct detection
3. Gather metrics on time savings

### Phase 2: Integration

1. Update branch protection rules to require `test-status` check
2. Make existing workflows callable (reusable)
3. Gradually migrate triggers to smart runner

### Phase 3: Optimization

1. Fine-tune path filters based on usage patterns
2. Add caching for frequently unchanged dependencies
3. Implement partial E2E test selection

## Monitoring and Metrics

### Success Metrics

- CI time reduction: Target 60-70%
- Cost reduction: Target 50-60%
- PR velocity: No increase in failed merges
- Developer satisfaction: Faster PR feedback

### Monitoring Dashboard

Track via GitHub Actions insights:

- Workflow run duration trends
- Success/failure rates by strategy
- Cost per PR type
- Queue time reduction

## Best Practices

### For Contributors

1. **Data-only PRs**: Keep them pure (no code changes)
2. **Code PRs**: Include relevant test updates
3. **Mixed PRs**: Consider splitting into separate PRs

### For Maintainers

1. **Review strategy**: Check bot comment for test coverage
2. **Manual override**: Use workflow_dispatch when uncertain
3. **Monitor trends**: Watch for patterns in test failures

## Troubleshooting

### Issue: Tests not running when expected

**Solution**: Check path filters in workflow

```bash
# Debug paths-filter
act -j analyze-changes --env GITHUB_EVENT_NAME=pull_request
```

### Issue: Wrong strategy selected

**Solution**: Review file change detection logic

```yaml
# Add debug output
- name: Debug file changes
  run: |
    echo "Frontend: ${{ steps.filter.outputs.frontend }}"
    echo "Data only: ${{ steps.filter.outputs.data-only }}"
```

### Issue: Reusable workflow not found

**Solution**: Ensure workflows are in default branch

```yaml
# Reusable workflows must be in main/master
uses: ./.github/workflows/frontend-tests.yml@main
```

## Security Considerations

1. **Path filters**: Cannot be bypassed by PR authors
2. **Required checks**: Still enforced by branch protection
3. **Manual dispatch**: Requires write permissions
4. **Token usage**: Uses default GITHUB_TOKEN (read-only for PRs)

## Future Enhancements

### Short Term (1-2 months)

- [ ] Add test result caching
- [ ] Implement incremental E2E tests
- [ ] Add performance benchmarks

### Medium Term (3-6 months)

- [ ] Machine learning for test selection
- [ ] Predictive test failure analysis
- [ ] Auto-retry flaky tests

### Long Term (6+ months)

- [ ] Self-optimizing CI pipeline
- [ ] Cost forecasting per PR
- [ ] Automated test parallelization

## Conclusion

This optimization strategy significantly reduces CI costs while maintaining code quality. By intelligently selecting which tests to run based on file changes, we can:

- Save 60-70% on CI time
- Reduce costs by 50-60%
- Provide faster PR feedback
- Maintain full test coverage where needed

The strategy is transparent, with PR comments explaining what tests run and why, ensuring developers understand the process and can override when necessary.
