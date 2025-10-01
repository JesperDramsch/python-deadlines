/**
 * Tests for Lazy Loading functionality
 */

describe('LazyLoad', () => {
  let LazyLoad;
  let mockIntersectionObserver;
  let observerCallbacks = [];
  let observedElements = [];
  let originalIntersectionObserver;

  beforeEach(() => {
    // Use fake timers
    jest.useFakeTimers();

    // Clear DOM
    document.body.innerHTML = '';
    document.head.innerHTML = '';

    // Reset document ready state
    Object.defineProperty(document, 'readyState', {
      writable: true,
      value: 'loading'
    });

    // Mock IntersectionObserver
    observedElements = [];
    observerCallbacks = [];

    let observerInstance = null;

    mockIntersectionObserver = jest.fn((callback, options) => {
      observerInstance = {
        observe: jest.fn(element => {
          observedElements.push(element);
        }),
        unobserve: jest.fn(element => {
          const index = observedElements.indexOf(element);
          if (index > -1) {
            observedElements.splice(index, 1);
          }
        }),
        disconnect: jest.fn(() => {
          observedElements = [];
        }),
        takeRecords: jest.fn(),
        root: options?.root || null,
        rootMargin: options?.rootMargin || '0px',
        thresholds: options?.threshold || [0],
        callback
      };
      observerCallbacks.push(callback);
      return observerInstance;
    });

    // Store reference to get observer instance
    mockIntersectionObserver.getInstance = () => observerInstance;

    originalIntersectionObserver = window.IntersectionObserver;
    window.IntersectionObserver = mockIntersectionObserver;

    // Mock matchMedia for reduced motion
    window.matchMedia = jest.fn(query => ({
      matches: query.includes('reduced-motion') ? false : true,
      media: query,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn()
    }));

    // Mock requestAnimationFrame
    window.requestAnimationFrame = jest.fn(cb => setTimeout(cb, 0));

    // Mock CustomEvent
    global.CustomEvent = jest.fn((name, options) => {
      const event = new Event(name);
      event.detail = options?.detail;
      return event;
    });

    // Store the original dispatchEvent
    const originalDispatchEvent = document.dispatchEvent;

    // Mock document.dispatchEvent but also call the original
    document.dispatchEvent = jest.fn((event) => {
      originalDispatchEvent.call(document, event);
    });

    // Add conference items to DOM
    document.body.innerHTML = `
      <div class="ConfItem" id="conf-1">
        <div class="conf-title"><a href="#">Conference 1</a></div>
        <div class="timer"></div>
      </div>
      <div class="ConfItem" id="conf-2">
        <div class="conf-title"><a href="#">Conference 2</a></div>
      </div>
      ${Array.from({ length: 20 }, (_, i) => `
        <div class="ConfItem" id="conf-${i + 3}">
          <div class="conf-title"><a href="#">Conference ${i + 3}</a></div>
        </div>
      `).join('')}
      <button id="load-more-conferences">Load More</button>
    `;

    // Load the lazy-load module
    // Important: The script checks document.readyState when it loads
    // Set readyState to 'complete' so it initializes immediately
    Object.defineProperty(document, 'readyState', {
      writable: true,
      value: 'complete'
    });

    const script = require('fs').readFileSync(
      require('path').resolve(__dirname, '../../../static/js/lazy-load.js'),
      'utf8'
    );

    // Execute the script - it will initialize immediately
    eval(script);

    LazyLoad = window.LazyLoad;

    // Check if LazyLoad was exposed
    if (!LazyLoad) {
      console.error('LazyLoad not exposed after eval');
    }
  });

  // Helper function to trigger DOMContentLoaded and run timers
  const triggerDOMContentLoaded = () => {
    document.dispatchEvent(new Event('DOMContentLoaded'));
    jest.runAllTimers();
  };

  afterEach(() => {
    window.IntersectionObserver = originalIntersectionObserver;
    jest.clearAllMocks();
    jest.useRealTimers();

    // Clean up styles
    const styleElement = document.getElementById('lazy-load-styles');
    if (styleElement) {
      styleElement.remove();
    }
  });

  describe('Initialization', () => {
    test('should expose LazyLoad API', () => {
      expect(LazyLoad).toBeDefined();
      expect(typeof LazyLoad.init).toBe('function');
      expect(typeof LazyLoad.loadAll).toBe('function');
      expect(typeof LazyLoad.loadNext).toBe('function');
      expect(typeof LazyLoad.cleanup).toBe('function');
      expect(typeof LazyLoad.getLoadedCount).toBe('function');
    });

    test('should create IntersectionObserver on init', () => {
      // LazyLoad should have been initialized in beforeEach
      expect(mockIntersectionObserver).toHaveBeenCalled();
      expect(mockIntersectionObserver.mock.calls[0][1]).toMatchObject({
        rootMargin: '50px 0px',
        threshold: 0.01
      });
    });

    test('should add lazy-load styles', () => {
      // Styles should have been added in beforeEach

      const styles = document.getElementById('lazy-load-styles');
      expect(styles).toBeTruthy();
      expect(styles.textContent).toContain('.lazy-placeholder');
      expect(styles.textContent).toContain('@keyframes shimmer');
    });

    test('should mark first batch as loaded immediately', () => {
      // LazyLoad should have processed first batch on init

      const conferences = document.querySelectorAll('.ConfItem');
      const firstBatch = Array.from(conferences).slice(0, 10);

      firstBatch.forEach(conf => {
        expect(conf.classList.contains('lazy-loaded')).toBe(true);
        expect(conf.classList.contains('lazy-load')).toBe(false);
      });
    });

    test('should prepare remaining items for lazy loading', () => {
      triggerDOMContentLoaded();

      const conferences = document.querySelectorAll('.ConfItem');
      const lazyItems = Array.from(conferences).slice(10);

      lazyItems.forEach((conf, index) => {
        expect(conf.classList.contains('lazy-load')).toBe(true);
        expect(conf.getAttribute('data-lazy-index')).toBe(String(index + 10));
      });
    });

    test('should observe lazy items', () => {
      triggerDOMContentLoaded();

      // Should observe items beyond the first batch (10)
      expect(observedElements.length).toBe(12); // Remaining items
    });

    test('should fallback when IntersectionObserver is not available', () => {
      // Create a fresh DOM without IntersectionObserver
      document.body.innerHTML = `
        <div class="ConfItem" id="conf-1">
          <div class="conf-title"><a href="#">Conference 1</a></div>
        </div>
        <div class="ConfItem" id="conf-2">
          <div class="conf-title"><a href="#">Conference 2</a></div>
        </div>
      `;

      // Remove IntersectionObserver before loading the script
      delete window.IntersectionObserver;

      // Set readyState to complete
      Object.defineProperty(document, 'readyState', {
        writable: true,
        value: 'complete'
      });

      // Re-load the lazy-load module without IntersectionObserver
      const script = require('fs').readFileSync(
        require('path').resolve(__dirname, '../../../static/js/lazy-load.js'),
        'utf8'
      );
      eval(script);

      // All conferences should be loaded without lazy loading
      const conferences = document.querySelectorAll('.ConfItem');
      expect(conferences.length).toBeGreaterThan(0);

      conferences.forEach(conf => {
        // Without IntersectionObserver, items should not have lazy-load class
        expect(conf.classList.contains('lazy-load')).toBe(false);
      });
    });
  });

  describe('Placeholder Creation', () => {
    test('should create placeholder content for lazy items', () => {
      triggerDOMContentLoaded();

      const lazyItems = document.querySelectorAll('.ConfItem.lazy-load');
      lazyItems.forEach(item => {
        const placeholder = item.querySelector('.lazy-placeholder');
        expect(placeholder).toBeTruthy();
        expect(placeholder.querySelector('.placeholder-shimmer')).toBeTruthy();
      });
    });

    test('should store original content', () => {
      triggerDOMContentLoaded();

      const lazyItem = document.querySelector('.ConfItem.lazy-load');
      expect(lazyItem.getAttribute('data-original-content')).toBeTruthy();
      expect(lazyItem.getAttribute('data-original-content')).toContain('Conference');
    });
  });

  describe('Intersection Handling', () => {
    test('should load conference when intersecting', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      // Simulate intersection
      if (observer && lazyItem) {
        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        expect(lazyItem.classList.contains('lazy-loaded')).toBe(true);
        expect(lazyItem.classList.contains('lazy-load')).toBe(false);
      }
    });

    test('should restore original content when loading', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        const originalContent = lazyItem.getAttribute('data-original-content');

        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        expect(lazyItem.innerHTML).toContain('Conference');
        expect(lazyItem.querySelector('.lazy-placeholder')).toBeFalsy();
      }
    });

    test('should unobserve element after loading', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        expect(observer.unobserve).toHaveBeenCalledWith(lazyItem);
      }
    });

    test('should not load if not intersecting', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        observer.callback([
          {
            isIntersecting: false,
            target: lazyItem
          }
        ], observer);

        expect(lazyItem.classList.contains('lazy-load')).toBe(true);
        expect(lazyItem.classList.contains('lazy-loaded')).toBe(false);
      }
    });
  });

  describe('Events', () => {
    test('should dispatch conferenceLoaded event when loading', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        expect(document.dispatchEvent).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'conferenceLoaded',
            detail: expect.objectContaining({
              element: lazyItem,
              count: expect.any(Number)
            })
          })
        );
      }
    });

    test('should dispatch events for initially loaded items', () => {
      triggerDOMContentLoaded();

      // Should dispatch for each of the first 10 items
      const calls = document.dispatchEvent.mock.calls.filter(
        call => call[0].type === 'conferenceLoaded'
      );
      expect(calls.length).toBe(10);
    });
  });

  describe('Manual Loading', () => {
    test('should load all conferences with loadAll', () => {
      triggerDOMContentLoaded();

      LazyLoad.loadAll();

      const conferences = document.querySelectorAll('.ConfItem');
      conferences.forEach(conf => {
        expect(conf.classList.contains('lazy-loaded') || !conf.innerHTML.includes('lazy-placeholder')).toBe(true);
      });
    });

    test('should load next batch with loadNext', () => {
      triggerDOMContentLoaded();

      const initialLazyCount = document.querySelectorAll('.ConfItem.lazy-load').length;

      LazyLoad.loadNext();

      const remainingLazyCount = document.querySelectorAll('.ConfItem.lazy-load').length;
      expect(remainingLazyCount).toBeLessThan(initialLazyCount);
    });

    test('should handle load more button click', () => {
      // LazyLoad should be initialized already
      const loadMoreBtn = document.getElementById('load-more-conferences');

      // Add click event listener to the button (normally done on DOMContentLoaded)
      loadMoreBtn.addEventListener('click', LazyLoad.loadNext);

      const initialLazyCount = document.querySelectorAll('.ConfItem.lazy-load').length;

      loadMoreBtn.click();

      const remainingLazyCount = document.querySelectorAll('.ConfItem.lazy-load').length;
      expect(remainingLazyCount).toBeLessThan(initialLazyCount);
    });
  });

  describe('Cleanup', () => {
    test('should disconnect observer on cleanup', () => {
      triggerDOMContentLoaded();

      const observer = mockIntersectionObserver.getInstance();

      if (observer) {
        LazyLoad.cleanup();
        expect(observer.disconnect).toHaveBeenCalled();
      }
    });

    test('should reset initialization state', () => {
      triggerDOMContentLoaded();

      LazyLoad.cleanup();

      // Should be able to reinitialize
      LazyLoad.init();
      expect(mockIntersectionObserver).toHaveBeenCalledTimes(2);
    });
  });

  describe('Load Counting', () => {
    test('should track loaded count', () => {
      triggerDOMContentLoaded();

      expect(LazyLoad.getLoadedCount()).toBe(0);

      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        expect(LazyLoad.getLoadedCount()).toBe(1);
      }
    });
  });

  describe('Animation and Transitions', () => {
    test('should apply fade-in transition', () => {
      // LazyLoad already initialized
      const observer = mockIntersectionObserver.getInstance();
      const lazyItem = document.querySelector('.ConfItem.lazy-load');

      if (observer && lazyItem) {
        // Simulate intersection
        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        // Check that opacity was set for transition
        expect(lazyItem.style.opacity).toBe('0');

        // Run requestAnimationFrame callbacks
        jest.runAllTimers();

        // After animation frame, opacity should be 1
        expect(lazyItem.style.opacity).toBe('1');
      }
    });

    test('should respect prefers-reduced-motion', () => {
      window.matchMedia = jest.fn(query => ({
        matches: query.includes('reduced-motion') ? true : false,
        media: query,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn()
      }));

      triggerDOMContentLoaded();

      const styles = document.getElementById('lazy-load-styles');
      expect(styles.textContent).toContain('@media (prefers-reduced-motion: reduce)');
    });
  });

  describe('Edge Cases', () => {
    test('should handle empty conference list', () => {
      document.body.innerHTML = '';

      expect(() => {
        triggerDOMContentLoaded();
      }).not.toThrow();
    });

    test('should handle missing original content', () => {
      triggerDOMContentLoaded();

      const lazyItem = document.querySelector('.ConfItem.lazy-load');
      const observer = mockIntersectionObserver.getInstance();

      if (lazyItem && observer) {
        lazyItem.removeAttribute('data-original-content');

        expect(() => {
          observer.callback([
            {
              isIntersecting: true,
              target: lazyItem
            }
          ], observer);
        }).not.toThrow();
      }
    });

    test('should handle already loaded items', () => {
      triggerDOMContentLoaded();

      const lazyItem = document.querySelector('.ConfItem.lazy-load');
      const observer = mockIntersectionObserver.getInstance();

      if (lazyItem && observer) {
        lazyItem.classList.add('lazy-loaded');

        const callsBefore = document.dispatchEvent.mock.calls.length;

        observer.callback([
          {
            isIntersecting: true,
            target: lazyItem
          }
        ], observer);

        // Should not process again
        const callsAfter = document.dispatchEvent.mock.calls.length;
        expect(callsAfter).toBe(callsBefore);
      }
    });

    test('should work when document is already ready', () => {
      Object.defineProperty(document, 'readyState', {
        writable: true,
        value: 'complete'
      });

      // Re-load module
      const script = require('fs').readFileSync(
        require('path').resolve(__dirname, '../../../static/js/lazy-load.js'),
        'utf8'
      );
      eval(script);

      const styles = document.getElementById('lazy-load-styles');
      expect(styles).toBeTruthy();
    });
  });
});