/**
 * Enhanced mock helpers for more robust testing
 */

/**
 * Enhanced Timer Controller with better Date.now() mocking
 */
class EnhancedTimerController {
  constructor() {
    this.currentTime = new Date('2024-01-15T12:00:00');
    this.originalDate = global.Date;
    this.originalDateNow = Date.now;
    jest.useFakeTimers();
    this.setCurrentTime(this.currentTime);
  }

  setCurrentTime(date) {
    this.currentTime = date instanceof Date ? date : new Date(date);
    jest.setSystemTime(this.currentTime);

    const mockedTime = this.currentTime.getTime();

    // Create a more comprehensive Date mock
    const OriginalDate = this.originalDate;
    const MockedDate = class extends OriginalDate {
      constructor(...args) {
        if (args.length === 0) {
          super(mockedTime);
        } else {
          super(...args);
        }
      }

      static now() {
        return mockedTime;
      }
    };

    // Preserve original Date methods
    Object.setPrototypeOf(MockedDate, OriginalDate);
    Object.setPrototypeOf(MockedDate.prototype, OriginalDate.prototype);

    global.Date = MockedDate;

    // Ensure Date.now() is consistently mocked
    global.Date.now = () => mockedTime;

    // Also update the window object if it exists
    if (typeof window !== 'undefined') {
      window.Date = MockedDate;
      window.Date.now = () => mockedTime;
    }

    return this;
  }

  advanceTime(ms) {
    this.currentTime = new Date(this.currentTime.getTime() + ms);
    this.setCurrentTime(this.currentTime);
    jest.advanceTimersByTime(ms);
    return this;
  }

  advanceHours(hours) {
    return this.advanceTime(hours * 60 * 60 * 1000);
  }

  advanceDays(days) {
    return this.advanceTime(days * 24 * 60 * 60 * 1000);
  }

  getCurrentTime() {
    return new Date(this.currentTime);
  }

  getTimeMillis() {
    return this.currentTime.getTime();
  }

  cleanup() {
    jest.useRealTimers();
    if (this.originalDate) {
      global.Date = this.originalDate;
      if (typeof window !== 'undefined') {
        window.Date = this.originalDate;
      }
    }
    if (this.originalDateNow) {
      global.Date.now = this.originalDateNow;
      if (typeof window !== 'undefined') {
        window.Date.now = this.originalDateNow;
      }
    }
  }
}

/**
 * Enhanced localStorage mock with better persistence
 */
function createEnhancedLocalStorage() {
  const storage = {};

  const enhancedMock = {
    getItem: jest.fn((key) => {
      const value = storage[key];
      return value !== undefined ? value : null;
    }),

    setItem: jest.fn((key, value) => {
      storage[key] = String(value);
      return undefined;
    }),

    removeItem: jest.fn((key) => {
      delete storage[key];
      return undefined;
    }),

    clear: jest.fn(() => {
      Object.keys(storage).forEach(key => delete storage[key]);
      return undefined;
    }),

    get length() {
      return Object.keys(storage).length;
    },

    key: jest.fn((index) => {
      const keys = Object.keys(storage);
      return keys[index] || null;
    }),

    // Helper methods for testing
    _getStorage: () => ({ ...storage }),
    _setStorage: (data) => {
      Object.keys(storage).forEach(key => delete storage[key]);
      Object.assign(storage, data);
    },
    _hasItem: (key) => key in storage,
    _debug: () => {
      console.log('LocalStorage contents:', storage);
    }
  };

  // Define localStorage on window
  Object.defineProperty(window, 'localStorage', {
    value: enhancedMock,
    writable: true,
    configurable: true
  });

  // Also set on global for consistency
  global.localStorage = enhancedMock;

  return enhancedMock;
}

/**
 * Enhanced jQuery mock with better DOM handling
 */
