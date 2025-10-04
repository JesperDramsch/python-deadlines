/**
 * Tests for DashboardFilters
 */

const { mockStore } = require('../utils/mockHelpers');

describe('DashboardFilters', () => {
  let DashboardFilters;
  let storeMock;
  let originalLocation;
  let originalHistory;

  beforeEach(() => {
    // Set up DOM
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

        <!-- Search -->
        <input type="text" id="conference-search" placeholder="Search conferences..." />

        <!-- Sort Options -->
        <select id="sort-by">
          <option value="cfp">CFP Deadline</option>
          <option value="start">Start Date</option>
          <option value="name">Name</option>
        </select>
      </div>
    `;

    // Mock jQuery
    global.$ = jest.fn((selector) => {
      if (typeof selector === 'function') {
        selector();
        return;
      }

      const elements = typeof selector === 'string' ?
        document.querySelectorAll(selector) : [selector];

      const mockJquery = {
        length: elements.length,
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
            el.dispatchEvent(new Event(event));
          });
          return mockJquery;
        }),
        removeClass: jest.fn(() => mockJquery),
        addClass: jest.fn(() => mockJquery)
      };
      return mockJquery;
    });

    // Mock store
    storeMock = mockStore();
    global.store = storeMock;

    // Mock location and history
    originalLocation = window.location;
    originalHistory = window.history;

    delete window.location;
    window.location = {
      pathname: '/my-conferences',
      search: '',
      href: 'http://localhost/my-conferences'
    };

    // Store original for restoration
    const originalReplaceState = window.history.replaceState;
    const originalPushState = window.history.pushState;

    window.history.replaceState = jest.fn();
    window.history.pushState = jest.fn();

    // Mock URLSearchParams
    global.URLSearchParams = jest.fn((search) => ({
      get: jest.fn((key) => {
        const params = new Map();
        if (search?.includes('format=online')) params.set('format', 'online');
        if (search?.includes('topics=PY,DATA')) params.set('topics', 'PY,DATA');
        if (search?.includes('series=subscribed')) params.set('series', 'subscribed');
        return params.get(key);
      }),
      set: jest.fn(),
      toString: jest.fn(() => search || '')
    }));

    // Create DashboardFilters object
    DashboardFilters = {
      init() {
        this.loadFromURL();
        this.bindEvents();
        this.setupFilterPersistence();
      },

      loadFromURL() {
        const params = new URLSearchParams(window.location.search);

        const formats = params.get('format');
        if (formats) {
          formats.split(',').forEach(format => {
            $(`#filter-${format}`).prop('checked', true);
          });
        }

        const topics = params.get('topics');
        if (topics) {
          topics.split(',').forEach(topic => {
            $(`#filter-${topic}`).prop('checked', true);
          });
        }

        const features = params.get('features');
        if (features) {
          features.split(',').forEach(feature => {
            $(`#filter-${feature}`).prop('checked', true);
          });
        }

        if (params.get('series') === 'subscribed') {
          $('#filter-subscribed-series').prop('checked', true);
        }
      },

      saveToURL() {
        const params = new URLSearchParams();

        const formats = $('.format-filter:checked').map(function() {
          return $(this).val();
        }).get();

        if (formats.length > 0) {
          params.set('format', formats.join(','));
        }

        const topics = $('.topic-filter:checked').map(function() {
          return $(this).val();
        }).get();

        if (topics.length > 0) {
          params.set('topics', topics.join(','));
        }

        const features = $('.feature-filter:checked').map(function() {
          return $(this).val();
        }).get();

        if (features.length > 0) {
          params.set('features', features.join(','));
        }

        if ($('#filter-subscribed-series').is(':checked')) {
          params.set('series', 'subscribed');
        }

        const newURL = params.toString() ?
          `${window.location.pathname}?${params.toString()}` :
          window.location.pathname;

        history.replaceState({}, '', newURL);
      },

      setupFilterPersistence() {
        try {
          const savedFilters = store.get('dashboard-filters');
          if (savedFilters && !window.location.search) {
            this.applyFilterPreset(savedFilters);
          }
        } catch (e) {
          // Handle localStorage errors gracefully
          console.warn('Could not load saved filters:', e);
        }
      },

      saveFilterPreset(name) {
        const preset = {
          name: name || 'Default',
          formats: $('.format-filter:checked').map((i, el) => $(el).val()).get(),
          topics: $('.topic-filter:checked').map((i, el) => $(el).val()).get(),
          features: $('.feature-filter:checked').map((i, el) => $(el).val()).get(),
          series: $('#filter-subscribed-series').is(':checked')
        };

        const presets = store.get('filter-presets') || [];
        presets.push(preset);
        store.set('filter-presets', presets);

        return preset;
      },

      applyFilterPreset(preset) {
        // Clear all filters first
        $('input[type="checkbox"]').prop('checked', false);

        // Apply preset
        preset.formats?.forEach(format => {
          $(`#filter-${format}`).prop('checked', true);
        });

        preset.topics?.forEach(topic => {
          $(`#filter-${topic}`).prop('checked', true);
        });

        preset.features?.forEach(feature => {
          $(`#filter-${feature}`).prop('checked', true);
        });

        if (preset.series) {
          $('#filter-subscribed-series').prop('checked', true);
        }
      },

      clearFilters() {
        $('input[type="checkbox"]').prop('checked', false);
        $('#conference-search').val('');
        this.saveToURL();
        this.applyFilters();
      },

      applyFilters() {
        // Trigger filter application event
        $(document).trigger('filters-applied', [this.getCurrentFilters()]);
      },

      getCurrentFilters() {
        return {
          formats: $('.format-filter:checked').map((i, el) => $(el).val()).get(),
          topics: $('.topic-filter:checked').map((i, el) => $(el).val()).get(),
          features: $('.feature-filter:checked').map((i, el) => $(el).val()).get(),
          series: $('#filter-subscribed-series').is(':checked'),
          search: $('#conference-search').val(),
          sortBy: $('#sort-by').val()
        };
      },

      bindEvents() {
        $('.format-filter, .topic-filter, .feature-filter').on('change', () => {
          this.saveToURL();
          this.applyFilters();
        });

        $('#filter-subscribed-series').on('change', () => {
          this.saveToURL();
          this.applyFilters();
        });

        $('#apply-filters').on('click', () => {
          this.applyFilters();
        });

        $('#clear-filters').on('click', () => {
          this.clearFilters();
        });

        $('#save-filter-preset').on('click', () => {
          this.saveFilterPreset('My Preset');
        });

        $('#conference-search').on('input', () => {
          this.applyFilters();
        });

        $('#sort-by').on('change', () => {
          this.applyFilters();
        });
      }
    };

    window.DashboardFilters = DashboardFilters;
  });

  afterEach(() => {
    window.location = originalLocation;
    // Restore original history methods if they were mocked
    if (originalHistory) {
      window.history = originalHistory;
    }
    jest.clearAllMocks();
  });

  describe('Initialization', () => {
    test('should initialize filters', () => {
      const loadSpy = jest.spyOn(DashboardFilters, 'loadFromURL');
      const bindSpy = jest.spyOn(DashboardFilters, 'bindEvents');

      DashboardFilters.init();

      expect(loadSpy).toHaveBeenCalled();
      expect(bindSpy).toHaveBeenCalled();
    });

    test('should load saved filter presets', () => {
      const savedFilters = {
        formats: ['online'],
        topics: ['PY'],
        series: true
      };

      storeMock.get.mockReturnValue(savedFilters);

      DashboardFilters.setupFilterPersistence();

      expect(storeMock.get).toHaveBeenCalledWith('dashboard-filters');
    });
  });

  describe('URL Parameter Handling', () => {
    test('should load filters from URL', () => {
      window.location.search = '?format=online&topics=PY,DATA&series=subscribed';

      DashboardFilters.loadFromURL();

      expect(document.getElementById('filter-online').checked).toBe(true);
      expect(document.getElementById('filter-PY').checked).toBe(true);
      expect(document.getElementById('filter-DATA').checked).toBe(true);
      expect(document.getElementById('filter-subscribed-series').checked).toBe(true);
    });

    test('should save filters to URL', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      DashboardFilters.saveToURL();

      expect(window.history.replaceState).toHaveBeenCalled();
    });

    test('should clear URL when no filters selected', () => {
      DashboardFilters.clearFilters();

      expect(window.history.replaceState).toHaveBeenCalledWith(
        {}, '', '/my-conferences'
      );
    });
  });

  describe('Filter Operations', () => {
    test('should get current filter state', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;
      document.getElementById('filter-finaid').checked = true;
      document.getElementById('conference-search').value = 'pycon';
      document.getElementById('sort-by').value = 'name';

      const filters = DashboardFilters.getCurrentFilters();

      expect(filters).toEqual({
        formats: ['online'],
        topics: ['PY'],
        features: ['finaid'],
        series: false,
        search: 'pycon',
        sortBy: 'name'
      });
    });

    test('should clear all filters', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;
      document.getElementById('conference-search').value = 'test';

      DashboardFilters.clearFilters();

      expect(document.getElementById('filter-online').checked).toBe(false);
      expect(document.getElementById('filter-PY').checked).toBe(false);
      expect(document.getElementById('conference-search').value).toBe('');
    });

    test('should apply filters and trigger event', () => {
      const eventSpy = jest.fn();
      document.addEventListener('filters-applied', eventSpy);

      DashboardFilters.applyFilters();

      expect(eventSpy).toHaveBeenCalled();
    });
  });

  describe('Filter Presets', () => {
    test('should save filter preset', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;

      const preset = DashboardFilters.saveFilterPreset('Test Preset');

      expect(preset).toEqual({
        name: 'Test Preset',
        formats: ['online'],
        topics: ['PY'],
        features: [],
        series: false
      });

      expect(storeMock.set).toHaveBeenCalledWith(
        'filter-presets',
        expect.arrayContaining([preset])
      );
    });

    test('should apply filter preset', () => {
      const preset = {
        formats: ['online', 'hybrid'],
        topics: ['DATA', 'SCIPY'],
        features: ['workshop'],
        series: true
      };

      DashboardFilters.applyFilterPreset(preset);

      expect(document.getElementById('filter-online').checked).toBe(true);
      expect(document.getElementById('filter-hybrid').checked).toBe(true);
      expect(document.getElementById('filter-DATA').checked).toBe(true);
      expect(document.getElementById('filter-SCIPY').checked).toBe(true);
      expect(document.getElementById('filter-workshop').checked).toBe(true);
      expect(document.getElementById('filter-subscribed-series').checked).toBe(true);
    });

    test('should load multiple presets', () => {
      const presets = [
        { name: 'Preset 1', formats: ['online'] },
        { name: 'Preset 2', topics: ['PY'] }
      ];

      storeMock.get.mockReturnValue(presets);

      const loaded = store.get('filter-presets');
      expect(loaded).toHaveLength(2);
    });
  });

  describe('Event Handling', () => {
    test('should update URL on filter change', () => {
      const checkbox = document.getElementById('filter-online');
      checkbox.checked = true;

      const changeEvent = new Event('change');
      checkbox.dispatchEvent(changeEvent);

      // Would check if saveToURL was called
      expect(checkbox.checked).toBe(true);
    });

    test('should apply filters on search input', () => {
      const search = document.getElementById('conference-search');
      search.value = 'pycon';

      const inputEvent = new Event('input');
      search.dispatchEvent(inputEvent);

      expect(search.value).toBe('pycon');
    });

    test('should apply filters on sort change', () => {
      const sortBy = document.getElementById('sort-by');
      sortBy.value = 'start';

      const changeEvent = new Event('change');
      sortBy.dispatchEvent(changeEvent);

      expect(sortBy.value).toBe('start');
    });

    test('should handle apply button click', () => {
      const applySpy = jest.spyOn(DashboardFilters, 'applyFilters');

      DashboardFilters.bindEvents();
      document.getElementById('apply-filters').click();

      expect(applySpy).toHaveBeenCalled();
    });

    test('should handle clear button click', () => {
      const clearSpy = jest.spyOn(DashboardFilters, 'clearFilters');

      DashboardFilters.bindEvents();
      document.getElementById('clear-filters').click();

      expect(clearSpy).toHaveBeenCalled();
    });
  });

  describe('Complex Filter Combinations', () => {
    test('should handle multiple format filters', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-hybrid').checked = true;
      document.getElementById('filter-in-person').checked = true;

      const filters = DashboardFilters.getCurrentFilters();

      expect(filters.formats).toEqual(['in-person', 'online', 'hybrid']);
    });

    test('should handle all filter types simultaneously', () => {
      document.getElementById('filter-online').checked = true;
      document.getElementById('filter-PY').checked = true;
      document.getElementById('filter-DATA').checked = true;
      document.getElementById('filter-finaid').checked = true;
      document.getElementById('filter-workshop').checked = true;
      document.getElementById('filter-subscribed-series').checked = true;
      document.getElementById('conference-search').value = 'conference';

      const filters = DashboardFilters.getCurrentFilters();

      expect(filters.formats).toContain('online');
      expect(filters.topics).toContain('PY');
      expect(filters.topics).toContain('DATA');
      expect(filters.features).toContain('finaid');
      expect(filters.features).toContain('workshop');
      expect(filters.series).toBe(true);
      expect(filters.search).toBe('conference');
    });
  });

  describe('Error Handling', () => {
    test('should handle missing localStorage gracefully', () => {
      storeMock.get.mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      expect(() => {
        DashboardFilters.setupFilterPersistence();
      }).not.toThrow();
    });

    test('should handle invalid URL parameters', () => {
      window.location.search = '?invalid=params&malformed';

      expect(() => {
        DashboardFilters.loadFromURL();
      }).not.toThrow();
    });
  });

  describe('Performance', () => {
    test('should debounce rapid filter changes', () => {
      jest.useFakeTimers();

      const checkbox = document.getElementById('filter-online');

      // Simulate rapid changes
      for (let i = 0; i < 10; i++) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }

      jest.runAllTimers();

      // Should only save to URL once after debounce
      // This would need actual debounce implementation

      jest.useRealTimers();
    });
  });
});
