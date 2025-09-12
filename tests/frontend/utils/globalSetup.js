/**
 * Global setup for Jest - runs before test environment is set up
 */

// Polyfill for TextEncoder/TextDecoder (needed for jsdom)
const { TextEncoder, TextDecoder } = require('util');
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Set up fetch polyfill
global.fetch = require('node-fetch');

// Mock window.location
delete window.location;
window.location = {
  href: 'http://localhost:4000/',
  hostname: 'localhost',
  pathname: '/',
  search: '',
  hash: '',
  reload: jest.fn(),
  assign: jest.fn(),
  replace: jest.fn()
};

// Mock window.scrollTo
window.scrollTo = jest.fn();
window.scroll = jest.fn();

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
  takeRecords() {
    return [];
  }
};

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
};

// Set up store.js mock (before it's required)
global.store = {
  get: jest.fn((key) => {
    return localStorage.getItem(key) ? JSON.parse(localStorage.getItem(key)) : null;
  }),
  set: jest.fn((key, value) => {
    localStorage.setItem(key, JSON.stringify(value));
  }),
  remove: jest.fn((key) => {
    localStorage.removeItem(key);
  }),
  clear: jest.fn(() => {
    localStorage.clear();
  })
};
