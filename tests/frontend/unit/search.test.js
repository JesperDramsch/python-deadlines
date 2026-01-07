/**
 * Tests for Search Functionality
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

describe('Search Module', () => {
  let originalLuxon;
  let timerController;

  beforeEach(() => {
    // Set up DOM
    document.body.innerHTML = `
      <div id="search-results"></div>
      <input id="search-box" type="text" />
      <div id="filter-container"></div>
    `;

    // Mock Luxon
    originalLuxon = global.luxon;
    global.luxon = {
      DateTime: {
        fromSQL: jest.fn((date, options) => ({
          invalid: false,
          toJSDate: () => new Date(date),
          toISO: () => new Date(date).toISOString(),
          toLocaleString: () => new Date(date).toLocaleString(),
          diffNow: () => ({
            toObject: () => ({ seconds: 86400 }) // 1 day in future
          })
        })),
        DATETIME_HUGE: 'DATETIME_HUGE'
      }
    };

    // Use real jQuery from setup.js, just mock the countdown plugin
    // (countdown is a third-party plugin not included in test environment)
    $.fn.countdown = jest.fn(function(date, callback) {
      // Simulate countdown callback with mock event
      if (callback) {
        callback.call(this, { strftime: () => '10 days 05h 30m 00s' });
      }
      return this;
    });

    // Mock calendar creation
    global.createCalendarFromObject = jest.fn(() => {
      const elem = document.createElement('div');
      elem.className = 'calendar-widget';
      return elem;
    });

    timerController = new TimerController();
    timerController.setCurrentTime('2024-01-15 12:00:00');

    // Load search module
    jest.isolateModules(() => {
      require('../../../static/js/search.js');
    });
  });

  afterEach(() => {
    global.luxon = originalLuxon;
    delete global.createCalendarFromObject;
    timerController.cleanup();
  });

  describe('displaySearchResults', () => {
    test('should display search results correctly', () => {
      const results = [
        { ref: 'conf-1', score: 0.9 },
        { ref: 'conf-2', score: 0.8 }
      ];

      const docs = {
        'conf-1': {
          conference: 'PyCon US',
          year: 2025,
          title: 'PyCon US 2025',
          url: '/conference/pycon-us-2025',
          link: 'https://pycon.org',
          cfp: '2025-02-15 23:59:00',
          place: 'Pittsburgh, PA',
          timezone: 'America/New_York',
          subs: 'PY,SCIPY',
          content: 'The largest Python conference'
        },
        'conf-2': {
          conference: 'EuroPython',
          year: 2025,
          title: 'EuroPython 2025',
          url: '/conference/europython-2025',
          link: 'https://europython.eu',
          cfp: '2025-03-01 23:59:00',
          place: 'Dublin, Ireland',
          timezone: 'Europe/Dublin',
          subs: 'PY',
          content: 'European Python conference'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('PyCon US 2025');
      expect(searchResults.innerHTML).toContain('EuroPython 2025');
      expect(searchResults.innerHTML).toContain('Pittsburgh, PA');
      expect(searchResults.innerHTML).toContain('Dublin, Ireland');
    });

    test('should show no results message when empty', () => {
      window.displaySearchResults([], {});

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('No results found');
    });

    test('should handle missing documents gracefully', () => {
      const results = [
        { ref: 'conf-1', score: 0.9 },
        { ref: 'missing-conf', score: 0.8 }
      ];

      const docs = {
        'conf-1': {
          conference: 'PyCon US',
          year: 2025,
          title: 'PyCon US 2025',
          url: '/conference/pycon-us-2025'
        }
      };

      // Should not throw error
      expect(() => {
        window.displaySearchResults(results, docs);
      }).not.toThrow();

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('PyCon US 2025');
      expect(searchResults.innerHTML).not.toContain('missing-conf');
    });

    test('should create calendar buttons for conferences', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          conference: 'PyCon US',
          year: 2025,
          title: 'PyCon US 2025',
          cfp: '2025-02-15 23:59:00',
          place: 'Pittsburgh, PA',
          link: 'https://pycon.org'
        }
      };

      window.displaySearchResults(results, docs);

      expect(global.createCalendarFromObject).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'PyCon US 2025 deadline',
          place: 'Pittsburgh, PA',
          link: 'https://pycon.org'
        })
      );
    });

    test('should handle conferences with TBA dates', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Future Conf',
          cfp: 'TBA',
          place: 'TBA'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('TBA');
    });

    test('should display countdown timer for future deadlines', () => {
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 10);

      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Future Conf',
          cfp: futureDate.toISOString().replace('T', ' ').slice(0, 19),
          timezone: 'UTC'
        }
      };

      // Mock Luxon to return future date
      global.luxon.DateTime.fromSQL.mockReturnValue({
        invalid: false,
        toJSDate: () => futureDate,
        toISO: () => futureDate.toISOString(),
        toLocaleString: () => futureDate.toLocaleString(),
        diffNow: () => ({
          toObject: () => ({ seconds: 864000 }) // 10 days in future
        })
      });

      window.displaySearchResults(results, docs);

      expect(global.$.fn.countdown).toBeDefined();
      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('search-timer');
    });

    test('should show "Deadline passed" for past conferences', () => {
      const pastDate = new Date('2020-01-01');

      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Past Conf',
          cfp: '2020-01-01 23:59:00',
          timezone: 'UTC'
        }
      };

      // Mock Luxon to return past date
      global.luxon.DateTime.fromSQL.mockReturnValue({
        invalid: false,
        toJSDate: () => pastDate,
        toISO: () => pastDate.toISOString(),
        toLocaleString: () => pastDate.toLocaleString(),
        diffNow: () => ({
          toObject: () => ({ seconds: -86400 }) // 1 day in past
        })
      });

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('Deadline passed');
    });

    test('should handle multiple submission types', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Multi-track Conf',
          subs: 'PY,DATA,WEB',
          cfp: '2025-03-01 23:59:00'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('PY-conf');
      expect(searchResults.innerHTML).toContain('DATA-conf');
      expect(searchResults.innerHTML).toContain('WEB-conf');
    });

    test('should add click handlers to conference type badges', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Conf',
          subs: 'PY',
          cfp: '2025-03-01 23:59:00'
        }
      };

      window.filterBySub = jest.fn();
      window.displaySearchResults(results, docs);

      const badge = document.querySelector('.conf-sub');
      badge.click();

      expect(window.filterBySub).toHaveBeenCalledWith('PY');
    });
  });

  describe('getQueryVariable', () => {
    test('should extract query parameter from URL', () => {
      // Mock window.location
      delete window.location;
      window.location = { search: '?q=python&type=conference' };

      expect(window.getQueryVariable('q')).toBe('python');
      expect(window.getQueryVariable('type')).toBe('conference');
    });

    test('should return null for missing parameter', () => {
      window.location = { search: '?q=python' };

      expect(window.getQueryVariable('missing')).toBeNull();
    });

    test('should decode URL-encoded values', () => {
      window.location = { search: '?q=python%20conference' };

      expect(window.getQueryVariable('q')).toBe('python conference');
    });
  });

  describe('Date Formatting', () => {
    test('should format dates with Luxon when available', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          cfp: '2025-02-15 23:59:00',
          timezone: 'America/New_York'
        }
      };

      window.displaySearchResults(results, docs);

      expect(global.luxon.DateTime.fromSQL).toHaveBeenCalledWith(
        '2025-02-15 23:59:00',
        { zone: 'America/New_York' }
      );
    });

    test('should fallback to native Date when Luxon unavailable', () => {
      delete global.luxon;

      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          cfp: '2025-02-15 23:59:00'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('Test Conf');
    });

    test('should use UTC-12 timezone as default', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          cfp: '2025-02-15 23:59:00'
          // No timezone specified
        }
      };

      window.displaySearchResults(results, docs);

      expect(global.luxon.DateTime.fromSQL).toHaveBeenCalledWith(
        '2025-02-15 23:59:00',
        { zone: 'UTC-12' }
      );
    });
  });

  describe('Error Handling', () => {
    test('should handle calendar creation errors gracefully', () => {
      global.createCalendarFromObject = jest.fn(() => {
        throw new Error('Calendar error');
      });

      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          cfp: '2025-02-15 23:59:00'
        }
      };

      // Should not throw
      expect(() => {
        window.displaySearchResults(results, docs);
      }).not.toThrow();

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('Test Conf');
    });

    test('should handle invalid date formats', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          cfp: 'invalid-date'
        }
      };

      global.luxon.DateTime.fromSQL.mockReturnValue({
        invalid: true,
        toJSDate: () => new Date('invalid'),
        toISO: () => '',
        toLocaleString: () => 'Invalid DateTime'
      });

      // Should not throw
      expect(() => {
        window.displaySearchResults(results, docs);
      }).not.toThrow();
    });

    test('should handle missing search results container', () => {
      document.body.innerHTML = ''; // Remove search-results div

      // Should not throw
      expect(() => {
        window.displaySearchResults([], {});
      }).not.toThrow();
    });
  });

  describe('Conference Links', () => {
    test('should create proper Google Maps links for places', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          place: 'San Francisco, CA',
          cfp: '2025-02-15 23:59:00'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('https://maps.google.com/?q=San%20Francisco%2C%20CA');
    });

    test('should handle online conferences differently', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          place: 'Online',
          cfp: '2025-02-15 23:59:00'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('<a href="#">Online</a>');
      expect(searchResults.innerHTML).not.toContain('maps.google.com');
    });

    test('should include conference website link when available', () => {
      const results = [{ ref: 'conf-1', score: 0.9 }];
      const docs = {
        'conf-1': {
          title: 'Test Conf',
          link: 'https://conference.org',
          cfp: '2025-02-15 23:59:00'
        }
      };

      window.displaySearchResults(results, docs);

      const searchResults = document.getElementById('search-results');
      expect(searchResults.innerHTML).toContain('https://conference.org');
      expect(searchResults.innerHTML).toContain('203-earth.svg');
    });
  });
});
