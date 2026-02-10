// Simple Countdown Timer System
// Single shared timer for all countdowns - efficient and maintainable
(function() {
    'use strict';

    // Ensure Luxon DateTime is available
    const DateTime = window.luxon ? window.luxon.DateTime : null;
    if (!DateTime) {
        return; // Luxon not available, skip countdown initialization
    }

    let globalTimer = null;

    function updateAllCountdowns() {
        // Query all countdown elements and update them
        document.querySelectorAll('.countdown-display').forEach(el => {
            const deadlineStr = el.dataset.deadline;
            const timezone = el.dataset.timezone || 'UTC-12';

            if (!deadlineStr || deadlineStr === 'TBA' || deadlineStr === 'Cancelled') {
                return; // Skip invalid deadlines
            }

            let deadline;
            try {
                // Try parsing as SQL format first (YYYY-MM-DD HH:mm:ss)
                deadline = DateTime.fromSQL(deadlineStr, { zone: timezone });

                // If invalid, try ISO format
                if (deadline.invalid) {
                    deadline = DateTime.fromISO(deadlineStr, { zone: timezone });
                }

                // If still invalid, fall back to system timezone
                if (deadline.invalid) {
                    deadline = DateTime.fromSQL(deadlineStr);
                    if (deadline.invalid) {
                        deadline = DateTime.fromISO(deadlineStr);
                    }
                }

                if (deadline.invalid) {
                    el.textContent = 'Invalid date';
                    return;
                }
            } catch (e) {
                el.textContent = 'Error';
                return;
            }

            // Calculate time difference
            const now = DateTime.now();
            const diff = deadline.diff(now);

            if (diff.toMillis() <= 0) {
                // Deadline has passed
                el.textContent = el.classList.contains('countdown-small')
                    ? 'Passed'
                    : 'Deadline passed';
                el.classList.add('deadline-passed');
                el.removeAttribute('data-urgency');
            } else {
                // Format and display countdown - get normalized components using shiftTo
                const normalized = diff.shiftTo('days', 'hours', 'minutes', 'seconds');
                const components = normalized.toObject();
                const days = Math.floor(components.days || 0);
                const hours = Math.floor(components.hours || 0);
                const minutes = Math.floor(components.minutes || 0);
                const seconds = Math.floor(components.seconds || 0);

                if (el.classList.contains('countdown-small')) {
                    // Compact format for small countdown
                    el.textContent = `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else if (el.classList.contains('conf-timer')) {
                    // Conference detail page format (matches jQuery countdown format)
                    const dayLabel = days === 1 ? 'day' : 'days';
                    el.textContent = `${days} ${dayLabel} ${hours}h ${minutes}m ${seconds}s`;
                } else {
                    // Full format for regular countdown
                    el.textContent = `${days} days ${hours}h ${minutes}m ${seconds}s`;
                }

                // Set urgency level for visual feedback
                if (days < 3) {
                    el.setAttribute('data-urgency', 'critical');
                } else if (days < 7) {
                    el.setAttribute('data-urgency', 'high');
                } else if (days < 14) {
                    el.setAttribute('data-urgency', 'medium');
                } else {
                    el.removeAttribute('data-urgency');
                }

                el.classList.remove('deadline-passed');
            }
        });
    }

    // Initialize countdowns
    function init() {
        // Clear any existing timer
        if (globalTimer) {
            clearInterval(globalTimer);
        }

        // Initial update
        updateAllCountdowns();

        // Start the global timer (updates every second)
        globalTimer = setInterval(updateAllCountdowns, 1000);
    }

    // Stop timer when page unloads
    window.addEventListener('beforeunload', () => {
        if (globalTimer) {
            clearInterval(globalTimer);
            globalTimer = null;
        }
    });

    // Stop timer when page is hidden (saves battery)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (globalTimer) {
                clearInterval(globalTimer);
                globalTimer = null;
            }
        } else {
            // Restart timer when page becomes visible
            init();
        }
    });

    // Public API for integration with filtering
    window.CountdownManager = {
        // Called when conferences are filtered (compatibility with existing code)
        onFilterUpdate: function() {
            // No action needed - countdowns continue working regardless of visibility
            // This function exists for backwards compatibility
        },

        // Manual refresh if needed
        refresh: function() {
            updateAllCountdowns();
        },

        // Initialize countdowns
        init: init,

        // Stop countdowns
        destroy: function() {
            if (globalTimer) {
                clearInterval(globalTimer);
                globalTimer = null;
            }
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
