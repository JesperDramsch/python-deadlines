/**
 * Tests for DashboardManager
 * FIXED: Tests the REAL module, not an inline mock
 */

const {
  mockNotificationAPI,
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

describe('DashboardManager', () => {
  let DashboardManager;
  let mockConfManager;
  let storeMock;
  let originalLocation;

  beforeEach(() => {
    // Set up DOM for dashboard page
    document.body.innerHTML = `
      <div id="loading-state" style="display: none;">Loading...</div>
      <div id="empty-state" style="display: none;">No conferences</div>
      <div id="conference-cards"></div>
      <div id="conference-count"></div>
      <div id="series-predictions"></div>
      <div id="conference-container"></div>
      <div id="notification-prompt" style="display: none;"></div>
      <div id="notification-settings"></div>
      <div id="notificationModal"></div>
      <button id="save-notification-settings"></button>
      <input type="checkbox" class="notify-days" value="7" />
      <input type="checkbox" id="notify-new-editions" />
      <input type="checkbox" id="auto-favorite-series" />
      <input type="checkbox" class="format-filter" value="in-person" />
      <input type="checkbox" class="format-filter" value="virtual" />
      <input type="checkbox" class="format-filter" value="hybrid" />
      <input type="checkbox" class="topic-filter" value="PY" />
      <input type="checkbox" class="topic-filter" value="DATA" />
      <input type="checkbox" class="feature-filter" value="finaid" />
      <input type="checkbox" class="feature-filter" value="workshop" />
      <input type="checkbox" class="feature-filter" value="sponsor" />
      <input type="checkbox" id="filter-subscribed-series" />
      <button id="clear-filters">Clear</button>
      <button id="clear-filters-inline" style="display: none;">Clear inline</button>
      <button id="view-grid">Grid</button>
      <button id="view-list">List</button>
      <button id="export-favorites">Export</button>
    `;

    // Mock store
    storeMock = mockStore();
    global.store = storeMock;
    window.store = storeMock;

    // Mock luxon DateTime for date parsing
    global.luxon = {
      DateTime: {
        fromSQL: jest.fn((dateStr) => {
          if (!dateStr) {
            return { isValid: false, toFormat: () => 'TBA', toJSDate: () => new Date() };
          }
          const date = new Date(dateStr.replace(' ', 'T'));
          return {
            isValid: !isNaN(date.getTime()),
            toFormat: jest.fn((format) => {
              if (format === 'MMM dd, yyyy') return 'Feb 15, 2025';
              if (format === 'MMM dd') return 'Feb 15';
              return dateStr;
            }),
            toJSDate: () => date
          };
        }),
        fromISO: jest.fn((dateStr) => {
          if (!dateStr) {
            return { isValid: false, toFormat: () => 'TBA', toJSDate: () => new Date() };
          }
          const date = new Date(dateStr);
          return {
            isValid: !isNaN(date.getTime()),
            toFormat: jest.fn((format) => {
              if (format === 'MMM dd, yyyy') return 'Feb 15, 2025';
              if (format === 'MMM dd') return 'Feb 15';
              return dateStr;
            }),
            toJSDate: () => date
          };
        }),
        invalid: jest.fn((reason) => ({
          isValid: false,
          toFormat: () => 'TBA',
          toJSDate: () => new Date()
        }))
      }
    };
    window.luxon = global.luxon;

    // Mock ConferenceStateManager
    const savedConferences = [
      {
        id: 'pycon-2025',
        conference: 'PyCon US',
        year: 2025,
        cfp: '2025-02-15 23:59:00',
        start: '2025-05-01',
        end: '2025-05-05',
        place: 'Pittsburgh, PA',
        format: 'in-person',
        sub: 'PY',
        has_finaid: 'true',
        link: 'https://pycon.org',
        cfp_link: 'https://pycon.org/cfp'
      },
      {
        id: 'europython-2025',
        conference: 'EuroPython',
        year: 2025,
        cfp: '2025-03-01 23:59:00',
        start: '2025-07-14',
        end: '2025-07-20',
        place: 'Prague',
        format: 'hybrid',
        sub: 'PY,DATA',
        has_workshop: 'true',
        link: 'https://europython.eu'
      }
    ];

    mockConfManager = {
      getSavedEvents: jest.fn(() => savedConferences),
      isEventSaved: jest.fn((id) => savedConferences.some(c => c.id === id)),
      removeSavedEvent: jest.fn(),
      isSeriesFollowed: jest.fn(() => false)
    };
    window.confManager = mockConfManager;

    // Mock FavoritesManager (used for export and toast)
    window.FavoritesManager = {
      showToast: jest.fn(),
      exportFavorites: jest.fn()
    };

    // Mock Notification API
    global.Notification = {
      permission: 'default'
    };
    window.Notification = global.Notification;

    // Mock Bootstrap modal
    $.fn = $.fn || {};
    $.fn.modal = jest.fn();

    // Mock location for dashboard page
    originalLocation = window.location;
    delete window.location;
    window.location = {
      pathname: '/my-conferences',
      href: 'http://localhost/my-conferences'
    };

    // Mock window.conferenceTypes for badge colors
    window.conferenceTypes = [
      { sub: 'PY', color: '#3776ab' },
      { sub: 'DATA', color: '#f68e56' }
    ];

    // Use real jQuery from setup.js - just mock Bootstrap plugins
    // that aren't available in the test environment
    $.fn.modal = jest.fn(function() { return this; });
    $.fn.countdown = jest.fn(function() { return this; });

    // Override show/hide to explicitly set display (tests expect specific values)
    $.fn.show = function() {
      this.each(function() {
        this.style.display = 'block';
      });
      return this;
    };
    $.fn.hide = function() {
      this.each(function() {
        this.style.display = 'none';
      });
      return this;
    };

    // Mock fadeOut to execute callback immediately (no animation in tests)
    $.fn.fadeOut = function(duration, callback) {
      if (typeof duration === 'function') {
        callback = duration;
      }
      this.each(function() {
        if (callback) callback.call($(this));
      });
      return this;
    };

    // Store document ready callback for manual execution if needed
    const originalReady = $.fn.ready;
    $.fn.ready = jest.fn(function(callback) {
      // Execute immediately since DOM is already ready in tests
      if (callback) callback();
      return this;
    });

    // Also handle $(function) shorthand
    const original$ = global.$;
    global.$ = function(selector) {
      if (typeof selector === 'function') {
        // Document ready shorthand - execute immediately
        selector();
        return;
      }
      return original$(selector);
    };
    // Copy over jQuery properties
    Object.keys(original$).forEach(key => {
      global.$[key] = original$[key];
    });
    global.$.fn = original$.fn;
    global.$.each = original$.each;
    global.$.extend = original$.extend;
    global.$.ajax = original$.ajax;


    // Load the REAL module using jest.isolateModules
    jest.isolateModules(() => {
      require('../../../static/js/dashboard.js');
    });

    // Get the real DashboardManager from window
    DashboardManager = window.DashboardManager;

    // Reset state for each test
    DashboardManager.conferences = [];
    DashboardManager.filteredConferences = [];
    DashboardManager.viewMode = 'grid';
  });

  afterEach(() => {
    window.location = originalLocation;
    delete window.confManager;
    delete window.DashboardManager;
    delete window.FavoritesManager;
    delete window.conferenceTypes;
    delete global.luxon;
    jest.clearAllMocks();
  });

  describe('Initialization', () => {
    test('should initialize on dashboard page', () => {
      const loadSpy = jest.spyOn(DashboardManager, 'loadConferences');
      const setupViewSpy = jest.spyOn(DashboardManager, 'setupViewToggle');
      const setupNotifSpy = jest.spyOn(DashboardManager, 'setupNotifications');
      const bindEventsSpy = jest.spyOn(DashboardManager, 'bindEvents');

      DashboardManager.init();

      expect(loadSpy).toHaveBeenCalled();
      expect(setupViewSpy).toHaveBeenCalled();
      expect(setupNotifSpy).toHaveBeenCalled();
      expect(bindEventsSpy).toHaveBeenCalled();
    });

    test('should not initialize on non-dashboard pages', () => {
      window.location.pathname = '/about';
      const loadSpy = jest.spyOn(DashboardManager, 'loadConferences');

      DashboardManager.init();

      expect(loadSpy).not.toHaveBeenCalled();
    });

    test('should load saved view preference on init', () => {
      storeMock.get.mockReturnValue('list');
      const setViewSpy = jest.spyOn(DashboardManager, 'setViewMode');

      DashboardManager.init();

      expect(storeMock.get).toHaveBeenCalledWith('pythondeadlines-view-mode');
      expect(setViewSpy).toHaveBeenCalledWith('list');
    });

    test('should initialize on /my-conferences page', () => {
      window.location.pathname = '/my-conferences';
      const loadSpy = jest.spyOn(DashboardManager, 'loadConferences');

      DashboardManager.init();

      expect(loadSpy).toHaveBeenCalled();
    });

    test('should initialize on /dashboard page', () => {
      window.location.pathname = '/dashboard';
      const loadSpy = jest.spyOn(DashboardManager, 'loadConferences');

      DashboardManager.init();

      expect(loadSpy).toHaveBeenCalled();
    });
  });

  describe('Conference Loading', () => {
    test('should load conferences from ConferenceStateManager', () => {
      DashboardManager.loadConferences();

      expect(mockConfManager.getSavedEvents).toHaveBeenCalled();
      expect(DashboardManager.conferences).toHaveLength(2);
    });

    test('should show and hide loading state', () => {
      const loadingState = document.getElementById('loading-state');

      DashboardManager.loadConferences();

      // Loading state should be hidden after loading completes
      expect(loadingState.style.display).toBe('none');
    });

    test('should wait for ConferenceStateManager if not ready', () => {
      jest.useFakeTimers();
      const setTimeoutSpy = jest.spyOn(global, 'setTimeout');
      const originalConfManager = window.confManager;
      delete window.confManager;

      DashboardManager.loadConferences();

      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 100);

      // Restore and run timer
      window.confManager = originalConfManager;
      jest.runAllTimers();

      expect(mockConfManager.getSavedEvents).toHaveBeenCalled();
      jest.useRealTimers();
      setTimeoutSpy.mockRestore();
    });

    test('should check empty state after loading', () => {
      const checkEmptySpy = jest.spyOn(DashboardManager, 'checkEmptyState');

      DashboardManager.loadConferences();

      expect(checkEmptySpy).toHaveBeenCalled();
    });

    test('should apply filters after loading conferences', () => {
      const applyFiltersSpy = jest.spyOn(DashboardManager, 'applyFilters');

      DashboardManager.loadConferences();

      expect(applyFiltersSpy).toHaveBeenCalled();
    });
  });

  describe('Filtering', () => {
    beforeEach(() => {
      DashboardManager.loadConferences();
    });

    test('should filter by format', () => {
      // Check "hybrid" format filter (EuroPython is hybrid)
      document.querySelector('.format-filter[value="hybrid"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].format).toBe('hybrid');
    });

    test('should filter by topic', () => {
      // Check "DATA" topic filter (only EuroPython has DATA)
      document.querySelector('.topic-filter[value="DATA"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].sub).toContain('DATA');
    });

    test('should filter by features - finaid', () => {
      // Check "finaid" feature filter (only PyCon has finaid)
      document.querySelector('.feature-filter[value="finaid"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].has_finaid).toBe('true');
    });

    test('should filter by features - workshop', () => {
      // Check "workshop" feature filter (only EuroPython has workshop)
      document.querySelector('.feature-filter[value="workshop"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].has_workshop).toBe('true');
    });

    test('should apply multiple filters', () => {
      // Filter by in-person + PY topic
      document.querySelector('.format-filter[value="in-person"]').checked = true;
      document.querySelector('.topic-filter[value="PY"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].conference).toBe('PyCon US');
    });

    test('should show message when no conferences match filters', () => {
      // Apply filter that matches nothing
      document.querySelector('.format-filter[value="virtual"]').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(0);
      const container = document.getElementById('conference-cards');
      expect(container.innerHTML).toContain('No conferences match');
    });

    test('should filter by subscribed series', () => {
      mockConfManager.isSeriesFollowed = jest.fn((confName) => confName === 'PyCon US');
      document.getElementById('filter-subscribed-series').checked = true;

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(1);
      expect(DashboardManager.filteredConferences[0].conference).toBe('PyCon US');
    });

    test('should show all conferences when no filters selected', () => {
      // Ensure no filters are checked
      document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);

      DashboardManager.applyFilters();

      expect(DashboardManager.filteredConferences).toHaveLength(2);
    });
  });

  describe('Conference Rendering', () => {
    beforeEach(() => {
      DashboardManager.loadConferences();
    });

    test('should render conference cards', () => {
      DashboardManager.renderConferences();

      const container = document.getElementById('conference-cards');
      expect(container.children.length).toBeGreaterThan(0);
    });

    test('should sort conferences by CFP deadline', () => {
      DashboardManager.renderConferences();

      // PyCon (Feb 15) should come before EuroPython (Mar 1)
      expect(DashboardManager.filteredConferences[0].conference).toBe('PyCon US');
      expect(DashboardManager.filteredConferences[1].conference).toBe('EuroPython');
    });

    test('should update conference count', () => {
      DashboardManager.renderConferences();

      const count = document.getElementById('conference-count');
      expect(count.textContent).toBe('2 conferences');
    });

    test('should handle single conference count correctly', () => {
      DashboardManager.filteredConferences = [DashboardManager.conferences[0]];
      DashboardManager.renderConferences();

      const count = document.getElementById('conference-count');
      expect(count.textContent).toBe('1 conference');
    });

    test('should initialize countdowns after rendering', () => {
      const initCountdownSpy = jest.spyOn(DashboardManager, 'initializeCountdowns');

      DashboardManager.renderConferences();

      expect(initCountdownSpy).toHaveBeenCalled();
    });
  });

  describe('Conference Card Creation', () => {
    test('should create conference card with correct data', () => {
      const conf = {
        id: 'test-conf',
        conference: 'Test Conference',
        year: 2025,
        cfp: '2025-02-15 23:59:00',
        start: '2025-05-01',
        end: '2025-05-05',
        place: 'Test City',
        format: 'in-person',
        link: 'https://test.com'
      };

      const card = DashboardManager.createConferenceCard(conf);

      // Card returns jQuery object
      expect(card).toBeDefined();
      expect(card.length).toBeGreaterThan(0);

      // Get the DOM element
      const element = card[0];
      expect(element.innerHTML).toContain('Test Conference');
      expect(element.innerHTML).toContain('2025');
    });

    test('should handle SQL date format', () => {
      const conf = {
        id: 'test',
        conference: 'Test',
        year: 2025,
        cfp: '2025-02-15 23:59:00'
      };

      DashboardManager.createConferenceCard(conf);

      expect(global.luxon.DateTime.fromSQL).toHaveBeenCalledWith('2025-02-15 23:59:00');
    });

    test('should handle ISO date format', () => {
      const conf = {
        id: 'test',
        conference: 'Test',
        year: 2025,
        cfp: '2025-02-15T23:59:00'
      };

      DashboardManager.createConferenceCard(conf);

      expect(global.luxon.DateTime.fromISO).toHaveBeenCalledWith('2025-02-15T23:59:00');
    });

    test('should use extended CFP deadline if available', () => {
      const conf = {
        id: 'test',
        conference: 'Test',
        year: 2025,
        cfp: '2025-02-15 23:59:00',
        cfp_ext: '2025-02-28 23:59:00'
      };

      DashboardManager.createConferenceCard(conf);

      expect(global.luxon.DateTime.fromSQL).toHaveBeenCalledWith('2025-02-28 23:59:00');
    });

    test('should display feature badges', () => {
      const conf = {
        id: 'test',
        conference: 'Test',
        year: 2025,
        cfp: '2025-02-15 23:59:00',
        has_finaid: 'true',
        has_workshop: 'true'
      };

      const card = DashboardManager.createConferenceCard(conf);
      const element = card[0];

      expect(element.innerHTML).toContain('Financial Aid');
      expect(element.innerHTML).toContain('Workshops');
    });

    test('should display topic badges', () => {
      const conf = {
        id: 'test',
        conference: 'Test',
        year: 2025,
        cfp: '2025-02-15 23:59:00',
        sub: 'PY,DATA'
      };

      const card = DashboardManager.createConferenceCard(conf);
      const element = card[0];

      expect(element.innerHTML).toContain('PY');
      expect(element.innerHTML).toContain('DATA');
    });
  });

  describe('View Mode', () => {
    beforeEach(() => {
      DashboardManager.loadConferences();
    });

    test('should toggle between grid and list view', () => {
      DashboardManager.viewMode = 'grid';

      DashboardManager.setViewMode('list');

      expect(DashboardManager.viewMode).toBe('list');
    });

    test('should save view preference to store', () => {
      DashboardManager.setViewMode('list');

      expect(storeMock.set).toHaveBeenCalledWith('pythondeadlines-view-mode', 'list');
    });

    test('should re-render conferences when view mode changes', () => {
      const renderSpy = jest.spyOn(DashboardManager, 'renderConferences');
      DashboardManager.filteredConferences = DashboardManager.conferences;

      DashboardManager.setViewMode('list');

      expect(renderSpy).toHaveBeenCalled();
    });

    test('should not re-render if no conferences loaded', () => {
      DashboardManager.filteredConferences = [];
      const renderSpy = jest.spyOn(DashboardManager, 'renderConferences');

      DashboardManager.setViewMode('list');

      expect(renderSpy).not.toHaveBeenCalled();
    });
  });

  describe('Empty State', () => {
    test('should show empty state when no conferences', () => {
      mockConfManager.getSavedEvents.mockReturnValue([]);

      DashboardManager.loadConferences();

      const emptyState = document.getElementById('empty-state');
      expect(emptyState.style.display).toBe('block');
    });

    test('should hide empty state when conferences exist', () => {
      DashboardManager.loadConferences();

      const emptyState = document.getElementById('empty-state');
      expect(emptyState.style.display).toBe('none');
    });

    test('should hide series predictions when no conferences', () => {
      mockConfManager.getSavedEvents.mockReturnValue([]);
      DashboardManager.loadConferences();

      const seriesPredictions = document.getElementById('series-predictions');
      expect(seriesPredictions.style.display).toBe('none');
    });
  });

  describe('Event Binding', () => {
    test('should bind filter change events', () => {
      DashboardManager.loadConferences();
      const applySpy = jest.spyOn(DashboardManager, 'applyFilters');

      DashboardManager.bindEvents();

      // Trigger filter change
      const formatFilter = document.querySelector('.format-filter');
      formatFilter.dispatchEvent(new Event('change'));

      expect(applySpy).toHaveBeenCalled();
    });

    test('should handle clear filters button', () => {
      DashboardManager.loadConferences();
      DashboardManager.bindEvents();

      // Check some filters
      document.querySelector('.format-filter').checked = true;
      document.querySelector('.topic-filter').checked = true;

      // Click clear
      document.getElementById('clear-filters').click();

      // Filters should be unchecked
      expect(document.querySelector('.format-filter').checked).toBe(false);
      expect(document.querySelector('.topic-filter').checked).toBe(false);
    });

    test('should listen for favorite changes', () => {
      DashboardManager.bindEvents();
      const loadSpy = jest.spyOn(DashboardManager, 'loadConferences');

      // Trigger favorite:added event
      document.dispatchEvent(new Event('favorite:added'));

      expect(loadSpy).toHaveBeenCalled();
    });
  });

  describe('Notification Setup', () => {
    test('should show notification prompt if browser supports and permission is default', () => {
      global.Notification = { permission: 'default' };
      window.Notification = global.Notification;

      DashboardManager.setupNotifications();

      const notifPrompt = document.getElementById('notification-prompt');
      expect(notifPrompt.style.display).toBe('block');
    });

    test('should not show notification prompt if permission already granted', () => {
      // Reset prompt to hidden state (simulating fresh page load)
      const notifPrompt = document.getElementById('notification-prompt');
      notifPrompt.style.display = 'none';

      global.Notification = { permission: 'granted' };
      window.Notification = global.Notification;

      DashboardManager.setupNotifications();

      // When permission is granted, the prompt should NOT be shown
      // (the real code only calls .show() when permission is 'default')
      expect(notifPrompt.style.display).toBe('none');
    });
  });

  describe('Format Type Helper', () => {
    test('should format virtual type', () => {
      expect(DashboardManager.formatType('virtual')).toBe('Virtual');
    });

    test('should format hybrid type', () => {
      expect(DashboardManager.formatType('hybrid')).toBe('Hybrid');
    });

    test('should format in-person type', () => {
      expect(DashboardManager.formatType('in-person')).toBe('In-Person');
    });

    test('should return Unknown for unrecognized type', () => {
      expect(DashboardManager.formatType('something-else')).toBe('Unknown');
    });
  });
});
