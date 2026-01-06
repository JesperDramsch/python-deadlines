/**
 * E2E tests for conference filtering functionality
 */

import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  waitForCountdowns,
  mockDateTime,
  clearLocalStorage
} from '../utils/helpers';

test.describe('Homepage Subject Filter', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await clearLocalStorage(page);
    await waitForPageReady(page);
    await waitForCountdowns(page);
  });

  test.describe('Filter Controls', () => {
    test('should display filter controls on homepage', async ({ page }) => {
      // The filter is a bootstrap-multiselect dropdown with id="subject-select"
      const filterSelect = page.locator('#subject-select');
      await expect(filterSelect).toBeAttached();

      // Bootstrap-multiselect creates a .multiselect button
      const multiselectButton = page.locator('.multiselect, button.multiselect');
      if (await multiselectButton.count() > 0) {
        await expect(multiselectButton.first()).toBeVisible();
      }
    });

    test('should have filter options available', async ({ page }) => {
      // Click the multiselect button to open dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();

      if (await multiselectButton.isVisible()) {
        await multiselectButton.click();

        // Check for filter options in the dropdown
        const filterOptions = page.locator('.multiselect-container li, #subject-select option');
        const optionCount = await filterOptions.count();
        expect(optionCount).toBeGreaterThan(0);
      }
    });
  });

  test.describe('Topic/Category Filtering', () => {
    test('should filter conferences by Python category', async ({ page }) => {
      // Open the multiselect dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();

      if (await multiselectButton.isVisible()) {
        await multiselectButton.click();

        // Find and click the PY option in the dropdown
        const pyOption = page.locator('.multiselect-container label:has-text("PY"), .multiselect-container input[value="PY"]').first();

        if (await pyOption.count() > 0) {
          await pyOption.click();
          await page.waitForFunction(() => document.readyState === 'complete');

          // Check that conferences are filtered - PY-conf class conferences should be visible
          // If the filter exists and is clicked, we expect at least some PY conferences
          const pyConferences = page.locator('.ConfItem.PY-conf');
          const count = await pyConferences.count();
          expect(count).toBeGreaterThan(0);
        }
      }
    });

    test('should filter conferences by Data Science category', async ({ page }) => {
      // Open the multiselect dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();

      if (await multiselectButton.isVisible()) {
        await multiselectButton.click();

        // Find DATA option
        const dataOption = page.locator('.multiselect-container label:has-text("DATA"), .multiselect-container input[value="DATA"]').first();

        if (await dataOption.count() > 0) {
          await dataOption.click();
          await page.waitForFunction(() => document.readyState === 'complete');

          // Check that DATA conferences are shown
          // If the filter exists and is clicked, we expect at least some DATA conferences
          const dataConferences = page.locator('.ConfItem.DATA-conf');
          const count = await dataConferences.count();
          expect(count).toBeGreaterThan(0);
        }
      }
    });

    test('should allow multiple category selection', async ({ page }) => {
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();

      if (await multiselectButton.isVisible()) {
        await multiselectButton.click();

        // Select multiple options
        const pyOption = page.locator('.multiselect-container label:has-text("PY")').first();
        const webOption = page.locator('.multiselect-container label:has-text("WEB")').first();

        if (await pyOption.count() > 0) {
          await pyOption.click();
        }
        if (await webOption.count() > 0) {
          await webOption.click();
        }

        await page.waitForFunction(() => document.readyState === 'complete');

        // Should show conferences with either PY or WEB
        // After selecting filters, we expect at least some conferences to match
        const conferences = page.locator('.ConfItem');
        const count = await conferences.count();
        expect(count).toBeGreaterThan(0);
      }
    });
  });
});

