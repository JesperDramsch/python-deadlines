/**
 * Tests for ConferenceStateManager
 */

const { mockStore } = require('../utils/mockHelpers');

describe('ConferenceStateManager', () => {
  let ConferenceStateManager;
  let storeMock;
  let originalJQuery;

  beforeEach(() => {
    // Set up DOM with conference elements
    document.body.innerHTML = `
      <div class="ConfItem"
           data-conf-id="pycon-2025"
           data-conf-name="PyCon US"
           data-conf-year="2025"
           data-location="Pittsburgh, PA"
           data-cfp="2025-02-15 23:59:00"
           data-start="2025-06-01"
           data-end="2025-06-05"
           data-link="https://pycon.org"
           data-topics="PY"
           data-format="In-Person"
           data-has-finaid="true">
      </div>
      <div class="ConfItem"
           data-conf-id="europython-2025"
           data-conf-name="EuroPython"
           data-conf-year="2025"
           data-location="Dublin, Ireland"
           data-cfp="2025-03-01 23:59:00"
           data-start="2025-07-01"
           data-end="2025-07-07"
           data-link="https://europython.eu"
           data-topics="PY,DATA"
           data-format="Online"
           data-has-workshop="true">
      </div>
    `;

    // Mock jQuery for DOM extraction
    originalJQuery = global.$;
    global.$ = jest.fn((selector) => {
      // Handle different selector types
      let elements;
      if (!selector) {
        elements = [];
      } else if (selector && selector.nodeType) {
        // DOM element
        elements = [selector];
      } else if (selector instanceof NodeList) {
        elements = Array.from(selector);
      } else if (Array.isArray(selector)) {
        elements = selector;
      } else if (typeof selector === 'string') {
        elements = Array.from(document.querySelectorAll(selector));
      } else if (selector === document) {
        elements = [document];
      } else {
        elements = [];
      }

      const result = {
        each: jest.fn((callback) => {
          elements.forEach((el, index) => {
            // Create jQuery-like wrapper for each element
            const $el = {
              data: jest.fn((key) => {
                const attrName = `data-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
                return el.getAttribute(attrName);
              })
            };
            callback.call(el, index, el);
            // Make data available on mock jQuery object
            global.$.mockElement = $el;
          });
        })
      };

      // For individual element queries
      if (elements.length === 1) {
        result.data = jest.fn((key) => {
          const attrName = `data-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
          return elements[0].getAttribute(attrName);
        });
      }

      return result;
    });

    storeMock = mockStore();

    // Mock localStorage - manager tries pydeadlines_ prefix first, then falls back
    const mockGetItem = jest.fn((key) => {
      // The manager checks both old and new storage keys
      if (key === 'pythondeadlines-favorites') {
        return null;  // No old data in most tests
      }
      // Return data from the pydeadlines_ prefix keys (new format)
      if (key === 'pydeadlines_savedEvents') {
        return JSON.stringify(['pycon-2024']);
      }
      if (key === 'pydeadlines_followedSeries') {
        return JSON.stringify(['PyCon']);
      }
      if (key === 'pydeadlines_notificationSettings') {
        return null;  // Use default
      }
      // Old format keys - return null since we're using the new format
      if (key === 'savedEvents' || key === 'followedSeries' || key === 'notificationSettings') {
        console.log('  -> Returning null for old format key');
        return null;
      }
      return null;
    });
    // Set up both Storage.prototype and global.localStorage
    Storage.prototype.getItem = mockGetItem;
    Storage.prototype.setItem = jest.fn();

    // Also set up global localStorage directly
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: mockGetItem,
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn()
      },
      writable: true
    });

    // Load ConferenceStateManager
    const managerCode = require('fs').readFileSync(
      require('path').resolve(__dirname, '../../../static/js/conference-manager.js'),
      'utf8'
    );

    // Execute the code with mocked localStorage in scope
    const wrapper = `
      (function(localStorage) {
        ${managerCode}
        return ConferenceStateManager;
      })
    `;
    const createConferenceStateManager = eval(wrapper);
    ConferenceStateManager = createConferenceStateManager(window.localStorage);

    // Make it available globally for tests
    global.ConferenceStateManager = ConferenceStateManager;
    window.ConferenceStateManager = ConferenceStateManager;
  });

  afterEach(() => {
    global.$ = originalJQuery;
    delete window.ConferenceStateManager;
  });

  describe('Initialization', () => {
    test('should create instance with conference data', () => {
      const confData = {
        active: [
          { conference: 'Test Conf', year: 2025, cfp: '2025-01-01 00:00:00' }
        ]
      };

      const manager = new ConferenceStateManager(confData);

      expect(manager.allConferences).toBeDefined();
      expect(manager.conferenceBySeries).toBeDefined();
    });

    test('should initialize with empty state when no data provided', () => {
      // ConferenceStateManager doesn't auto-extract from DOM
      // It requires conferenceData to be passed in the constructor
      const manager = new ConferenceStateManager();

      // Without data, allConferences should be empty
      expect(manager.allConferences.size).toBe(0);
      expect(manager.conferenceBySeries.size).toBe(0);
    });

    test('should load saved events from localStorage', () => {
      const manager = new ConferenceStateManager();

      expect(manager.savedEvents).toBeDefined();
      expect(manager.savedEvents).toBeInstanceOf(Set);
      expect(manager.savedEvents.has('pycon-2024')).toBe(true);
    });

    test('should load followed series from localStorage', () => {
      const manager = new ConferenceStateManager();

      expect(manager.followedSeries).toBeDefined();
      expect(manager.followedSeries).toBeInstanceOf(Set);
      expect(manager.followedSeries.has('PyCon')).toBe(true);
    });

    test('should initialize with empty storage when no saved data exists', () => {
      // Mock empty storage
      const emptyMock = jest.fn(() => null);
      Storage.prototype.getItem = emptyMock;
      window.localStorage.getItem = emptyMock;

      const manager = new ConferenceStateManager();

      expect(manager.savedEvents.size).toBe(0);
      expect(manager.followedSeries.size).toBe(0);
    });
  });

  // Conference IDs are now generated by Jekyll, not JavaScript
  // These tests have been removed since generateConferenceId() no longer exists

  describe('Conference Data Management', () => {
    test('should process active conferences with Jekyll-generated IDs', () => {
      const manager = new ConferenceStateManager();

      const data = {
        active: [
          { id: 'test-conf-1-2025', conference: 'Test Conf 1', year: 2025, cfp: '2025-01-01 00:00:00' },
          { id: 'test-conf-2-2025', conference: 'Test Conf 2', year: 2025, cfp: '2025-02-01 00:00:00' }
        ]
      };

      manager.processConferenceData(data);

      expect(manager.allConferences.size).toBeGreaterThanOrEqual(2);
      expect(manager.conferenceBySeries.has('Test Conf 1')).toBe(true);
      expect(manager.conferenceBySeries.has('Test Conf 2')).toBe(true);
    });

    test('should get conference by ID', () => {
      const manager = new ConferenceStateManager();

      const conf = {
        id: 'test-conf-2025',
        conference: 'Test Conf',
        year: 2025,
        cfp: '2025-01-01 00:00:00'
      };

      manager.processConferenceData({ active: [conf] });

      const retrieved = manager.getConference('test-conf-2025');

      expect(retrieved).toBeDefined();
      expect(retrieved.conference).toBe('Test Conf');
    });

    test('should get conferences by series', () => {
      const manager = new ConferenceStateManager();

      const data = {
        active: [
          { id: 'pycon-2024', conference: 'PyCon', year: 2024, cfp: '2024-01-01 00:00:00' },
          { id: 'pycon-2025', conference: 'PyCon', year: 2025, cfp: '2025-01-01 00:00:00' }
        ]
      };

      manager.processConferenceData(data);

      const series = manager.getConferenceSeries('PyCon');

      expect(series).toHaveLength(2);
      expect(series[0].conference).toBe('PyCon');
      expect(series[1].conference).toBe('PyCon');
    });
  });

  describe('Event Management', () => {
    test('should save event', () => {
      const manager = new ConferenceStateManager();

      const conf = {
        id: 'test-conf-2025',
        conference: 'Test Conf',
        year: 2025,
        cfp: '2025-01-01 00:00:00'
      };

      manager.processConferenceData({ active: [conf] });

      const result = manager.saveEvent('test-conf-2025');

      expect(result).toBe(true);
      expect(manager.isEventSaved('test-conf-2025')).toBe(true);

      // Check that localStorage.setItem was called with the right arguments
      const setItemCalls = window.localStorage.setItem.mock.calls;
      const savedEventsCall = setItemCalls.find(call => call[0] === 'pydeadlines_savedEvents');
      expect(savedEventsCall).toBeDefined();
      expect(savedEventsCall[1]).toContain('test-conf-2025');
    });

    test('should remove saved event', () => {
      const manager = new ConferenceStateManager();

      // First save an event
      manager.savedEvents.add('test-conf-2025');

      const result = manager.removeSavedEvent('test-conf-2025');

      expect(result).toBe(true);
      expect(manager.isEventSaved('test-conf-2025')).toBe(false);
    });

    test('should get saved events with full data', () => {
      const manager = new ConferenceStateManager();

      const data = {
        active: [
          { id: 'conf-a-2025', conference: 'Conf A', year: 2025, cfp: '2025-03-01 00:00:00' },
          { id: 'conf-b-2025', conference: 'Conf B', year: 2025, cfp: '2025-02-01 00:00:00' },
          { id: 'conf-c-2025', conference: 'Conf C', year: 2025, cfp: '2025-01-01 00:00:00' }
        ]
      };

      manager.processConferenceData(data);

      // Save some events
      manager.saveEvent('conf-a-2025');
      manager.saveEvent('conf-b-2025');

      const savedEvents = manager.getSavedEvents();

      expect(savedEvents).toHaveLength(2);
      // Should be sorted by CFP date
      expect(savedEvents[0].conference).toBe('Conf B'); // Earlier CFP
      expect(savedEvents[1].conference).toBe('Conf A'); // Later CFP
    });

    test('should handle non-existent conference when saving', () => {
      const manager = new ConferenceStateManager();

      const result = manager.saveEvent('non-existent-conf');

      expect(result).toBe(false);
      expect(manager.isEventSaved('non-existent-conf')).toBe(false);
    });
  });

  describe('Series Management', () => {
    test('should follow series', () => {
      const manager = new ConferenceStateManager();

      const result = manager.followSeries('PyCon');

      expect(result).toBe(true);
      expect(manager.isSeriesFollowed('PyCon')).toBe(true);

      // Check that localStorage.setItem was called with the right arguments
      const setItemCalls = window.localStorage.setItem.mock.calls;
      const followedSeriesCall = setItemCalls.find(call => call[0] === 'pydeadlines_followedSeries');
      expect(followedSeriesCall).toBeDefined();
      expect(followedSeriesCall[1]).toContain('PyCon');
    });

    test('should unfollow series', () => {
      const manager = new ConferenceStateManager();

      // First follow
      manager.followedSeries.add('PyCon');

      const result = manager.unfollowSeries('PyCon');

      expect(result).toBe(true);
      expect(manager.isSeriesFollowed('PyCon')).toBe(false);
    });

    test('should auto-save future events when following series', () => {
      const manager = new ConferenceStateManager();

      const futureDate = new Date();
      futureDate.setMonth(futureDate.getMonth() + 3);

      const data = {
        active: [
          {
            id: 'pycon-2025',
            conference: 'PyCon',
            year: 2025,
            cfp: futureDate.toISOString().replace('T', ' ').slice(0, 19)
          }
        ]
      };

      manager.processConferenceData(data);

      manager.followSeries('PyCon');

      // Should auto-save the future conference
      expect(manager.isEventSaved('pycon-2025')).toBe(true);
    });
  });

  describe('Storage Management', () => {
    test('should persist data to localStorage', () => {
      const manager = new ConferenceStateManager();

      manager.persistToStorage('testKey', { test: 'data' });

      // Check that either Storage.prototype or window.localStorage was called
      const setItemCalls = window.localStorage.setItem.mock.calls;
      expect(setItemCalls).toContainEqual([
        'pydeadlines_testKey',
        JSON.stringify({ test: 'data' })
      ]);
    });

    test('should load data from localStorage', () => {
      const testMock = jest.fn((key) => {
        // The manager tries pydeadlines_ prefix first
        if (key === 'pydeadlines_testKey') {
          return JSON.stringify({ test: 'data' });
        }
        return null;
      });

      Storage.prototype.getItem = testMock;
      window.localStorage.getItem = testMock;

      const manager = new ConferenceStateManager();

      const data = manager.loadFromStorage('testKey', {});

      expect(data).toEqual({ test: 'data' });
    });

    test('should handle corrupted localStorage data', () => {
      const corruptMock = jest.fn((key) => {
        if (key.startsWith('pydeadlines_')) {
          return 'invalid json';
        }
        return null;
      });

      Storage.prototype.getItem = corruptMock;
      window.localStorage.getItem = corruptMock;

      const manager = new ConferenceStateManager();

      const data = manager.loadFromStorage('testKey', ['default']);

      expect(data).toEqual(['default']);
    });
  });

  describe('Event Triggering', () => {
    test('should trigger update events', () => {
      const manager = new ConferenceStateManager();
      const eventSpy = jest.fn();

      window.addEventListener('conferenceStateUpdate', eventSpy);

      manager.triggerUpdate('savedEvents', 'conf-id', 'added');

      expect(eventSpy).toHaveBeenCalled();

      window.removeEventListener('conferenceStateUpdate', eventSpy);
    });
  });

  describe('Archive Loading', () => {
    test('should load archive data on demand', async () => {
      const manager = new ConferenceStateManager();

      // Mock fetch
      global.fetch = jest.fn(() =>
        Promise.resolve({
          json: () => Promise.resolve([
            { conference: 'Old Conf', year: 2023, cfp: '2023-01-01 00:00:00' }
          ])
        })
      );

      await manager.loadArchiveData();

      expect(manager.archiveLoaded).toBe(true);
      expect(fetch).toHaveBeenCalledWith('/data/archive.json');
    });

    test('should handle archive loading failure', async () => {
      const manager = new ConferenceStateManager();

      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      await manager.loadArchiveData();

      // Archive should fail to load silently (no console.error)
      expect(manager.archiveLoaded).toBe(false);
    });
  });
});
