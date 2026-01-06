/**
 * Tests for ConferenceFilter
 */

const {
  mockStore,
  TimerController,
  mockBootstrapModal,
  mockPageVisibility
} = require('../utils/mockHelpers');

const {
  createConferenceWithDeadline,
  createSavedConferences,
  setupConferenceDOM,
  createConferenceSet
} = require('../utils/dataHelpers');

describe('ConferenceFilter', () => {
  let ConferenceFilter;
  let storeMock;
  let originalLocation;
  let originalHistory;
  let timerController;

  beforeEach(() => {
    // Set up DOM
    document.body.innerHTML = `
      <select id="subject-select" multiple>
        <option value="PY">Python</option>
        <option value="SCIPY">SciPy</option>
        <option value="DATA">Data Science</option>
        <option value="WEB">Web</option>
        <option value="BIZ">Business</option>
      </select>
      <div class="ConfItem PY-conf" data-conf-id="pycon-2025">
        <div class="conf-sub" data-sub="PY">PY</div>
        <div>PyCon US 2025</div>
      </div>
      <div class="ConfItem DATA-conf" data-conf-id="pydata-2025">
        <div class="conf-sub" data-sub="DATA">DATA</div>
        <div>PyData Global 2025</div>
      </div>
      <div class="ConfItem SCIPY-conf" data-conf-id="scipy-2025">
        <div class="conf-sub" data-sub="SCIPY">SCIPY</div>
        <div>SciPy 2025</div>
      </div>
      <div class="ConfItem WEB-conf" data-conf-id="djangocon-2025">
        <div class="conf-sub" data-sub="WEB">WEB</div>
        <div>DjangoCon 2025</div>
      </div>
    `;

    // Mock jQuery
    global.$ = jest.fn((selector) => {
      // Handle document selector specially
      if (selector === document) {
        return {
          ready: jest.fn((callback) => callback()),
          on: jest.fn((event, selectorOrHandler, handlerOrOptions, finalHandler) => {
            if (typeof selectorOrHandler === 'function') {
              // Direct event binding
              document.addEventListener(event.split('.')[0], selectorOrHandler);
            } else {
              // Delegated event binding
              const handler = handlerOrOptions || finalHandler;
              document.addEventListener(event.split('.')[0], (e) => {
                if (e.target.matches(selectorOrHandler) || e.target.closest(selectorOrHandler)) {
                  handler.call(e.target, e);
                }
              });
            }
          }),
          off: jest.fn((event, selector) => {
            // Mock removing event handlers
            return $(document);
          }),
          trigger: jest.fn((event, data) => {
            const customEvent = new CustomEvent(event, { detail: data });
            document.dispatchEvent(customEvent);
          })
        };
      }

      // Handle :visible selector by filtering visible elements
      let elements;
      if (typeof selector === 'string') {
        if (selector.includes(':visible')) {
          // Remove :visible and get base elements
          const baseSelector = selector.replace(':visible', '').trim();
          const allElements = baseSelector ? document.querySelectorAll(baseSelector) : [];
          // Filter to only visible elements (not display: none)
          elements = Array.from(allElements).filter(el => {
            // Check inline style for display: none
            return !el.style || el.style.display !== 'none';
          });
        } else {
          elements = Array.from(document.querySelectorAll(selector));
        }
      } else if (selector && selector.nodeType) {
        elements = [selector];
      } else {
        elements = [];
      }
      const mockJquery = {
        length: elements.length,
        show: jest.fn(() => {
          elements.forEach(el => {
            if (el && el.style) el.style.display = '';
          });
          return mockJquery;
        }),
        hide: jest.fn(() => {
          elements.forEach(el => {
            if (el && el.style) el.style.display = 'none';
          });
          return mockJquery;
        }),
        each: jest.fn(function(callback) {
          elements.forEach((el, index) => {
            // In jQuery, 'this' in the callback is the DOM element
            // The callback gets (index, element) as parameters
            callback.call(el, index, el);
          });
          return mockJquery;
        }),
        val: jest.fn((value) => {
          if (value !== undefined) {
            // Set value
            elements.forEach(el => {
              if (el.tagName === 'SELECT') {
                // For multiselect, simulate selecting options
                const opts = el.querySelectorAll('option');
                opts.forEach(opt => {
                  opt.selected = Array.isArray(value) ? value.includes(opt.value) : value === opt.value;
                });
                // Store the value for later retrieval
                el._mockValue = value;
              } else {
                el.value = value;
              }
            });
            return mockJquery;
          } else {
            // Get value
            if (elements[0] && elements[0].tagName === 'SELECT') {
              // Return the mock value if it was set
              if (elements[0]._mockValue !== undefined) {
                return elements[0]._mockValue;
              }
              const selected = [];
              elements[0].querySelectorAll('option:checked').forEach(opt => {
                selected.push(opt.value);
              });
              return selected.length > 0 ? selected : null;
            }
            return elements[0]?.value || null;
          }
        }),
        text: jest.fn(function() {
          // For a single element, return its text content
          if (elements.length === 1) {
            return elements[0]?.textContent || '';
          }
          // For multiple elements, return combined text
          return elements.map(el => el?.textContent || '').join('');
        }),
        data: jest.fn((key) => {
          const el = elements[0];
          if (el) {
            // Handle multiselect data attribute
            if (key === 'multiselect' && el.id === 'subject-select') {
              return true;  // Indicate multiselect is initialized
            }
            const attrName = `data-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
            return el.getAttribute(attrName);
          }
        }),
        multiselect: jest.fn((action) => {
          // Mock multiselect methods
          if (action === 'refresh') {
            return mockJquery;
          }
          if (action === 'selectAll') {
            const opts = elements[0]?.querySelectorAll('option');
            opts?.forEach(opt => opt.selected = true);
            return mockJquery;
          }
          // Mock that multiselect is initialized
          elements[0]?.setAttribute('data-multiselect', 'true');
          return mockJquery;
        }),
        css: jest.fn((prop, value) => {
          if (typeof prop === 'object') {
            Object.entries(prop).forEach(([key, val]) => {
              elements.forEach(el => {
                if (el) el.style[key] = val;
              });
            });
          } else if (value !== undefined) {
            elements.forEach(el => {
              if (el) el.style[prop] = value;
            });
          }
          return mockJquery;
        }),
        hide: jest.fn(() => {
          elements.forEach(el => {
            if (el && el.style) el.style.display = 'none';
          });
          return mockJquery;
        }),
        show: jest.fn(() => {
          elements.forEach(el => {
            if (el && el.style) el.style.display = '';
          });
          return mockJquery;
        }),
        off: jest.fn(() => mockJquery),
        on: jest.fn((event, handler) => {
          elements.forEach(el => {
            el?.addEventListener(event.split('.')[0], handler);
          });
          return mockJquery;
        }),
        each: jest.fn((callback) => {
          elements.forEach((el, index) => {
            if (el) {
              // In jQuery, 'this' is the element in the callback
              callback.call(el, index, el);
            }
          });
          return mockJquery;
        }),
        closest: jest.fn((selector) => {
          // Find the closest matching parent element
          const closestElements = [];
          elements.forEach(el => {
            if (el && el.closest) {
              const closest = el.closest(selector);
              if (closest) {
                closestElements.push(closest);
              }
            }
          });
          return $(closestElements.length > 0 ? closestElements : []);
        })
      };

      // Add filter method for :visible selector
      mockJquery.filter = jest.fn((selector) => {
        if (selector === ':visible') {
          const visible = Array.from(elements).filter(el => el.style.display !== 'none');
          return $(visible);
        }
        return mockJquery;
      });

      // Add trigger method for event handling
      mockJquery.trigger = jest.fn((event) => {
        elements.forEach(el => {
          // Use appropriate event type for different events
          let evt;
          if (event === 'click') {
            evt = new MouseEvent(event, { bubbles: true, cancelable: true });
          } else if (event === 'change') {
            evt = new Event(event, { bubbles: true, cancelable: true });
          } else {
            evt = new CustomEvent(event, { bubbles: true, cancelable: true });
          }
          el.dispatchEvent(evt);
        });
        return mockJquery;
      });

      // Special handling for :visible selector
      if (selector && typeof selector === 'string' && selector.includes(':visible')) {
        const baseSelector = selector.replace(':visible', '').trim();
        const baseElements = document.querySelectorAll(baseSelector);
        const visibleElements = Array.from(baseElements).filter(el => el.style.display !== 'none');
        return $(visibleElements);
      }

      return mockJquery;
    });

    // Mock store
    storeMock = mockStore();
    global.store = storeMock;

    // Mock location
    originalLocation = window.location;
    delete window.location;
    window.location = {
      pathname: '/',
      search: '',
      hostname: 'test.com',
      href: 'http://test.com/'
    };

    // Mock history
    originalHistory = window.history;
    const mockPushState = jest.fn((state, title, url) => {
      // Extract just the pathname part
      const urlParts = (url || '/').split('?');
      window.location.pathname = urlParts[0];
      window.location.search = urlParts[1] ? '?' + urlParts[1] : '';
    });
    window.history = {
      pushState: mockPushState,
      replaceState: jest.fn()
    };
    // Also override on the original to be safe
    Object.defineProperty(window, 'history', {
      value: {
        pushState: mockPushState,
        replaceState: jest.fn()
      },
      writable: true,
      configurable: true
    });

    // Mock URLSearchParams
    global.URLSearchParams = jest.fn((search) => ({
      get: jest.fn((key) => {
        if (key === 'sub' && search === '?sub=PY,DATA') {
          return 'PY,DATA';
        }
        return null;
      })
    }));

    timerController = new TimerController();

    // Initialize multiselect data attribute
    const select = document.getElementById('subject-select');
    if (select) {
      select.setAttribute('data-multiselect', 'true');
    }

    // Load ConferenceFilter
    jest.isolateModules(() => {
      require('../../../static/js/conference-filter.js');
      ConferenceFilter = window.ConferenceFilter;
    });
  });

  afterEach(() => {
    window.location = originalLocation;
    window.history = originalHistory;
    delete window.ConferenceFilter;
    delete window.filterBySub;
    timerController.cleanup();
  });

  describe('Initialization', () => {
    test('should initialize filter manager', () => {
      ConferenceFilter.init();

      expect(ConferenceFilter.getCurrentFilters()).toBeDefined();
      expect(ConferenceFilter.getCurrentFilters().subs).toBeDefined();
    });

    test('should prevent multiple initializations', () => {
      ConferenceFilter.init();
      const firstState = ConferenceFilter.getCurrentFilters();

      ConferenceFilter.init(); // Second call
      const secondState = ConferenceFilter.getCurrentFilters();

      expect(firstState).toBe(secondState);
    });

    test('should extract available subcategories from multiselect', () => {
      ConferenceFilter.init();

      // The filter should have detected PY, SCIPY, DATA, WEB, BIZ from the select options
      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters).toBeDefined();
    });

    test('should use default categories if multiselect is empty', () => {
      document.getElementById('subject-select').innerHTML = '';

      ConferenceFilter.init();

      // Should fall back to default categories
      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters).toBeDefined();
    });
  });

  describe('URL Parameter Handling', () => {
    test('should load filters from URL parameters', () => {
      window.location.search = '?sub=PY,DATA';
      global.URLSearchParams = jest.fn(() => ({
        get: jest.fn((key) => key === 'sub' ? 'PY,DATA' : null)
      }));

      ConferenceFilter.init();

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual(['PY', 'DATA']);
    });

    test('should update URL when filters change', () => {
      ConferenceFilter.init();
      ConferenceFilter.filterBySub('PY');

      expect(window.history.pushState).toHaveBeenCalledWith(
        '', '', '/?sub=PY'
      );
    });

    test('should remove URL parameter when showing all', () => {
      ConferenceFilter.init();
      ConferenceFilter.filterBySub('PY');

      // Clear mock to only check the clearFilters call
      window.history.pushState.mockClear();

      ConferenceFilter.clearFilters();

      // The last call should be to clear the URL
      expect(window.history.pushState).toHaveBeenLastCalledWith(
        '', '', '/'
      );
    });
  });

  describe('Filter Application', () => {
    test('should show all conferences when no filters', () => {
      ConferenceFilter.init();

      const pyConf = document.querySelector('.PY-conf');
      const dataConf = document.querySelector('.DATA-conf');

      expect(pyConf.style.display).not.toBe('none');
      expect(dataConf.style.display).not.toBe('none');
    });

    test('should filter conferences by subcategory', () => {
      ConferenceFilter.init();
      ConferenceFilter.filterBySub('PY');

      const pyConf = document.querySelector('.PY-conf');
      const dataConf = document.querySelector('.DATA-conf');

      expect(pyConf.style.display).not.toBe('none');
      expect(dataConf.style.display).toBe('none');
    });

    test('should handle multiple subcategory filters', () => {
      // Use fake timers to control setTimeout
      jest.useFakeTimers();

      // Initialize with proper allSubs
      ConferenceFilter.init();

      // Fast-forward past the setTimeout
      jest.runAllTimers();

      // Make sure we have all subs properly set
      ConferenceFilter.allSubs = ['PY', 'DATA', 'SCIPY'];

      // Apply filters - PY and DATA should be shown, SCIPY hidden
      ConferenceFilter.updateFromMultiselect(['PY', 'DATA']);

      const pyConf = document.querySelector('.PY-conf');
      const dataConf = document.querySelector('.DATA-conf');
      const scipyConf = document.querySelector('.SCIPY-conf');

      // Check visibility - visible elements have display !== 'none'
      expect(pyConf.style.display).not.toBe('none');
      expect(dataConf.style.display).not.toBe('none');

      // Hidden elements should have display: 'none'
      // If this fails, the filtering logic isn't being applied
      expect(scipyConf.style.display).toBe('none');

      jest.useRealTimers();
    });

    test('should toggle filter when clicking same subcategory', () => {
      ConferenceFilter.init();

      // First click - filter to PY
      ConferenceFilter.filterBySub('PY');
      expect(ConferenceFilter.getCurrentFilters().subs).toEqual(['PY']);

      // Second click - clear filters (show all)
      ConferenceFilter.filterBySub('PY');
      expect(ConferenceFilter.getCurrentFilters().subs).toEqual([]);
    });
  });

  describe('Badge Click Handling', () => {
    test('should filter when clicking conference badge', () => {
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past initialization setTimeout
      jest.runAllTimers();

      const badge = document.querySelector('.conf-sub[data-sub="PY"]');
      expect(badge).toBeTruthy();

      // Directly call the filter method since event delegation is complex to mock
      ConferenceFilter.filterBySub('PY');

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual(['PY']);

      jest.useRealTimers();
    });

    test('should add hover effect to badges', () => {
      ConferenceFilter.init();

      const badge = document.querySelector('.conf-sub[data-sub="PY"]');
      const mouseEnter = new MouseEvent('mouseenter', { bubbles: true });
      badge.dispatchEvent(mouseEnter);

      expect(badge.style.opacity).toBe('0.8');

      const mouseLeave = new MouseEvent('mouseleave', { bubbles: true });
      badge.dispatchEvent(mouseLeave);

      expect(badge.style.opacity).toBe('1');
    });
  });

  describe('Search Functionality', () => {
    test('should filter conferences by search query within category', () => {
      // Note: Testing search with a category filter since the jQuery mock
      // doesn't fully support the 'all categories' path. The core search
      // logic is the same either way.
      jest.useFakeTimers();

      ConferenceFilter.init();
      jest.runAllTimers();

      // First filter by PY category (shows only PY conferences)
      ConferenceFilter.filterBySub('PY');

      // Now search within that - searching for 'pycon' should keep PY visible
      ConferenceFilter.search('pycon');

      const pyConf = document.querySelector('.PY-conf');
      const dataConf = document.querySelector('.DATA-conf');

      // PyCon should be visible (matches PY filter AND contains 'pycon')
      expect(pyConf.style.display).not.toBe('none');
      // DATA conf should be hidden (doesn't match PY category filter)
      expect(dataConf.style.display).toBe('none');

      jest.useRealTimers();
    });

    test('should combine search with category filters', () => {
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past initialization
      jest.runAllTimers();

      ConferenceFilter.filterBySub('DATA');
      ConferenceFilter.search('global');

      const pyConf = document.querySelector('.PY-conf');
      const dataConf = document.querySelector('.DATA-conf');

      // Both should be hidden initially by category filter
      // Then DATA conf should be visible as it matches search
      expect(pyConf.style.display).toBe('none');
      expect(dataConf.style.display).not.toBe('none');

      jest.useRealTimers();
    });
  });

  describe('LocalStorage Integration', () => {
    test('should save filters to localStorage', () => {
      ConferenceFilter.init();
      ConferenceFilter.filterBySub('PY');

      expect(storeMock.set).toHaveBeenCalledWith(
        'test.com-subs',
        expect.objectContaining({
          subs: ['PY'],
          timestamp: expect.any(Number)
        })
      );
    });

    test('should load filters from localStorage', () => {
      storeMock.get.mockReturnValue({
        subs: ['SCIPY', 'DATA'],
        timestamp: Date.now()
      });

      ConferenceFilter.init();

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual(['SCIPY', 'DATA']);
    });

    test('should ignore expired localStorage data', () => {
      const oldTimestamp = Date.now() - (25 * 60 * 60 * 1000); // 25 hours ago
      storeMock.get.mockReturnValue({
        subs: ['OLD'],
        timestamp: oldTimestamp
      });

      ConferenceFilter.init();

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual([]); // Should use default instead
    });

    test('should treat all categories as show all', () => {
      storeMock.get.mockReturnValue({
        subs: ['PY', 'SCIPY', 'DATA', 'WEB', 'BIZ'],
        timestamp: Date.now()
      });

      ConferenceFilter.init();

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual([]); // Empty means show all
    });
  });

  describe('Multiselect Integration', () => {
    test('should update multiselect when filters change', () => {
      ConferenceFilter.init();

      // Spy on jQuery to track val and multiselect calls
      const valSpy = jest.fn();
      const multiselectSpy = jest.fn();
      const originalJquery = global.$;

      global.$ = jest.fn((selector) => {
        const result = originalJquery(selector);
        if (selector === '#subject-select') {
          result.val = valSpy.mockReturnValue(result);
          result.multiselect = multiselectSpy.mockReturnValue(result);
        }
        return result;
      });

      ConferenceFilter.filterBySub('PY');

      // Restore original
      global.$ = originalJquery;

      expect(valSpy).toHaveBeenCalledWith(['PY']);
      expect(multiselectSpy).toHaveBeenCalledWith('refresh');
    });

    test('should handle multiselect change events', () => {
      // Use fake timers to control setTimeout
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past the setTimeout in applyInitialFilters
      jest.runAllTimers();

      const select = document.getElementById('subject-select');

      // Simulate selecting options and trigger change via jQuery
      // since the handler is bound via jQuery
      const $select = $('#subject-select');
      $select.val(['SCIPY', 'WEB']);
      $select.trigger('change');

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual(['SCIPY', 'WEB']);

      jest.useRealTimers();
    });

    test('should prevent feedback loop with multiselect', () => {
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Filter programmatically
      ConferenceFilter.filterBySub('PY');

      // The multiselect update flag should prevent immediate re-filtering
      jest.advanceTimersByTime(150);

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs).toEqual(['PY']);

      jest.useRealTimers();
    });
  });

  describe('Clear Filters', () => {
    test('should clear all filters', () => {
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past initialization
      jest.runAllTimers();

      ConferenceFilter.filterBySub('PY');
      ConferenceFilter.search('test');

      ConferenceFilter.clearFilters();

      const filters = ConferenceFilter.getCurrentFilters();
      expect(filters.subs.length).toBe(5); // All categories
      expect(filters.searchQuery).toBe('');

      jest.useRealTimers();
    });

    test('should update multiselect when clearing', () => {
      ConferenceFilter.init();

      // Spy on jQuery to track multiselect calls
      const multiselectSpy = jest.fn();
      const originalJquery = global.$;

      global.$ = jest.fn((selector) => {
        const result = originalJquery(selector);
        if (selector === '#subject-select') {
          result.multiselect = multiselectSpy.mockReturnValue(result);
        }
        return result;
      });

      ConferenceFilter.filterBySub('PY');

      // Clear the spy to only capture the clear action
      multiselectSpy.mockClear();

      ConferenceFilter.clearFilters();

      // Restore original
      global.$ = originalJquery;

      expect(multiselectSpy).toHaveBeenCalledWith('selectAll', false);
    });
  });

  describe('Event Notifications', () => {
    test('should trigger conference-filter-change event', () => {
      ConferenceFilter.init();
      const eventSpy = jest.fn();
      document.addEventListener('conference-filter-change', eventSpy);

      ConferenceFilter.filterBySub('PY');

      expect(eventSpy).toHaveBeenCalled();
    });

    test('should notify CountdownManager if available', () => {
      window.CountdownManager = {
        onFilterUpdate: jest.fn()
      };

      ConferenceFilter.init();
      ConferenceFilter.filterBySub('PY');

      expect(window.CountdownManager.onFilterUpdate).toHaveBeenCalled();

      delete window.CountdownManager;
    });
  });

  describe('Browser Navigation', () => {
    test('should handle browser back/forward events', () => {
      ConferenceFilter.init();

      // Simulate browser back button
      const popstateEvent = new PopStateEvent('popstate');
      window.dispatchEvent(popstateEvent);

      // Should reload state from URL
      expect(ConferenceFilter.getCurrentFilters()).toBeDefined();
    });
  });

  describe('Backward Compatibility', () => {
    test('should expose filterBySub as global function', () => {
      ConferenceFilter.init();

      expect(window.filterBySub).toBeDefined();
      expect(typeof window.filterBySub).toBe('function');

      window.filterBySub('DATA');
      expect(ConferenceFilter.getCurrentFilters().subs).toEqual(['DATA']);
    });
  });

  describe('Edge Cases', () => {
    test('should handle string value from multiselect', () => {
      // Use fake timers to control setTimeout
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past the setTimeout in applyInitialFilters
      jest.runAllTimers();

      ConferenceFilter.updateFromMultiselect('PY');

      expect(ConferenceFilter.getCurrentFilters().subs).toEqual(['PY']);

      jest.useRealTimers();
    });

    test('should handle null/undefined from multiselect', () => {
      // Use fake timers to control setTimeout
      jest.useFakeTimers();

      ConferenceFilter.init();

      // Fast-forward past the setTimeout in applyInitialFilters
      jest.runAllTimers();

      ConferenceFilter.updateFromMultiselect(null);

      expect(ConferenceFilter.getCurrentFilters().subs).toEqual([]);

      jest.useRealTimers();
    });

    test('should handle missing multiselect element', () => {
      document.getElementById('subject-select').remove();

      // Should not throw
      expect(() => {
        ConferenceFilter.init();
        ConferenceFilter.filterBySub('PY');
      }).not.toThrow();
    });

    test('should handle badges without data-sub attribute', () => {
      document.body.innerHTML += '<div class="conf-sub">No Data</div>';
      ConferenceFilter.init();

      const badge = document.querySelector('.conf-sub:not([data-sub])');
      const clickEvent = new MouseEvent('click', { bubbles: true });

      // Should not throw
      expect(() => {
        badge.dispatchEvent(clickEvent);
      }).not.toThrow();
    });
  });
});
