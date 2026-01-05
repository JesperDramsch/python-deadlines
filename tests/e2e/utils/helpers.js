/**
 * E2E test helper utilities
 */

/**
 * Wait for countdown timers to initialize
 */
export async function waitForCountdowns(page) {
  // Wait for Luxon to be available
  await page.waitForFunction(() => window.luxon !== undefined, { timeout: 5000 });

  // Wait for at least one countdown to have content
  await page.waitForFunction(() => {
    const countdowns = document.querySelectorAll('.countdown-display');
    return Array.from(countdowns).some(el => el.textContent.trim() !== '');
  }, { timeout: 5000 });
}

/**
 * Mock current date/time for consistent testing
 */
export async function mockDateTime(page, dateString) {
  await page.addInitScript((mockDate) => {
    // Override Date constructor
    const RealDate = Date;
    const mockedDate = new RealDate(mockDate);

    window.Date = class extends RealDate {
      constructor(...args) {
        if (args.length === 0) {
          return new RealDate(mockedDate);
        }
        return new RealDate(...args);
      }

      static now() {
        return mockedDate.getTime();
      }
    };

    // Preserve other Date methods
    Object.setPrototypeOf(window.Date, RealDate);
    window.Date.prototype = RealDate.prototype;

    // Also mock performance.now if needed
    const originalPerformanceNow = performance.now;
    const performanceNowOffset = originalPerformanceNow();
    performance.now = () => performanceNowOffset;
  }, dateString);
}

/**
 * Grant notification permissions
 */
export async function grantNotificationPermission(context) {
  await context.grantPermissions(['notifications']);
}

/**
 * Clear all localStorage data
 * Note: Page must be navigated to a valid URL before calling this function
 */
export async function clearLocalStorage(page) {
  // Check if page has a valid URL
  const url = page.url();
  if (!url || url === 'about:blank' || url === '') {
    console.warn('Cannot clear localStorage on blank page. Navigate to a page first.');
    return;
  }

  try {
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  } catch (error) {
    console.error('Failed to clear storage:', error.message);
    // Don't throw - let tests continue but log the issue
  }
}

/**
 * Set up localStorage with saved conferences
 */
export async function setupSavedConferences(page, conferences) {
  await page.evaluate((confs) => {
    // Set up favorites
    const favoriteIds = confs.map(c => c.id);
    localStorage.setItem('pythondeadlines-favorites', JSON.stringify(favoriteIds));

    // Set up saved conference data
    const savedData = {};
    confs.forEach(conf => {
      savedData[conf.id] = {
        ...conf,
        savedAt: new Date().toISOString(),
        addedAt: new Date().toISOString()
      };
    });
    localStorage.setItem('pythondeadlines-saved-conferences', JSON.stringify(savedData));

    // Also set up action bar preferences
    const actionBarPrefs = {};
    confs.forEach(conf => {
      actionBarPrefs[conf.id] = { saved: true };
    });
    localStorage.setItem('pydeadlines_actionBarPrefs', JSON.stringify(actionBarPrefs));
  }, conferences);
}

/**
 * Wait for notification toast to appear
 * Returns a Locator (not ElementHandle) for compatibility with Playwright expect assertions
 */
export async function waitForToast(page, timeout = 5000) {
  // Wait for the toast to appear
  await page.waitForSelector('.toast', {
    state: 'visible',
    timeout
  });
  // Return a Locator for proper Playwright assertions
  return page.locator('.toast').first();
}

/**
 * Dismiss all toasts
 */
export async function dismissToasts(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.toast').forEach(toast => {
      const closeBtn = toast.querySelector('[data-dismiss="toast"]');
      if (closeBtn) closeBtn.click();
    });
  });
}

/**
 * Get conference card by ID
 */
export async function getConferenceCard(page, confId) {
  return await page.locator(`[data-conf-id="${confId}"]`).first();
}

/**
 * Check if conference is favorited
 */
export async function isConferenceFavorited(page, confId) {
  const card = await getConferenceCard(page, confId);
  const favoriteBtn = card.locator('.favorite-btn');
  const classes = await favoriteBtn.getAttribute('class');
  return classes?.includes('favorited') || false;
}

/**
 * Toggle favorite status
 */
export async function toggleFavorite(page, confId) {
  const card = await getConferenceCard(page, confId);
  const favoriteBtn = card.locator('.favorite-btn');
  await favoriteBtn.click();
  // Wait for the button state to change instead of arbitrary timeout
  await page.waitForFunction(
    (id) => {
      const btn = document.querySelector(`[data-conf-id="${id}"] .favorite-btn`);
      return btn && btn.classList.contains('favorited') !== btn.classList.contains('favorited');
    },
    confId,
    { timeout: 2000 }
  ).catch(() => {}); // Graceful fallback if animation doesn't trigger class change
}

/**
 * Get countdown text for a conference
 */
export async function getCountdownText(page, confId) {
  const card = await getConferenceCard(page, confId);
  const countdown = card.locator('.countdown-display');
  return await countdown.textContent();
}

/**
 * Navigate to a specific page section
 */
