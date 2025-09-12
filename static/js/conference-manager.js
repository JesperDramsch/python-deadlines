/**
 * ConferenceStateManager - Centralized state management for conference data
 * Handles saved events, followed series, and conference data access
 * Uses hybrid approach: DOM extraction for visible data, on-demand for archive
 */
class ConferenceStateManager {
    constructor(conferenceData) {
        // Initialize conference data maps
        this.allConferences = new Map();
        this.conferenceBySeries = new Map();
        this.archiveLoaded = false;

        // Process initial conference data (only active conferences)
        if (conferenceData) {
            this.processConferenceData(conferenceData);
        }

        // Extract visible conference data from DOM for immediate use
        this.extractVisibleConferences();

        // Load user preferences from localStorage
        // Also check for old storage keys for migration
        const oldFavorites = this.loadFromStorage('pythondeadlines-favorites', []);
        const newSavedEvents = this.loadFromStorage('savedEvents', []);

        // Merge old and new favorites
        this.savedEvents = new Set([...oldFavorites, ...newSavedEvents]);

        // If we migrated old favorites, save them to new location
        if (oldFavorites.length > 0 && newSavedEvents.length === 0) {
            this.persistToStorage('savedEvents', Array.from(this.savedEvents));
        }

        this.followedSeries = new Set(this.loadFromStorage('followedSeries', []));

        // Track notification preferences
        this.notificationSettings = this.loadFromStorage('notificationSettings', {
            enabled: false,
            daysBefore: [7, 3, 1]
        });
    }

    /**
     * Extract conference data from visible DOM elements
     * This avoids needing all data in memory for basic operations
     */
    extractVisibleConferences() {
        // Extract from conference items on the page
        $('.ConfItem').each((index, element) => {
            const $conf = $(element);

            // Extract data from individual data attributes
            const confData = {
                id: $conf.data('conf-id'),
                conference: $conf.data('conf-name'),
                year: $conf.data('conf-year'),
                place: $conf.data('location'),
                cfp: $conf.data('cfp'),
                cfp_ext: $conf.data('cfp-ext'),
                start: $conf.data('start'),
                end: $conf.data('end'),
                link: $conf.data('link'),
                cfp_link: $conf.data('cfp-link'),
                sub: $conf.data('topics'),
                format: $conf.data('format'),
                has_finaid: $conf.data('has-finaid'),
                has_workshop: $conf.data('has-workshop'),
                has_sponsor: $conf.data('has-sponsor')
            };

            // Only process if we have essential data
            if (confData.id && confData.conference) {
                confData.status = 'active';
                this.allConferences.set(confData.id, confData);

                // Index by series
                if (!this.conferenceBySeries.has(confData.conference)) {
                    this.conferenceBySeries.set(confData.conference, []);
                }
                this.conferenceBySeries.get(confData.conference).push(confData);
            }
        });
    }

    /**
     * Process and index conference data for efficient access
     */
    processConferenceData(data) {
        // Process active conferences
        if (data.active) {
            data.active.forEach(conf => {
                const id = this.generateConferenceId(conf);
                conf.id = id;
                conf.status = 'active';
                this.allConferences.set(id, conf);

                // Index by series name
                if (!this.conferenceBySeries.has(conf.conference)) {
                    this.conferenceBySeries.set(conf.conference, []);
                }
                this.conferenceBySeries.get(conf.conference).push(conf);
            });
        }

        // Don't process archive immediately - load on demand
        if (data.archive) {
            this.archiveLoaded = true;
            data.archive.forEach(conf => {
                const id = this.generateConferenceId(conf);
                conf.id = id;
                conf.status = 'archived';
                this.allConferences.set(id, conf);

                // Index by series name
                if (!this.conferenceBySeries.has(conf.conference)) {
                    this.conferenceBySeries.set(conf.conference, []);
                }
                this.conferenceBySeries.get(conf.conference).push(conf);
            });
        }
    }

