/**
 * Lazy Loading Implementation for Python Deadlines
 * Improves initial page load performance by loading conference cards on demand
 */

(function(window, document) {
    'use strict';

    // Configuration
    const config = {
        rootMargin: '50px 0px', // Start loading 50px before visible
        threshold: 0.01, // Trigger when 1% visible
        batchSize: 10, // Number of items to load at once
        debounceDelay: 100 // Debounce scroll events
    };

    // State
    let observer = null;
    let isInitialized = false;
    let loadedCount = 0;

    /**
     * Initialize Intersection Observer for lazy loading
     */
    function initializeLazyLoad() {
        if (isInitialized || !('IntersectionObserver' in window)) {
            // Fallback for browsers without IntersectionObserver
            showAllConferences();
            return;
        }

        observer = new IntersectionObserver(handleIntersection, {
            root: null,
            rootMargin: config.rootMargin,
            threshold: config.threshold
        });

        isInitialized = true;
        setupLazyLoading();
    }

    /**
     * Handle intersection observer callbacks
     */
    function handleIntersection(entries, observer) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                loadConferenceCard(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }

    /**
     * Setup lazy loading for conference cards
     */
    function setupLazyLoading() {
        // Find all conference items
        const conferences = document.querySelectorAll('.ConfItem');

        if (conferences.length === 0) return;

        // Initially hide conferences beyond the first batch
        conferences.forEach((conf, index) => {
            if (index < config.batchSize) {
                // First batch is already visible, just initialize features
                conf.classList.add('lazy-loaded');
                initializeCardFeatures(conf);
                
                // Emit event so FavoritesManager can apply favorite state
                const event = new CustomEvent('conferenceLoaded', {
                    detail: { element: conf, count: index + 1 }
                });
                document.dispatchEvent(event);
            } else {
                // Prepare for lazy loading
                conf.classList.add('lazy-load');
                conf.setAttribute('data-lazy-index', index);

                // Create placeholder content
                createPlaceholder(conf);

                // Observe for lazy loading
                if (observer) {
                    observer.observe(conf);
                }
            }
        });
    }

    /**
     * Create placeholder content for lazy loaded items
     */
    function createPlaceholder(element) {
        if (!element.querySelector('.lazy-placeholder')) {
            const placeholder = document.createElement('div');
            placeholder.className = 'lazy-placeholder';
            placeholder.innerHTML = `
                <div class="placeholder-shimmer">
                    <div class="placeholder-line placeholder-title"></div>
                    <div class="placeholder-line placeholder-text"></div>
                    <div class="placeholder-line placeholder-text short"></div>
                </div>
            `;

            // Store original content
            element.setAttribute('data-original-content', element.innerHTML);
            element.innerHTML = '';
            element.appendChild(placeholder);
        }
    }

    /**
     * Load conference card content
     */
    function loadConferenceCard(element) {
        if (element.classList.contains('lazy-loaded')) return;

        // Get original content
        const originalContent = element.getAttribute('data-original-content');

        if (originalContent) {
            // Restore content with fade-in effect
            element.style.opacity = '0';
            element.innerHTML = originalContent;
            element.classList.remove('lazy-load');
            element.classList.add('lazy-loaded');

            // Remove the min-height that was set for lazy loading
            element.style.minHeight = '';

            // Fade in
            requestAnimationFrame(() => {
                element.style.transition = 'opacity 0.3s ease-in-out';
                element.style.opacity = '1';
            });

            // Initialize any JavaScript for this card
            initializeCardFeatures(element);

            loadedCount++;

            // Emit custom event
            const event = new CustomEvent('conferenceLoaded', {
                detail: { element: element, count: loadedCount }
            });
            document.dispatchEvent(event);
        }
    }

    /**
     * Initialize JavaScript features for a loaded card
     */
    function initializeCardFeatures(element) {
        // Re-run the countdown initialization logic from index.html
        // Get conference ID from element
        const confId = element.id;
        if (!confId) return;

        // Find the timer elements
        const timer = element.querySelector('.timer');
        const timerSmall = element.querySelector('.timer-small');

        if ((timer || timerSmall) && typeof window.conferenceData !== 'undefined') {
            // Get conference data that was stored globally
            const conf = window.conferenceData[confId];
            if (conf && conf.cfpDate && typeof $ !== 'undefined' && $.fn.countdown) {
                // Initialize countdown timers with the stored date
                if (timer) {
                    $(timer).countdown(conf.cfpDate, function(event) {
                        if (event.elapsed) {
                            $(this).html('Deadline passed');
                        } else {
                            $(this).html(event.strftime('%D days %Hh %Mm %Ss'));
                        }
                    });
                }
                if (timerSmall) {
                    $(timerSmall).countdown(conf.cfpDate, function(event) {
                        if (event.elapsed) {
                            $(this).html('Passed');
                        } else {
                            $(this).html(event.strftime('%Dd %H:%M:%S'));
                        }
                    });
                }
            }
        }

        // Initialize calendar buttons
        const calendarContainers = element.querySelectorAll('.calendar');
        calendarContainers.forEach(container => {
            const confData = {
                id: element.id,
                title: element.querySelector('.conf-title a')?.textContent,
                start_date: new Date(container.getAttribute('data-deadline')),
                duration: 60,
                place: element.querySelector('.conf-place a')?.textContent,
                link: element.querySelector('.conf-title a')?.href
            };

            if (typeof createCalendarFromObject === 'function' && confData.start_date && !isNaN(confData.start_date)) {
                try {
                    const calendar = createCalendarFromObject(confData);
                    container.appendChild(calendar);
                } catch (error) {
                    console.error('Error creating calendar:', error);
                }
            }
        });

        // Initialize any click handlers
        const badges = element.querySelectorAll('.conf-sub');
        badges.forEach(badge => {
            badge.addEventListener('click', function(e) {
                const sub = this.getAttribute('data-sub');
                if (sub && typeof window.filterBySub === 'function') {
                    window.filterBySub(sub);
                }
            });
        });

        // Initialize action bar for this conference card
        if (window.ActionBar && typeof window.ActionBar.initForConference === 'function') {
            window.ActionBar.initForConference(element);
        }
    }

    /**
     * Show all conferences (fallback or user action)
     */
    function showAllConferences() {
        const conferences = document.querySelectorAll('.ConfItem.lazy-load');
        conferences.forEach(conf => {
            loadConferenceCard(conf);
        });
    }

    /**
     * Load next batch of conferences
     */
    function loadNextBatch() {
        const lazyItems = document.querySelectorAll('.ConfItem.lazy-load');
        const toLoad = Array.from(lazyItems).slice(0, config.batchSize);

        toLoad.forEach(item => {
            loadConferenceCard(item);
            if (observer) {
                observer.unobserve(item);
            }
        });
    }

    /**
     * Cleanup observer
     */
    function cleanup() {
        if (observer) {
            observer.disconnect();
            observer = null;
        }
        isInitialized = false;
    }

    /**
     * Debounce function for scroll events
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Check if user prefers reduced motion
     */
    function prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    // Add CSS for placeholders
    function addPlaceholderStyles() {
        if (!document.getElementById('lazy-load-styles')) {
            const style = document.createElement('style');
            style.id = 'lazy-load-styles';
            style.textContent = `
                .ConfItem.lazy-load {
                    position: relative;
                }

                .lazy-placeholder {
                    padding: 20px;
                }

                .placeholder-shimmer {
                    animation: shimmer 1.5s infinite;
                    background: linear-gradient(
                        90deg,
                        #f0f0f0 25%,
                        #e0e0e0 50%,
                        #f0f0f0 75%
                    );
                    background-size: 200% 100%;
                }

                @keyframes shimmer {
                    0% { background-position: -200% 0; }
                    100% { background-position: 200% 0; }
                }

                .placeholder-line {
                    height: 16px;
                    margin-bottom: 10px;
                    background: rgba(0, 0, 0, 0.1);
                    border-radius: 4px;
                }

                .placeholder-title {
                    width: 60%;
                    height: 24px;
                }

                .placeholder-text {
                    width: 80%;
                }

                .placeholder-text.short {
                    width: 40%;
                }

                @media (prefers-reduced-motion: reduce) {
                    .placeholder-shimmer {
                        animation: none;
                        background: #f0f0f0;
                    }
                }

                .ConfItem.lazy-loaded {
                    animation: fadeIn 0.3s ease-in-out;
                }

                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
            `;
            if (document.head) {
                document.head.appendChild(style);
            }
        }
    }

    // Export public API
    window.LazyLoad = {
        init: initializeLazyLoad,
        loadAll: showAllConferences,
        loadNext: loadNextBatch,
        cleanup: cleanup,
        getLoadedCount: () => loadedCount
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            addPlaceholderStyles();
            initializeLazyLoad();
        });
    } else {
        addPlaceholderStyles();
        initializeLazyLoad();
    }

    // Add "Load More" button support
    document.addEventListener('DOMContentLoaded', () => {
        const loadMoreBtn = document.getElementById('load-more-conferences');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', loadNextBatch);
        }
    });

})(window, document);
