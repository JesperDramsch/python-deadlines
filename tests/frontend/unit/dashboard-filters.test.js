/**
 * Tests for DashboardFilters
 *
 * FIXED: Now imports and tests the real static/js/dashboard-filters.js module
 * instead of testing an inline mock implementation.
 */

const { mockStore } = require('../utils/mockHelpers');

describe('DashboardFilters', () => {
  let DashboardFilters;
  let storeMock;
  let originalLocation;

  beforeEach(() => {
    // Set up DOM with filter elements
    document.body.innerHTML = `
      <div id="filter-container">
        <!-- Format Filters -->
        <input type="checkbox" id="filter-in-person" class="format-filter" value="in-person" />
        <input type="checkbox" id="filter-online" class="format-filter" value="online" />
        <input type="checkbox" id="filter-hybrid" class="format-filter" value="hybrid" />

        <!-- Topic Filters -->
        <input type="checkbox" id="filter-PY" class="topic-filter" value="PY" />
        <input type="checkbox" id="filter-DATA" class="topic-filter" value="DATA" />
        <input type="checkbox" id="filter-SCIPY" class="topic-filter" value="SCIPY" />
        <input type="checkbox" id="filter-WEB" class="topic-filter" value="WEB" />

        <!-- Feature Filters -->
        <input type="checkbox" id="filter-finaid" class="feature-filter" value="finaid" />
        <input type="checkbox" id="filter-workshop" class="feature-filter" value="workshop" />
        <input type="checkbox" id="filter-tutorial" class="feature-filter" value="tutorial" />

        <!-- Series Filter -->
        <input type="checkbox" id="filter-subscribed-series" />

        <!-- Action Buttons -->
        <button id="apply-filters">Apply</button>
        <button id="clear-filters">Clear</button>
        <button id="save-filter-preset">Save Preset</button>

        <!-- Filter Panel (for filter count badge) -->
        <div class="filter-panel">
          <div class="card-header">
            <h5>Filters</h5>
          </div>
        </div>

        <!-- Filter presets container -->
        <div id="filter-presets"></div>
      </div>
    `;

    // Mock store
    storeMock = mockStore();
    global.store = storeMock;
    window.store = storeMock;

    // Mock location and history
    originalLocation = window.location;

    delete window.location;
    window.location = {
      pathname: '/dashboard',
      search: '',
      href: 'http://localhost/dashboard'
    };

    window.history.replaceState = jest.fn();
    window.history.pushState = jest.fn();

    // Mock FavoritesManager (used by savePreset/loadPreset for toast)
    window.FavoritesManager = {
      showToast: jest.fn()
    };

    // Set up jQuery mock that works with the real module
    global.$ = jest.fn((selector) => {
      if (typeof selector === 'function') {
        // Document ready shorthand - DON'T auto-execute during module load
        // Store callback for manual testing if needed
        global.$.readyCallback = selector;
        return;
      }

      // Handle document selector
      if (selector === document) {
        return {
          ready: jest.fn((callback) => {
            if (callback) callback();
          })
        };
      }

      // Handle string selectors
      if (typeof selector === 'string') {
        // Check if this is HTML content (starts with <)
        const trimmed = selector.trim();
        if (trimmed.startsWith('<')) {
          const container = document.createElement('div');
          container.innerHTML = trimmed;
          const elements = Array.from(container.children);
          return createMockJquery(elements);
        }

        // Regular selector
        const elements = Array.from(document.querySelectorAll(selector));
        return createMockJquery(elements);
      }

      // Handle DOM elements
      const elements = selector.nodeType ? [selector] : Array.from(selector);
      return createMockJquery(elements);
    });

    // Helper to create jQuery-like object
    function createMockJquery(elements) {
      const mockJquery = {
        length: elements.length,
        get: (index) => index !== undefined ? elements[index] : elements,
        first: () => createMockJquery(elements.slice(0, 1)),
        prop: jest.fn((prop, value) => {
          if (value !== undefined) {
            elements.forEach(el => {
              if (prop === 'checked') el.checked = value;
              else el[prop] = value;
            });
            return mockJquery;
          }
          return elements[0]?.[prop];
        }),
        is: jest.fn((selector) => {
          if (selector === ':checked') {
            return elements[0]?.checked || false;
          }
          return false;
        }),
        map: jest.fn((callback) => {
          const results = [];
          elements.forEach((el, i) => {
            results.push(callback.call(el, i, el));
          });
          return {
            get: () => results
          };
        }),
        val: jest.fn((value) => {
          if (value !== undefined) {
            elements.forEach(el => el.value = value);
            return mockJquery;
          }
          return elements[0]?.value;
        }),
        on: jest.fn((event, handler) => {
          elements.forEach(el => {
            el.addEventListener(event, handler);
          });
          return mockJquery;
        }),
        trigger: jest.fn((event) => {
          elements.forEach(el => {
            el.dispatchEvent(new Event(event, { bubbles: true }));
          });
          return mockJquery;
        }),
        removeClass: jest.fn(() => mockJquery),
        addClass: jest.fn(() => mockJquery),
        text: jest.fn((value) => {
          if (value !== undefined) {
            elements.forEach(el => el.textContent = value);
            return mockJquery;
          }
          return elements[0]?.textContent;
        }),
        append: jest.fn((content) => {
          elements.forEach(el => {
            if (typeof content === 'string') {
              el.insertAdjacentHTML('beforeend', content);
            } else if (content.nodeType) {
              el.appendChild(content);
            } else if (content && content[0] && content[0].nodeType) {
              // jQuery object - append the first DOM element
              el.appendChild(content[0]);
            }
          });
          return mockJquery;
        }),
        empty: jest.fn(() => {
          elements.forEach(el => el.innerHTML = '');
          return mockJquery;
        }),
        remove: jest.fn(() => {
          elements.forEach(el => el.remove());
          return mockJquery;
        })
      };

      // Add array-like access
      elements.forEach((el, i) => {
        mockJquery[i] = el;
      });

      return mockJquery;
    }

    // Add $.fn for jQuery plugins
    $.fn = {
      ready: jest.fn((callback) => {
        // Store but don't auto-execute
        $.fn.ready.callback = callback;
        return $;
      })
    };

    // FIXED: Load the REAL DashboardFilters module instead of inline mock
    jest.isolateModules(() => {
      require('../../../static/js/dashboard-filters.js');
      DashboardFilters = window.DashboardFilters;
    });
  });

  afterEach(() => {
    window.location = originalLocation;
    delete window.DashboardFilters;
    delete window.FavoritesManager;
    jest.clearAllMocks();
  });

  describe('Initialization', () => {
    test('should initialize and call required methods', () => {
      // Spy on the actual methods
      const loadSpy = jest.spyOn(DashboardFilters, 'loadFromURL');
      const bindSpy = jest.spyOn(DashboardFilters, 'bindEvents');
      const persistSpy = jest.spyOn(DashboardFilters, 'setupFilterPersistence');

      DashboardFilters.init();

      // FIXED: Verify real module methods are called
      expect(loadSpy).toHaveBeenCalled();
      expect(bindSpy).toHaveBeenCalled();
      expect(persistSpy).toHaveBeenCalled();
    });

    test('should load saved filter preferences when no URL params', () => {
      const savedFilters = {
        formats: ['online'],
        topics: ['PY'],
        subscribedSeries: true
      };

      storeMock.get.mockReturnValue(savedFilters);

      DashboardFilters.setupFilterPersistence();

      // FIXED: Verify store.get was called with correct key
      expect(storeMock.get).toHaveBeenCalledWith('pythondeadlines-filter-preferences');
    });
  });

  describe('URL Parameter Handling', () => {
    test('should load filters from URL parameters', () => {
      window.location.search = '?format=online&topics=PY,DATA&series=subscribed';

      DashboardFilters.loadFromURL();

      // FIXED: Verify DOM was actually updated by the real module
      expect(document.getElementById('filter-online').checked).toBe(true);
      expect(document.getElementById('filter-PY').checked).toBe(true);
      expect(document.getElementById('filter-DATA').checked).toBe(true);
      expect(document.getElementById('filter-subscribed-series').checked).toBe(true);
    });

    test('should save filters to URL via history.replaceState', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      DashboardFilters.saveToURL();

      // FIXED: Verify history.replaceState was called
      expect(window.history.replaceState).toHaveBeenCalled();

      // Get the URL that was passed
      const call = window.history.replaceState.mock.calls[0];
      const newUrl = call[2];
      expect(newUrl).toContain('format=online');
      expect(newUrl).toContain('topics=PY');
    });

    test('should clear URL when no filters are selected', () => {
      // Ensure all checkboxes are unchecked
      document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);

      DashboardFilters.saveToURL();

      // FIXED: Verify URL is cleared (just pathname, no query string)
      const call = window.history.replaceState.mock.calls[0];
      const newUrl = call[2];
      expect(newUrl).toBe('/dashboard');
    });
  });

  describe('Filter Operations', () => {
    test('should update filter count badge when filters are applied', () => {
      DashboardFilters.bindEvents();

      // Check some filters
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      DashboardFilters.updateFilterCount();

      // FIXED: Verify badge was created with correct count
      const badge = document.getElementById('filter-count-badge');
      expect(badge).toBeTruthy();
      expect(badge.textContent).toBe('2');
    });

    test('should remove badge when no filters active', () => {
      // First add a badge
      const header = document.querySelector('.filter-panel .card-header h5');
      const badge = document.createElement('span');
      badge.id = 'filter-count-badge';
      badge.textContent = '2';
      header.appendChild(badge);

      // Now clear filters
      document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);

      DashboardFilters.updateFilterCount();

      // FIXED: Verify badge was removed
      expect(document.getElementById('filter-count-badge')).toBeFalsy();
    });
  });

  describe('Filter Presets', () => {
    test('should save filter preset to store', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;
      storeMock.get.mockReturnValue({});

      DashboardFilters.savePreset('Test Preset');

      // FIXED: Verify store.set was called with preset data
      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-filter-presets',
        expect.objectContaining({
          'Test Preset': expect.objectContaining({
            name: 'Test Preset',
            formats: expect.arrayContaining(['online']),
            topics: expect.arrayContaining(['PY'])
          })
        })
      );

      // Verify toast was shown
      expect(window.FavoritesManager.showToast).toHaveBeenCalledWith(
        'Preset Saved',
        expect.stringContaining('Test Preset')
      );
    });

    test('should load filter preset from store', () => {
      const preset = {
        formats: ['hybrid'],
        topics: ['DATA', 'SCIPY'],
        features: ['workshop'],
        subscribedSeries: true
      };

      storeMock.get.mockReturnValue({ 'My Preset': preset });

      DashboardFilters.loadPreset('My Preset');

      // FIXED: Verify DOM was updated by real module
      expect(document.getElementById('filter-hybrid').checked).toBe(true);
      expect(document.getElementById('filter-DATA').checked).toBe(true);
      expect(document.getElementById('filter-SCIPY').checked).toBe(true);
      expect(document.getElementById('filter-workshop').checked).toBe(true);
      expect(document.getElementById('filter-subscribed-series').checked).toBe(true);
    });
  });

  describe('Event Handling', () => {
    test('should save to URL when filter checkbox changes', () => {
      DashboardFilters.bindEvents();
      const saveToURLSpy = jest.spyOn(DashboardFilters, 'saveToURL');

      const checkbox = document.getElementById('filter-online');
      checkbox.checked = true;
      checkbox.dispatchEvent(new Event('change', { bubbles: true }));

      // FIXED: Verify saveToURL was actually called (not just that checkbox is checked)
      expect(saveToURLSpy).toHaveBeenCalled();
    });

    test('should call updateFilterCount on bindEvents initialization', () => {
      // The real module calls updateFilterCount() at the end of bindEvents()
      const updateCountSpy = jest.spyOn(DashboardFilters, 'updateFilterCount');

      // Set some filters before binding to verify count is calculated
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      DashboardFilters.bindEvents();

      // FIXED: Verify updateFilterCount was called during bindEvents init
      expect(updateCountSpy).toHaveBeenCalled();
    });

    test('should clear all filters when clear button clicked', () => {
      DashboardFilters.bindEvents();

      // Check some filters
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      // Click clear button
      document.getElementById('clear-filters').click();

      // FIXED: Verify all checkboxes are unchecked
      const checkedBoxes = document.querySelectorAll('input[type="checkbox"]:checked');
      expect(checkedBoxes.length).toBe(0);

      // Verify stored preferences were removed
      expect(storeMock.remove).toHaveBeenCalledWith('pythondeadlines-filter-preferences');
    });
  });

  describe('Complex Filter Combinations', () => {
    test('should handle multiple format filters in URL', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-hybrid').checked = true;
      document.getElementById('filter-in-person').checked = true;

      DashboardFilters.saveToURL();

      const call = window.history.replaceState.mock.calls[0];
      const newUrl = call[2];

      // FIXED: Verify all formats are in URL
      expect(newUrl).toContain('format=');
      expect(newUrl).toMatch(/online/);
      expect(newUrl).toMatch(/hybrid/);
      expect(newUrl).toMatch(/in-person/);
    });

    test('should handle all filter types in URL', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;
      document.getElementById('filter-finaid').checked = true;
      document.getElementById('filter-subscribed-series').checked = true;

      DashboardFilters.saveToURL();

      const call = window.history.replaceState.mock.calls[0];
      const newUrl = call[2];

      // FIXED: Verify all filter types are in URL
      expect(newUrl).toContain('format=online');
      expect(newUrl).toContain('topics=PY');
      expect(newUrl).toContain('features=finaid');
      expect(newUrl).toContain('series=subscribed');
    });
  });

  describe('Filter Persistence', () => {
    test('should save filter state to localStorage on change', () => {
      DashboardFilters.setupFilterPersistence();

      // Trigger a filter change
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-online').dispatchEvent(new Event('change', { bubbles: true }));

      // FIXED: Verify filter state was saved
      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-filter-preferences',
        expect.objectContaining({
          formats: expect.any(Array)
        })
      );
    });

    test('should restore filters from localStorage when no URL params', () => {
      const savedFilters = {
        formats: ['hybrid'],
        topics: ['WEB'],
        features: ['tutorial'],
        subscribedSeries: false
      };

      storeMock.get.mockReturnValue(savedFilters);
      window.location.search = ''; // No URL params

      DashboardFilters.setupFilterPersistence();

      // FIXED: Verify filters were restored
      expect(document.getElementById('filter-hybrid').checked).toBe(true);
      expect(document.getElementById('filter-WEB').checked).toBe(true);
      expect(document.getElementById('filter-tutorial').checked).toBe(true);
    });
  });

  describe('Error Handling', () => {
    test('should require store to be defined for filter persistence', () => {
      // The real module requires store.js to be loaded
      // This test documents that setupFilterPersistence() needs store
      const originalStore = global.store;

      // Remove store
      global.store = undefined;
      window.store = undefined;

      // Calling setupFilterPersistence without store should throw
      // (This is the actual behavior - module depends on store.js)
      expect(() => {
        DashboardFilters.setupFilterPersistence();
      }).toThrow();

      // Restore
      global.store = originalStore;
      window.store = originalStore;
    });

    test('should handle empty URL parameters', () => {
      // Test with no URL params - shouldn't cause errors
      window.location.search = '';

      expect(() => {
        DashboardFilters.loadFromURL();
      }).not.toThrow();
    });
  });
});
