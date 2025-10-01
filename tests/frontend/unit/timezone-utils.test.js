/**
 * Tests for Timezone Utilities
 */

describe('TimezoneUtils', () => {
  let TimezoneUtils;
  let originalLuxon;

  beforeEach(() => {
    // Clear any existing window properties
    delete window.TimezoneUtils;
    delete window.luxon;

    // Mock luxon library
    originalLuxon = global.luxon;
    const mockDateTime = {
      fromSQL: jest.fn(),
      fromISO: jest.fn(),
      fromJSDate: jest.fn(),
      now: jest.fn(),
      toJSDate: jest.fn(),
      toLocaleString: jest.fn(),
      toFormat: jest.fn(),
      toRelative: jest.fn(),
      setZone: jest.fn(),
      invalid: false,
      zoneName: 'America/New_York',
      DATE_SHORT: 'DATE_SHORT',
      DATETIME_FULL: 'DATETIME_FULL',
      DATETIME_HUGE_WITH_SECONDS: 'DATETIME_HUGE_WITH_SECONDS'
    };

    mockDateTime.now.mockReturnValue(mockDateTime);
    mockDateTime.setZone.mockReturnValue(mockDateTime);
    mockDateTime.toFormat.mockImplementation((format) => {
      if (format === 'ZZZ') return '-05:00';
      if (format === 'ZZZZ') return 'EST';
      return '';
    });

    global.luxon = {
      DateTime: mockDateTime
    };
    window.luxon = global.luxon;

    // Load the timezone-utils module
    const script = require('fs').readFileSync(
      require('path').resolve(__dirname, '../../../static/js/timezone-utils.js'),
      'utf8'
    );
    eval(script);

    TimezoneUtils = window.TimezoneUtils;
  });

  afterEach(() => {
    global.luxon = originalLuxon;
    jest.clearAllMocks();
  });

  describe('normalizeTimezone', () => {
    test('should return AOE_TIMEZONE for empty input', () => {
      expect(TimezoneUtils.normalizeTimezone('')).toBe('UTC-12');
      expect(TimezoneUtils.normalizeTimezone(null)).toBe('UTC-12');
      expect(TimezoneUtils.normalizeTimezone(undefined)).toBe('UTC-12');
    });

    test('should map common timezone aliases', () => {
      expect(TimezoneUtils.normalizeTimezone('AoE')).toBe('UTC-12');
      expect(TimezoneUtils.normalizeTimezone('AOE')).toBe('UTC-12');
      expect(TimezoneUtils.normalizeTimezone('Anywhere on Earth')).toBe('UTC-12');
      expect(TimezoneUtils.normalizeTimezone('EST')).toBe('America/New_York');
      expect(TimezoneUtils.normalizeTimezone('PST')).toBe('America/Los_Angeles');
      expect(TimezoneUtils.normalizeTimezone('CET')).toBe('Europe/Paris');
      expect(TimezoneUtils.normalizeTimezone('JST')).toBe('Asia/Tokyo');
    });

    test('should return IANA timezone unchanged', () => {
      expect(TimezoneUtils.normalizeTimezone('America/New_York')).toBe('America/New_York');
      expect(TimezoneUtils.normalizeTimezone('Europe/London')).toBe('Europe/London');
      expect(TimezoneUtils.normalizeTimezone('Asia/Tokyo')).toBe('Asia/Tokyo');
    });
  });

  describe('parseConferenceDate', () => {
    test('should handle special case date strings', () => {
      expect(TimezoneUtils.parseConferenceDate('TBA', 'UTC').warning).toBe('TBA');
      expect(TimezoneUtils.parseConferenceDate('Cancelled', 'UTC').warning).toBe('Cancelled');
      expect(TimezoneUtils.parseConferenceDate('None', 'UTC').warning).toBe('None');
      expect(TimezoneUtils.parseConferenceDate('', 'UTC').warning).toBe('TBA');
    });

    test('should parse valid SQL date with timezone', () => {
      const mockDt = {
        invalid: false,
        toJSDate: jest.fn().mockReturnValue(new Date('2025-03-15T23:59:00Z'))
      };

      luxon.DateTime.fromSQL.mockReturnValue(mockDt);

      const result = TimezoneUtils.parseConferenceDate('2025-03-15 23:59:00', 'America/New_York');

      expect(result.isValid).toBe(true);
      expect(result.date).toBe(mockDt);
      expect(result.normalizedTimezone).toBe('America/New_York');
      expect(luxon.DateTime.fromSQL).toHaveBeenCalledWith('2025-03-15 23:59:00', { zone: 'America/New_York' });
    });

    test('should fallback to ISO parsing if SQL parsing fails', () => {
      const invalidDt = { invalid: true };
      const validDt = {
        invalid: false,
        toJSDate: jest.fn().mockReturnValue(new Date('2025-03-15T23:59:00Z'))
      };

      luxon.DateTime.fromSQL.mockReturnValue(invalidDt);
      luxon.DateTime.fromISO.mockReturnValue(validDt);

      const result = TimezoneUtils.parseConferenceDate('2025-03-15T23:59:00', 'America/New_York');

      expect(result.isValid).toBe(true);
      expect(result.date).toBe(validDt);
      expect(luxon.DateTime.fromISO).toHaveBeenCalled();
    });

    test('should fallback to JS Date parsing as last resort', () => {
      const invalidDt = { invalid: true };
      const validDt = {
        invalid: false,
        toJSDate: jest.fn().mockReturnValue(new Date('2025-03-15T23:59:00Z'))
      };

      luxon.DateTime.fromSQL.mockReturnValue(invalidDt);
      luxon.DateTime.fromISO.mockReturnValue(invalidDt);
      luxon.DateTime.fromJSDate.mockReturnValue(validDt);

      const result = TimezoneUtils.parseConferenceDate('March 15, 2025', 'America/New_York');

      expect(result.isValid).toBe(true);
      expect(result.warning).toBe('Parsed using fallback method');
    });

    test('should handle invalid timezone with fallback', () => {
      const invalidDt = { invalid: true };
      const validDt = {
        invalid: false,
        toJSDate: jest.fn().mockReturnValue(new Date('2025-03-15T23:59:00Z'))
      };

      luxon.DateTime.fromSQL
        .mockReturnValueOnce(invalidDt)  // First call with invalid timezone
        .mockReturnValueOnce(validDt);    // Second call without timezone

      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      const result = TimezoneUtils.parseConferenceDate('2025-03-15 23:59:00', 'INVALID/TZ');

      expect(result.isValid).toBe(true);
      expect(result.warning).toContain('Invalid timezone');
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    test('should work without luxon library', () => {
      delete window.luxon;
      delete global.luxon;

      const result = TimezoneUtils.parseConferenceDate('2025-03-15T23:59:00Z', 'America/New_York');

      expect(result.isValid).toBe(true);
      expect(result.jsDate).toBeInstanceOf(Date);
      expect(result.warning).toBe('Using basic Date parsing (Luxon not available)');
    });
  });

  describe('formatConferenceDate', () => {
    test('should return warning for invalid date', () => {
      const invalidDateInfo = {
        isValid: false,
        warning: 'Invalid date format'
      };

      expect(TimezoneUtils.formatConferenceDate(invalidDateInfo)).toBe('Invalid date format');
    });

    test('should format date in short format', () => {
      const mockDt = {
        toLocaleString: jest.fn().mockReturnValue('3/15/25')
      };

      const dateInfo = {
        isValid: true,
        date: mockDt
      };

      const result = TimezoneUtils.formatConferenceDate(dateInfo, 'short');

      expect(result).toBe('3/15/25');
      expect(mockDt.toLocaleString).toHaveBeenCalledWith('DATE_SHORT');
    });

    test('should format date in long format', () => {
      const mockDt = {
        toLocaleString: jest.fn().mockReturnValue('March 15, 2025, 11:59 PM EST')
      };

      const dateInfo = {
        isValid: true,
        date: mockDt
      };

      const result = TimezoneUtils.formatConferenceDate(dateInfo, 'long');

      expect(result).toBe('March 15, 2025, 11:59 PM EST');
      expect(mockDt.toLocaleString).toHaveBeenCalledWith('DATETIME_FULL');
    });

    test('should format date in relative format', () => {
      const mockDt = {
        toRelative: jest.fn().mockReturnValue('in 2 days')
      };

      const dateInfo = {
        isValid: true,
        date: mockDt
      };

      const result = TimezoneUtils.formatConferenceDate(dateInfo, 'relative');

      expect(result).toBe('in 2 days');
      expect(mockDt.toRelative).toHaveBeenCalled();
    });

    test('should fallback to JS Date formatting without luxon', () => {
      const jsDate = new Date('2025-03-15T23:59:00Z');
      const dateInfo = {
        isValid: true,
        jsDate: jsDate,
        date: null
      };

      const result = TimezoneUtils.formatConferenceDate(dateInfo);

      expect(result).toBe(jsDate.toLocaleString());
    });

    test('should handle formatting errors gracefully', () => {
      const mockDt = {
        toLocaleString: jest.fn().mockImplementation(() => {
          throw new Error('Format error');
        })
      };

      const dateInfo = {
        isValid: true,
        date: mockDt,
        warning: 'Fallback warning'
      };

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const result = TimezoneUtils.formatConferenceDate(dateInfo);

      expect(result).toBe('Fallback warning');
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('getTimezoneDisplay', () => {
    test('should format timezone display with offset', () => {
      const result = TimezoneUtils.getTimezoneDisplay('America/New_York');

      expect(result).toBe('EST (-05:00)');
      expect(luxon.DateTime.now).toHaveBeenCalled();
    });

    test('should handle timezone aliases', () => {
      const result = TimezoneUtils.getTimezoneDisplay('EST');

      expect(result).toBe('EST (-05:00)');
    });

    test('should return original timezone on error', () => {
      luxon.DateTime.now.mockImplementation(() => {
        throw new Error('Timezone error');
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const result = TimezoneUtils.getTimezoneDisplay('America/New_York');

      expect(result).toBe('America/New_York');
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    test('should return AOE_TIMEZONE for empty input', () => {
      // When empty, getTimezoneDisplay still tries to format it
      // Set up mock to handle empty timezone case
      const mockDt = {
        invalid: true
      };
      luxon.DateTime.now().setZone.mockReturnValue(mockDt);

      const result = TimezoneUtils.getTimezoneDisplay('');

      expect(result).toBe('UTC-12');
    });

    test('should work without luxon', () => {
      delete window.luxon;
      delete global.luxon;

      const result = TimezoneUtils.getTimezoneDisplay('America/New_York');

      expect(result).toBe('America/New_York');
    });
  });

  describe('getTimeRemaining', () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date('2025-01-10T12:00:00Z'));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('should calculate time remaining correctly', () => {
      const dateInfo = {
        isValid: true,
        jsDate: new Date('2025-01-15T23:59:00Z')
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(false);
      expect(result.days).toBe(5);
      expect(result.hours).toBe(11);
      expect(result.minutes).toBe(59);
      expect(result.display).toBe('5d 11h 59m 0s');
    });

    test('should detect expired deadlines', () => {
      const dateInfo = {
        isValid: true,
        jsDate: new Date('2025-01-05T23:59:00Z')
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(true);
      expect(result.message).toBe('Deadline passed');
    });

    test('should handle invalid dates', () => {
      const dateInfo = {
        isValid: false,
        warning: 'Invalid date'
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(true);
      expect(result.message).toBe('Invalid date');
    });

    test('should calculate hours, minutes, seconds correctly', () => {
      const dateInfo = {
        isValid: true,
        jsDate: new Date('2025-01-10T14:30:45Z')  // 2 hours, 30 minutes, 45 seconds
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(false);
      expect(result.days).toBe(0);
      expect(result.hours).toBe(2);
      expect(result.minutes).toBe(30);
      expect(result.seconds).toBe(45);
    });
  });

  describe('isValidTimezone', () => {
    test('should validate standard IANA timezones', () => {
      const mockDt = { invalid: false };
      luxon.DateTime.now().setZone.mockReturnValue(mockDt);

      expect(TimezoneUtils.isValidTimezone('America/New_York')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('Europe/London')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('Asia/Tokyo')).toBe(true);
    });

    test('should validate timezone aliases', () => {
      const mockDt = { invalid: false };
      luxon.DateTime.now().setZone.mockReturnValue(mockDt);

      expect(TimezoneUtils.isValidTimezone('EST')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('AoE')).toBe(true);
    });

    test('should detect invalid timezones', () => {
      const mockDt = { invalid: true };
      luxon.DateTime.now().setZone.mockReturnValue(mockDt);

      expect(TimezoneUtils.isValidTimezone('Invalid/Timezone')).toBe(false);
    });

    test('should return false for empty input', () => {
      expect(TimezoneUtils.isValidTimezone('')).toBe(false);
      expect(TimezoneUtils.isValidTimezone(null)).toBe(false);
      expect(TimezoneUtils.isValidTimezone(undefined)).toBe(false);
    });

    test('should use basic validation without luxon', () => {
      delete window.luxon;
      delete global.luxon;

      expect(TimezoneUtils.isValidTimezone('America/New_York')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('UTC-12')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('Invalid')).toBe(false);
    });

    test('should handle timezone validation errors', () => {
      luxon.DateTime.now().setZone.mockImplementation(() => {
        throw new Error('Validation error');
      });

      expect(TimezoneUtils.isValidTimezone('America/New_York')).toBe(false);
    });
  });

  describe('getUserTimezone', () => {
    test('should get user timezone from luxon', () => {
      const result = TimezoneUtils.getUserTimezone();

      expect(result).toBe('America/New_York');
      expect(luxon.DateTime.now).toHaveBeenCalled();
    });

    test('should fallback to Intl API without luxon', () => {
      delete window.luxon;
      delete global.luxon;

      const mockResolvedOptions = {
        timeZone: 'Europe/Berlin'
      };

      const originalIntl = global.Intl;
      global.Intl = {
        DateTimeFormat: jest.fn().mockReturnValue({
          resolvedOptions: jest.fn().mockReturnValue(mockResolvedOptions)
        })
      };

      const result = TimezoneUtils.getUserTimezone();

      expect(result).toBe('Europe/Berlin');

      global.Intl = originalIntl;
    });

    test('should fallback to UTC on error', () => {
      delete window.luxon;
      delete global.luxon;

      const originalIntl = global.Intl;
      global.Intl = {
        DateTimeFormat: jest.fn().mockImplementation(() => {
          throw new Error('Intl not supported');
        })
      };

      const result = TimezoneUtils.getUserTimezone();

      expect(result).toBe('UTC');

      global.Intl = originalIntl;
    });
  });

  describe('Constants', () => {
    test('should export AOE_TIMEZONE constant', () => {
      expect(TimezoneUtils.AOE_TIMEZONE).toBe('UTC-12');
    });

    test('should export TIMEZONE_ALIASES object', () => {
      expect(TimezoneUtils.TIMEZONE_ALIASES).toHaveProperty('EST', 'America/New_York');
      expect(TimezoneUtils.TIMEZONE_ALIASES).toHaveProperty('PST', 'America/Los_Angeles');
      expect(TimezoneUtils.TIMEZONE_ALIASES).toHaveProperty('AoE', 'UTC-12');
    });
  });

  describe('Edge Cases', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('should handle leap year dates', () => {
      // Set current time to Feb 28, 2024
      jest.setSystemTime(new Date('2024-02-28T12:00:00Z'));

      const dateInfo = {
        isValid: true,
        jsDate: new Date('2024-02-29T23:59:00Z')  // Leap day deadline
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(false);
      expect(result.days).toBe(1);
      expect(result.hours).toBe(11);
      expect(result.minutes).toBe(59);
    });

    test('should handle daylight saving time transitions', () => {
      const mockDt = {
        invalid: false,
        toJSDate: jest.fn().mockReturnValue(new Date('2025-03-09T07:00:00Z')),
        toFormat: jest.fn().mockImplementation((format) => {
          if (format === 'ZZZ') return '-04:00';  // EDT
          if (format === 'ZZZZ') return 'EDT';
          return '';
        })
      };

      luxon.DateTime.fromSQL.mockReturnValue(mockDt);
      luxon.DateTime.now().setZone.mockReturnValue(mockDt);

      const result = TimezoneUtils.getTimezoneDisplay('America/New_York');

      expect(result).toBe('EDT (-04:00)');
    });

    test('should handle timezones with underscores and slashes', () => {
      expect(TimezoneUtils.isValidTimezone('America/Indiana/Knox')).toBe(true);
      expect(TimezoneUtils.isValidTimezone('America/North_Dakota/Center')).toBe(true);
    });

    test('should handle very long deadline calculations', () => {
      // Set current time to Jan 10, 2025
      jest.setSystemTime(new Date('2025-01-10T12:00:00Z'));

      const dateInfo = {
        isValid: true,
        jsDate: new Date('2025-05-05T12:00:00Z')  // 115 days in future
      };

      const result = TimezoneUtils.getTimeRemaining(dateInfo);

      expect(result.expired).toBe(false);
      expect(result.days).toBe(115);
      expect(result.hours).toBe(0);
      expect(result.minutes).toBe(0);
    });
  });
});