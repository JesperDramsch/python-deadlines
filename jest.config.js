module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/tests/frontend', '<rootDir>/static/js'],

  // Setup files
  setupFiles: [
    '<rootDir>/tests/frontend/utils/globalSetup.js',
    'jest-localstorage-mock'
  ],
  setupFilesAfterEnv: [
    '<rootDir>/tests/frontend/setup.js'
  ],

  // Module mappings
  moduleNameMapper: {
    // Mock static assets
    '\\.(css|less|scss|sass)$': '<rootDir>/tests/frontend/__mocks__/styleMock.js',
    '\\.(jpg|jpeg|png|gif|svg)$': '<rootDir>/tests/frontend/__mocks__/fileMock.js',

    // Map jQuery and other libraries
    '^jquery$': '<rootDir>/static/js/jquery.min.js',
    '^luxon$': '<rootDir>/static/js/luxon.js',
    '^store$': '<rootDir>/static/js/store.min.js'
  },

  // Coverage configuration
  collectCoverageFrom: [
    'static/js/**/*.js',
    '!static/js/**/*.min.js',
    '!static/js/jquery*.js',
    '!static/js/bootstrap*.js',
    '!static/js/popper*.js',
    '!static/js/lunr*.js',
    '!static/js/store*.js',
    '!static/js/luxon.js',
    '!static/js/js-year-calendar*.js',
    '!static/js/ouical*.js',
    '!static/js/bootstrap-multiselect*.js',
    '!static/js/jquery.countdown*.js',
    '!static/js/snek.js',
    '!static/js/about.js'
  ],

  coverageDirectory: '<rootDir>/coverage',

  coverageThreshold: {
    './static/js/notifications.js': {
      branches: 71,
      functions: 85,
      lines: 85,
      statements: 82
    },
    './static/js/countdown-simple.js': {
      branches: 75,
      functions: 80,
      lines: 80,
      statements: 80
    },
    './static/js/search.js': {
      branches: 70,
      functions: 75,
      lines: 75,
      statements: 75
    },
    './static/js/favorites.js': {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80
    },
    './static/js/dashboard.js': {
      branches: 60,
      functions: 70,
      lines: 70,
      statements: 70
    },
    './static/js/conference-manager.js': {
      branches: 65,
      functions: 75,
      lines: 75,
      statements: 75
    },
    './static/js/conference-filter.js': {
      branches: 65,
      functions: 70,
      lines: 70,
      statements: 70
    }
  },

  // Test patterns
  testMatch: [
    '**/tests/frontend/**/*.test.js',
    '**/tests/frontend/**/*.spec.js'
  ],


  // Global variables available in tests
  globals: {
    IS_TESTING: true,
    JEKYLL_ENV: 'test'
  },

  // Ignore patterns
  testPathIgnorePatterns: [
    '/node_modules/',
    '/_site/',
    '/vendor/'
  ],

  // Reporter configuration
  reporters: [
    'default'
    // Uncomment if jest-html-reporter is installed:
    // ['jest-html-reporter', {
    //   pageTitle: 'Python Deadlines Frontend Test Report',
    //   outputPath: './coverage/test-report.html'
    // }]
  ],

  // Timeout for tests
  testTimeout: 10000,

  // Clear mocks between tests
  clearMocks: true,
  restoreMocks: true,
  resetMocks: true
};
