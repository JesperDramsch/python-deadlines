/**
 * Timezone Utilities for Python Deadlines
 * Provides consistent timezone handling across the site
 */

(function(window) {
    'use strict';

    // Default timezone for "Anywhere on Earth"
    const AOE_TIMEZONE = 'UTC-12';

    // Common timezone aliases that need mapping
    const TIMEZONE_ALIASES = {
        'AoE': AOE_TIMEZONE,
        'AOE': AOE_TIMEZONE,
        'Anywhere on Earth': AOE_TIMEZONE,
        'EST': 'America/New_York',
        'EDT': 'America/New_York',
        'CST': 'America/Chicago',
        'CDT': 'America/Chicago',
        'MST': 'America/Denver',
        'MDT': 'America/Denver',
        'PST': 'America/Los_Angeles',
        'PDT': 'America/Los_Angeles',
        'BST': 'Europe/London',
        'CET': 'Europe/Paris',
        'CEST': 'Europe/Paris',
        'JST': 'Asia/Tokyo',
        'IST': 'Asia/Kolkata',
        'AEST': 'Australia/Sydney',
        'AEDT': 'Australia/Sydney'
    };

    /**
     * Normalize timezone string to IANA format
     * @param {string} timezone - Input timezone string
     * @returns {string} Normalized timezone
     */
    function normalizeTimezone(timezone) {
        if (!timezone) {
            return AOE_TIMEZONE;
        }

        // Check if it's an alias
        if (TIMEZONE_ALIASES[timezone]) {
            return TIMEZONE_ALIASES[timezone];
        }

        // Return as-is if it looks like a valid IANA timezone
        return timezone;
    }

    /**
     * Parse date with timezone handling and fallback
     * @param {string} dateStr - Date string to parse
     * @param {string} timezone - Timezone string
     * @returns {Object} Object with date and warning info
     */
    function parseConferenceDate(dateStr, timezone) {
        const result = {
            date: null,
            jsDate: null,
            timezone: timezone,
            normalizedTimezone: null,
            warning: null,
            isValid: false
        };

        // Handle special cases
        if (!dateStr || dateStr === 'TBA' || dateStr === 'Cancelled' || dateStr === 'None') {
            result.warning = dateStr || 'TBA';
            return result;
        }

        // Normalize timezone
        const normalizedTz = normalizeTimezone(timezone);
        result.normalizedTimezone = normalizedTz;

        try {
            if (typeof luxon !== 'undefined') {
                const DateTime = luxon.DateTime;

                // Try parsing with provided timezone
                let dt = DateTime.fromSQL(dateStr, { zone: normalizedTz });

                // If invalid, try without timezone
                if (dt.invalid) {
                    dt = DateTime.fromSQL(dateStr);

                    if (!dt.invalid) {
                        result.warning = `Invalid timezone "${timezone}", using system timezone`;
                        console.warn(`Invalid timezone for date ${dateStr}: ${timezone}. Using system timezone.`);
                    }
                }

                // If still invalid, try ISO format
                if (dt.invalid) {
                    dt = DateTime.fromISO(dateStr, { zone: normalizedTz });
                }

                // If still invalid, try JS Date parsing as last resort
                if (dt.invalid) {
                    const jsDate = new Date(dateStr);
                    if (!isNaN(jsDate)) {
                        dt = DateTime.fromJSDate(jsDate);
                        result.warning = `Parsed using fallback method`;
                    }
                }

                if (!dt.invalid) {
                    result.date = dt;
                    result.jsDate = dt.toJSDate();
                    result.isValid = true;
                } else {
                    result.warning = `Could not parse date: ${dateStr}`;
                    console.error(`Failed to parse date: ${dateStr} with timezone: ${timezone}`);
                }

            } else {
                // Fallback when Luxon is not available
                const jsDate = new Date(dateStr);

                if (!isNaN(jsDate)) {
                    result.jsDate = jsDate;
                    result.isValid = true;
                    result.warning = 'Using basic Date parsing (Luxon not available)';
                } else {
                    result.warning = `Invalid date: ${dateStr}`;
                }
            }
        } catch (error) {
            result.warning = `Error parsing date: ${error.message}`;
            console.error('Date parsing error:', error);
        }

        return result;
    }

    /**
     * Format date for display with proper timezone
     * @param {Object} dateInfo - Result from parseConferenceDate
     * @param {string} format - Display format (short, long, huge)
     * @returns {string} Formatted date string
     */
    function formatConferenceDate(dateInfo, format = 'long') {
        if (!dateInfo.isValid) {
            return dateInfo.warning || 'Invalid date';
        }

        try {
            if (dateInfo.date && typeof luxon !== 'undefined') {
                const DateTime = luxon.DateTime;

                switch(format) {
                    case 'short':
                        return dateInfo.date.toLocaleString(DateTime.DATE_SHORT);
                    case 'long':
                        return dateInfo.date.toLocaleString(DateTime.DATETIME_FULL);
                    case 'huge':
                        return dateInfo.date.toLocaleString(DateTime.DATETIME_HUGE_WITH_SECONDS);
                    case 'relative':
                        return dateInfo.date.toRelative();
                    default:
                        return dateInfo.date.toLocaleString(DateTime.DATETIME_FULL);
                }
            } else if (dateInfo.jsDate) {
                // Fallback formatting
                return dateInfo.jsDate.toLocaleString();
            }
        } catch (error) {
            console.error('Date formatting error:', error);
        }

        return dateInfo.warning || 'Format error';
    }

    /**
     * Get timezone display string with location
     * @param {string} timezone - Timezone identifier
     * @returns {string} Display string like "EST (New York)"
     */
    function getTimezoneDisplay(timezone) {
        const normalized = normalizeTimezone(timezone);

        if (typeof luxon !== 'undefined') {
            try {
                const DateTime = luxon.DateTime;
                const dt = DateTime.now().setZone(normalized);

                if (!dt.invalid) {
                    const offsetStr = dt.toFormat('ZZZ');
                    const abbr = dt.toFormat('ZZZZ');
                    return `${abbr} (${offsetStr})`;
                }
            } catch (error) {
                console.error('Timezone display error:', error);
            }
        }

        return timezone || AOE_TIMEZONE;
    }

    /**
     * Calculate time remaining until deadline
     * @param {Object} dateInfo - Result from parseConferenceDate
     * @returns {Object} Time remaining breakdown
     */
    function getTimeRemaining(dateInfo) {
        if (!dateInfo.isValid) {
            return { expired: true, message: dateInfo.warning };
        }

        const now = new Date();
        const deadline = dateInfo.jsDate;
        const diff = deadline - now;

        if (diff <= 0) {
            return { expired: true, message: 'Deadline passed' };
        }

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        return {
            expired: false,
            days: days,
            hours: hours,
            minutes: minutes,
            seconds: seconds,
            totalMs: diff,
            display: `${days}d ${hours}h ${minutes}m ${seconds}s`
        };
    }

    /**
     * Validate if a timezone string is valid
     * @param {string} timezone - Timezone to validate
     * @returns {boolean} True if valid
     */
    function isValidTimezone(timezone) {
        if (!timezone) return false;

        const normalized = normalizeTimezone(timezone);

        if (typeof luxon !== 'undefined') {
            try {
                const DateTime = luxon.DateTime;
                const dt = DateTime.now().setZone(normalized);
                return !dt.invalid;
            } catch (error) {
                return false;
            }
        }

        // Basic validation without Luxon
        return /^[A-Za-z]+\/[A-Za-z_]+$/.test(normalized) || normalized === AOE_TIMEZONE;
    }

    /**
     * Get user's local timezone
     * @returns {string} IANA timezone string
     */
    function getUserTimezone() {
        if (typeof luxon !== 'undefined') {
            return luxon.DateTime.now().zoneName;
        }

        // Fallback method
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone;
        } catch (error) {
            return 'UTC';
        }
    }

    // Export utilities
    window.TimezoneUtils = {
        normalizeTimezone: normalizeTimezone,
        parseConferenceDate: parseConferenceDate,
        formatConferenceDate: formatConferenceDate,
        getTimezoneDisplay: getTimezoneDisplay,
        getTimeRemaining: getTimeRemaining,
        isValidTimezone: isValidTimezone,
        getUserTimezone: getUserTimezone,
        AOE_TIMEZONE: AOE_TIMEZONE,
        TIMEZONE_ALIASES: TIMEZONE_ALIASES
    };

})(window);
