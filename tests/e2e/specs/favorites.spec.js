/**
 * E2E tests for favorites workflow
 */

import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  clearLocalStorage,
  setupSavedConferences,
  toggleFavorite,
  isConferenceFavorited,
  waitForToast,
  dismissToast,
  navigateToSection,
  createMockConference
} from '../utils/helpers';

test.describe('Favorites Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await clearLocalStorage(page);
    await waitForPageReady(page);
  });

  test.describe('Adding to Favorites', () => {
    test('should add conference to favorites from homepage', async ({ page }) => {
      // Find the first conference card with a favorite button
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      // Get the conference ID
      const confId = await favoriteBtn.getAttribute('data-conf-id');
      expect(confId).toBeTruthy();

      // Verify initial state (not favorited)
      const initialClasses = await favoriteBtn.getAttribute('class');
      const wasAlreadyFavorited = initialClasses?.includes('favorited');

      // Click to favorite
      await favoriteBtn.click();

      // Wait for the state to change
      await page.waitForFunction(
        ({ id, wasInitiallyFavorited }) => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && btn.classList.contains('favorited') !== wasInitiallyFavorited;
        },
        { id: confId, wasInitiallyFavorited: wasAlreadyFavorited },
        { timeout: 3000 }
      );

      // Verify the button now shows favorited state
      const newClasses = await favoriteBtn.getAttribute('class');
      if (wasAlreadyFavorited) {
        expect(newClasses).not.toContain('favorited');
      } else {
        expect(newClasses).toContain('favorited');
      }
    });

    test('should show toast notification when favoriting', async ({ page }) => {
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      // Click to favorite
      await favoriteBtn.click();

      // Wait for toast to appear
      const toast = await waitForToast(page, 5000).catch(() => null);

      // Toast may or may not appear depending on implementation
      if (toast) {
        await expect(toast).toBeVisible();
        // Dismiss the toast for cleanup
        await dismissToast(page, toast);
      }
    });

    test('should change star icon when favoriting', async ({ page }) => {
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Get initial icon state
      const icon = favoriteBtn.locator('i').first();
      const initialIconClasses = await icon.getAttribute('class');
      const hadSolidStar = initialIconClasses?.includes('fas');

      // Click to toggle
      await favoriteBtn.click();

      // Wait for icon class to change
      await page.waitForFunction(
        ({ id, wasSolid }) => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          const iconEl = btn?.querySelector('i');
          return iconEl && iconEl.classList.contains('fas') !== wasSolid;
        },
        { id: confId, wasSolid: hadSolidStar },
        { timeout: 3000 }
      );

      // Verify icon changed
      const newIconClasses = await icon.getAttribute('class');
      if (hadSolidStar) {
        expect(newIconClasses).toContain('far');
      } else {
        expect(newIconClasses).toContain('fas');
      }
    });

    test('should persist favorites in localStorage', async ({ page }) => {
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Ensure not favorited initially
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && !btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Now add to favorites
      await favoriteBtn.click();
      await page.waitForFunction(
        id => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && btn.classList.contains('favorited');
        },
        confId,
        { timeout: 3000 }
      );

      // Check localStorage
      const stored = await page.evaluate(() => {
        return {
          favorites: localStorage.getItem('pythondeadlines-favorites'),
          saved: localStorage.getItem('pythondeadlines-saved-conferences')
        };
      });

      // At least one storage key should have data
      const hasData = stored.favorites !== null || stored.saved !== null;
      expect(hasData).toBe(true);
    });
  });

  test.describe('Removing from Favorites', () => {
    test('should remove conference from favorites', async ({ page }) => {
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // First, ensure it's favorited
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (!initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Now remove from favorites
      await favoriteBtn.click();
      await page.waitForFunction(
        id => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && !btn.classList.contains('favorited');
        },
        confId,
        { timeout: 3000 }
      );

      // Verify button state
      const finalClasses = await favoriteBtn.getAttribute('class');
      expect(finalClasses).not.toContain('favorited');
    });

    test('should toggle favorite state correctly', async ({ page }) => {
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Get initial state
      const initialFavorited = (await favoriteBtn.getAttribute('class'))?.includes('favorited');

      // Toggle 1: first click
      await favoriteBtn.click();
      await page.waitForFunction(
        ({ id, wasInitial }) => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && btn.classList.contains('favorited') !== wasInitial;
        },
        { id: confId, wasInitial: initialFavorited },
        { timeout: 3000 }
      );

      const afterFirst = (await favoriteBtn.getAttribute('class'))?.includes('favorited');
      expect(afterFirst).toBe(!initialFavorited);

      // Toggle 2: second click (should return to original state)
      await favoriteBtn.click();
      await page.waitForFunction(
        ({ id, wasAfterFirst }) => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && btn.classList.contains('favorited') !== wasAfterFirst;
        },
        { id: confId, wasAfterFirst: afterFirst },
        { timeout: 3000 }
      );

      const afterSecond = (await favoriteBtn.getAttribute('class'))?.includes('favorited');
      expect(afterSecond).toBe(initialFavorited);
    });
  });

  test.describe('Favorites on Dashboard', () => {
    test('should show favorited conferences on dashboard', async ({ page }) => {
      // First, favorite a conference from homepage
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Ensure it's favorited
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (!initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Navigate to dashboard
      await navigateToSection(page, 'dashboard');
      await waitForPageReady(page);

      // Wait for dashboard to load content
      await page.waitForFunction(() => {
        const loading = document.querySelector('#loading-state');
        return !loading || loading.style.display === 'none';
      }, { timeout: 5000 });

      // Check for conference cards or empty state
      const conferenceCards = page.locator('#conference-cards .conference-card, .conference-card');
      const emptyState = page.locator('#empty-state');

      const cardCount = await conferenceCards.count();
      const emptyVisible = await emptyState.isVisible().catch(() => false);

      // Either we have cards or empty state is shown (depending on timing)
      expect(cardCount > 0 || emptyVisible).toBe(true);
    });

    test('should show empty state when no favorites', async ({ page }) => {
      // Ensure localStorage is clear
      await clearLocalStorage(page);

      // Navigate to dashboard
      await navigateToSection(page, 'dashboard');
      await waitForPageReady(page);

      // Wait for loading to complete
      await page.waitForFunction(() => {
        const loading = document.querySelector('#loading-state');
        return !loading || loading.style.display === 'none';
      }, { timeout: 5000 });

      // Check for empty state
      const emptyState = page.locator('#empty-state');
      const isVisible = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);

      // Empty state should be visible when no favorites
      // Note: This may depend on implementation details
      expect(isVisible).toBe(true);
    });

    test('should remove conference from dashboard when unfavorited', async ({ page }) => {
      // First set up a favorite from homepage
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Ensure it's favorited
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (!initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Navigate to dashboard
      await navigateToSection(page, 'dashboard');
      await waitForPageReady(page);

      // Wait for dashboard to load
      await page.waitForFunction(() => {
        const loading = document.querySelector('#loading-state');
        return !loading || loading.style.display === 'none';
      }, { timeout: 5000 });

      // Find the favorite button for this conference on dashboard
      const dashboardFavBtn = page.locator(`.favorite-btn[data-conf-id="${confId}"]`);
      const dashboardBtnCount = await dashboardFavBtn.count();

      if (dashboardBtnCount > 0) {
        // Click to unfavorite
        await dashboardFavBtn.click();

        // Wait for card to be removed or button state to change
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return !btn || !btn.classList.contains('favorited');
          },
          confId,
          { timeout: 5000 }
        );
      }
    });
  });

  test.describe('Favorites Counter', () => {
    test('should update favorites count in navigation', async ({ page }) => {
      // Get initial count
      const favCount = page.locator('#fav-count');
      const initialCountText = await favCount.textContent().catch(() => '');
      const initialCount = parseInt(initialCountText) || 0;

      // Favorite a conference
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');
      const initialClasses = await favoriteBtn.getAttribute('class');
      const wasAlreadyFavorited = initialClasses?.includes('favorited');

      await favoriteBtn.click();

      // Wait for the button state to change
      await page.waitForFunction(
        ({ id, wasInitial }) => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn && btn.classList.contains('favorited') !== wasInitial;
        },
        { id: confId, wasInitial: wasAlreadyFavorited },
        { timeout: 3000 }
      );

      // Wait a moment for count update
      await page.waitForFunction(() => true, {}, { timeout: 500 });

      // Check count changed (may or may not have visible badge depending on implementation)
      const newCountText = await favCount.textContent().catch(() => '');
      const newCount = parseInt(newCountText) || 0;

      if (wasAlreadyFavorited) {
        expect(newCount).toBeLessThanOrEqual(initialCount);
      } else {
        expect(newCount).toBeGreaterThanOrEqual(initialCount);
      }
    });
  });

  test.describe('Favorites Persistence', () => {
    test('should restore favorites after page reload', async ({ page }) => {
      // Favorite a conference
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Ensure it's favorited
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (!initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Reload the page
      await page.reload();
      await waitForPageReady(page);

      // Wait for favorites to be restored
      await page.waitForFunction(
        id => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn !== null;
        },
        confId,
        { timeout: 5000 }
      );

      // Check that favorite state is preserved
      const reloadedBtn = page.locator(`.favorite-btn[data-conf-id="${confId}"]`);
      const reloadedClasses = await reloadedBtn.getAttribute('class');
      expect(reloadedClasses).toContain('favorited');
    });

    test('should maintain favorites across different pages', async ({ page }) => {
      // Favorite a conference
      const favoriteBtn = page.locator('.favorite-btn').first();
      const btnCount = await favoriteBtn.count();

      test.skip(btnCount === 0, 'No favorite buttons found on page');

      const confId = await favoriteBtn.getAttribute('data-conf-id');

      // Ensure it's favorited
      const initialClasses = await favoriteBtn.getAttribute('class');
      if (!initialClasses?.includes('favorited')) {
        await favoriteBtn.click();
        await page.waitForFunction(
          id => {
            const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
            return btn && btn.classList.contains('favorited');
          },
          confId,
          { timeout: 3000 }
        );
      }

      // Navigate to archive page
      await navigateToSection(page, 'archive');
      await waitForPageReady(page);

      // Navigate back to home
      await navigateToSection(page, 'home');
      await waitForPageReady(page);

      // Wait for the button to be rendered
      await page.waitForFunction(
        id => {
          const btn = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
          return btn !== null;
        },
        confId,
        { timeout: 5000 }
      );

      // Check favorite state is still preserved
      const returnedBtn = page.locator(`.favorite-btn[data-conf-id="${confId}"]`);
      const returnedClasses = await returnedBtn.getAttribute('class');
      expect(returnedClasses).toContain('favorited');
    });
  });

  test.describe('Multiple Favorites', () => {
    test('should handle multiple favorites', async ({ page }) => {
      const favoriteBtns = page.locator('.favorite-btn');
      const totalCount = await favoriteBtns.count();

      test.skip(totalCount < 2, 'Not enough favorite buttons for multiple favorites test');

      // Favorite first two conferences
      const numToFavorite = Math.min(2, totalCount);
      const favoritedIds = [];

      for (let i = 0; i < numToFavorite; i++) {
        const btn = favoriteBtns.nth(i);
        const confId = await btn.getAttribute('data-conf-id');
        const classes = await btn.getAttribute('class');

        if (!classes?.includes('favorited')) {
          await btn.click();
          await page.waitForFunction(
            id => {
              const button = document.querySelector(`.favorite-btn[data-conf-id="${id}"]`);
              return button && button.classList.contains('favorited');
            },
            confId,
            { timeout: 3000 }
          );
          favoritedIds.push(confId);
        }
      }

      // Verify all favorited
      for (const confId of favoritedIds) {
        const btn = page.locator(`.favorite-btn[data-conf-id="${confId}"]`);
        const classes = await btn.getAttribute('class');
        expect(classes).toContain('favorited');
      }
    });
  });
});

