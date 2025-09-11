/**
 * Tests for countdown-simple.js
 */

import { TimerController, mockLuxonDateTime } from '../utils/mockHelpers';
import { createConferenceWithDeadline, setupConferenceDOM } from '../utils/dataHelpers';

describe('Countdown Timer System', () => {
  let timerController;
  let luxonMock;
  
  beforeEach(() => {
    timerController = new TimerController();
    timerController.setCurrentTime('2024-01-15 12:00:00');
    
    // Mock Luxon
    luxonMock = mockLuxonDateTime();
    
    // Clear any existing intervals
    jest.clearAllTimers();
  });
  
  afterEach(() => {
    timerController.cleanup();
  });
  
  describe('Timer Initialization', () => {
    test('initializes countdown timer on page load', () => {
      document.body.innerHTML = `
        <div class="countdown-display" 
             data-deadline="2024-01-22 23:59:59" 
             data-timezone="UTC">
        </div>
      `;
      
      // Load the countdown script
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Should have set up an interval
      expect(setInterval).toHaveBeenCalledWith(expect.any(Function), 1000);
    });
    
    test('updates all countdown elements every second', () => {
      // Set up multiple countdowns
      document.body.innerHTML = `
        <div class="countdown-display" id="cd1"
             data-deadline="2024-01-22 23:59:59" 
             data-timezone="UTC">
        </div>
        <div class="countdown-display" id="cd2"
             data-deadline="2024-01-25 23:59:59" 
             data-timezone="UTC">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Advance timer by 1 second
      timerController.advanceTime(1000);
      
      // Both elements should have content
      const cd1 = document.getElementById('cd1');
      const cd2 = document.getElementById('cd2');
      
      expect(cd1.textContent).toBeTruthy();
      expect(cd2.textContent).toBeTruthy();
    });
  });
  
  describe('Countdown Display Formats', () => {
    beforeEach(() => {
      // Mock Luxon DateTime more specifically for these tests
      const createMockDateTime = (days, hours, minutes, seconds) => ({
        invalid: false,
        diff: jest.fn(() => ({
          days,
          hours,
          minutes,
          seconds,
          toMillis: () => (days * 24 * 60 * 60 + hours * 60 * 60 + minutes * 60 + seconds) * 1000
        }))
      });
      
      window.luxon = {
        DateTime: {
          now: jest.fn(() => ({ toMillis: () => Date.now() })),
          fromSQL: jest.fn(() => createMockDateTime(7, 12, 30, 45)),
          fromISO: jest.fn(() => createMockDateTime(7, 12, 30, 45))
        }
      };
    });
    
    test('displays full format for regular countdown', () => {
      document.body.innerHTML = `
        <div class="countdown-display" id="regular"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('regular');
      expect(element.textContent).toMatch(/\d+ days \d+h \d+m \d+s/);
    });
    
    test('displays compact format for small countdown', () => {
      document.body.innerHTML = `
        <div class="countdown-display countdown-small" id="small"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('small');
      expect(element.textContent).toMatch(/\d+d \d{2}:\d{2}:\d{2}/);
    });
  });
  
  describe('Deadline States', () => {
    test('shows "Deadline passed" for past deadlines', () => {
      // Mock Luxon to return negative diff
      window.luxon = {
        DateTime: {
          now: jest.fn(() => ({ toMillis: () => Date.now() })),
          fromSQL: jest.fn(() => ({
            invalid: false,
            diff: jest.fn(() => ({
              days: -1,
              hours: -5,
              minutes: 0,
              seconds: 0,
              toMillis: () => -1 * 24 * 60 * 60 * 1000
            }))
          })),
          fromISO: jest.fn(() => ({
            invalid: false,
            diff: jest.fn(() => ({
              days: -1,
              hours: -5,
              minutes: 0,
              seconds: 0,
              toMillis: () => -1 * 24 * 60 * 60 * 1000
            }))
          }))
        }
      };
      
      document.body.innerHTML = `
        <div class="countdown-display" id="past"
             data-deadline="2024-01-10 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('past');
      expect(element.textContent).toContain('Deadline passed');
      expect(element).toHaveClass('deadline-passed');
    });
    
    test('shows "Passed" for small countdown past deadline', () => {
      // Mock Luxon to return negative diff
      window.luxon = {
        DateTime: {
          now: jest.fn(() => ({ toMillis: () => Date.now() })),
          fromSQL: jest.fn(() => ({
            invalid: false,
            diff: jest.fn(() => ({
              toMillis: () => -1000
            }))
          })),
          fromISO: jest.fn(() => ({
            invalid: false,
            diff: jest.fn(() => ({
              toMillis: () => -1000
            }))
          }))
        }
      };
      
      document.body.innerHTML = `
        <div class="countdown-display countdown-small" id="past-small"
             data-deadline="2024-01-10 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('past-small');
      expect(element.textContent).toBe('Passed');
    });
    
    test('skips TBA deadlines', () => {
      document.body.innerHTML = `
        <div class="countdown-display" id="tba"
             data-deadline="TBA">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('tba');
      expect(element.textContent).toBe('');
    });
    
    test('skips Cancelled deadlines', () => {
      document.body.innerHTML = `
        <div class="countdown-display" id="cancelled"
             data-deadline="Cancelled">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('cancelled');
      expect(element.textContent).toBe('');
    });
  });
  
  describe('Timezone Handling', () => {
    test('uses specified timezone for countdown', () => {
      const fromSQLSpy = jest.spyOn(window.luxon.DateTime, 'fromSQL');
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59"
             data-timezone="America/New_York">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      expect(fromSQLSpy).toHaveBeenCalledWith(
        '2024-01-22 23:59:59',
        expect.objectContaining({ zone: 'America/New_York' })
      );
    });
    
    test('defaults to UTC-12 (AoE) if no timezone specified', () => {
      const fromSQLSpy = jest.spyOn(window.luxon.DateTime, 'fromSQL');
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      expect(fromSQLSpy).toHaveBeenCalledWith(
        '2024-01-22 23:59:59',
        expect.objectContaining({ zone: 'UTC-12' })
      );
    });
    
    test('falls back to system timezone on invalid timezone', () => {
      // Mock invalid timezone handling
      let callCount = 0;
      window.luxon.DateTime.fromSQL = jest.fn(() => {
        callCount++;
        return {
          invalid: callCount === 1, // First call returns invalid
          diff: jest.fn(() => ({
            days: 7,
            hours: 12,
            minutes: 30,
            seconds: 45,
            toMillis: () => 7 * 24 * 60 * 60 * 1000
          }))
        };
      });
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59"
             data-timezone="Invalid/Zone">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Should try multiple times
      expect(window.luxon.DateTime.fromSQL).toHaveBeenCalledTimes(2);
    });
  });
  
  describe('Date Format Parsing', () => {
    test('parses SQL format dates', () => {
      const fromSQLSpy = jest.spyOn(window.luxon.DateTime, 'fromSQL');
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      expect(fromSQLSpy).toHaveBeenCalled();
    });
    
    test('falls back to ISO format if SQL parsing fails', () => {
      // Mock to make fromSQL return invalid
      window.luxon.DateTime.fromSQL = jest.fn(() => ({ invalid: true }));
      const fromISOSpy = jest.spyOn(window.luxon.DateTime, 'fromISO');
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22T23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      expect(fromISOSpy).toHaveBeenCalled();
    });
    
    test('shows error for invalid date formats', () => {
      // Mock both parsing methods to fail
      window.luxon.DateTime.fromSQL = jest.fn(() => ({ invalid: true }));
      window.luxon.DateTime.fromISO = jest.fn(() => ({ invalid: true }));
      
      document.body.innerHTML = `
        <div class="countdown-display" id="invalid"
             data-deadline="not-a-date">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('invalid');
      expect(element.textContent).toBe('Invalid date');
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining('Invalid deadline format'),
        'not-a-date'
      );
    });
  });
  
  describe('Performance and Memory', () => {
    test('uses single shared timer for all countdowns', () => {
      document.body.innerHTML = `
        ${Array(10).fill().map((_, i) => `
          <div class="countdown-display"
               data-deadline="2024-01-22 23:59:59"
               data-timezone="UTC">
          </div>
        `).join('')}
      `;
      
      const setIntervalSpy = jest.spyOn(global, 'setInterval');
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Should only create one interval
      expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    });
    
    test('clears timer on page unload', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Simulate page unload
      const unloadEvent = new Event('beforeunload');
      window.dispatchEvent(unloadEvent);
      
      expect(clearIntervalSpy).toHaveBeenCalled();
    });
    
    test('handles dynamic countdown addition', () => {
      document.body.innerHTML = `
        <div class="countdown-display" id="original"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      // Add new countdown dynamically
      const newCountdown = document.createElement('div');
      newCountdown.className = 'countdown-display';
      newCountdown.id = 'dynamic';
      newCountdown.dataset.deadline = '2024-01-25 23:59:59';
      document.body.appendChild(newCountdown);
      
      // Advance timer
      timerController.advanceTime(1000);
      
      // New countdown should also be updated
      expect(document.getElementById('dynamic').textContent).toBeTruthy();
    });
  });
  
  describe('Edge Cases', () => {
    test('handles missing Luxon library gracefully', () => {
      // Remove Luxon
      delete window.luxon;
      
      document.body.innerHTML = `
        <div class="countdown-display"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      // Should not throw error
      expect(() => {
        jest.isolateModules(() => {
          require('../../../static/js/countdown-simple.js');
        });
      }).not.toThrow();
      
      expect(console.error).toHaveBeenCalledWith(
        'Luxon DateTime not available. Countdowns disabled.'
      );
    });
    
    test('handles error in date parsing gracefully', () => {
      // Mock to throw error
      window.luxon.DateTime.fromSQL = jest.fn(() => {
        throw new Error('Parse error');
      });
      
      document.body.innerHTML = `
        <div class="countdown-display" id="error"
             data-deadline="2024-01-22 23:59:59">
        </div>
      `;
      
      jest.isolateModules(() => {
        require('../../../static/js/countdown-simple.js');
      });
      
      const element = document.getElementById('error');
      expect(element.textContent).toBe('Error');
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('Error parsing deadline'),
        expect.any(Error)
      );
    });
  });
});