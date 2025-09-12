/**
 * Global teardown for Playwright tests
 * Runs once after all tests
 */

async function globalTeardown() {
  const duration = Date.now() - global.__TEST_START_TIME__;
  const minutes = Math.floor(duration / 60000);
  const seconds = ((duration % 60000) / 1000).toFixed(0);

  console.log(`\n✅ E2E tests completed in ${minutes}m ${seconds}s`);

  // Clean up any test data if needed
  // This is where you could clean up test conferences, etc.
}

module.exports = globalTeardown;
