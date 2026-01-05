/**
 * Notification System for Python Deadlines
 * Handles browser notifications and in-app alerts for CFP deadlines
 */

const NotificationManager = {
    settingsKey: 'pythondeadlines-notification-settings',
    lastCheckKey: 'pythondeadlines-last-notification-check',
    scheduledKey: 'pythondeadlines-scheduled-notifications',

    /**
     * Check if daysUntil is within range of a notification threshold
     * Uses a 24-hour window (±0.5 days) to ensure notifications aren't missed
     * due to timing of periodic checks
     * @param {number} daysUntil - Days until deadline (can be fractional)
     * @param {number} threshold - Target day threshold (e.g., 7, 3, 1)
     * @returns {boolean} True if within notification window
     */
    isWithinNotificationWindow(daysUntil, threshold) {
        // Check if daysUntil is within ±0.5 days of threshold
        // This gives a 24-hour window to catch each notification
        return daysUntil > threshold - 0.5 && daysUntil <= threshold + 0.5;
    },

    /**
     * Find which threshold (if any) applies for the given daysUntil
     * @param {number} daysUntil - Days until deadline (can be fractional)
     * @param {number[]} thresholds - Array of day thresholds to check
     * @returns {number|null} The matching threshold or null
     */
    findMatchingThreshold(daysUntil, thresholds) {
        for (const threshold of thresholds) {
            if (this.isWithinNotificationWindow(daysUntil, threshold)) {
                return threshold;
            }
        }
        return null;
    },

    /**
     * Initialize notification system
     */
    init() {
        try {
            this.checkBrowserSupport();
            this.loadSettings();
            this.bindEvents();
            this.checkUpcomingDeadlines();

            // Schedule periodic checks
            this.schedulePeriodicChecks();
        } catch (error) {
            // Try to at least set up basic functionality
            try {
                this.loadSettings();
                this.bindEvents();
            } catch (fallbackError) {
                // Critical initialization failure - fail silently in production
            }
        }
    },

    /**
     * Check if browser supports notifications
     */
    checkBrowserSupport() {
        if ('Notification' in window) {
            // Check current permission status
            if (Notification.permission === 'default') {
                // Show prompt to enable notifications
                $('#notification-prompt').show();
            } else if (Notification.permission === 'granted') {
                $('#notification-prompt').hide();
            } else {
                $('#notification-prompt').hide();
            }
        } else {
            $('#notification-prompt').hide();
        }
    },

    /**
     * Request notification permission
     */
    async requestPermission() {
        if ('Notification' in window) {
            const permission = await Notification.requestPermission();

            if (permission === 'granted') {
                // Defensive check for FavoritesManager
                if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
                    FavoritesManager.showToast(
                        'Notifications Enabled',
                        'You will receive notifications for upcoming CFP deadlines.',
                        'success'
                    );
                }

                $('#notification-prompt').fadeOut();

                // Show test notification
                this.showTestNotification();
            } else if (permission === 'denied') {
                // Defensive check for FavoritesManager
                if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
                    FavoritesManager.showToast(
                        'Notifications Blocked',
                        'You can enable notifications in your browser settings.',
                        'warning'
                    );
                }

                $('#notification-prompt').fadeOut();
            }

            return permission;
        }
        return 'unsupported';
    },

    /**
     * Show test notification
     */
    showTestNotification() {
        if (Notification.permission === 'granted') {
            const notification = new Notification('Python Deadlines', {
                body: 'Notifications are now enabled! You\'ll be notified about upcoming CFP deadlines.',
                icon: '/static/img/python-deadlines-logo.png',
                badge: '/static/img/python-deadlines-badge.png',
                tag: 'test-notification',
                requireInteraction: false
            });

            notification.onclick = function() {
                window.focus();
                notification.close();
            };

            setTimeout(() => notification.close(), 5000);
        }
    },

    /**
     * Load notification settings
     */
    loadSettings() {
        const defaultSettings = {
            days: [14, 7, 3, 1],
            newEditions: true,
            autoFavorite: true,
            enabled: true,
            soundEnabled: false,
            emailEnabled: false
        };

        const saved = store.get(this.settingsKey);
        this.settings = { ...defaultSettings, ...saved };

        // Apply settings to UI
        this.applySettingsToUI();
    },

    /**
     * Save notification settings
     */
    saveSettings() {
        store.set(this.settingsKey, this.settings);
        // Defensive check for FavoritesManager
        if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
            FavoritesManager.showToast('Settings Saved', 'Notification preferences updated.');
        }
    },

    /**
     * Apply settings to UI
     */
    applySettingsToUI() {
        // Update checkboxes in modal
        $('.notify-days').each((i, el) => {
            const value = parseInt($(el).val());
            $(el).prop('checked', this.settings.days.includes(value));
        });

        $('#notify-new-editions').prop('checked', this.settings.newEditions);
        $('#auto-favorite-series').prop('checked', this.settings.autoFavorite);
    },

    /**
     * Bind notification events
     */
    bindEvents() {
        // Enable notifications button
        $('#enable-notifications').on('click', () => {
            this.requestPermission();
        });

        // Save notification settings
        $('#save-notification-settings').on('click', () => {
            // Collect settings from modal
            this.settings.days = $('.notify-days:checked').map(function() {
                return parseInt($(this).val());
            }).get();

            this.settings.newEditions = $('#notify-new-editions').is(':checked');
            this.settings.autoFavorite = $('#auto-favorite-series').is(':checked');

            this.saveSettings();
            $('#notificationModal').modal('hide');

            // Reschedule notifications with new settings
            this.scheduleNotifications();
        });
    },

    /**
     * Check notification preferences from action bar
     */
    checkActionBarNotifications() {
        const prefs = JSON.parse(localStorage.getItem('pydeadlines_actionBarPrefs') || '{}');
        const now = Date.now();
        const lastCheck = parseInt(localStorage.getItem('pydeadlines_lastNotifyCheck') || '0');

        // Only check every 4 hours
        if (now - lastCheck < 4 * 60 * 60 * 1000) return;

        // Get all conferences from the page
        const conferences = new Map();
        document.querySelectorAll('.ConfItem').forEach(conf => {
            const id = conf.dataset.confId || conf.id;
            const cfp = conf.dataset.cfp || conf.dataset.cfpExt;
            const name = conf.dataset.confName || conf.querySelector('.conf-title a')?.textContent;

            if (id && cfp && cfp !== 'TBA' && cfp !== 'None') {
                conferences.set(id, { cfp, name });
            }
        });

        // Check each conference with save enabled (includes notifications)
        Object.entries(prefs).forEach(([confId, settings]) => {
            if (!settings.save) return;  // Changed from notify to save
            if (confId === '_series') return; // Skip series data

            const conf = conferences.get(confId);
            if (!conf) return;

            try {
                // Validate date string before parsing
                if (!conf.cfp || conf.cfp === 'TBA' || conf.cfp === 'None') {
                    return; // Skip invalid date entries
                }

                const cfpDate = new Date(conf.cfp);
                // Check for Invalid Date
                if (isNaN(cfpDate.getTime())) {
                    return;
                }

                // Use fractional days for range-based matching
                const daysUntil = (cfpDate - now) / (1000 * 60 * 60 * 24);

                // Check if we should notify (within ±0.5 days of 7, 3, or 1 day thresholds)
                const matchedThreshold = this.findMatchingThreshold(daysUntil, [7, 3, 1]);
                if (matchedThreshold !== null) {
                    const notifyKey = `pydeadlines_notify_${confId}_${matchedThreshold}`;
                    const lastShown = parseInt(localStorage.getItem(notifyKey) || '0');

                    // Only show once per day for each notification
                    if (now - lastShown > 24 * 60 * 60 * 1000) {
                        // Show browser notification if supported and permission granted
                        if ('Notification' in window && Notification.permission === 'granted') {
                            const notification = new Notification('Python Deadlines Reminder', {
                                body: `${matchedThreshold} day${matchedThreshold > 1 ? 's' : ''} until ${conf.name} CFP closes!`,
                                icon: '/static/img/python-deadlines-logo.png',
                                badge: '/static/img/python-deadlines-badge.png',
                                tag: `deadline-${confId}-${matchedThreshold}`,
                                requireInteraction: false
                            });

                            notification.onclick = function() {
                                window.focus();
                                // Scroll to the conference
                                const element = document.getElementById(confId);
                                if (element) {
                                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }
                                notification.close();
                            };

                            setTimeout(() => notification.close(), 10000);
                        }

                        // Record notification attempt regardless of browser support
                        // This prevents duplicate notifications on browsers that don't support the API
                        localStorage.setItem(notifyKey, now.toString());
                    }
                }
            } catch(e) {
                // Silently handle notification check error
            }
        });

        localStorage.setItem('pydeadlines_lastNotifyCheck', now.toString());
    },

    /**
     * Check for upcoming deadlines
     */
    checkUpcomingDeadlines() {
        try {
            const now = new Date();
            // Defensive check for FavoritesManager
            const favorites = (typeof FavoritesManager !== 'undefined' && FavoritesManager.getSavedConferences)
                ? FavoritesManager.getSavedConferences()
                : {};
            const notifiedKey = 'pythondeadlines-notified-deadlines';
            const notified = store.get(notifiedKey) || {};

        Object.values(favorites).forEach(conf => {
            // Validate date strings before parsing
            const dateString = conf.cfpExt || conf.cfp;
            if (!dateString || dateString === 'TBA' || dateString === 'None') {
                return; // Skip invalid date entries
            }

            const cfpDate = new Date(dateString);
            // Check for Invalid Date
            if (isNaN(cfpDate.getTime())) {
                return;
            }

            // Use fractional days for range-based matching
            const daysUntil = (cfpDate - now) / (1000 * 60 * 60 * 24);

            // Check if we should notify for this deadline (within ±0.5 days of thresholds)
            const matchedThreshold = this.findMatchingThreshold(daysUntil, this.settings.days);
            if (matchedThreshold !== null) {
                const notificationKey = `${conf.id}-${matchedThreshold}`;

                // Check if we've already notified for this
                if (!notified[notificationKey]) {
                    this.sendDeadlineNotification(conf, matchedThreshold);

                    // Mark as notified
                    notified[notificationKey] = new Date().toISOString();
                    store.set(notifiedKey, notified);
                }
            }

            // Clean up old notifications (older than 30 days)
            const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
            Object.keys(notified).forEach(key => {
                if (new Date(notified[key]) < thirtyDaysAgo) {
                    delete notified[key];
                }
            });
            store.set(notifiedKey, notified);
        });
        } catch (error) {
            // Don't let errors crash the entire system
        }
    },

    /**
     * Send deadline notification
     */
    sendDeadlineNotification(conf, daysUntil) {
        const title = `CFP Deadline: ${conf.name} ${conf.year}`;
        const body = daysUntil === 0
            ? 'CFP deadline is TODAY!'
            : `${daysUntil} day${daysUntil !== 1 ? 's' : ''} until CFP deadline`;

        // Browser notification
        if (Notification.permission === 'granted') {
            const notification = new Notification(title, {
                body: body,
                icon: '/static/img/python-deadlines-logo.png',
                badge: '/static/img/python-deadlines-badge.png',
                tag: `deadline-${conf.id}`,
                requireInteraction: daysUntil <= 1,
                data: {
                    confId: conf.id,
                    url: conf.cfpLink || conf.link
                }
            });

            notification.onclick = function() {
                if (notification.data.url) {
                    window.open(notification.data.url, '_blank');
                } else {
                    window.focus();
                }
                notification.close();
            };

            // Auto-close after 10 seconds (unless urgent)
            if (daysUntil > 1) {
                setTimeout(() => notification.close(), 10000);
            }
        }

        // In-app toast notification
        this.showInAppNotification(title, body, daysUntil <= 3 ? 'warning' : 'info');
    },

    /**
     * Show in-app notification
     */
    showInAppNotification(title, message, type = 'info') {
        // Ensure toast container exists
        if (!$('#toast-container').length) {
            $('body').append('<div id="toast-container" style="position: fixed; top: 80px; right: 20px; z-index: 9999;"></div>');
        }

        const bgClass = type === 'warning' ? 'bg-warning' :
                       type === 'danger' ? 'bg-danger' :
                       type === 'success' ? 'bg-success' : 'bg-info';

        const textClass = type === 'warning' ? 'text-dark' : 'text-white';

        const toast = $(`
            <div class="toast" role="alert" data-delay="5000">
                <div class="toast-header ${bgClass} ${textClass}">
                    <i class="fa fa-bell mr-2"></i>
                    <strong class="mr-auto">${title}</strong>
                    <button type="button" class="ml-2 mb-1 close ${textClass}" data-dismiss="toast">
                        <span>&times;</span>
                    </button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `);

        $('#toast-container').append(toast);
        toast.toast('show');

        // Remove after hidden
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    },

    /**
     * Schedule notifications for all favorites
     */
    scheduleNotifications() {
        const scheduled = {};
        // Defensive check for FavoritesManager
        const favorites = (typeof FavoritesManager !== 'undefined' && FavoritesManager.getSavedConferences)
            ? FavoritesManager.getSavedConferences()
            : {};
        const now = new Date();

        Object.values(favorites).forEach(conf => {
            // Validate date strings before parsing
            const dateString = conf.cfpExt || conf.cfp;
            if (!dateString || dateString === 'TBA' || dateString === 'None') {
                return; // Skip invalid date entries
            }

            const cfpDate = new Date(dateString);
            // Check for Invalid Date
            if (isNaN(cfpDate.getTime())) {
                return;
            }

            // Only schedule for future deadlines
            if (cfpDate > now) {
                scheduled[conf.id] = [];

                this.settings.days.forEach(daysBefore => {
                    const notifyDate = new Date(cfpDate);
                    notifyDate.setDate(notifyDate.getDate() - daysBefore);

                    if (notifyDate > now) {
                        scheduled[conf.id].push({
                            date: notifyDate.toISOString(),
                            daysBefore: daysBefore
                        });
                    }
                });
            }
        });

        store.set(this.scheduledKey, scheduled);
    },

    /**
     * Schedule periodic checks for notifications
     */
    schedulePeriodicChecks() {
        // Clear any existing interval to prevent memory leaks
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }

        // Check every hour
        this.checkInterval = setInterval(() => {
            this.checkUpcomingDeadlines();
        }, 60 * 60 * 1000);

        // Also check when page becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkUpcomingDeadlines();
            }
        });

        // Check on focus
        window.addEventListener('focus', () => {
            this.checkUpcomingDeadlines();
        });
    },

    /**
     * Send series notification
     */
    sendSeriesNotification(seriesName, message) {
        const title = `Conference Series: ${seriesName}`;

        // Browser notification
        if (Notification.permission === 'granted') {
            const notification = new Notification(title, {
                body: message,
                icon: '/static/img/python-deadlines-logo.png',
                badge: '/static/img/python-deadlines-badge.png',
                tag: `series-${seriesName}`,
                requireInteraction: false
            });

            notification.onclick = function() {
                window.focus();
                notification.close();
            };

            setTimeout(() => notification.close(), 5000);
        }

        // In-app notification
        this.showInAppNotification(title, message, 'info');
    },

    /**
     * Test notification system
     */
    testNotifications() {
        // Create a test conference
        const testConf = {
            id: 'test-conf',
            name: 'Test Conference',
            year: new Date().getFullYear(),
            cfp: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
        };

        this.sendDeadlineNotification(testConf, 7);
    },

    /**
     * Cleanup method to prevent memory leaks
     */
    cleanup() {
        // Clear interval timer
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }

        // Remove event listeners (using named functions would make this easier)
    }
};

// Initialize on document ready
$(document).ready(function() {
    NotificationManager.init();
});

// Cleanup on page unload to prevent memory leaks
$(window).on('beforeunload', function() {
    if (NotificationManager && NotificationManager.cleanup) {
        NotificationManager.cleanup();
    }
});

// Expose for testing
if (typeof window !== 'undefined') {
    window.NotificationManager = NotificationManager;
}
