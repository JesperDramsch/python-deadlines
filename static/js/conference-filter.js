// Consolidated Conference Filtering Module
// Single source of truth for all filtering operations
(function() {
    'use strict';
    
    const FilterManager = {
        // Configuration
        STORAGE_KEY: 'pythondeadlines-filter-state',
        STORAGE_DOMAIN: window.location.hostname,
        
        // State
        currentFilters: {
            subs: [],
            searchQuery: '',
            dateRange: null
        },
        
        allSubs: [],
        isUpdatingMultiselect: false,
        isInitialized: false,
        
        // Initialize the filter manager
        init: function() {
            // Prevent multiple initializations
            if (this.isInitialized) {
                return;
            }
            this.isInitialized = true;
            
            this.loadState();
            this.bindEvents();
            this.applyInitialFilters();
        },
        
        // Load filter state from localStorage and URL
        loadState: function() {
            // Get all available subcategories from multiselect or fallback to known categories
            this.allSubs = [];
            $('#subject-select option').each((i, opt) => {
                if (opt.value) this.allSubs.push(opt.value);
            });
            
            // If multiselect doesn't exist or has no options, use default categories
            if (this.allSubs.length === 0) {
                this.allSubs = ['PY', 'SCIPY', 'DATA', 'WEB', 'BIZ', 'GEO', 'CAMP', 'DAY'];
            }
            
            // Check URL parameters first (highest priority)
            const urlParams = new URLSearchParams(window.location.search);
            const urlSubs = urlParams.get('sub');
            
            if (urlSubs) {
                this.currentFilters.subs = urlSubs.split(',').map(s => s.trim());
            } else {
                // Fall back to localStorage
                const stored = store.get(this.STORAGE_DOMAIN + '-subs');
                if (stored && !this.isDataExpired(stored)) {
                    // If stored filters are all categories, treat as empty (show all)
                    if (stored.subs && stored.subs.length === this.allSubs.length) {
                        this.currentFilters.subs = [];
                    } else {
                        this.currentFilters.subs = stored.subs || [];
                    }
                } else {
                    // Default to empty (show all) instead of listing all categories
                    this.currentFilters.subs = [];
                }
            }
        },
        
        // Save filter state
        saveState: function() {
            store.set(this.STORAGE_DOMAIN + '-subs', {
                subs: this.currentFilters.subs,
                timestamp: new Date().getTime()
            });
            
            this.updateURL();
        },
        
        // Update URL with current filters
        updateURL: function() {
            const page_url = window.location.pathname;
            
            if (this.currentFilters.subs.length === 0 || 
                this.currentFilters.subs.length === this.allSubs.length) {
                // Show all - remove query parameter
                window.history.pushState('', '', page_url);
            } else {
                // Show filtered - add query parameter
                window.history.pushState('', '', 
                    page_url + '?sub=' + this.currentFilters.subs.join(','));
            }
        },
        
        // Apply filters to conference cards
        applyFilters: function() {
            // If no filters or all filters selected, show all conferences
            if (!this.currentFilters.subs || 
                this.currentFilters.subs.length === 0 || 
                (this.allSubs.length > 0 && this.currentFilters.subs.length === this.allSubs.length)) {
                // Show all
                $('.ConfItem').show();
            } else {
                // Hide all conferences first
                $('.ConfItem').hide();
                
                // Show only selected subcategories
                this.currentFilters.subs.forEach(sub => {
                    $('.' + sub + '-conf').show();
                });
            }
            
            // Apply search filter if present
            if (this.currentFilters.searchQuery) {
                this.applySearchFilter();
            }
            
            // Notify other systems about filter change
            this.notifyFilterChange();
        },
        
        // Apply search filter on top of category filters
        applySearchFilter: function() {
            const query = this.currentFilters.searchQuery.toLowerCase();
            
            $('.ConfItem:visible').each(function() {
                const $item = $(this);
                const text = $item.text().toLowerCase();
                
                if (!text.includes(query)) {
                    $item.hide();
                }
            });
        },
        
        // Notify other components about filter changes
        notifyFilterChange: function() {
            // Notify countdown manager for lazy loading optimization
            if (window.CountdownManager && window.CountdownManager.onFilterUpdate) {
                window.CountdownManager.onFilterUpdate();
            }
            
            // Trigger custom event for other components
            $(document).trigger('conference-filter-change', [this.currentFilters]);
        },
        
        // Update filters from multiselect dropdown
        updateFromMultiselect: function(selectedValues) {
            // Skip if we're programmatically updating the multiselect
            if (this.isUpdatingMultiselect) {
                return;
            }
            
            // Ensure selectedValues is always an array
            if (typeof selectedValues === 'string') {
                this.currentFilters.subs = [selectedValues];
            } else if (Array.isArray(selectedValues)) {
                this.currentFilters.subs = selectedValues;
            } else {
                this.currentFilters.subs = [];
            }
            
            this.saveState();
            this.applyFilters();
        },
        
        // Filter by single subcategory (from badge click)
        filterBySub: function(sub) {
            // Check if this is currently the only selected filter
            const isOnlyFilter = this.currentFilters.subs.length === 1 && 
                                this.currentFilters.subs[0] === sub;
            
            if (isOnlyFilter) {
                // Toggle behavior: clear filters to show all
                this.currentFilters.subs = [];
            } else {
                // Otherwise filter to just this category
                this.currentFilters.subs = [sub];
            }
            
            // Save state and apply filters
            this.saveState();
            this.applyFilters();
            
            // Update multiselect UI if it exists
            const $select = $('#subject-select');
            if ($select.length && $select.data('multiselect')) {
                // Set flag to prevent feedback loop
                this.isUpdatingMultiselect = true;
                
                if (this.currentFilters.subs.length === 0) {
                    // Select all
                    $select.val(this.allSubs);
                } else {
                    $select.val(this.currentFilters.subs);
                }
                $select.multiselect('refresh');
                
                // Reset flag after a short delay to ensure change event has fired
                setTimeout(() => {
                    this.isUpdatingMultiselect = false;
                }, 100);
            }
        },
        
        // Search conferences
        search: function(query) {
            this.currentFilters.searchQuery = query;
            this.applyFilters();
        },
        
        // Clear all filters
        clearFilters: function() {
            this.currentFilters.subs = [...this.allSubs];
            this.currentFilters.searchQuery = '';
            
            // Update multiselect UI
            const $select = $('#subject-select');
            $select.multiselect('selectAll', false);
            $select.multiselect('refresh');
            
            this.saveState();
            this.applyFilters();
        },
        
        // Check if stored data is expired
        isDataExpired: function(data) {
            const EXPIRATION_PERIOD = 24 * 60 * 60 * 1000; // 1 day
            const now = new Date().getTime();
            return data.timestamp && (now - data.timestamp > EXPIRATION_PERIOD);
        },
        
        // Bind events
        bindEvents: function() {
            const self = this;
            
            // Unbind any existing handlers first to prevent duplicates
            $(document).off('change.conferenceFilter');
            $(document).off('click.conferenceFilter');
            $(document).off('mouseenter.conferenceFilter');
            $(document).off('mouseleave.conferenceFilter');
            
            // Handle multiselect changes
            $(document).on('change.conferenceFilter', '#subject-select', function() {
                // Skip if we're programmatically updating
                if (self.isUpdatingMultiselect) {
                    return;
                }
                const selected = $(this).val() || [];
                self.updateFromMultiselect(selected);
            });
            
            // Handle badge clicks - use document delegation for dynamically loaded elements
            // First remove any legacy direct click handlers
            $('.conf-sub').off('click');
            
            // Then bind our delegated handler with specific selector
            $(document).off('click.conferenceFilter', '.conf-sub')
                .on('click.conferenceFilter', '.conf-sub', function(e) {
                    e.preventDefault();
                    e.stopImmediatePropagation(); // Stop all other handlers
                    const sub = $(this).data('sub');
                    if (sub) {
                        // Call FilterManager directly to maintain context
                        self.filterBySub(sub);
                    }
                });
            
            // Add hover effects to indicate clickability
            $(document).on('mouseenter.conferenceFilter', '.conf-sub', function() {
                $(this).css('opacity', '0.8');
            });
            
            $(document).on('mouseleave.conferenceFilter', '.conf-sub', function() {
                $(this).css('opacity', '1');
            });
            
            // Handle browser back/forward
            window.addEventListener('popstate', function() {
                self.loadState();
                self.applyInitialFilters();
            });
        },
        
        // Apply initial filters on page load
        applyInitialFilters: function() {
            // If filters contain all categories, treat as "show all" (empty filters)
            if (this.currentFilters.subs.length === this.allSubs.length) {
                this.currentFilters.subs = [];
            }
            
            // Apply filters first
            this.applyFilters();
            
            // Update multiselect to match current state (without triggering change events)
            const $select = $('#subject-select');
            if ($select.length && $select.data('multiselect')) {
                // Set flag to prevent feedback loop during initialization
                this.isUpdatingMultiselect = true;
                
                // Update multiselect without triggering change events
                if (this.currentFilters.subs.length === 0) {
                    // Show all selected in multiselect
                    $select.val(this.allSubs);
                } else {
                    // Show only filtered categories selected
                    $select.val(this.currentFilters.subs);
                }
                $select.multiselect('refresh');
                
                // Reset flag after update
                setTimeout(() => {
                    this.isUpdatingMultiselect = false;
                }, 100);
            }
        }
    };
    
    // Public API
    window.ConferenceFilter = {
        init: function() { 
            return FilterManager.init(); 
        },
        filterBySub: function(sub) { 
            return FilterManager.filterBySub(sub); 
        },
        search: function(query) { 
            return FilterManager.search(query); 
        },
        clearFilters: function() { 
            return FilterManager.clearFilters(); 
        },
        getCurrentFilters: function() { 
            return FilterManager.currentFilters; 
        },
        updateFromMultiselect: function(values) { 
            return FilterManager.updateFromMultiselect(values); 
        }
    };
    
    // Global alias for backward compatibility
    window.filterBySub = (sub) => FilterManager.filterBySub(sub);
    
    // Auto-initialize when DOM is ready
    // Wait for jQuery to be ready and for page setup to complete
    if (typeof jQuery !== 'undefined') {
        // Use jQuery's ready handler which ensures DOM is ready
        jQuery(document).ready(function() {
            // Add a small delay to ensure other scripts have finished setup
            setTimeout(() => FilterManager.init(), 100);
        });
    } else if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Add delay for other scripts
            setTimeout(() => FilterManager.init(), 100);
        });
    } else {
        // Already loaded, but still wait for other scripts
        setTimeout(() => FilterManager.init(), 100);
    }
})();