// Simple Countdown Timer System
// Single shared timer for all countdowns - efficient and maintainable
(function() {
    'use strict';
    
    // Ensure Luxon DateTime is available
    const DateTime = window.luxon ? window.luxon.DateTime : null;
    if (!DateTime) {
        console.error('Luxon DateTime not available. Countdowns disabled.');
        return;
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
                    console.warn(`Invalid deadline format for element:`, deadlineStr);
                    el.textContent = 'Invalid date';
                    return;
                }
            } catch (e) {
                console.error(`Error parsing deadline: ${deadlineStr}`, e);
                el.textContent = 'Error';
                return;
            }
            
            // Calculate time difference
            const now = DateTime.now();
            const diff = deadline.diff(now, ['days', 'hours', 'minutes', 'seconds']);
            
            if (diff.toMillis() <= 0) {
                // Deadline has passed
                el.textContent = el.classList.contains('countdown-small') 
                    ? 'Passed' 
                    : 'Deadline passed';
                el.classList.add('deadline-passed');
            } else {
                // Format and display countdown
                const days = Math.floor(diff.days);
                const hours = Math.floor(diff.hours);
                const minutes = Math.floor(diff.minutes);
                const seconds = Math.floor(diff.seconds);
                
                if (el.classList.contains('countdown-small')) {
                    // Compact format for small countdown
                    el.textContent = `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    // Full format for regular countdown
                    el.textContent = `${days} days ${hours}h ${minutes}m ${seconds}s`;
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