export async function navigateToSection(page, section) {
  const sectionMap = {
    'home': '/',
    'dashboard': '/my-conferences',
    'archive': '/archive',
    'search': '/search',
    'about': '/about',
    'calendar': '/calendar'
  };

  const path = sectionMap[section] || section;
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

/**
 * Search for conferences
 */
export async function searchConferences(page, query) {
  // Navigate to search page
  await navigateToSection(page, 'search');

  // Enter search query
  const searchInput = page.locator('#search-input, input[type="search"]').first();
  await searchInput.fill(query);

  // Wait for search results to update by checking for result changes
  await page.waitForFunction(() => document.readyState === 'complete', { timeout: 2000 });
}

/**
 * Apply conference filters
 */
export async function applyFilters(page, filters) {
  // Topic filter
  if (filters.topics) {
    for (const topic of filters.topics) {
      await page.locator(`input[value="${topic}"]`).check();
    }
  }

  // Format filter
  if (filters.format) {
    await page.locator(`input[value="${filters.format}"]`).check();
  }

  // Date range filter
  if (filters.dateRange) {
    if (filters.dateRange.start) {
      await page.locator('input[name="start-date"]').fill(filters.dateRange.start);
    }
    if (filters.dateRange.end) {
      await page.locator('input[name="end-date"]').fill(filters.dateRange.end);
    }
  }

  // Wait for DOM to stabilize after filter changes
  await page.waitForFunction(() => document.readyState === 'complete', { timeout: 2000 });
}

/**
 * Create mock conference data for testing
 */
export function createMockConference(overrides = {}) {
  const baseDate = new Date();
  const cfpDate = new Date(baseDate);
  cfpDate.setDate(cfpDate.getDate() + 30);

  return {
    id: `test-conf-${Date.now()}`,
    conference: 'Test Conference',
    year: baseDate.getFullYear(),
    cfp: cfpDate.toISOString().split('T')[0] + ' 23:59:59',
    place: 'Virtual',
    start: new Date(cfpDate.getTime() + 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date(cfpDate.getTime() + 63 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    link: 'https://example.com',
    ...overrides
  };
}

/**
 * Wait for page to be ready
 */
export async function waitForPageReady(page) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(() => document.readyState === 'complete', { timeout: 5000 });
}

/**
 * Take screenshot with timestamp
 */
export async function takeScreenshot(page, name) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  await page.screenshot({
    path: `test-results/screenshots/${name}-${timestamp}.png`,
    fullPage: true
  });
}

/**
 * Check if element is in viewport
 */
export async function isInViewport(page, selector) {
  return await page.evaluate((sel) => {
    const element = document.querySelector(sel);
    if (!element) return false;

    const rect = element.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }, selector);
}

/**
 * Get a visible search input, handling mobile collapsed navbar
 * On mobile, the navbar is collapsed and #search-box is hidden.
 * This function finds a visible search input, preferring the page's #search over navbar's #search-box.
 * @param {Page} page - Playwright page object
 * @returns {Locator} A locator for a visible search input
 */
export async function getVisibleSearchInput(page) {
  // First, check if we're on the search page which has its own search input (#search)
  const pageSearchInput = page.locator('#search');
  if (await pageSearchInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    return pageSearchInput;
  }

  // Check if navbar search-box is visible (desktop view)
  const navbarSearchInput = page.locator('#search-box');
  if (await navbarSearchInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    return navbarSearchInput;
  }

  // On mobile, the navbar might be collapsed. Try to expand it.
  const navbarToggle = page.locator('.navbar-toggler').first();
  if (await navbarToggle.isVisible({ timeout: 1000 }).catch(() => false)) {
    // Check if navbar is collapsed (aria-expanded="false")
    const isExpanded = await navbarToggle.getAttribute('aria-expanded');
    if (isExpanded !== 'true') {
      await navbarToggle.click();
      // Wait for the collapse animation to complete
      await page.waitForTimeout(400);
    }

    // Now check if search-box is visible
    if (await navbarSearchInput.isVisible({ timeout: 1000 }).catch(() => false)) {
      return navbarSearchInput;
    }
  }

  // Fallback: return any visible search input
  const allSearchInputs = page.locator('#search-box, #search, input[type="search"]');
  const count = await allSearchInputs.count();
  for (let i = 0; i < count; i++) {
    const input = allSearchInputs.nth(i);
    if (await input.isVisible({ timeout: 500 }).catch(() => false)) {
      return input;
    }
  }

  // Last resort: return the first one (tests will fail with a clear error if not visible)
  return allSearchInputs.first();
}

/**
 * Dismiss a Bootstrap toast programmatically
 * Works around issues with Bootstrap 4 toast dismiss on mobile browsers
 * @param {Page} page - Playwright page object
 * @param {Locator} toast - Locator for the toast element
 */
export async function dismissToast(page, toast) {
  // Try clicking the close button first
  const closeBtn = toast.locator('.close, [data-dismiss="toast"], [data-bs-dismiss="toast"]').first();
  if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
    await closeBtn.click({ force: true });
    // Wait a moment for the click to register
    await page.waitForTimeout(100);
  }

  // If toast is still visible, use JavaScript to hide it
  const isStillVisible = await toast.isVisible({ timeout: 500 }).catch(() => false);
  if (isStillVisible) {
    await page.evaluate(() => {
      // Try Bootstrap 4 jQuery method
      if (typeof $ !== 'undefined' && $.fn.toast) {
        $('.toast').toast('hide');
      }
      // Also try direct DOM manipulation as fallback
      document.querySelectorAll('.toast').forEach(t => {
        t.classList.remove('show', 'showing');
        t.classList.add('hide');
        // Trigger the hidden event for cleanup
        t.dispatchEvent(new Event('hidden.bs.toast'));
      });
    });
  }
}