    /**
     * Load archive data on-demand (for pattern analysis on dashboard)
     */
    async loadArchiveData() {
        if (this.archiveLoaded) return;

        try {
            // Create a JSON endpoint for archive data
            const response = await fetch('/data/archive.json');
            const archiveData = await response.json();

            this.processConferenceData({ archive: archiveData });
            this.archiveLoaded = true;
        } catch (error) {
            console.error('Failed to load archive data:', error);
            // Fall back to extracting from page if available
        }
    }

    /**
     * Generate consistent conference ID
     */
    generateConferenceId(conf) {
        return `${conf.conference}-${conf.year}`.toLowerCase().replace(/[^a-z0-9-]/g, '-');
    }

    /**
     * Get conference by ID
     */
    getConference(id) {
        return this.allConferences.get(id);
    }

    /**
     * Get all conferences in a series
     */
    getConferenceSeries(seriesName) {
        return this.conferenceBySeries.get(seriesName) || [];
    }

    /**
     * Save a specific event
     */
    saveEvent(confId) {
        const conf = this.getConference(confId);
        if (conf) {
            this.savedEvents.add(confId);
            this.persistToStorage('savedEvents', Array.from(this.savedEvents));
            this.triggerUpdate('savedEvents', confId, 'added');
            return true;
        }
        return false;
    }

    /**
     * Remove a saved event
     */
    removeSavedEvent(confId) {
        if (this.savedEvents.delete(confId)) {
            this.persistToStorage('savedEvents', Array.from(this.savedEvents));
            this.triggerUpdate('savedEvents', confId, 'removed');
            return true;
        }
        return false;
    }

    /**
     * Follow a conference series
     */
    followSeries(seriesName) {
        this.followedSeries.add(seriesName);
        this.persistToStorage('followedSeries', Array.from(this.followedSeries));
        this.triggerUpdate('followedSeries', seriesName, 'added');

        // Optionally auto-save current/future events from this series
        const seriesConfs = this.getConferenceSeries(seriesName);
        const now = new Date();
        seriesConfs.forEach(conf => {
            if (conf.cfp && new Date(conf.cfp) > now) {
                this.saveEvent(conf.id);
            }
        });
        return true;
    }

    /**
     * Unfollow a conference series
     */
    unfollowSeries(seriesName) {
        if (this.followedSeries.delete(seriesName)) {
            this.persistToStorage('followedSeries', Array.from(this.followedSeries));
            this.triggerUpdate('followedSeries', seriesName, 'removed');
            return true;
        }
        return false;
    }

    /**
     * Check if an event is saved
     */
    isEventSaved(confId) {
        return this.savedEvents.has(confId);
    }

    /**
     * Check if a series is followed
     */
    isSeriesFollowed(seriesName) {
        return this.followedSeries.has(seriesName);
    }

    /**
     * Get all saved events with full conference data
     */
    getSavedEvents() {
        return Array.from(this.savedEvents)
            .map(id => this.getConference(id))
            .filter(conf => conf !== undefined)
            .sort((a, b) => {
                // Sort by CFP deadline
                const dateA = new Date(a.cfp_ext || a.cfp || '9999-12-31');
                const dateB = new Date(b.cfp_ext || b.cfp || '9999-12-31');
                return dateA - dateB;
            });
    }

    /**
     * Get all followed series with their conferences
     */
    getFollowedSeries() {
        const seriesData = [];
        this.followedSeries.forEach(seriesName => {
            const conferences = this.getConferenceSeries(seriesName);
            if (conferences.length > 0) {
                seriesData.push({
                    name: seriesName,
                    conferences: conferences.sort((a, b) => b.year - a.year),
                    pattern: this.analyzeSeriesPattern(seriesName)
                });
            }
        });
        return seriesData;
    }

