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

    // Mock confManager
    confManager = {
      ready: true
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
      const detectNewConferencesSpy = jest.spyOn(SeriesManager, 'detectNewConferences');

      SeriesManager.init();

      expect(bindSeriesButtonsSpy).toHaveBeenCalled();
      expect(bindQuickSubscribeSpy).toHaveBeenCalled();
      expect(detectNewConferencesSpy).toHaveBeenCalled();
    });

    test('should listen for conferenceStateUpdate events', () => {
      SeriesManager.init();

      expect(window.addEventListener).toHaveBeenCalledWith(
        'conferenceStateUpdate',
        expect.any(Function)
      );
    });
  });

  describe('Series Identification', () => {
    test('should extract series name from conference name', () => {
      expect(SeriesManager.extractSeriesName('PyCon US 2025')).toBe('PyCon US');
      expect(SeriesManager.extractSeriesName('PyData NYC 2024')).toBe('PyData NYC');
      expect(SeriesManager.extractSeriesName('EuroPython Conference 2025')).toBe('EuroPython');
      expect(SeriesManager.extractSeriesName('PyCon 2025')).toBe('PyCon');
    });

    test('should generate series ID from conference name', () => {
      expect(SeriesManager.getSeriesId('PyCon US 2025')).toBe('pycon-us');
      expect(SeriesManager.getSeriesId('PyData NYC 2025')).toBe('pydata-nyc');
      expect(SeriesManager.getSeriesId('EuroPython 2025')).toBe('europython');
    });

    test('should handle conference names with special characters', () => {
      expect(SeriesManager.extractSeriesName('PyCon AU/NZ 2025')).toBe('PyCon AU/NZ');
      expect(SeriesManager.getSeriesId('PyCon AU/NZ 2025')).toBe('pycon-aunz');
    });
  });

  describe('Subscription Management', () => {
    test('should subscribe to a conference series', () => {
      const seriesId = 'pycon-us';
      const seriesName = 'PyCon US';

      SeriesManager.subscribe(seriesId, seriesName);

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-series-subscriptions',
        expect.objectContaining({
          'pycon-us': expect.objectContaining({
            name: 'PyCon US',
            autoFavorite: true,
            notifyOnNew: true,
            pattern: false
          })
        })
      );

      expect(FavoritesManager.showToast).toHaveBeenCalledWith(
        'Series Subscribed',
        expect.stringContaining('PyCon US')
      );
    });

    test('should unsubscribe from a series', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': { name: 'PyCon US' }
      });

      SeriesManager.unsubscribe('pycon-us');

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-series-subscriptions',
        {}
      );

      expect(FavoritesManager.showToast).toHaveBeenCalledWith(
        'Series Unsubscribed',
        expect.stringContaining('PyCon US')
      );
    });

    test('should get all subscribed series', () => {
      const mockSubscriptions = {
        'pycon-us': { name: 'PyCon US' },
        'pydata': { name: 'PyData' }
      };

      storeMock.get.mockReturnValue(mockSubscriptions);

      const subscriptions = SeriesManager.getSubscribedSeries();

      expect(subscriptions).toEqual(mockSubscriptions);
    });

    test('should handle empty subscriptions', () => {
      storeMock.get.mockReturnValue(null);

      const subscriptions = SeriesManager.getSubscribedSeries();

      expect(subscriptions).toEqual({});
    });
  });

  describe('Pattern Subscriptions', () => {
    test('should subscribe to a pattern', () => {
      SeriesManager.subscribeToPattern('PyData');

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-series-subscriptions',
        expect.objectContaining({
          'PyData-all': expect.objectContaining({
            name: 'All PyData Events',
            pattern: 'PyData',
            isPattern: true,
            autoFavorite: false
          })
        })
      );
    });

    test('should unsubscribe from a pattern', () => {
      storeMock.get.mockReturnValue({
        'PyData-all': { name: 'All PyData Events', pattern: 'PyData' }
      });

      SeriesManager.unsubscribePattern('PyData');

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-series-subscriptions',
        {}
      );
    });

    test('should detect pattern matches', () => {
      document.body.innerHTML += `
        <div class="ConfItem" data-conf-name="PyData Berlin 2025"></div>
        <div class="ConfItem" data-conf-name="PyData London 2025"></div>
      `;

      SeriesManager.detectPatternMatches('PyData');

      expect(FavoritesManager.showToast).toHaveBeenCalledWith(
        'Pattern Matches Found',
        expect.stringContaining('3 PyData conference'),
        'info'
      );
    });
  });

  describe('Auto-Favorite Functionality', () => {
    test('should auto-favorite conferences in subscribed series', () => {
      FavoritesManager.isFavorite.mockReturnValue(false);

      SeriesManager.autoFavoriteSeriesConferences('pycon-us');

      expect(FavoritesManager.add).toHaveBeenCalledWith(
        'pycon-us-2025',
        expect.objectContaining({
          id: 'pycon-us-2025',
          name: 'PyCon US 2025'
        })
      );
    });

    test('should not auto-favorite already favorited conferences', () => {
      FavoritesManager.isFavorite.mockReturnValue(true);

      SeriesManager.autoFavoriteSeriesConferences('pycon-us');

      expect(FavoritesManager.add).not.toHaveBeenCalled();
    });
  });

  describe('New Conference Detection', () => {
    test('should detect new conferences in subscribed series', () => {
      storeMock.get.mockImplementation((key) => {
        if (key === 'pythondeadlines-series-subscriptions') {
          return {
            'pycon-us': {
              name: 'PyCon US',
              autoFavorite: true,
              notifyOnNew: true
            }
          };
        }
        if (key === 'pythondeadlines-processed-confs') {
          return [];
        }
        return null;
      });

      SeriesManager.detectNewConferences();

      expect(FavoritesManager.add).toHaveBeenCalled();
      expect(FavoritesManager.showToast).toHaveBeenCalledWith(
        'New Conference in Series',
        expect.stringContaining('PyCon US 2025'),
        'info'
      );
    });

    test('should not process already processed conferences', () => {
      storeMock.get.mockImplementation((key) => {
        if (key === 'pythondeadlines-series-subscriptions') {
          return { 'pycon-us': { name: 'PyCon US', notifyOnNew: true } };
        }
        if (key === 'pythondeadlines-processed-confs') {
          return ['pycon-us-2025'];
        }
        return null;
      });

      SeriesManager.detectNewConferences();

      expect(FavoritesManager.showToast).not.toHaveBeenCalled();
    });
  });

  describe('UI Updates', () => {
    test('should highlight subscribed series buttons', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': { name: 'PyCon US' }
      });

      SeriesManager.highlightSubscribedSeries();

      const button = document.querySelector('.series-btn[data-conf-name="PyCon US 2025"]');
      expect(button.classList.contains('subscribed')).toBe(true);
    });

    test('should update series count', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': { name: 'PyCon US' },
        'pydata': { name: 'PyData' }
      });

      SeriesManager.updateSeriesCount();

      const countElement = document.getElementById('series-count');
      expect(countElement.textContent).toBe('2 series subscriptions');
    });

    test('should handle single series count correctly', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': { name: 'PyCon US' }
      });

      SeriesManager.updateSeriesCount();

      const countElement = document.getElementById('series-count');
      expect(countElement.textContent).toBe('1 series subscription');
    });
  });

  describe('Series List Rendering', () => {
    test('should render subscribed series list', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': {
          name: 'PyCon US',
          autoFavorite: true,
          notifyOnNew: true,
          isPattern: false
        }
      });

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('PyCon US');
      expect(container.innerHTML).toContain('Auto-favorite');
      expect(container.innerHTML).toContain('Notify');
    });

    test('should show empty message when no subscriptions', () => {
      storeMock.get.mockReturnValue({});

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('No series subscriptions yet');
    });

    test('should render pattern subscriptions with badge', () => {
      storeMock.get.mockReturnValue({
        'PyData-all': {
          name: 'All PyData Events',
          isPattern: true,
          pattern: 'PyData'
        }
      });

      SeriesManager.renderSubscribedSeries();

      const container = document.getElementById('subscribed-series-list');
      expect(container.innerHTML).toContain('All PyData Events');
      expect(container.innerHTML).toContain('Pattern');
    });
  });

  describe('Predictions', () => {
    test('should generate predictions for subscribed series', () => {
      storeMock.get.mockReturnValue({
        'pycon-us': {
          name: 'PyCon US',
          isPattern: false
        }
      });

      SeriesManager.generatePredictions();

      const container = document.getElementById('predictions-container');
      expect(container.innerHTML).toContain('PyCon US');
      expect(container.innerHTML).toContain('December 2024');
    });

    test('should show no predictions message when empty', () => {
      storeMock.get.mockReturnValue({});

      SeriesManager.generatePredictions();

      const container = document.getElementById('predictions-container');
      expect(container.innerHTML).toContain('No predictions available');
    });

    test('should predict next CFP for known series', () => {
      const prediction = SeriesManager.predictNextCFP('pycon-us', 'PyCon US');

      expect(prediction).toEqual({
        seriesId: 'pycon-us',
        seriesName: 'PyCon US',
        cfpDate: 'December 2024',
        confidence: 0.9
      });
    });

    test('should return null for unknown series', () => {
      const prediction = SeriesManager.predictNextCFP('unknown-conf', 'Unknown');

      expect(prediction).toBeNull();
    });
  });

  describe('Event Handlers', () => {
    test('should handle series button click for subscription', () => {
      SeriesManager.init();

      const button = document.querySelector('.series-btn[data-conf-name="PyCon US 2025"]');
      const clickEvent = new MouseEvent('click');
      button.dispatchEvent(clickEvent);

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-series-subscriptions',
        expect.objectContaining({
          'pycon-us': expect.objectContaining({
            name: 'PyCon US'
          })
        })
      );
    });

    test('should handle quick subscribe button click', () => {
      const subscribeSpy = jest.spyOn(SeriesManager, 'subscribeToPattern');

      SeriesManager.bindQuickSubscribe();

      const button = document.querySelector('.quick-subscribe');
      button.click();

      expect(subscribeSpy).toHaveBeenCalledWith('PyData');
    });

    test('should handle unsubscribe from quick subscribe', () => {
      const unsubscribeSpy = jest.spyOn(SeriesManager, 'unsubscribePattern');

      const button = document.querySelector('.quick-subscribe');
      button.classList.add('subscribed');

      SeriesManager.bindQuickSubscribe();
      button.click();

      expect(unsubscribeSpy).toHaveBeenCalledWith('PyData');
    });
  });

  describe('Error Handling', () => {
    test('should handle missing FavoritesManager gracefully', () => {
      delete window.FavoritesManager;

      expect(() => {
        SeriesManager.subscribe('test', 'Test');
      }).not.toThrow();
    });

    test('should handle missing conference data', () => {
      FavoritesManager.extractConferenceData.mockReturnValue(null);

      SeriesManager.autoFavoriteSeriesConferences('pycon-us');

      expect(FavoritesManager.add).not.toHaveBeenCalled();
    });

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

  describe('Compatibility', () => {
    test('should provide getSubscriptions alias for getSubscribedSeries', () => {
      const mockSubscriptions = {
        'pycon-us': { name: 'PyCon US' }
      };

      storeMock.get.mockReturnValue(mockSubscriptions);

      expect(SeriesManager.getSubscriptions()).toEqual(mockSubscriptions);
      expect(SeriesManager.getSubscriptions()).toEqual(SeriesManager.getSubscribedSeries());
    });
  });
});