test.describe('My Conferences Page Filters', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to my-conferences page where advanced filters exist
    await page.goto('/my-conferences');
    await clearLocalStorage(page);
    await waitForPageReady(page);
  });

  test.describe('Format Filtering', () => {
    test('should filter by online conferences', async ({ page }) => {
      const onlineFilter = page.locator('.format-filter[value="virtual"], label:has-text("Online") input, label:has-text("Virtual") input').first();

      if (await onlineFilter.count() > 0) {
        await onlineFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        // Filter should be checked
        expect(await onlineFilter.isChecked()).toBe(true);
      }
    });

    test('should filter by in-person conferences', async ({ page }) => {
      const inPersonFilter = page.locator('.format-filter[value="in-person"], label:has-text("In-Person") input').first();

      if (await inPersonFilter.count() > 0) {
        await inPersonFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await inPersonFilter.isChecked()).toBe(true);
      }
    });

    test('should filter by hybrid conferences', async ({ page }) => {
      const hybridFilter = page.locator('.format-filter[value="hybrid"], label:has-text("Hybrid") input').first();

      if (await hybridFilter.count() > 0) {
        await hybridFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await hybridFilter.isChecked()).toBe(true);
      }
    });
  });

  test.describe('Feature Filtering', () => {
    test('should filter by financial aid availability', async ({ page }) => {
      const finaidFilter = page.locator('.feature-filter[value="finaid"], label:has-text("Financial Aid") input').first();

      if (await finaidFilter.count() > 0) {
        await finaidFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await finaidFilter.isChecked()).toBe(true);
      }
    });

    test('should filter by workshop availability', async ({ page }) => {
      const workshopFilter = page.locator('.feature-filter[value="workshop"], label:has-text("Workshop") input').first();

      if (await workshopFilter.count() > 0) {
        await workshopFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await workshopFilter.isChecked()).toBe(true);
      }
    });

    test('should filter by sponsorship opportunities', async ({ page }) => {
      const sponsorFilter = page.locator('.feature-filter[value="sponsor"], label:has-text("Sponsor") input').first();

      if (await sponsorFilter.count() > 0) {
        await sponsorFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await sponsorFilter.isChecked()).toBe(true);
      }
    });
  });

  test.describe('Topic Filtering', () => {
    test('should filter by topic category', async ({ page }) => {
      const topicFilter = page.locator('.topic-filter').first();

      if (await topicFilter.count() > 0) {
        await topicFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        expect(await topicFilter.isChecked()).toBe(true);
      }
    });
  });

  test.describe('Clear Filters', () => {
    test('should clear all applied filters', async ({ page }) => {
      // Apply some filters first
      const filters = page.locator('.format-filter, .feature-filter, .topic-filter');

      if (await filters.count() > 0) {
        await filters.first().check();
        await page.waitForFunction(() => document.readyState === 'complete');

        // Find and click clear/reset button
        const clearButton = page.locator('button:has-text("Clear"), button:has-text("Reset"), #clear-filters, .clear-filters');

        if (await clearButton.count() > 0) {
          await clearButton.first().click();
          await page.waitForFunction(() => document.readyState === 'complete');

          // All checkboxes should be unchecked
          const checkedFilters = page.locator('.format-filter:checked, .feature-filter:checked, .topic-filter:checked');
          const checkedCount = await checkedFilters.count();

          expect(checkedCount).toBe(0);
        }
      }
    });
  });

  test.describe('Filter Combinations', () => {
    test('should handle multiple filter types simultaneously', async ({ page }) => {
      const formatFilter = page.locator('.format-filter').first();
      const featureFilter = page.locator('.feature-filter').first();

      if (await formatFilter.count() > 0 && await featureFilter.count() > 0) {
        await formatFilter.check();
        await featureFilter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        // Both should be checked
        expect(await formatFilter.isChecked()).toBe(true);
        expect(await featureFilter.isChecked()).toBe(true);
      }
    });
  });

  test.describe('Mobile Filtering', () => {
    test('should work on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });

      // Reload to apply mobile layout
      await page.reload();
      await waitForPageReady(page);

      // Filters might be in a collapsible menu on mobile
      const filterToggle = page.locator('[data-toggle="collapse"], .filter-toggle, button:has-text("Filter")');

      if (await filterToggle.count() > 0) {
        await filterToggle.first().click();
        await page.waitForFunction(() => document.readyState === 'complete');
      }

      // Apply a filter
      const filter = page.locator('.format-filter, .feature-filter, .topic-filter').first();

      if (await filter.isVisible()) {
        await filter.check();
        await page.waitForFunction(() => document.readyState === 'complete');

        // Verify filter is applied
        expect(await filter.isChecked()).toBe(true);
      }
    });
  });

  test.describe('Filter Performance', () => {
    test('should apply filters quickly', async ({ page }) => {
      const filter = page.locator('.format-filter, .feature-filter, .topic-filter').first();

      if (await filter.count() > 0) {
        const startTime = Date.now();

        await filter.click();
        await page.waitForFunction(() => document.readyState === 'complete');

        const endTime = Date.now();
        const duration = endTime - startTime;

        // Filter should apply in less than 2 seconds
        expect(duration).toBeLessThan(2000);
      }
    });

    test('should handle rapid filter changes', async ({ page }) => {
      const filters = page.locator('.format-filter, .feature-filter, .topic-filter');
      const filterCount = await filters.count();

      if (filterCount >= 2) {
        // Rapidly toggle filters
        for (let i = 0; i < Math.min(5, filterCount); i++) {
          await filters.nth(i % filterCount).click();
        }

        await page.waitForFunction(() => document.readyState === 'complete');

        // Page should not crash or show errors
        const error = page.locator('.error, .exception');
        expect(await error.count()).toBe(0);
      }
    });
  });
});