    /**
     * Analyze historical pattern for CFP opening
     */
    analyzeSeriesPattern(seriesName) {
        const conferences = this.getConferenceSeries(seriesName);
        const cfpDates = conferences
            .filter(conf => conf.cfp && conf.start)
            .map(conf => {
                const cfp = new Date(conf.cfp);
                const start = new Date(conf.start);
                return {
                    year: conf.year,
                    cfpMonth: cfp.getMonth(),
                    daysBefore: Math.floor((start - cfp) / (1000 * 60 * 60 * 24))
                };
            });

        if (cfpDates.length < 2) {
            return { pattern: 'Not enough data', confidence: 'low' };
        }

        // Find most common CFP month
        const monthCounts = {};
        cfpDates.forEach(d => {
            monthCounts[d.cfpMonth] = (monthCounts[d.cfpMonth] || 0) + 1;
        });

        const mostCommonMonth = Object.entries(monthCounts)
            .sort((a, b) => b[1] - a[1])[0][0];

        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December'];

        // Calculate average days before conference
        const avgDaysBefore = Math.round(
            cfpDates.reduce((sum, d) => sum + d.daysBefore, 0) / cfpDates.length
        );

        return {
            pattern: `Usually opens in ${monthNames[mostCommonMonth]}`,
            daysBefore: `About ${Math.round(avgDaysBefore / 30)} months before conference`,
            confidence: cfpDates.length >= 3 ? 'high' : 'medium',
            basedOn: `${cfpDates.length} previous years`
        };
    }

    /**
     * Load data from localStorage
     */
    loadFromStorage(key, defaultValue) {
        try {
            // Check both old and new storage key formats
            let stored = localStorage.getItem(`pydeadlines_${key}`);
            if (!stored) {
                // Try old format without prefix
                stored = localStorage.getItem(key);
            }
            return stored ? JSON.parse(stored) : defaultValue;
        } catch (e) {
            console.error(`Error loading ${key} from storage:`, e);
            return defaultValue;
        }
    }

    /**
     * Save data to localStorage
     */
    persistToStorage(key, value) {
        try {
            localStorage.setItem(`pydeadlines_${key}`, JSON.stringify(value));
        } catch (e) {
            console.error(`Error saving ${key} to storage:`, e);
        }
    }

    /**
     * Trigger update event for UI synchronization
     */
    triggerUpdate(type, target, action) {
        window.dispatchEvent(new CustomEvent('conferenceStateUpdate', {
            detail: { type, target, action }
        }));
    }

    /**
     * Get upcoming deadlines for saved events
     */
    getUpcomingDeadlines(daysAhead = 30) {
        const now = new Date();
        const future = new Date(now.getTime() + (daysAhead * 24 * 60 * 60 * 1000));

        return this.getSavedEvents().filter(conf => {
            const cfpDate = new Date(conf.cfp_ext || conf.cfp);
            return cfpDate >= now && cfpDate <= future;
        });
    }

    /**
     * Export saved events as ICS calendar
     */
    exportToCalendar() {
        const events = this.getSavedEvents();
        // This would generate ICS format - implementation depends on calendar library
        console.log('Export to calendar:', events.length, 'events');
        // Return ICS string or trigger download
    }

    /**
     * Clear all saved data (for debugging/reset)
     */
    clearAllData() {
        this.savedEvents.clear();
        this.followedSeries.clear();
        this.persistToStorage('savedEvents', []);
        this.persistToStorage('followedSeries', []);
        this.triggerUpdate('all', null, 'cleared');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait for conference data to be injected
    if (window.conferenceData) {
        window.confManager = new ConferenceStateManager(window.conferenceData);
        console.log('ConferenceStateManager initialized with',
                   window.confManager.allConferences.size, 'conferences');

        // Trigger event to notify that manager is ready
        window.dispatchEvent(new CustomEvent('conferenceManagerReady', {
            detail: { manager: window.confManager }
        }));
    }
});
