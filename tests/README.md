# Python Deadlines Testing Guide

## Quick Start

```bash
# Install dependencies
npm install

# Install Playwright browsers (just Chromium for quick testing)
npm run playwright:install

# Run E2E tests with automatic server startup
npm run e2e
```

## Test Types

### Unit Tests (Jest)
Frontend JavaScript unit tests with mocked browser APIs.

```bash
npm test                 # Run all unit tests
npm run test:watch      # Watch mode for development
npm run test:coverage   # Generate coverage report
```

### E2E Tests (Playwright)
End-to-end tests that run against a real Jekyll server.

```bash
npm run e2e             # Run all E2E tests
npm run e2e:fast        # Chromium only (fastest)
npm run e2e:headed      # See the browser
npm run e2e:debug       # Step through tests
npm run e2e:ui          # Interactive UI mode
```

## Server Configurations

The project includes multiple Jekyll configurations optimized for different use cases:

### Test Configuration (`_config.test.yml`)
**Fastest option for E2E testing**
- English only
- No archive/legacy processing
- Minimal plugins
- ~10-15 second startup

```bash
npm run serve:test
# or
bundle exec jekyll serve --config _config.yml,_config.test.yml --incremental
```

### Minimal Configuration (`_config.minimal.yml`)
**Ultra-fast for quick checks**
- English only
- Only current conferences
- Bare minimum features
- ~5-10 second startup

```bash
npm run serve:minimal
# or
bundle exec jekyll serve --config _config.yml,_config.minimal.yml --incremental
```

### Dev Configuration (`_config.dev.yml`)
**Good balance for development**
- English and German
- No archive/legacy
- Most features enabled
- ~20-30 second startup

```bash
npm run serve:dev
# or
bundle exec jekyll serve --config _config.yml,_config.dev.yml --incremental
```

### Production Configuration
**Full features (slow)**
- All languages
- All data processing
- All features enabled
- ~60-90 second startup

```bash
bundle exec jekyll serve
```

## Running Tests Locally

### Option 1: Automatic Server (Recommended)
Let Playwright manage the server:

```bash
npm run e2e
```

### Option 2: Manual Server
Start server separately for faster test iterations:

```bash
# Terminal 1: Start fast test server
npm run serve:test

# Terminal 2: Run tests (with existing server)
npm run e2e
```

### Option 3: Headed Mode for Debugging
See what's happening in the browser:

```bash
npm run e2e:headed
```

### Option 4: UI Mode for Development
Interactive test development:

```bash
npm run e2e:ui
```

## CI/CD Configuration

GitHub Actions workflows are configured to:
- Use the test configuration for speed
- Run tests on multiple browsers
- Generate coverage reports
- Comment on PRs with results

## Test Coverage Areas

### Notification System
- Permission requests
- Deadline alerts (7, 3, 1 day)
- Toast notifications
- Settings persistence

### Countdown Timers
- Real-time updates
- Timezone handling
- Format variations
- Performance with many timers

### Conference Management
- Favoriting/unfavoriting
- Dashboard display
- Action bar interactions
- Search and filtering

## Performance Tips

1. **Use test configuration**: Always use `_config.test.yml` for E2E tests
2. **Run single browser**: Use `npm run e2e:fast` for quick checks
3. **Keep server running**: Start server once, run multiple test iterations
4. **Use incremental builds**: The `--incremental` flag speeds up rebuilds
5. **Skip initial build**: Use `--skip-initial-build` when content hasn't changed

## Troubleshooting

### Tests timeout waiting for server
- Check if port 4000 is already in use
- Try the minimal configuration for faster startup
- Increase timeout in `playwright.config.js`

### Notification tests fail
- Ensure browser has notification permissions
- Check that localStorage is not blocked
- Verify JavaScript is enabled

### Countdown timer tests flaky
- Mock time for consistent testing
- Use `waitForCountdowns` helper
- Allow for 1-2 second variance

### Server won't start
- Check Ruby/Bundler installation
- Run `bundle install`
- Clear Jekyll cache: `rm -rf _site .jekyll-cache`

## Writing New Tests

### Unit Tests
Place in `tests/frontend/unit/`:
```javascript
import { mockHelpers } from '../utils/mockHelpers';

describe('Feature', () => {
  test('should work', () => {
    // Test implementation
  });
});
```

### E2E Tests
Place in `tests/e2e/specs/`:
```javascript
import { test, expect } from '@playwright/test';
import { helpers } from '../utils/helpers';

test.describe('Feature', () => {
  test('should work', async ({ page }) => {
    await page.goto('/');
    // Test implementation
  });
});
```

## Coverage Goals

- **Unit Tests**: 80% line coverage
- **E2E Tests**: All critical user paths
- **Visual Tests**: Key page states
- **Performance**: Page load < 3s
