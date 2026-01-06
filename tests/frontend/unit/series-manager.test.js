/**
 * Tests for Series Manager functionality
 */

const { mockStore } = require('../utils/mockHelpers');

describe('SeriesManager', () => {
  let storeMock;
  let SeriesManager;
  let FavoritesManager;
  let confManager;

  beforeEach(() => {
    // Clear existing globals
    delete window.SeriesManager;
    delete window.FavoritesManager;
    delete window.confManager;
    delete window.$;

    // Mock store
    storeMock = mockStore();
    global.store = storeMock;

    // Mock FavoritesManager
    FavoritesManager = {
      isFavorite: jest.fn().mockReturnValue(false),
      add: jest.fn(),
      extractConferenceData: jest.fn((confId) => {
        // Return data based on conference ID
        if (confId === 'pycon-us-2025') {
          return {
            id: 'pycon-us-2025',
            name: 'PyCon US 2025',
            cfp: '2025-03-01 23:59:00',
            place: 'Virtual'
          };
        }
        return {
          id: confId || 'test-conf',
          name: 'Test Conference',
          cfp: '2025-03-01 23:59:00',
          place: 'Virtual'
        };
      }),
      showToast: jest.fn()
    };
    window.FavoritesManager = FavoritesManager;

    // Mock confManager with all required methods
    const followedSeriesSet = new Set();
    confManager = {
      ready: true,
      isSeriesFollowed: jest.fn((seriesName) => followedSeriesSet.has(seriesName)),
      followSeries: jest.fn((seriesName) => {
        followedSeriesSet.add(seriesName);
        return true;
      }),
      unfollowSeries: jest.fn((seriesName) => {
        return followedSeriesSet.delete(seriesName);
      }),
      getFollowedSeries: jest.fn(() => {
        return Array.from(followedSeriesSet).map(name => ({
          name,
          conferences: [],
          pattern: { pattern: 'Not enough data', confidence: 'low' }
        }));
      })
    };
    window.confManager = confManager;

    // Set up DOM
    document.body.innerHTML = `
      <div class="ConfItem" data-conf-id="pycon-us-2025" data-conf-name="PyCon US 2025">
        <button class="series-btn" data-conf-id="pycon-us-2025" data-conf-name="PyCon US 2025">
          <i class="far fa-star"></i> Follow Series
        </button>
        <div class="conf-title"><a href="#">PyCon US 2025</a></div>
      </div>
      <div class="ConfItem" data-conf-id="pydata-nyc-2025" data-conf-name="PyData NYC 2025">
        <button class="series-btn" data-conf-id="pydata-nyc-2025" data-conf-name="PyData NYC 2025">
          <i class="far fa-star"></i> Follow Series
        </button>
      </div>
      <div class="quick-subscribe btn btn-outline-primary" data-series="PyData">+ PyData</div>
      <div id="subscribed-series-list"></div>
      <div id="series-count"></div>
      <div id="predictions-container"></div>
    `;

    // Mock jQuery
    const jQuery = jest.fn((selector) => {
      if (typeof selector === 'function') {
        // Document ready
        selector();
        return;
      }

      // Handle HTML creation - if selector starts with '<' it's HTML
      if (typeof selector === 'string' && selector.trim().startsWith('<')) {
        const div = document.createElement('div');
        div.innerHTML = selector.trim();
        const element = div.firstElementChild;
        return jQuery(element);
      }

      // Handle 'this' context from event handlers
      if (selector && selector.nodeType === 1) {
        // It's a DOM element (like 'this' in an event handler)
        selector = [selector];
      }

      if (selector === document) {
        return {
          on: jest.fn((event, delegateSelector, handler) => {
            // Handle event delegation
            if (typeof delegateSelector === 'function') {
              handler = delegateSelector;
              delegateSelector = null;
            }

            // Simulate click on series button
            if (event === 'click' && delegateSelector === '.series-btn') {
              document.querySelectorAll('.series-btn').forEach(btn => {
                btn.addEventListener('click', function(e) {
                  // The handler expects this to be wrapped in jQuery
                  // Create a mock event object
                  const mockEvent = {
                    preventDefault: jest.fn(),
                    stopPropagation: jest.fn(),
                    target: this
                  };
                  handler.call(this, mockEvent);
                });
              });
            }
          }),
          ready: jest.fn((cb) => cb())
        };
      }

      // Handle jQuery wrapped elements
      if (selector && selector.jquery) {
        return selector;
      }

      // Handle arrays of DOM elements
      if (Array.isArray(selector)) {
        const nodeList = selector;
        const result = {
          length: nodeList.length,
          jquery: true,
          0: nodeList[0],
          each: jest.fn(function(callback) {
            nodeList.forEach((el, i) => callback.call(el, i, el));
            return result;
          }),
          hasClass: jest.fn(function(className) {
            return nodeList[0]?.classList.contains(className) || false;
          }),
          removeClass: jest.fn(function(className) {
            nodeList.forEach(el => {
              if (el?.classList) {
                const classes = className.split(/\s+/);
                classes.forEach(cls => {
                  if (cls) el.classList.remove(cls);
                });
              }
            });
            return result;
          }),
          addClass: jest.fn(function(className) {
            nodeList.forEach(el => {
              if (el?.classList) {
                const classes = className.split(/\s+/);
                classes.forEach(cls => {
                  if (cls) el.classList.add(cls);
                });
              }
            });
            return result;
          }),
          find: jest.fn(function(subSelector) {
            const subElements = nodeList[0]?.querySelectorAll(subSelector) || [];
            return jQuery(Array.from(subElements));
          }),
          data: jest.fn(function(key) {
            return nodeList[0]?.dataset[key.replace(/-([a-z])/g, (g) => g[1].toUpperCase())];
          }),
          css: jest.fn(function(prop, value) {
            nodeList.forEach(el => {
              if (el?.style) el.style[prop] = value;
            });
            return result;
          }),
          text: jest.fn(function(newText) {
            if (newText !== undefined) {
              nodeList.forEach(el => {
                if (el) el.textContent = newText;
              });
              return result;
            }
            return nodeList[0]?.textContent || '';
          }),
          html: jest.fn(function(newHtml) {
            if (newHtml !== undefined) {
              nodeList.forEach(el => {
                if (el) el.innerHTML = newHtml;
              });
              return result;
            }
            return nodeList[0]?.innerHTML || '';
          })
        };
        return result;
      }

      // Handle DOM elements directly
      if (selector instanceof Element || selector instanceof NodeList || selector instanceof HTMLCollection) {
        const nodeList = selector instanceof Element ? [selector] : Array.from(selector);
        const result = {
          length: nodeList.length,
          jquery: true,
          0: nodeList[0],
          each: jest.fn(function(callback) {
            nodeList.forEach((el, i) => callback.call(el, i, el));
            return result;
          }),
          text: jest.fn(function(newText) {
            if (newText !== undefined) {
              nodeList.forEach(el => el.textContent = newText);
              return result;
            }
            return nodeList[0]?.textContent || '';
          }),
          data: jest.fn(function(key) {
            return nodeList[0]?.dataset[key.replace(/-([a-z])/g, (g) => g[1].toUpperCase())];
          }),
          find: jest.fn(function(subSelector) {
            const subElements = nodeList[0]?.querySelectorAll(subSelector) || [];
            return jQuery(Array.from(subElements));
          }),
          first: jest.fn(function() {
            return jQuery(nodeList[0] || []);
          })
        };
        return result;
      }

      // Handle string selectors
      if (typeof selector !== 'string') {
        return { length: 0, each: jest.fn() };
      }

      const elements = document.querySelectorAll(selector);
      const result = {
        length: elements.length,
        each: jest.fn(function(callback) {
          elements.forEach((el, i) => callback.call(el, i, el));
          return result;
        }),
        on: jest.fn(function(event, handler) {
          elements.forEach(el => {
            el.addEventListener(event, handler);
          });
          return result;
        }),
        removeClass: jest.fn(function(className) {
          elements.forEach(el => {
            // Handle multiple classes separated by spaces
            const classes = className.split(/\s+/);
            classes.forEach(cls => {
              if (cls) el.classList.remove(cls);
            });
          });
          return result;
        }),
        addClass: jest.fn(function(className) {
          elements.forEach(el => {
            // Handle multiple classes separated by spaces
            const classes = className.split(/\s+/);
            classes.forEach(cls => {
              if (cls) el.classList.add(cls);
            });
          });
          return result;
        }),
        hasClass: jest.fn(function(className) {
          return elements[0]?.classList.contains(className) || false;
        }),
        find: jest.fn(function(subSelector) {
          const subElements = elements[0]?.querySelectorAll(subSelector) || [];
          return jQuery(Array.from(subElements));
        }),
        first: jest.fn(function() {
          return jQuery(elements[0] || []);
        }),
        css: jest.fn(function(prop, value) {
          elements.forEach(el => {
            el.style[prop] = value;
          });
          return result;
        }),
        data: jest.fn(function(key) {
          return elements[0]?.dataset[key.replace(/-([a-z])/g, (g) => g[1].toUpperCase())];
        }),
        text: jest.fn(function(newText) {
          if (newText !== undefined) {
            elements.forEach(el => el.textContent = newText);
            return result;
          }
          return elements[0]?.textContent || '';
        }),
        html: jest.fn(function(newHtml) {
          if (newHtml !== undefined) {
            elements.forEach(el => el.innerHTML = newHtml);
            return result;
          }
          return elements[0]?.innerHTML || '';
        }),
        empty: jest.fn(function() {
          elements.forEach(el => el.innerHTML = '');
          return result;
        }),
        append: jest.fn(function(content) {
          elements.forEach(el => {
            if (typeof content === 'string') {
              el.insertAdjacentHTML('beforeend', content);
            } else if (content.jquery) {
              // jQuery object
              el.appendChild(content[0]);
            } else {
              el.appendChild(content);
            }
          });
          return result;
        }),
        attr: jest.fn(function(name) {
          return elements[0]?.getAttribute(name);
        }),
        is: jest.fn(function(selector) {
          if (selector === ':checked') {
            return elements[0]?.checked || false;
          }
          return false;
        }),
        children: jest.fn(function() {
          const childElements = elements[0]?.children || [];
          return {
            length: childElements.length,
            jquery: true
          };
        })
      };

      // Store reference to elements for jQuery object
      result.jquery = true;
      result[0] = elements[0];

      return result;
    });

    global.$ = jQuery;
    window.$ = jQuery;

    // Mock addEventListener
    window.addEventListener = jest.fn();

    // Load SeriesManager
    const script = require('fs').readFileSync(
      require('path').resolve(__dirname, '../../../static/js/series-manager.js'),
      'utf8'
    );

    // The SeriesManager is defined as a const, we need to modify it to attach to window
    // Replace const SeriesManager with window.SeriesManager
    const modifiedScript = script
      .replace('const SeriesManager = {', 'window.SeriesManager = {')
      .replace(
        /\$\(document\)\.ready\(function\(\)\s*{\s*SeriesManager\.init\(\);\s*}\);?/,
        ''
      );

    // Execute the script to define SeriesManager
    try {
      eval(modifiedScript);
      SeriesManager = window.SeriesManager;
    } catch (error) {
      console.error('Error loading SeriesManager:', error);
    }
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Initialization', () => {
    test('should wait for ConferenceStateManager if not ready', () => {
      delete window.confManager;
      const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

      // Check if SeriesManager is loaded
      expect(SeriesManager).toBeDefined();
      expect(typeof SeriesManager.init).toBe('function');

      SeriesManager.init();

      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 100);

      setTimeoutSpy.mockRestore();
    });

    test('should initialize when confManager is ready', () => {
      const bindSeriesButtonsSpy = jest.spyOn(SeriesManager, 'bindSeriesButtons');
      const bindQuickSubscribeSpy = jest.spyOn(SeriesManager, 'bindQuickSubscribe');
      const renderSubscribedSeriesSpy = jest.spyOn(SeriesManager, 'renderSubscribedSeries');

      SeriesManager.init();

      expect(bindSeriesButtonsSpy).toHaveBeenCalled();
      expect(bindQuickSubscribeSpy).toHaveBeenCalled();
      expect(renderSubscribedSeriesSpy).toHaveBeenCalled();
    });

    test('should listen for conferenceStateUpdate events', () => {
      SeriesManager.init();

      expect(window.addEventListener).toHaveBeenCalledWith(
        'conferenceStateUpdate',
        expect.any(Function)
      );
    });
  });

  // Note: Series identification, subscription management, pattern subscriptions,
  // auto-favorite, and new conference detection are all handled by confManager,
  // not SeriesManager. SeriesManager is a UI-focused module that delegates
  // data operations to confManager. Tests for those features belong in
  // conference-manager.test.js.

  describe('UI Updates', () => {
    test('should update series count', () => {
      // Mock confManager to return 2 followed series
      confManager.getFollowedSeries.mockReturnValue([
        { name: 'PyCon US', conferences: [], pattern: {} },
        { name: 'PyData', conferences: [], pattern: {} }
      ]);

      SeriesManager.updateSeriesCount();

      const countElement = document.getElementById('series-count');
      expect(countElement.textContent).toBe('2 series subscriptions');
    });

    test('should handle single series count correctly', () => {
      // Mock confManager to return 1 followed series
      confManager.getFollowedSeries.mockReturnValue([
        { name: 'PyCon US', conferences: [], pattern: {} }
      ]);

      SeriesManager.updateSeriesCount();

      const countElement = document.getElementById('series-count');
      expect(countElement.textContent).toBe('1 series subscription');
    });
  });

  describe('Series List Rendering', () => {
    test('should render subscribed series list', () => {
      // Mock confManager to return followed series
      confManager.getFollowedSeries.mockReturnValue([
        {
          name: 'PyCon US',
          conferences: [{ id: 'pycon-us-2025', year: 2025 }],
          pattern: { pattern: 'Annual event', confidence: 'high' }
        }
      ]);

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('PyCon US');
    });

    test('should show empty message when no subscriptions', () => {
      confManager.getFollowedSeries.mockReturnValue([]);

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('No series subscriptions yet');
    });

    test('should render series with event count badge', () => {
      confManager.getFollowedSeries.mockReturnValue([
        {
          name: 'PyData',
          conferences: [
            { id: 'pydata-2025', year: 2025 },
            { id: 'pydata-2024', year: 2024 }
          ],
          pattern: { pattern: 'Not enough data', confidence: 'low' }
        }
      ]);

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('PyData');
      expect(container.innerHTML).toContain('2 events');
    });
  });

  describe('Predictions', () => {
    test('should generate predictions for subscribed series', () => {
      // Mock confManager to return followed series with pattern data
      confManager.getFollowedSeries.mockReturnValue([
        {
          name: 'PyCon US',
          conferences: [{ id: 'pycon-us-2025', year: 2025 }],
          pattern: { pattern: 'CFP typically opens in December', confidence: 'high', basedOn: '3 years' }
        }
      ]);

      SeriesManager.generatePredictions();

      const container = document.getElementById('predictions-container');
      expect(container.innerHTML).toContain('PyCon US');
    });

    test('should show no predictions message when empty', () => {
      confManager.getFollowedSeries.mockReturnValue([]);

      SeriesManager.generatePredictions();

      const container = document.getElementById('predictions-container');
      expect(container.innerHTML).toContain('No predictions available');
    });

    // Note: predictNextCFP is not a method on SeriesManager - pattern analysis
    // is handled by confManager. Tests for that belong in conference-manager.test.js
  });

  describe('Event Handlers', () => {
    test('should handle series button click for subscription', () => {
      SeriesManager.init();

      const button = document.querySelector('.series-btn[data-conf-name="PyCon US 2025"]');
      const clickEvent = new MouseEvent('click');
      button.dispatchEvent(clickEvent);

      // SeriesManager delegates to confManager.followSeries
      expect(confManager.followSeries).toHaveBeenCalledWith('PyCon US 2025');
    });

    test('should handle quick subscribe button click', () => {
      SeriesManager.bindQuickSubscribe();

      const button = document.querySelector('.quick-subscribe');
      button.click();

      // SeriesManager delegates to confManager.followSeries for quick subscribe
      expect(confManager.followSeries).toHaveBeenCalledWith('PyData');
    });

    test('should handle unsubscribe from quick subscribe', () => {
      // Make confManager report that PyData is already followed
      confManager.isSeriesFollowed.mockReturnValue(true);

      const button = document.querySelector('.quick-subscribe');

      SeriesManager.bindQuickSubscribe();
      // After bindQuickSubscribe, updateQuickSubscribeButtons() adds 'subscribed' class
      // since isSeriesFollowed returns true

      button.click();

      // SeriesManager delegates to confManager.unfollowSeries
      expect(confManager.unfollowSeries).toHaveBeenCalledWith('PyData');
    });
  });

  describe('Error Handling', () => {
    // Note: subscribe and autoFavoriteSeriesConferences are not methods on
    // SeriesManager - it delegates to confManager for all data operations

    test('should handle missing DOM elements', () => {
      document.getElementById('subscribed-series-list').remove();
      document.getElementById('series-count').remove();
      document.getElementById('predictions-container').remove();

      expect(() => {
        SeriesManager.renderSubscribedSeries();
        SeriesManager.updateSeriesCount();
        SeriesManager.generatePredictions();
      }).not.toThrow();
    });
  });

  // Note: SeriesManager does not have getSubscriptions - it delegates to
  // confManager.getFollowedSeries for all subscription data
});
