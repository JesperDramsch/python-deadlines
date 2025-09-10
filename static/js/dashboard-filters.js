/**
 * Dashboard Filters for Python Deadlines
 * Handles advanced filtering logic and URL persistence
 */

const DashboardFilters = {
    /**
     * Initialize filters
     */
    init() {
        this.loadFromURL();
        this.bindEvents();
        this.setupFilterPersistence();
    },
    
    /**
     * Load filter state from URL parameters
     */
    loadFromURL() {
        const params = new URLSearchParams(window.location.search);
        
        // Format filters
        const formats = params.get('format');
        if (formats) {
            formats.split(',').forEach(format => {
                $(`#filter-${format}`).prop('checked', true);
            });
        }
        
        // Topic filters
        const topics = params.get('topics');
        if (topics) {
            topics.split(',').forEach(topic => {
                $(`#filter-${topic}`).prop('checked', true);
            });
        }
        
        // Feature filters
        const features = params.get('features');
        if (features) {
            features.split(',').forEach(feature => {
                $(`#filter-${feature}`).prop('checked', true);
            });
        }
        
        // Series filter
        if (params.get('series') === 'subscribed') {
            $('#filter-subscribed-series').prop('checked', true);
        }
    },
    
    /**
     * Save current filter state to URL
     */
    saveToURL() {
        const params = new URLSearchParams();
        
        // Collect format filters
        const formats = $('.format-filter:checked').map(function() {
            return $(this).val();
        }).get();
        
        if (formats.length > 0) {
            params.set('format', formats.join(','));
        }
        
        // Collect topic filters
        const topics = $('.topic-filter:checked').map(function() {
            return $(this).val();
        }).get();
        
        if (topics.length > 0) {
            params.set('topics', topics.join(','));
        }
        
        // Collect feature filters
        const features = $('.feature-filter:checked').map(function() {
            return $(this).val();
        }).get();
        
        if (features.length > 0) {
            params.set('features', features.join(','));
        }
        
        // Series filter
        if ($('#filter-subscribed-series').is(':checked')) {
            params.set('series', 'subscribed');
        }
        
        // Update URL without reload
        const newURL = params.toString() ? 
            `${window.location.pathname}?${params.toString()}` : 
            window.location.pathname;
            
        history.replaceState({}, '', newURL);
    },
    
    /**
     * Setup filter persistence in localStorage
     */
    setupFilterPersistence() {
        // Save filter preferences
        const saveFilters = () => {
            const filterState = {
                formats: $('.format-filter:checked').map(function() {
                    return $(this).val();
                }).get(),
                topics: $('.topic-filter:checked').map(function() {
                    return $(this).val();
                }).get(),
                features: $('.feature-filter:checked').map(function() {
                    return $(this).val();
                }).get(),
                subscribedSeries: $('#filter-subscribed-series').is(':checked')
            };
            
            store.set('pythondeadlines-filter-preferences', filterState);
        };
        
        // Load saved filter preferences if no URL params
        if (!window.location.search) {
            const savedFilters = store.get('pythondeadlines-filter-preferences');
            if (savedFilters) {
                // Apply saved formats
                savedFilters.formats?.forEach(format => {
                    $(`#filter-${format}`).prop('checked', true);
                });
                
                // Apply saved topics
                savedFilters.topics?.forEach(topic => {
                    $(`#filter-${topic}`).prop('checked', true);
                });
                
                // Apply saved features
                savedFilters.features?.forEach(feature => {
                    $(`#filter-${feature}`).prop('checked', true);
                });
                
                // Apply series filter
                if (savedFilters.subscribedSeries) {
                    $('#filter-subscribed-series').prop('checked', true);
                }
            }
        }
        
        // Save on change
        $('.format-filter, .topic-filter, .feature-filter, #filter-subscribed-series')
            .on('change', saveFilters);
    },
    
    /**
     * Bind filter events
     */
    bindEvents() {
        // Update URL on filter change
        $('.format-filter, .topic-filter, .feature-filter, #filter-subscribed-series')
            .on('change', () => {
                this.saveToURL();
                this.updateFilterCount();
            });
        
        // Clear all filters
        $('#clear-filters').on('click', () => {
            // Clear checkboxes
            $('input[type="checkbox"]').prop('checked', false);
            
            // Clear URL
            history.replaceState({}, '', window.location.pathname);
            
            // Clear saved preferences
            store.remove('pythondeadlines-filter-preferences');
            
            // Update count
            this.updateFilterCount();
        });
        
        // Initialize filter count
        this.updateFilterCount();
    },
    
    /**
     * Update active filter count display
     */
    updateFilterCount() {
        const activeFilters = $('input[type="checkbox"]:checked:not(#filter-subscribed-series)').length;
        
        if (activeFilters > 0) {
            // Add badge to filter header
            let badge = $('#filter-count-badge');
            if (!badge.length) {
                badge = $('<span id="filter-count-badge" class="badge badge-primary ml-2"></span>');
                $('.filter-panel .card-header h5').append(badge);
            }
            badge.text(activeFilters);
        } else {
            $('#filter-count-badge').remove();
        }
    },
    
    /**
     * Create filter preset
     */
    savePreset(name) {
        const preset = {
            name: name,
            formats: $('.format-filter:checked').map(function() {
                return $(this).val();
            }).get(),
            topics: $('.topic-filter:checked').map(function() {
                return $(this).val();
            }).get(),
            features: $('.feature-filter:checked').map(function() {
                return $(this).val();
            }).get(),
            subscribedSeries: $('#filter-subscribed-series').is(':checked')
        };
        
        const presets = store.get('pythondeadlines-filter-presets') || {};
        presets[name] = preset;
        store.set('pythondeadlines-filter-presets', presets);
        
        this.renderPresets();
        FavoritesManager.showToast('Preset Saved', `Filter preset "${name}" has been saved.`);
    },
    
    /**
     * Load filter preset
     */
    loadPreset(name) {
        const presets = store.get('pythondeadlines-filter-presets') || {};
        const preset = presets[name];
        
        if (!preset) return;
        
        // Clear all filters first
        $('input[type="checkbox"]').prop('checked', false);
        
        // Apply preset
        preset.formats?.forEach(format => {
            $(`#filter-${format}`).prop('checked', true);
        });
        
        preset.topics?.forEach(topic => {
            $(`#filter-${topic}`).prop('checked', true);
        });
        
        preset.features?.forEach(feature => {
            $(`#filter-${feature}`).prop('checked', true);
        });
        
        if (preset.subscribedSeries) {
            $('#filter-subscribed-series').prop('checked', true);
        }
        
        // Trigger filter update
        $('.format-filter').first().trigger('change');
        
        FavoritesManager.showToast('Preset Loaded', `Filter preset "${name}" has been applied.`);
    },
    
    /**
     * Render filter presets
     */
    renderPresets() {
        const presets = store.get('pythondeadlines-filter-presets') || {};
        const container = $('#filter-presets');
        
        if (!container.length) return;
        
        container.empty();
        
        Object.keys(presets).forEach(name => {
            const btn = $(`
                <button class="btn btn-sm btn-outline-secondary mr-1 mb-1">
                    ${name}
                    <span class="remove-preset" data-name="${name}">&times;</span>
                </button>
            `);
            
            btn.on('click', function(e) {
                if ($(e.target).hasClass('remove-preset')) {
                    // Remove preset
                    delete presets[$(e.target).data('name')];
                    store.set('pythondeadlines-filter-presets', presets);
                    DashboardFilters.renderPresets();
                } else {
                    // Load preset
                    DashboardFilters.loadPreset(name);
                }
            });
            
            container.append(btn);
        });
    },
    
    /**
     * Apply current filters to the conference list
     * This method is exposed for external usage
     */
    applyFilters() {
        // Trigger change event on first filter to apply all filters
        const firstFilter = $('.format-filter, .topic-filter, .feature-filter').first();
        if (firstFilter.length) {
            firstFilter.trigger('change');
        }
        
        // Update URL to reflect current filters
        this.updateURL();
    }
};

// Initialize on document ready
$(document).ready(function() {
    if (window.location.pathname.includes('/dashboard')) {
        DashboardFilters.init();
    }
});