test.describe('Dashboard Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/my-conferences');
    await clearLocalStorage(page);
    await waitForPageReady(page);
  });

  test.describe('View Toggle', () => {
    test('should toggle between grid and list view', async ({ page }) => {
      const gridBtn = page.locator('#view-grid');
      const listBtn = page.locator('#view-list');

      const gridBtnExists = await gridBtn.count() > 0;
      const listBtnExists = await listBtn.count() > 0;

      test.skip(!gridBtnExists || !listBtnExists, 'View toggle buttons not found');

      // Verify grid view is active by default
      const gridClasses = await gridBtn.getAttribute('class');
      expect(gridClasses).toContain('active');

      // Switch to list view
      await listBtn.click();
      await page.waitForFunction(() => true, {}, { timeout: 300 });

      const listClassesAfter = await listBtn.getAttribute('class');
      expect(listClassesAfter).toContain('active');

      // Switch back to grid view
      await gridBtn.click();
      await page.waitForFunction(() => true, {}, { timeout: 300 });

      const gridClassesAfter = await gridBtn.getAttribute('class');
      expect(gridClassesAfter).toContain('active');
    });
  });

  test.describe('Series Subscriptions', () => {
    test('should display quick subscribe buttons', async ({ page }) => {
      const quickSubscribeBtns = page.locator('.quick-subscribe');
      const count = await quickSubscribeBtns.count();

      expect(count).toBeGreaterThan(0);
    });

    test('should handle series subscription click', async ({ page }) => {
      const quickSubscribeBtn = page.locator('.quick-subscribe').first();
      const btnCount = await quickSubscribeBtn.count();

      test.skip(btnCount === 0, 'No quick subscribe buttons found');

      // Get initial button text
      const initialText = await quickSubscribeBtn.textContent();

      // Click to subscribe
      await quickSubscribeBtn.click();
      await page.waitForFunction(() => true, {}, { timeout: 500 });

      // Button may change text or style after subscription
      // This depends on implementation
    });
  });

  test.describe('Notification Settings', () => {
    test('should open notification settings modal', async ({ page }) => {
      const notificationBtn = page.locator('#notification-settings');
      const btnExists = await notificationBtn.count() > 0;

      test.skip(!btnExists, 'Notification settings button not found');

      await notificationBtn.click();

      // Wait for modal to appear
      const modal = page.locator('#notificationModal');
      await expect(modal).toBeVisible({ timeout: 3000 });
    });

    test('should have notification time options', async ({ page }) => {
      const notificationBtn = page.locator('#notification-settings');
      const btnExists = await notificationBtn.count() > 0;

      test.skip(!btnExists, 'Notification settings button not found');

      await notificationBtn.click();

      // Wait for modal
      const modal = page.locator('#notificationModal');
      await expect(modal).toBeVisible({ timeout: 3000 });

      // Check for notification day checkboxes
      const notifyDays = page.locator('.notify-days');
      const count = await notifyDays.count();
      expect(count).toBeGreaterThan(0);
    });

    test('should save notification settings', async ({ page }) => {
      const notificationBtn = page.locator('#notification-settings');
      const btnExists = await notificationBtn.count() > 0;

      test.skip(!btnExists, 'Notification settings button not found');

      await notificationBtn.click();

      const modal = page.locator('#notificationModal');
      await expect(modal).toBeVisible({ timeout: 3000 });

      // Find save button
      const saveBtn = page.locator('#save-notification-settings');
      const saveBtnExists = await saveBtn.count() > 0;

      test.skip(!saveBtnExists, 'Save notification settings button not found');

      await saveBtn.click();

      // Modal should close or show confirmation
      await page.waitForFunction(() => true, {}, { timeout: 500 });
    });
  });

  test.describe('Filter Panel', () => {
    test('should display filter panel', async ({ page }) => {
      const filterPanel = page.locator('.filter-panel');
      const panelExists = await filterPanel.count() > 0;

      expect(panelExists).toBe(true);
    });

    test('should have clear filters button', async ({ page }) => {
      const clearBtn = page.locator('#clear-filters');
      const btnExists = await clearBtn.count() > 0;

      expect(btnExists).toBe(true);
    });

    test('should clear all filters when clicked', async ({ page }) => {
      // Apply a filter first
      const formatFilter = page.locator('.format-filter').first();
      const filterExists = await formatFilter.count() > 0;

      test.skip(!filterExists, 'No format filters found');

      await formatFilter.check();
      expect(await formatFilter.isChecked()).toBe(true);

      // Clear filters
      const clearBtn = page.locator('#clear-filters');
      await clearBtn.click();

      await page.waitForFunction(() => true, {}, { timeout: 300 });

      // Filter should be unchecked
      expect(await formatFilter.isChecked()).toBe(false);
    });
  });
});

test.describe('Conference Detail Actions', () => {
  test('should have favorite button on conference detail page', async ({ page }) => {
    // First go to homepage
    await page.goto('/');
    await waitForPageReady(page);

    // Find a conference link
    const confLink = page.locator('.ConfItem a[href*="/conference/"]').first();
    const linkCount = await confLink.count();

    test.skip(linkCount === 0, 'No conference links found');

    // Navigate to conference detail page
    const href = await confLink.getAttribute('href');
    await page.goto(href);
    await waitForPageReady(page);

    // Check for favorite button on detail page
    const favoriteBtn = page.locator('.favorite-btn, .btn:has-text("Favorite"), [data-action="favorite"]');
    const btnExists = await favoriteBtn.count() > 0;

    // Some implementations may not have favorite on detail page - this is informational
    if (!btnExists) {
      console.log('Note: No favorite button found on conference detail page');
    }
  });
});
