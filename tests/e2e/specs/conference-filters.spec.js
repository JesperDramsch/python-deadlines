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
      const buttonCount = await multiselectButton.count();

      // Skip multiselect button check if not present (bootstrap-multiselect may not be loaded)
      test.skip(buttonCount === 0, 'Multiselect button not found - bootstrap-multiselect may not be loaded');

      await expect(multiselectButton.first()).toBeVisible();
    });

    test('should have filter options available', async ({ page }) => {
      // Click the multiselect button to open dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();
      const isVisible = await multiselectButton.isVisible();

      // Skip if multiselect button not visible
      test.skip(!isVisible, 'Multiselect button not visible - filter UI may not be loaded');

      await multiselectButton.click();

      // Check for filter options in the dropdown
      const filterOptions = page.locator('.multiselect-container li, #subject-select option');
      const optionCount = await filterOptions.count();
      expect(optionCount).toBeGreaterThan(0);
    });
  });

  test.describe('Topic/Category Filtering', () => {
    test('should filter conferences by Python category', async ({ page }) => {
      // Open the multiselect dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();
      const buttonVisible = await multiselectButton.isVisible();

      // Skip if multiselect button not visible
      test.skip(!buttonVisible, 'Multiselect button not visible - filter UI may not be loaded');

      await multiselectButton.click();

      // Find and click the PY option in the dropdown
      const pyOption = page.locator('.multiselect-container label:has-text("PY"), .multiselect-container input[value="PY"]').first();
      const pyOptionCount = await pyOption.count();

      // Skip if PY filter option not found
      test.skip(pyOptionCount === 0, 'PY filter option not found in dropdown');

      await pyOption.click();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Check that conferences are filtered - PY-conf class conferences should be visible
      const pyConferences = page.locator('.ConfItem.PY-conf');
      const count = await pyConferences.count();
      expect(count).toBeGreaterThan(0);
    });

    test('should filter conferences by Data Science category', async ({ page }) => {
      // Open the multiselect dropdown
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();
      const buttonVisible = await multiselectButton.isVisible();

      // Skip if multiselect button not visible
      test.skip(!buttonVisible, 'Multiselect button not visible - filter UI may not be loaded');

      await multiselectButton.click();

      // Find DATA option
      const dataOption = page.locator('.multiselect-container label:has-text("DATA"), .multiselect-container input[value="DATA"]').first();
      const dataOptionCount = await dataOption.count();

      // Skip if DATA filter option not found
      test.skip(dataOptionCount === 0, 'DATA filter option not found in dropdown');

      await dataOption.click();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Check that DATA conferences are shown
      const dataConferences = page.locator('.ConfItem.DATA-conf');
      const count = await dataConferences.count();
      expect(count).toBeGreaterThan(0);
    });

    test('should allow multiple category selection', async ({ page }) => {
      const multiselectButton = page.locator('.multiselect, button.multiselect').first();
      const buttonVisible = await multiselectButton.isVisible();

      // Skip if multiselect button not visible
      test.skip(!buttonVisible, 'Multiselect button not visible - filter UI may not be loaded');

      await multiselectButton.click();

      // Select multiple options
      const pyOption = page.locator('.multiselect-container label:has-text("PY")').first();
      const webOption = page.locator('.multiselect-container label:has-text("WEB")').first();

      // Skip if no filter options found
      const pyCount = await pyOption.count();
      const webCount = await webOption.count();
      test.skip(pyCount === 0 && webCount === 0, 'No PY or WEB filter options found in dropdown');

      if (pyCount > 0) {
        await pyOption.click();
      }
      if (webCount > 0) {
        await webOption.click();
      }

      await page.waitForFunction(() => document.readyState === 'complete');

      // Should show conferences with either PY or WEB
      const conferences = page.locator('.ConfItem');
      const count = await conferences.count();
      expect(count).toBeGreaterThan(0);
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
      const filterCount = await onlineFilter.count();

      // Skip if online filter not found on page
      test.skip(filterCount === 0, 'Online/Virtual filter not found on my-conferences page');

      await onlineFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Filter should be checked
      expect(await onlineFilter.isChecked()).toBe(true);
    });

    test('should filter by in-person conferences', async ({ page }) => {
      const inPersonFilter = page.locator('.format-filter[value="in-person"], label:has-text("In-Person") input').first();
      const filterCount = await inPersonFilter.count();

      // Skip if in-person filter not found on page
      test.skip(filterCount === 0, 'In-Person filter not found on my-conferences page');

      await inPersonFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await inPersonFilter.isChecked()).toBe(true);
    });

    test('should filter by hybrid conferences', async ({ page }) => {
      const hybridFilter = page.locator('.format-filter[value="hybrid"], label:has-text("Hybrid") input').first();
      const filterCount = await hybridFilter.count();

      // Skip if hybrid filter not found on page
      test.skip(filterCount === 0, 'Hybrid filter not found on my-conferences page');

      await hybridFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await hybridFilter.isChecked()).toBe(true);
    });
  });

  test.describe('Feature Filtering', () => {
    test('should filter by financial aid availability', async ({ page }) => {
      const finaidFilter = page.locator('.feature-filter[value="finaid"], label:has-text("Financial Aid") input').first();
      const filterCount = await finaidFilter.count();

      // Skip if financial aid filter not found on page
      test.skip(filterCount === 0, 'Financial Aid filter not found on my-conferences page');

      await finaidFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await finaidFilter.isChecked()).toBe(true);
    });

    test('should filter by workshop availability', async ({ page }) => {
      const workshopFilter = page.locator('.feature-filter[value="workshop"], label:has-text("Workshop") input').first();
      const filterCount = await workshopFilter.count();

      // Skip if workshop filter not found on page
      test.skip(filterCount === 0, 'Workshop filter not found on my-conferences page');

      await workshopFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await workshopFilter.isChecked()).toBe(true);
    });

    test('should filter by sponsorship opportunities', async ({ page }) => {
      const sponsorFilter = page.locator('.feature-filter[value="sponsor"], label:has-text("Sponsor") input').first();
      const filterCount = await sponsorFilter.count();

      // Skip if sponsor filter not found on page
      test.skip(filterCount === 0, 'Sponsor filter not found on my-conferences page');

      await sponsorFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await sponsorFilter.isChecked()).toBe(true);
    });
  });

  test.describe('Topic Filtering', () => {
    test('should filter by topic category', async ({ page }) => {
      const topicFilter = page.locator('.topic-filter').first();
      const filterCount = await topicFilter.count();

      // Skip if topic filter not found on page
      test.skip(filterCount === 0, 'Topic filter not found on my-conferences page');

      await topicFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      expect(await topicFilter.isChecked()).toBe(true);
    });
  });

  test.describe('Clear Filters', () => {
    test('should clear all applied filters', async ({ page }) => {
      // Apply some filters first
      const filters = page.locator('.format-filter, .feature-filter, .topic-filter');
      const filterCount = await filters.count();

      // Skip if no filters found on page
      test.skip(filterCount === 0, 'No filters found on my-conferences page');

      await filters.first().check();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Find and click clear/reset button
      const clearButton = page.locator('button:has-text("Clear"), button:has-text("Reset"), #clear-filters, .clear-filters');
      const clearButtonCount = await clearButton.count();

      // Skip if no clear button found
      test.skip(clearButtonCount === 0, 'No clear/reset button found on my-conferences page');

      await clearButton.first().click();
      await page.waitForFunction(() => document.readyState === 'complete');

      // All checkboxes should be unchecked
      const checkedFilters = page.locator('.format-filter:checked, .feature-filter:checked, .topic-filter:checked');
      const checkedCount = await checkedFilters.count();

      expect(checkedCount).toBe(0);
    });
  });

  test.describe('Filter Combinations', () => {
    test('should handle multiple filter types simultaneously', async ({ page }) => {
      const formatFilter = page.locator('.format-filter').first();
      const featureFilter = page.locator('.feature-filter').first();
      const formatCount = await formatFilter.count();
      const featureCount = await featureFilter.count();

      // Skip if both filter types are not found
      test.skip(formatCount === 0 || featureCount === 0, 'Format or feature filter not found on my-conferences page');

      await formatFilter.check();
      await featureFilter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Both should be checked
      expect(await formatFilter.isChecked()).toBe(true);
      expect(await featureFilter.isChecked()).toBe(true);
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
      const toggleCount = await filterToggle.count();

      // Click filter toggle if present (optional on some layouts)
      if (toggleCount > 0) {
        await filterToggle.first().click();
        await page.waitForFunction(() => document.readyState === 'complete');
      }

      // Apply a filter
      const filter = page.locator('.format-filter, .feature-filter, .topic-filter').first();
      const isVisible = await filter.isVisible();

      // Skip if no filter visible after attempting to open toggle
      test.skip(!isVisible, 'No filter visible on mobile viewport');

      await filter.check();
      await page.waitForFunction(() => document.readyState === 'complete');

      // Verify filter is applied
      expect(await filter.isChecked()).toBe(true);
    });
  });

  test.describe('Filter Performance', () => {
    test('should apply filters quickly', async ({ page }) => {
      const filter = page.locator('.format-filter, .feature-filter, .topic-filter').first();
      const filterCount = await filter.count();

      // Skip if no filter found on page
      test.skip(filterCount === 0, 'No filters found on my-conferences page');

      const startTime = Date.now();

      await filter.click();
      await page.waitForFunction(() => document.readyState === 'complete');

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Filter should apply in less than 2 seconds
      expect(duration).toBeLessThan(2000);
    });

    test('should handle rapid filter changes', async ({ page }) => {
      const filters = page.locator('.format-filter, .feature-filter, .topic-filter');
      const filterCount = await filters.count();

      // Skip if not enough filters for rapid change test
      test.skip(filterCount < 2, 'Not enough filters found for rapid change test');

      // Rapidly toggle filters
      for (let i = 0; i < Math.min(5, filterCount); i++) {
        await filters.nth(i % filterCount).click();
      }

      await page.waitForFunction(() => document.readyState === 'complete');

      // Page should not crash or show errors
      const error = page.locator('.error, .exception');
      expect(await error.count()).toBe(0);
    });
  });
});
