/**
 * Global setup for Playwright tests
 * Runs once before all tests
 */

async function globalSetup(config) {
  console.log('🚀 Starting E2E test suite...');
  
  // Set environment variables for tests
  process.env.TEST_ENV = 'e2e';
  process.env.BASE_URL = config.use?.baseURL || 'http://localhost:4000';
  
  // Store the start time for test duration tracking
  global.__TEST_START_TIME__ = Date.now();
  
  console.log(`📍 Base URL: ${process.env.BASE_URL}`);
  console.log(`🧪 Running ${config.projects.length} test projects`);
  
  return async () => {
    // This function will be called as global teardown
  };
}

module.exports = globalSetup;