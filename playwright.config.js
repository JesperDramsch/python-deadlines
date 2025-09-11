/**
 * Playwright E2E test configuration
 */

import { defineConfig, devices } from '@playwright/test';

const PORT = process.env.PORT || 4000;
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

export default defineConfig({
  // Test directory
  testDir: './tests/e2e',
  
  // Test file patterns
  testMatch: /.*\.(spec|test)\.(js|ts)$/,
  
  // Maximum time one test can run
  timeout: 30 * 1000,
  
  // Maximum time to wait for page to load
  expect: {
    timeout: 10 * 1000,
  },
  
  // Run tests in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Limit parallel workers on CI
  workers: process.env.CI ? 2 : undefined,
  
  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['list'],
  ],
  
  // Global test settings
  use: {
    // Base URL for all tests
    baseURL: BASE_URL,
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video on failure
    video: 'retain-on-failure',
    
    // Action timeout
    actionTimeout: 10 * 1000,
    
    // Navigation timeout
    navigationTimeout: 30 * 1000,
    
    // Emulate timezone for consistent testing
    timezoneId: 'UTC',
    
    // Locale for consistent testing
    locale: 'en-US',
    
    // Permissions to grant
    permissions: ['notifications'],
    
    // Viewport size
    viewport: { width: 1280, height: 720 },
  },
  
  // Configure projects for different browsers
  projects: [
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome'],
        // Custom launch options for Chromium
        launchOptions: {
          args: ['--disable-dev-shm-usage'],
        },
      },
    },
    
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    
    // Mobile viewports
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
    },
    
    // Test with different timezones
    {
      name: 'timezone-ny',
      use: {
        ...devices['Desktop Chrome'],
        timezoneId: 'America/New_York',
      },
    },
    
    {
      name: 'timezone-berlin',
      use: {
        ...devices['Desktop Chrome'],
        timezoneId: 'Europe/Berlin',
      },
    },
  ],
  
  // Run local dev server before starting tests (optional)
  webServer: process.env.CI ? undefined : {
    // Use optimized test server for fastest startup
    command: 'bundle exec jekyll serve --config _config.yml,_config.test.yml --incremental',
    port: PORT,
    timeout: 30 * 1000, // Very fast with test config
    reuseExistingServer: true,
    stdout: 'pipe',
    stderr: 'pipe',
  },
  
  // Output folder for test artifacts
  outputDir: 'test-results/',
  
  // Global setup and teardown
  globalSetup: './tests/e2e/global-setup.js',
  globalTeardown: './tests/e2e/global-teardown.js',
});