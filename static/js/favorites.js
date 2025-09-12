/**
 * Favorites Management System for Python Deadlines
 * Works with ConferenceStateManager for centralized data management
 */

const FavoritesManager = {
    initialized: false,

    /**
     * Initialize the favorites system
     */
    init() {
        // Prevent multiple initializations
        if (this.initialized) {
            console.log('FavoritesManager already initialized');
            return;
        }

        // Wait for ConferenceStateManager to be ready
        if (!window.confManager) {
            console.error('ConferenceStateManager not found, cannot initialize FavoritesManager');
            return;
        }

        this.initialized = true;
        console.log('Initializing FavoritesManager');

        this.bindFavoriteButtons();
        this.updateFavoriteCounts();
        this.highlightFavorites();

        // Check for import/export functionality
        this.setupImportExport();

        // Listen for state updates from ConferenceStateManager
        window.addEventListener('conferenceStateUpdate', (e) => {
            this.updateFavoriteCounts();
            this.highlightFavorites();
        });
    },

    /**
     * Bind click events to favorite buttons
     */
    bindFavoriteButtons() {
        $(document).on('click', '.favorite-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const $btn = $(this);
            const confId = $btn.data('conf-id');

            if (!confId) {
                console.error('No conference ID found on favorite button');
                return;
            }

            if (window.confManager.isEventSaved(confId)) {
                // Remove from saved events
                window.confManager.removeSavedEvent(confId);
                $btn.removeClass('favorited');
                $btn.find('i').removeClass('fas').addClass('far');
                $btn.css('color', '#ccc');
            } else {
                // Add to saved events
                window.confManager.saveEvent(confId);
                $btn.addClass('favorited');
                $btn.find('i').removeClass('far').addClass('fas');
                $btn.css('color', '#ffd700');
            }

            FavoritesManager.updateFavoriteCounts();
        });
    },

    /**
     * Extract conference data from DOM elements
     */
    extractConferenceData(confId) {
        const $confElement = $(`[data-conf-id="${confId}"]`).first();

        if (!$confElement.length) {
            console.error('Conference element not found:', confId);
            return null;
        }

        return {
            id: confId,
            name: $confElement.data('conf-name') || $confElement.find('.conf-title a').first().text(),
            year: $confElement.data('conf-year'),
            location: $confElement.data('location'),
            format: $confElement.data('format'),
            topics: $confElement.data('topics'),
            cfp: $confElement.data('cfp'),
            cfpExt: $confElement.data('cfp-ext'),
            start: $confElement.data('start'),
            end: $confElement.data('end'),
            link: $confElement.data('link'),
            cfpLink: $confElement.data('cfp-link'),
            hasFinaid: $confElement.data('has-finaid'),
            hasWorkshop: $confElement.data('has-workshop'),
            hasSponsor: $confElement.data('has-sponsor'),
            addedAt: new Date().toISOString()
        };
    },

    /**
     * Add a conference to favorites
     */
    add(confId, confData) {
        if (window.confManager && window.confManager.saveEvent(confId)) {
            // Show success toast
            this.showToast('Added to Favorites', `${confData.conference} ${confData.year} has been added to your dashboard.`);

            // Trigger custom event
            $(document).trigger('favorite:added', [confId, confData]);
        }
    },

    /**
     * Remove a conference from favorites
     */
    remove(confId) {
        if (window.confManager) {
            const conf = window.confManager.getConference(confId);
            const confName = conf?.conference;

            if (window.confManager.removeSavedEvent(confId)) {
                // Show removal toast
                if (confName) {
                    this.showToast('Removed from Favorites', `${confName} has been removed from your dashboard.`);
                }

                // Trigger custom event
                $(document).trigger('favorite:removed', [confId]);

                // If on dashboard, remove the card
                if (window.location.pathname.includes('/my-conferences')) {
                    $(`#conference-cards [data-conf-id="${confId}"]`).fadeOut(300, function() {
                        $(this).remove();
                        DashboardManager.checkEmptyState();
                    });
                }
            }
        }
    },

    /**
     * Get all favorites (delegates to ConferenceStateManager)
     */
    getFavorites() {
        if (window.confManager) {
            return Array.from(window.confManager.savedEvents);
        }
        return [];
    },

    /**
     * Get saved conference data
     */
    getSavedConferences() {
        if (window.confManager) {
            const conferences = {};
            window.confManager.savedEvents.forEach(id => {
                const conf = window.confManager.getConference(id);
                if (conf) {
                    conferences[id] = conf;
                }
            });
            return conferences;
        }
        return {};
    },

    /**
     * Check if a conference is favorited
     */
    isFavorite(confId) {
        if (window.confManager) {
            return window.confManager.isEventSaved(confId);
        }
        return false;
    },

    /**
     * Update favorite counts in navigation
     */
    updateFavoriteCounts() {
        const favorites = this.getFavorites();
        const count = favorites.length;

        // Update badge in navigation
        $('#fav-count').text(count > 0 ? count : '');

        // Update dashboard counter
        $('#conference-count').text(`${count} favorite conference${count !== 1 ? 's' : ''}`);
    },

    /**
     * Highlight favorited conferences on page load
     */
    highlightFavorites() {
        const favorites = this.getFavorites();

        // Ensure favorites is an array before using forEach
        if (Array.isArray(favorites)) {
            favorites.forEach(confId => {
                const $btn = $(`.favorite-btn[data-conf-id="${confId}"]`);
                $btn.addClass('favorited');
                $btn.find('i').removeClass('far').addClass('fas');
                $btn.css('color', '#ffd700');
            });
        }
    },

    /**
     * Setup import/export functionality
     */
    setupImportExport() {
        // Export favorites
        $('#export-favorites').on('click', function() {
            FavoritesManager.exportFavorites();
        });

        // Import favorites (would need file input)
        $('#import-favorites').on('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                FavoritesManager.importFavorites(file);
            }
        });
    },

    /**
     * Export favorites as JSON
     */
    exportFavorites() {
        const data = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            favorites: this.getFavorites(),
            conferences: this.getSavedConferences(),
            settings: store.get('pythondeadlines-settings') || {}
        };

        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `python-deadlines-favorites-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.showToast('Export Complete', 'Your favorites have been downloaded.');
    },

    /**
     * Import favorites from JSON file
     */
    importFavorites(file) {
        const reader = new FileReader();

        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);

                // Validate data structure
                if (!data.favorites || !data.conferences) {
                    throw new Error('Invalid import file format');
                }

                // Merge with existing favorites
                const existingFavorites = this.getFavorites();
                const existingConferences = this.getSavedConferences();

                // Add new favorites
                const newFavorites = [...new Set([...existingFavorites, ...data.favorites])];
                const newConferences = { ...existingConferences, ...data.conferences };

                // Save
                store.set(this.storageKey, newFavorites);
                store.set(this.conferencesKey, newConferences);

                // Update UI
                this.updateFavoriteCounts();
                this.highlightFavorites();

                // Reload dashboard if on dashboard page
                if (window.location.pathname.includes('/dashboard')) {
                    DashboardManager.loadConferences();
                }

                this.showToast('Import Complete', `Imported ${data.favorites.length} favorites.`);
            } catch (error) {
                console.error('Import error:', error);
                this.showToast('Import Failed', 'Could not import the file. Please check the format.', 'error');
            }
        };

        reader.readAsText(file);
    },

    /**
     * Show toast notification
     */
    showToast(title, message, type = 'success') {
        // Create toast container if it doesn't exist
        if (!$('#toast-container').length) {
            $('body').append('<div id="toast-container" style="position: fixed; top: 80px; right: 20px; z-index: 9999;"></div>');
        }

        const bgClass = type === 'error' ? 'bg-danger' : type === 'warning' ? 'bg-warning' : 'bg-success';

        const toast = $(`
            <div class="toast" role="alert" data-delay="3000">
                <div class="toast-header ${bgClass} text-white">
                    <strong class="mr-auto">${title}</strong>
                    <button type="button" class="ml-2 mb-1 close text-white" data-dismiss="toast">
                        <span>&times;</span>
                    </button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `);

        $('#toast-container').append(toast);

        // Try Bootstrap toast if available
        if ($.fn.toast) {
            try {
                toast.toast('show');

                // Remove after hidden
                toast.on('hidden.bs.toast', function() {
                    $(this).remove();
                });
            } catch (error) {
                console.warn('Bootstrap toast failed, using fallback:', error);
                this.showFallbackToast(toast);
            }
        } else {
            // Fallback to simple display without Bootstrap
            this.showFallbackToast(toast);
        }
    },

    /**
     * Fallback toast display without Bootstrap
     */
    showFallbackToast(toast) {
        // Add custom styles for visibility
        toast.css({
            'display': 'block',
            'background': 'white',
            'border': '1px solid rgba(0,0,0,.125)',
            'border-radius': '.25rem',
            'margin-bottom': '10px',
            'box-shadow': '0 0.25rem 0.75rem rgba(0,0,0,.1)'
        });

        // Find close button and make it work
        toast.find('.close').on('click', function() {
            toast.fadeOut(300, function() {
                $(this).remove();
            });
        });

        // Auto-hide after 3 seconds
        setTimeout(() => {
            toast.fadeOut(300, function() {
                $(this).remove();
            });
        }, 3000);
    },

    /**
     * Clear all favorites (with confirmation)
     */
    clearAll() {
        if (confirm('Are you sure you want to remove all favorites? This cannot be undone.')) {
            store.remove(this.storageKey);
            store.remove(this.conferencesKey);

            // Update UI
            $('.favorite-btn').removeClass('favorited')
                .find('i').removeClass('fas').addClass('far');
            $('.favorite-btn').css('color', '#ccc');

            this.updateFavoriteCounts();

            if (window.location.pathname.includes('/dashboard')) {
                DashboardManager.loadConferences();
            }

            this.showToast('Favorites Cleared', 'All favorites have been removed.');
        }
    }
};

// Export to window for debugging and external access
window.FavoritesManager = FavoritesManager;

// Initialize favorites manager when ConferenceStateManager is ready
function initFavoritesWhenReady() {
    if (window.confManager && window.FavoritesManager && !window.FavoritesManager.initialized) {
        console.log('Both managers ready, initializing FavoritesManager');
        window.FavoritesManager.init();
    } else if (!window.confManager) {
        console.log('Waiting for ConferenceStateManager...');
        setTimeout(initFavoritesWhenReady, 50);
    }
}

// Try multiple initialization strategies to ensure it works
// Strategy 1: Listen for conferenceManagerReady event
window.addEventListener('conferenceManagerReady', function(e) {
    console.log('Conference manager ready event received');
    initFavoritesWhenReady();
});

// Strategy 2: Check on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded - checking for managers');
    initFavoritesWhenReady();
});

// Strategy 3: If script loads after DOM is ready
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    console.log('Document already loaded - checking for managers');
    setTimeout(initFavoritesWhenReady, 100);
}
