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
            return;
        }

        // Wait for ConferenceStateManager to be ready
        if (!window.confManager) {
            return;
        }

        this.initialized = true;

        this.bindFavoriteButtons();
        this.updateFavoriteCounts();
        this.highlightFavorites();

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
                return;
            }

            if (window.confManager.isEventSaved(confId)) {
                // Remove from saved events using FavoritesManager method
                FavoritesManager.remove(confId);
                $btn.removeClass('favorited');
                $btn.find('i').removeClass('fas').addClass('far');
                $btn.css('color', '#ccc');
            } else {
                // Add to saved events using FavoritesManager method
                // Get conference data from ConferenceStateManager
                const confData = window.confManager.getConference(confId) ||
                                 FavoritesManager.extractConferenceData(confId);
                if (confData) {
                    FavoritesManager.add(confId, confData);
                    $btn.addClass('favorited');
                    $btn.find('i').removeClass('far').addClass('fas');
                    $btn.css('color', '#ffd700');
                }
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
                    // Find the card with the conf-id and get its parent column
                    const $card = $(`#conference-cards .conference-card[data-conf-id="${confId}"]`).closest('.col-md-6, .col-lg-4, .col-12');
                    if ($card.length) {
                        $card.fadeOut(300, function() {
                            $(this).remove();
                            if (typeof DashboardManager !== 'undefined') {
                                DashboardManager.checkEmptyState();
                            }
                        });
                    }
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
        window.FavoritesManager.init();
    } else if (!window.confManager) {
        setTimeout(initFavoritesWhenReady, 50);
    }
}

// Try multiple initialization strategies to ensure it works
// Strategy 1: Listen for conferenceManagerReady event
window.addEventListener('conferenceManagerReady', function(e) {
    initFavoritesWhenReady();
});

// Strategy 2: Check on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    initFavoritesWhenReady();
});

// Strategy 3: If script loads after DOM is ready
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    setTimeout(initFavoritesWhenReady, 100);
}
