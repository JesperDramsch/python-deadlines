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
        
        // Initialize the filter manager
        init: function() {
            this.loadState();
            this.bindEvents();
            this.applyInitialFilters();
        },
        
        // Load filter state from localStorage and URL
        loadState: function() {
            // Get all available subcategories
            this.allSubs = [];
            $('#subject-select option').each((i, opt) => {
                if (opt.value) this.allSubs.push(opt.value);
            });
            
            // Check URL parameters first (highest priority)
            const urlParams = new URLSearchParams(window.location.search);
            const urlSubs = urlParams.get('sub');
            
            if (urlSubs) {
                this.currentFilters.subs = urlSubs.split(',').map(s => s.trim());
            } else {
                // Fall back to localStorage
                const stored = store.get(this.STORAGE_DOMAIN + '-subs');
                if (stored && !this.isDataExpired(stored)) {
                    this.currentFilters.subs = stored.subs || [];
                } else {
                    // Default to all categories
                    this.currentFilters.subs = [...this.allSubs];
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
            // Hide all conferences first
            $('.ConfItem').hide();
            
            // Show filtered conferences
            if (this.currentFilters.subs.length === 0 || 
                this.currentFilters.subs.length === this.allSubs.length) {
                // Show all
                $('.ConfItem').show();
            } else {
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
            this.currentFilters.subs = selectedValues || [];
            this.saveState();
            this.applyFilters();
        },
        
        // Filter by single subcategory (from badge click)
        filterBySub: function(sub) {
            // Check if this is the only selected item - if so, select all (toggle behavior)
            const $select = $('#subject-select');
            const currentlySelected = $select.val() || [];
            
            if (currentlySelected.length === 1 && currentlySelected[0] === sub) {
                // If clicking the same single selected item, select all
                this.clearFilters();
            } else {
                // Otherwise filter by this subcategory only
                this.currentFilters.subs = [sub];
                
                // Update multiselect UI
                $select.multiselect('deselectAll', false);
                $select.multiselect('select', sub);
                $select.multiselect('refresh');
                
                this.saveState();
                this.applyFilters();
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
            
            // Handle multiselect changes
            $(document).on('change', '#subject-select', function() {
                const selected = $(this).val() || [];
                self.updateFromMultiselect(selected);
            });
            
            // Handle badge clicks
            $(document).on('click', '.conf-sub', function(e) {
                e.preventDefault();
                e.stopPropagation();
                const sub = $(this).data('sub');
                if (sub) {
                    self.filterBySub(sub);
                }
            });
            
            // Add hover effects to indicate clickability
            $(document).on('mouseenter', '.conf-sub', function() {
                $(this).css('opacity', '0.8');
            });
            
            $(document).on('mouseleave', '.conf-sub', function() {
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
            // Update multiselect to match current state
            const $select = $('#subject-select');
            if ($select.length) {
                $select.multiselect('deselectAll', false);
                this.currentFilters.subs.forEach(sub => {
                    $select.multiselect('select', sub);
                });
                $select.multiselect('refresh');
            }
            
            // Apply filters
            this.applyFilters();
        }
    };
    
    // Public API
    window.ConferenceFilter = {
        init: () => FilterManager.init(),
        filterBySub: (sub) => FilterManager.filterBySub(sub),
        search: (query) => FilterManager.search(query),
        clearFilters: () => FilterManager.clearFilters(),
        getCurrentFilters: () => FilterManager.currentFilters,
        updateFromMultiselect: (values) => FilterManager.updateFromMultiselect(values)
    };
    
    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => FilterManager.init());
    } else {
        FilterManager.init();
    }
})();