// Lazy loading countdown timer system
// Keeps Luxon for date/time handling as requested
(function() {
    'use strict';
    
    // Timer management
    const activeTimers = new Map();
    const TIMER_BATCH_SIZE = 10;
    const UPDATE_INTERVAL = 1000;
    
    // Single shared timer for all countdowns
    let globalTimer = null;
    let visibleConferences = new Set();
    
    // Initialize Intersection Observer for lazy loading
    const observerOptions = {
        root: null,
        rootMargin: '50px',
        threshold: 0.01
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const confId = entry.target.dataset.confId;
            
            if (entry.isIntersecting) {
                // Conference card is visible
                if (!visibleConferences.has(confId)) {
                    visibleConferences.add(confId);
                    initializeCountdown(entry.target);
                }
            } else {
                // Conference card is hidden
                if (visibleConferences.has(confId)) {
                    visibleConferences.delete(confId);
                    cleanupCountdown(confId);
                }
            }
        });
        
        // Manage global timer based on visible conferences
        manageGlobalTimer();
    }, observerOptions);
    
    function initializeCountdown(element) {
        const confId = element.dataset.confId;
        const countdownElements = element.querySelectorAll('.countdown-display');
        
        if (!countdownElements.length) return;
        
        // Get deadline from the countdown element's data attribute
        const deadlineStr = countdownElements[0].dataset.deadline;
        if (!deadlineStr) return;
        
        // Parse deadline using Luxon (keeping existing library)
        const deadline = DateTime.fromISO(deadlineStr);
        
        // Store timer data for both regular and small countdown
        countdownElements.forEach((el, index) => {
            const timerId = `${confId}-${index}`;
            activeTimers.set(timerId, {
                element: el,
                deadline: deadline,
                isSmall: el.classList.contains('countdown-small')
            });
            
            // Immediate update
            updateCountdown(timerId);
        });
    }
    
    function cleanupCountdown(confId) {
        // Clean up all timers for this conference
        const keysToDelete = [];
        activeTimers.forEach((timer, key) => {
            if (key.startsWith(confId + '-')) {
                keysToDelete.push(key);
            }
        });
        keysToDelete.forEach(key => activeTimers.delete(key));
    }
    
    function updateCountdown(timerId) {
        const timer = activeTimers.get(timerId);
        if (!timer) return;
        
        const now = DateTime.now();
        const diff = timer.deadline.diff(now, ['days', 'hours', 'minutes', 'seconds']);
        
        if (diff.toMillis() <= 0) {
            // Deadline passed
            if (timer.element) {
                timer.element.innerHTML = timer.isSmall ? 'Passed' : 'Deadline passed';
            }
            activeTimers.delete(timerId);
        } else {
            // Update countdown display
            const days = Math.floor(diff.days);
            const hours = Math.floor(diff.hours);
            const minutes = Math.floor(diff.minutes);
            const seconds = Math.floor(diff.seconds);
            
            if (timer.element) {
                if (timer.isSmall) {
                    // Small format: "2d 14:30:45"
                    timer.element.innerHTML = `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    // Full format: "2 days 14h 30m 45s"
                    timer.element.innerHTML = `${days} days ${hours}h ${minutes}m ${seconds}s`;
                }
            }
        }
    }
    
    function updateAllCountdowns() {
        // Update only visible countdowns
        activeTimers.forEach((timer, timerId) => {
            updateCountdown(timerId);
        });
        
        // Remove expired timers
        if (activeTimers.size === 0) {
            stopGlobalTimer();
        }
    }
    
    function manageGlobalTimer() {
        if (activeTimers.size > 0 && !globalTimer) {
            // Start global timer
            globalTimer = setInterval(updateAllCountdowns, UPDATE_INTERVAL);
        } else if (activeTimers.size === 0 && globalTimer) {
            // Stop global timer
            stopGlobalTimer();
        }
    }
    
    function stopGlobalTimer() {
        if (globalTimer) {
            clearInterval(globalTimer);
            globalTimer = null;
        }
    }
    
    // Public API for filtering integration
    window.CountdownManager = {
        // Called when conferences are filtered
        onFilterUpdate: function() {
            // Re-observe visible conferences
            document.querySelectorAll('.ConfItem:not([style*="display: none"])').forEach(conf => {
                observer.observe(conf);
            });
            
            // Unobserve hidden conferences
            document.querySelectorAll('.ConfItem[style*="display: none"]').forEach(conf => {
                observer.unobserve(conf);
                const confId = conf.dataset.confId;
                if (confId && visibleConferences.has(confId)) {
                    visibleConferences.delete(confId);
                    cleanupCountdown(confId);
                }
            });
            
            manageGlobalTimer();
        },
        
        // Initialize on page load
        init: function() {
            // Observe all conference cards
            document.querySelectorAll('.ConfItem').forEach(conf => {
                // Add conf ID if not present
                if (!conf.dataset.confId) {
                    const link = conf.querySelector('a[id]');
                    if (link) {
                        conf.dataset.confId = link.id;
                    }
                }
                
                // Start observing
                observer.observe(conf);
            });
        },
        
        // Cleanup
        destroy: function() {
            observer.disconnect();
            stopGlobalTimer();
            activeTimers.clear();
            visibleConferences.clear();
        }
    };
    
    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => CountdownManager.init());
    } else {
        CountdownManager.init();
    }
})();