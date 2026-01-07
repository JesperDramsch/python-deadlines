/**
 * Tests for Snek Easter Egg
 * 🐍 Testing the most important feature of pythondeadlin.es
 */

describe('Snek Easter Egg', () => {
  // Store reference to real Date before any tests
  const RealDate = Date;

  beforeEach(() => {
    // Clear any existing seasonal styles
    const existingStyle = document.getElementById('seasonal-styles');
    if (existingStyle) {
      existingStyle.remove();
    }

    // Set up DOM with snake elements
    document.body.innerHTML = `
      <div id="left-snek" style="display: none;"></div>
      <div id="right-snek" style="display: none;"></div>
      <div id="smol-snek-all" style="display: none;">
        <div id="smol-snek-body"><path></path></div>
        <div id="smol-snek-tongue"><path></path></div>
      </div>
      <div id="location-pin" style="display: none;"></div>
    `;

    // Ensure head exists
    if (!document.head) {
      document.documentElement.insertBefore(
        document.createElement('head'),
        document.body
      );
    }
  });

  afterEach(() => {
    // Restore real Date
    global.Date = RealDate;
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  /**
   * Helper to mock a specific date
   */
  function mockDate(month, day, year = 2025) {
    const mockedDate = new RealDate(year, month - 1, day, 12, 0, 0);

    global.Date = class extends RealDate {
      constructor(...args) {
        if (args.length === 0) {
          super(year, month - 1, day, 12, 0, 0);
          return mockedDate;
        }
        super(...args);
      }

      static now() {
        return mockedDate.getTime();
      }
    };

    // Copy static methods
    global.Date.UTC = RealDate.UTC;
    global.Date.parse = RealDate.parse;
  }

  /**
   * Helper to load snek module and get injected style content
   */
  function loadSnekAndGetStyleContent() {
    // Override jQuery's ready to call callbacks immediately
    const originalReady = $.fn.ready;
    $.fn.ready = function(callback) {
      if (typeof callback === 'function') {
        callback.call(document, $);
      }
      return this;
    };

    // Also override the shorthand $(function(){})
    const original$ = window.$;
    window.$ = function(arg) {
      if (typeof arg === 'function') {
        // This is $(function(){}) shorthand for document ready
        arg.call(document, original$);
        return original$(document);
      }
      return original$(arg);
    };
    // Copy over jQuery methods
    Object.assign(window.$, original$);
    window.$.fn = original$.fn;

    jest.isolateModules(() => {
      require('../../../static/js/snek.js');
    });

    // Restore
    $.fn.ready = originalReady;
    window.$ = original$;

    const styleTag = document.getElementById('seasonal-styles');
    return styleTag ? styleTag.innerHTML : null;
  }

  describe('Seasonal Styles via DOM Injection', () => {
    test('should inject Earth Day style on April 21', () => {
      mockDate(4, 21);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#earth-day)');
      expect(styleContent).toContain('blue');
    });

    test('should inject party style on July 22', () => {
      mockDate(7, 22);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#party)');
      expect(styleContent).toContain('purple');
    });

    test('should inject visibility style on March 31 (Trans Day of Visibility)', () => {
      mockDate(3, 31);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#visibility)');
      expect(styleContent).toContain('purple');
    });

    test('should inject pink style on March 8 (International Women\'s Day)', () => {
      mockDate(3, 8);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('pink');
      expect(styleContent).toContain('red');
    });

    test('should inject lightblue style on November 19 (International Men\'s Day)', () => {
      mockDate(11, 19);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('lightblue');
      expect(styleContent).toContain('blue');
    });

    test('should inject green style on March 17 (St. Patrick\'s Day)', () => {
      mockDate(3, 17);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('lightgreen');
      expect(styleContent).toContain('green');
    });

    test('should inject Pride style during June', () => {
      mockDate(6, 15);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#pride)');
      expect(styleContent).toContain('url(#progress)');
    });

    test('should inject Halloween style during October', () => {
      mockDate(10, 15);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#spider-web)');
      expect(styleContent).toContain('black');
    });

    test('should inject Christmas style during December', () => {
      mockDate(12, 25);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#candy-cane)');
      expect(styleContent).toContain('red');
    });

    test('should inject Christmas style during first week of January', () => {
      mockDate(1, 5);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#candy-cane)');
      expect(styleContent).toContain('red');
    });

    test('should inject default style on a regular day', () => {
      mockDate(2, 15); // February 15 - no special day
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('#646464');
      expect(styleContent).toContain('#eea9b8');
    });

    test('should inject Easter style around Easter Sunday 2025 (April 20)', () => {
      mockDate(4, 20, 2025);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#easter-eggs)');
      expect(styleContent).toContain('orange');
    });

    test('should inject Easter style within a week of Easter', () => {
      // Easter 2025 is April 20, test April 18
      mockDate(4, 18, 2025);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#easter-eggs)');
      expect(styleContent).toContain('orange');
    });
  });

  describe('Click Counter', () => {
    beforeEach(() => {
      mockDate(2, 15); // Regular day

      // Override jQuery's ready to call callbacks immediately
      const originalReady = $.fn.ready;
      $.fn.ready = function(callback) {
        if (typeof callback === 'function') {
          callback.call(document, $);
        }
        return this;
      };

      jest.isolateModules(() => {
        require('../../../static/js/snek.js');
      });

      $.fn.ready = originalReady;
    });

    test('should not add annoyed class before 5 clicks', () => {
      const leftSnek = $('#left-snek');

      for (let i = 0; i < 4; i++) {
        leftSnek.trigger('click');
      }

      expect(leftSnek.hasClass('annoyed')).toBe(false);
      expect($('#right-snek').hasClass('annoyed')).toBe(false);
    });

    test('should add annoyed class after 5 clicks', () => {
      const leftSnek = $('#left-snek');

      for (let i = 0; i < 5; i++) {
        leftSnek.trigger('click');
      }

      expect(leftSnek.hasClass('annoyed')).toBe(true);
      expect($('#right-snek').hasClass('annoyed')).toBe(true);
    });

    test('should add annoyed class after more than 5 clicks', () => {
      const leftSnek = $('#left-snek');

      for (let i = 0; i < 10; i++) {
        leftSnek.trigger('click');
      }

      expect(leftSnek.hasClass('annoyed')).toBe(true);
    });
  });

  describe('Scroll Behavior', () => {
    beforeEach(() => {
      mockDate(2, 15); // Regular day
      jest.isolateModules(() => {
        require('../../../static/js/snek.js');
      });
    });

    test('should not show location pin when scroll is below 100', () => {
      // Mock scrollTop to return 50
      $.fn.scrollTop = jest.fn(() => 50);

      $(window).trigger('scroll');

      expect($('#location-pin').hasClass('visible')).toBe(false);
    });

    test('should show location pin when scroll exceeds 100', () => {
      // Mock scrollTop to return 150
      $.fn.scrollTop = jest.fn(() => 150);

      $(window).trigger('scroll');

      expect($('#location-pin').hasClass('visible')).toBe(true);
    });
  });

  describe('Easter Date Calculation', () => {
    // Easter dates for verification:
    // 2024: March 31 (but also Trans Day of Visibility, which takes precedence)
    // 2025: April 20
    // 2026: April 5

    test('should prioritize Trans Day of Visibility over Easter on March 31, 2024', () => {
      mockDate(3, 31, 2024);
      const styleContent = loadSnekAndGetStyleContent();
      // Trans Day takes precedence due to order in code
      expect(styleContent).toContain('url(#visibility)');
    });

    test('should show Easter style for Easter 2026 (April 5)', () => {
      mockDate(4, 5, 2026);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#easter-eggs)');
      expect(styleContent).toContain('orange');
    });

    test('should show Easter style a few days before Easter 2025', () => {
      mockDate(4, 15, 2025); // 5 days before Easter (April 20)
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#easter-eggs)');
    });
  });

  describe('Edge Cases', () => {
    test('should show default style on January 8 (after Christmas)', () => {
      mockDate(1, 8);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('#646464');
    });

    test('should show Christmas style on December 1', () => {
      mockDate(12, 1);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#candy-cane)');
    });

    test('should show Halloween style on October 1', () => {
      mockDate(10, 1);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#spider-web)');
    });

    test('should show Pride style on June 30 (last day of Pride)', () => {
      mockDate(6, 30);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('url(#pride)');
    });

    test('should show default style on July 1 (after Pride)', () => {
      mockDate(7, 1);
      const styleContent = loadSnekAndGetStyleContent();
      // July 1 is not a special day (July 22 is), so default
      expect(styleContent).toContain('#646464');
    });
  });

  describe('Style Tag Structure', () => {
    test('should create style tag with correct ID', () => {
      mockDate(2, 15);
      const styleContent = loadSnekAndGetStyleContent();

      const styleTag = document.getElementById('seasonal-styles');
      expect(styleTag).toBeTruthy();
      expect(styleTag.tagName.toLowerCase()).toBe('style');
    });

    test('should target smol-snek-body path elements', () => {
      mockDate(2, 15);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('#smol-snek-body path');
    });

    test('should target smol-snek-tongue path elements', () => {
      mockDate(2, 15);
      const styleContent = loadSnekAndGetStyleContent();
      expect(styleContent).toContain('#smol-snek-tongue path');
    });
  });
});
