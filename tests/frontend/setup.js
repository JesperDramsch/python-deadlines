/**
 * Jest setup file - runs after test environment is set up
 */

// Add custom matchers from jest-dom
require('@testing-library/jest-dom');

// Set up global jQuery
global.$ = global.jQuery = require('../../static/js/jquery.min.js');

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  error: jest.fn(console.error),
  warn: jest.fn(console.warn),
  log: jest.fn(console.log)
};

// Add custom matchers
expect.extend({
  toBeWithinRange(received, floor, ceiling) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () => `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false,
      };
    }
  },

  toHaveBeenCalledWithDate(received, expectedDate, tolerance = 1000) {
    const calls = received.mock.calls;
    const pass = calls.some(call => {
      const arg = call[0];
      if (arg instanceof Date || arg.cfp || arg.cfpExt) {
        const date = new Date(arg.cfp || arg.cfpExt || arg);
        return Math.abs(date - expectedDate) <= tolerance;
      }
      return false;
    });

    if (pass) {
      return {
        message: () => `expected not to be called with date near ${expectedDate}`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected to be called with date near ${expectedDate}`,
        pass: false,
      };
    }
  }
});

// Clean up after each test
afterEach(() => {
  // Clear all timers
  jest.clearAllTimers();

  // Clear localStorage
  localStorage.clear();
  sessionStorage.clear();

  // Clear all mocks
  jest.clearAllMocks();

  // Reset document body
  document.body.innerHTML = '';

  // Remove any event listeners
  const oldElem = document.body;
  const newElem = oldElem.cloneNode(true);
  oldElem.parentNode.replaceChild(newElem, oldElem);
});