function createEnhancedJQueryMock() {
  const jQuery = jest.fn((selector) => {
    // Handle document ready
    if (typeof selector === 'function') {
      // Don't auto-execute, store for manual triggering
      jQuery._readyCallbacks = jQuery._readyCallbacks || [];
      jQuery._readyCallbacks.push(selector);
      return jQuery;
    }

    // Handle string selectors
    if (typeof selector === 'string') {
      const elements = document.querySelectorAll(selector);
      return createJQueryObject(Array.from(elements));
    }

    // Handle DOM elements
    if (selector instanceof Element) {
      return createJQueryObject([selector]);
    }

    // Handle NodeList
    if (selector instanceof NodeList) {
      return createJQueryObject(Array.from(selector));
    }

    // Handle jQuery objects
    if (selector && selector.jquery) {
      return selector;
    }

    return createJQueryObject([]);
  });

  function createJQueryObject(elements) {
    const obj = {
      length: elements.length,
      jquery: true,

      each: jest.fn(function(callback) {
        elements.forEach((el, index) => {
          callback.call(el, index, el);
        });
        return obj;
      }),

      find: jest.fn(function(selector) {
        const results = [];
        elements.forEach(el => {
          const found = el.querySelectorAll(selector);
          results.push(...Array.from(found));
        });
        return createJQueryObject(results);
      }),

      data: jest.fn(function(key, value) {
        if (elements.length === 0) return obj;

        if (value === undefined) {
          // Getter
          const el = elements[0];
          const attrName = `data-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
          return el.getAttribute(attrName);
        } else {
          // Setter
          elements.forEach(el => {
            const attrName = `data-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
            el.setAttribute(attrName, value);
          });
          return obj;
        }
      }),

      attr: jest.fn(function(name, value) {
        if (elements.length === 0) return obj;

        if (value === undefined) {
          return elements[0].getAttribute(name);
        } else {
          elements.forEach(el => el.setAttribute(name, value));
          return obj;
        }
      }),

      prop: jest.fn(function(name, value) {
        if (elements.length === 0) return obj;

        if (value === undefined) {
          return elements[0][name];
        } else {
          elements.forEach(el => { el[name] = value; });
          return obj;
        }
      }),

      val: jest.fn(function(value) {
        if (elements.length === 0) return obj;

        if (value === undefined) {
          return elements[0].value;
        } else {
          elements.forEach(el => { el.value = value; });
          return obj;
        }
      }),

      on: jest.fn(function(event, handler) {
        elements.forEach(el => {
          el.addEventListener(event, handler);
        });
        return obj;
      }),

      off: jest.fn(function(event, handler) {
        elements.forEach(el => {
          el.removeEventListener(event, handler);
        });
        return obj;
      }),

      click: jest.fn(function(handler) {
        if (handler) {
          return obj.on('click', handler);
        } else {
          elements.forEach(el => el.click());
          return obj;
        }
      }),

      show: jest.fn(function() {
        elements.forEach(el => {
          el.style.display = '';
        });
        return obj;
      }),

      hide: jest.fn(function() {
        elements.forEach(el => {
          el.style.display = 'none';
        });
        return obj;
      }),

      fadeOut: jest.fn(function() {
        elements.forEach(el => {
          el.style.display = 'none';
        });
        return obj;
      }),

      fadeIn: jest.fn(function() {
        elements.forEach(el => {
          el.style.display = '';
        });
        return obj;
      }),

      is: jest.fn(function(selector) {
        if (elements.length === 0) return false;
        if (selector === ':checked') {
          return elements[0].checked;
        }
        return elements[0].matches(selector);
      }),

      map: jest.fn(function(callback) {
        const results = [];
        elements.forEach((el, index) => {
          results.push(callback.call(el, index, el));
        });
        return results;
      }),

      get: jest.fn(function(index) {
        if (index === undefined) return elements;
        return elements[index];
      })
    };

    // Add array access
    elements.forEach((el, index) => {
      obj[index] = el;
    });

    return obj;
  }

  // Add jQuery methods
  jQuery.fn = {
    ready: jest.fn(function(callback) {
      jQuery._readyCallbacks = jQuery._readyCallbacks || [];
      jQuery._readyCallbacks.push(callback);
      return this;
    }),
    modal: jest.fn(),
    toast: jest.fn(),
    countdown: jest.fn()
  };

  // Helper to trigger ready callbacks
  jQuery._triggerReady = () => {
    if (jQuery._readyCallbacks) {
      jQuery._readyCallbacks.forEach(cb => cb());
    }
  };

  return jQuery;
}

module.exports = {
  EnhancedTimerController,
  createEnhancedLocalStorage,
  createEnhancedJQueryMock
};