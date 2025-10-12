/**
 * Mock helpers for browser APIs and external dependencies
 */

/**
 * Mock Notification API
 */
function mockNotificationAPI(permission = 'default') {
  const NotificationMock = jest.fn().mockImplementation(function(title, options) {
    this.title = title;
    this.body = options?.body;
    this.icon = options?.icon;
    this.badge = options?.badge;
    this.tag = options?.tag;
    this.data = options?.data;
    this.requireInteraction = options?.requireInteraction || false;
    this.onclick = null;
    this.onclose = null;
    this.onerror = null;
    this.close = jest.fn();

    // Track created notifications
    NotificationMock.instances.push(this);
  });

  NotificationMock.instances = [];
  NotificationMock.permission = permission;
  NotificationMock.requestPermission = jest.fn().mockResolvedValue(permission);

  // Helper to clear instances
  NotificationMock.clearInstances = () => {
    NotificationMock.instances = [];
  };

  global.Notification = NotificationMock;

  return NotificationMock;
}

/**
 * Mock localStorage with persistence within test
 */
function mockLocalStorage() {
  const storage = {};

  const localStorageMock = {
    getItem: jest.fn((key) => storage[key] || null),
    setItem: jest.fn((key, value) => {
      storage[key] = value.toString();
    }),
    removeItem: jest.fn((key) => {
      delete storage[key];
    }),
    clear: jest.fn(() => {
      Object.keys(storage).forEach(key => delete storage[key]);
    }),
    get length() {
      return Object.keys(storage).length;
    },
    key: jest.fn((index) => {
      const keys = Object.keys(storage);
      return keys[index] || null;
    }),
    // Helper to get raw storage for assertions
    _getStorage: () => ({ ...storage })
  };

  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true
  });

  return localStorageMock;
}

/**
 * Mock store.js library
 */
function mockStore() {
  const storage = new Map();

  const storeMock = {
    get: jest.fn((key) => storage.get(key)),
    set: jest.fn((key, value) => storage.set(key, value)),
    remove: jest.fn((key) => storage.delete(key)),
    clear: jest.fn(() => storage.clear()),
    // Helper methods for testing
    _getAll: () => Object.fromEntries(storage),
    _reset: () => storage.clear()
  };

  global.store = storeMock;
  window.store = storeMock;

  return storeMock;
}

/**
 * Mock timers with control
 */
class TimerController {
  constructor() {
    this.currentTime = new Date();
    this.originalDate = global.Date;
    jest.useFakeTimers();
  }

  setCurrentTime(date) {
    this.currentTime = date instanceof Date ? date : new Date(date);
    jest.setSystemTime(this.currentTime);

    // Mock global Date constructor to return our mocked time
    const mockedDate = this.currentTime;
    global.Date = class extends Date {
      constructor(...args) {
        if (args.length === 0) {
          // new Date() should return mocked time
          super(mockedDate.getTime());
        } else {
          // new Date(args) should work normally
          super(...args);
        }
      }

      static now() {
        return mockedDate.getTime();
      }
    };

    // Also explicitly override Date.now at the global level
    // This ensures it works even when called as Date.now()
    global.Date.now = () => mockedDate.getTime();

    return this;
  }

  advanceTime(ms) {
    this.currentTime = new Date(this.currentTime.getTime() + ms);
    jest.setSystemTime(this.currentTime);
    jest.advanceTimersByTime(ms);

    // Update Date.now() to return the new time
    const mockedDate = this.currentTime;
    global.Date.now = () => mockedDate.getTime();

    return this;
  }

  advanceDays(days) {
    return this.advanceTime(days * 24 * 60 * 60 * 1000);
  }

  advanceToNextInterval() {
    jest.advanceTimersToNextTimer();
    return this;
  }

  runAllTimers() {
    jest.runAllTimers();
    return this;
  }

  runOnlyPendingTimers() {
    jest.runOnlyPendingTimers();
    return this;
  }

  getCurrentTime() {
    return new Date(this.currentTime);
  }

  cleanup() {
    jest.useRealTimers();
    // Restore original Date
    if (this.originalDate) {
      global.Date = this.originalDate;
    }
  }
}

/**
 * Mock Bootstrap modal
 */
function mockBootstrapModal() {
  $.fn.modal = jest.fn(function(action) {
    if (action === 'show') {
      $(this).addClass('show');
      $(this).trigger('shown.bs.modal');
    } else if (action === 'hide') {
      $(this).removeClass('show');
      $(this).trigger('hidden.bs.modal');
    }
    return this;
  });

  $.fn.toast = jest.fn(function(action) {
    if (action === 'show') {
      $(this).addClass('show');
      $(this).trigger('shown.bs.toast');
      // Auto-hide after delay
      const delay = $(this).data('delay') || 5000;
      setTimeout(() => {
        $(this).removeClass('show');
        $(this).trigger('hidden.bs.toast');
      }, delay);
    } else if (action === 'hide') {
      $(this).removeClass('show');
      $(this).trigger('hidden.bs.toast');
    }
    return this;
  });
}

/**
 * Mock window.focus and document.hidden
 */
function mockPageVisibility(isVisible = true) {
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => !isVisible
  });

  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => isVisible ? 'visible' : 'hidden'
  });

  window.focus = jest.fn(() => {
    const event = new Event('focus');
    window.dispatchEvent(event);
  });

  window.blur = jest.fn(() => {
    const event = new Event('blur');
    window.dispatchEvent(event);
  });

  return {
    setVisible: (visible) => {
      isVisible = visible;
      const event = new Event('visibilitychange');
      document.dispatchEvent(event);
    }
  };
}

/**
 * Mock Luxon DateTime
 */
function mockLuxonDateTime() {
  if (!window.luxon) {
    // Create a helper to generate proper Duration mocks
    const createDurationMock = (days, hours, minutes, seconds) => {
      const totalMillis = (days * 24 * 60 * 60 + hours * 60 * 60 + minutes * 60 + seconds) * 1000;
      return {
        // Total milliseconds
        toMillis: () => totalMillis,
        // shiftTo method returns normalized components
        shiftTo: jest.fn((...units) => ({
          toObject: () => ({ days, hours, minutes, seconds })
        }))
      };
    };

    // Simple mock if Luxon not loaded
    window.luxon = {
      DateTime: {
        now: jest.fn(() => ({
          toISO: () => new Date().toISOString(),
          toMillis: () => Date.now(),
          diff: jest.fn(() => createDurationMock(7, 12, 30, 45))
        })),
        fromSQL: jest.fn((str) => ({
          invalid: false,
          diff: jest.fn(() => createDurationMock(7, 12, 30, 45))
        })),
        fromISO: jest.fn((str) => ({
          invalid: false,
          diff: jest.fn(() => createDurationMock(7, 12, 30, 45))
        }))
      }
    };
  }
  return window.luxon;
}

// Export all mock helpers
module.exports = {
  mockNotificationAPI,
  mockLocalStorage,
  mockStore,
  TimerController,
  mockBootstrapModal,
  mockPageVisibility,
  mockLuxonDateTime
};
