/**
 * Dashboard Manager for Python Deadlines
 * Manages the personal conference dashboard page
 */

const DashboardManager = {
    conferences: [],
    filteredConferences: [],
    viewMode: 'grid',

    /**
     * Initialize the dashboard
     */
    init() {
        // Only initialize on dashboard/my-conferences page
        if (!window.location.pathname.includes('/my-conferences') &&
            !window.location.pathname.includes('/dashboard')) {
            return;
        }

        this.loadConferences();
        this.setupViewToggle();
        this.setupNotifications();
        this.bindEvents();

        // Load saved view preference
        const savedView = store.get('pythondeadlines-view-mode');
        if (savedView) {
            this.setViewMode(savedView);
        }
    },

    /**
     * Load favorite conferences using ConferenceStateManager
     */
    loadConferences() {
        // Wait for ConferenceStateManager
        if (!window.confManager) {
            setTimeout(() => this.loadConferences(), 100);
            return;
        }

        // Show loading state
        $('#loading-state').show();
        $('#empty-state').hide();
        $('#conference-cards').empty();

        // Get saved events from ConferenceStateManager
        this.conferences = window.confManager.getSavedEvents();

        // Apply initial filters
        this.applyFilters();

        // Hide loading state
        $('#loading-state').hide();

        // Check empty state
        this.checkEmptyState();
    },

    /**
     * Apply all active filters
     */
    applyFilters() {
        // Start with all conferences
        this.filteredConferences = [...this.conferences];

        // Get active filters
        const formatFilters = $('.format-filter:checked').map(function() {
            return $(this).val();
        }).get();

        const topicFilters = $('.topic-filter:checked').map(function() {
            return $(this).val();
        }).get();

        const featureFilters = $('.feature-filter:checked').map(function() {
            return $(this).val();
        }).get();

        const onlySubscribedSeries = $('#filter-subscribed-series').is(':checked');

        // Apply format filter
        if (formatFilters.length > 0) {
            this.filteredConferences = this.filteredConferences.filter(conf => {
                return formatFilters.includes(conf.format);
            });
        }

        // Apply topic filter
        if (topicFilters.length > 0) {
            this.filteredConferences = this.filteredConferences.filter(conf => {
                if (!conf.sub) return false;
                const confTopics = conf.sub.split(',').map(t => t.trim());
                return topicFilters.some(filter => confTopics.includes(filter));
            });
        }

        // Apply feature filters
        if (featureFilters.length > 0) {
            this.filteredConferences = this.filteredConferences.filter(conf => {
                if (featureFilters.includes('finaid') && conf.has_finaid !== 'true') {
                    return false;
                }
                if (featureFilters.includes('workshop') && conf.has_workshop !== 'true') {
                    return false;
                }
                if (featureFilters.includes('sponsor') && conf.has_sponsor !== 'true') {
                    return false;
                }
                return true;
            });
        }

        // Apply series filter using ConferenceStateManager
        if (onlySubscribedSeries && window.confManager) {
            this.filteredConferences = this.filteredConferences.filter(conf => {
                return window.confManager.isSeriesFollowed(conf.conference);
            });
        }

        // Render filtered conferences
        this.renderConferences();
    },

    /**
     * Render conference cards
     */
    renderConferences() {
        const container = $('#conference-cards');
        container.empty();

        if (this.filteredConferences.length === 0) {
            // No conferences match filters
            container.html(`
                <div class="col-12">
                    <div class="alert alert-info">
                        <i class="fa fa-filter"></i> No conferences match your current filters.
                        <button class="btn btn-sm btn-link" id="clear-filters-inline">Clear filters</button>
                    </div>
                </div>
            `);

            $('#clear-filters-inline').on('click', function() {
                $('#clear-filters').click();
            });

            return;
        }

        // Sort by CFP deadline
        this.filteredConferences.sort((a, b) => {
            const dateA = new Date(a.cfp_ext || a.cfp);
            const dateB = new Date(b.cfp_ext || b.cfp);
            return dateA - dateB;
        });

        // Render each conference
        this.filteredConferences.forEach(conf => {
            const card = this.createConferenceCard(conf);
            container.append(card);
        });

        // Update count
        $('#conference-count').text(`${this.filteredConferences.length} conference${this.filteredConferences.length !== 1 ? 's' : ''}`);

        // Initialize countdowns
        this.initializeCountdowns();
    },

    /**
     * Create a conference card element
     */
    createConferenceCard(conf) {
        const now = new Date();

        // Determine card column class based on view mode
        const colClass = this.viewMode === 'grid' ? 'col-md-6 col-lg-4' : 'col-12';

        // Format dates - handle both ISO and SQL formats
        const cfpStr = conf.cfp_ext || conf.cfp;
        let cfpDate;
        if (cfpStr && cfpStr.includes(' ')) {
            // SQL format: "2025-09-15 00:00:00"
            cfpDate = luxon.DateTime.fromSQL(cfpStr);
        } else if (cfpStr) {
            // ISO format: "2025-09-15T00:00:00"
            cfpDate = luxon.DateTime.fromISO(cfpStr);
        } else {
            cfpDate = luxon.DateTime.invalid('No CFP date');
        }

        const cfpFormatted = cfpDate.isValid ? cfpDate.toFormat('MMM dd, yyyy') : 'TBA';

        // Calculate days left after parsing the date
        const daysLeft = cfpDate.isValid ? Math.ceil((cfpDate.toJSDate() - now) / (1000 * 60 * 60 * 24)) : null;

        // Determine deadline status
        let deadlineClass = 'text-muted';
        let deadlineText = '';

        if (daysLeft === null) {
            deadlineClass = 'text-muted';
            deadlineText = 'TBA';
        } else if (daysLeft < 0) {
            deadlineClass = 'text-danger';
            deadlineText = 'Deadline passed';
        } else if (daysLeft === 0) {
            deadlineClass = 'text-danger font-weight-bold';
            deadlineText = 'Deadline today!';
        } else if (daysLeft <= 3) {
            deadlineClass = 'text-danger';
            deadlineText = `${daysLeft} day${daysLeft !== 1 ? 's' : ''} left`;
        } else if (daysLeft <= 7) {
            deadlineClass = 'text-warning';
            deadlineText = `${daysLeft} days left`;
        } else if (daysLeft <= 14) {
            deadlineClass = 'text-info';
            deadlineText = `${daysLeft} days left`;
        } else {
            deadlineClass = 'text-success';
            deadlineText = `${daysLeft} days left`;
        }

        let startDate = conf.start ? luxon.DateTime.fromISO(conf.start) : luxon.DateTime.invalid('No start date');
        let endDate = conf.end ? luxon.DateTime.fromISO(conf.end) : luxon.DateTime.invalid('No end date');

        const confDates = startDate.isValid && endDate.isValid
            ? `${startDate.toFormat('MMM dd')} - ${endDate.toFormat('MMM dd, yyyy')}`
            : 'Dates TBA';

        // Build feature badges
        let featureBadges = '';
        if (conf.has_finaid === 'true') {
            featureBadges += '<span class="badge badge-success mr-1">Financial Aid</span>';
        }
        if (conf.has_workshop === 'true') {
            featureBadges += '<span class="badge badge-info mr-1">Workshops</span>';
        }
        if (conf.has_sponsor === 'true') {
            featureBadges += '<span class="badge badge-warning mr-1">Sponsorship</span>';
        }

        // Build topic badges
        let topicBadges = '';
        if (conf.sub) {
            const topics = conf.sub.split(',').map(t => t.trim());
            topics.forEach(topic => {
                const typeData = window.conferenceTypes?.find(t => t.sub === topic);
                const color = typeData?.color || '#6c757d';
                topicBadges += `<span class="badge mr-1" style="background-color: ${color}">${topic}</span>`;
            });
        }

        // Generate conference detail page URL
        const confUrl = `/conference/${conf.id}/`;

        return $(`
            <div class="${colClass} mb-3">
                <div class="card conference-card h-100" data-conf-id="${conf.id}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h5 class="card-title mb-0">
                                <a href="${confUrl}" class="text-dark text-decoration-none" title="View conference details">
                                    ${conf.conference} ${conf.year}
                                </a>
                            </h5>
                            <div>
                                <button class="btn btn-sm btn-link favorite-btn favorited p-0 ml-2"
                                        data-conf-id="${conf.id}"
                                        title="Remove from favorites"
                                        style="color: #ffd700;">
                                    <i class="fas fa-star"></i>
                                </button>
                                <button class="btn btn-sm btn-link series-btn p-0 ml-2"
                                        data-conf-name="${conf.conference}"
                                        data-conf-id="${conf.id}"
                                        title="Subscribe to series"
                                        style="color: #6c757d;">
                                    <i class="far fa-bell"></i>
                                </button>
                            </div>
                        </div>

                        <p class="card-text">
                            <small class="text-muted">
                                <i class="fas fa-map-marker-alt"></i> ${conf.place}<br>
                                <i class="fas fa-calendar"></i> ${confDates}<br>
                                <i class="fas fa-laptop"></i> ${this.formatType(conf.format)}
                            </small>
                        </p>

                        <div class="mb-2">
                            ${topicBadges}
                        </div>

                        <div class="mb-3">
                            ${featureBadges}
                        </div>

                        <div class="deadline-info mb-3">
                            <strong>CFP Deadline:</strong> ${cfpFormatted}<br>
                            <span class="${deadlineClass} font-weight-bold">
                                <i class="far fa-clock"></i> ${deadlineText}
                            </span>
                        </div>

                        <div class="btn-group btn-group-sm" role="group">
                            ${conf.link ? `<a href="${conf.link}" class="btn btn-outline-primary" target="_blank">
                                <i class="fas fa-globe"></i> Website
                            </a>` : ''}
                            ${conf.cfp_link ? `<a href="${conf.cfp_link}" class="btn btn-outline-info" target="_blank">
                                <i class="fas fa-file-alt"></i> CFP
                            </a>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `);
    },

    /**
     * Format conference type for display
     */
    formatType(type) {
        switch(type) {
            case 'virtual': return 'Virtual';
            case 'hybrid': return 'Hybrid';
            case 'in-person': return 'In-Person';
            default: return 'Unknown';
        }
    },

    /**
     * Check if dashboard is empty and show appropriate state
     */
    checkEmptyState() {
        if (this.conferences.length === 0) {
            $('#empty-state').show();
            $('#conference-cards').hide();
            $('#series-predictions').hide();
        } else {
            $('#empty-state').hide();
            $('#conference-cards').show();
            $('#series-predictions').show();
        }
    },

    /**
     * Setup view mode toggle
     */
    setupViewToggle() {
        $('#view-grid').on('click', () => this.setViewMode('grid'));
        $('#view-list').on('click', () => this.setViewMode('list'));
    },

    /**
     * Set view mode (grid or list)
     */
    setViewMode(mode) {
        this.viewMode = mode;

        // Update buttons
        $('#view-grid, #view-list').removeClass('active');
        $(`#view-${mode}`).addClass('active');

        // Update container class
        $('#conference-container').removeClass('view-grid view-list').addClass(`view-${mode}`);

        // Save preference
        store.set('pythondeadlines-view-mode', mode);

        // Re-render if conferences loaded
        if (this.filteredConferences.length > 0) {
            this.renderConferences();
        }
    },

    /**
     * Setup notification settings
     */
    setupNotifications() {
        // Check if browser supports notifications
        if ('Notification' in window && Notification.permission === 'default') {
            $('#notification-prompt').show();
        }

        // Notification settings button
        $('#notification-settings').on('click', function() {
            $('#notificationModal').modal('show');
        });

        // Save notification settings
        $('#save-notification-settings').on('click', function() {
            const settings = {
                days: $('.notify-days:checked').map(function() {
                    return parseInt($(this).val());
                }).get(),
                newEditions: $('#notify-new-editions').is(':checked'),
                autoFavorite: $('#auto-favorite-series').is(':checked')
            };

            store.set('pythondeadlines-notification-settings', settings);
            $('#notificationModal').modal('hide');

            FavoritesManager.showToast('Settings Saved', 'Notification preferences updated.');
        });
    },

    /**
     * Bind various dashboard events
     */
    bindEvents() {
        // Filter change events
        $('.format-filter, .topic-filter, .feature-filter, #filter-subscribed-series')
            .on('change', () => this.applyFilters());

        // Clear filters
        $('#clear-filters').on('click', () => {
            $('input[type="checkbox"]').prop('checked', false);
            this.applyFilters();
        });

        // Export favorites
        $('#export-favorites').on('click', () => {
            FavoritesManager.exportFavorites();
        });

        // Listen for favorite changes
        $(document).on('favorite:added', () => this.loadConferences());
        $(document).on('favorite:removed', () => this.loadConferences());
    },

    /**
     * Initialize countdown timers
     */
    initializeCountdowns() {
        // This would integrate with the existing countdown logic
        // For now, we'll keep it simple with the static text
    }
};

// Initialize on document ready
$(document).ready(function() {
    // Load conference types for badge colors
    // This should be populated from the page via a script tag
    // If not available, use empty array as fallback
    window.conferenceTypes = window.conferenceTypes || [];

    DashboardManager.init();
});
