/**
 * Conference Series Manager for Python Deadlines
 * Handles conference series subscriptions and predictions
 */

const SeriesManager = {
    /**
     * Initialize series manager
     */
    init() {
        // Prevent infinite recursion with max retries
        if (!this.initRetryCount) {
            this.initRetryCount = 0;
        }

        // Wait for ConferenceStateManager to be ready
        if (!window.confManager) {
            this.initRetryCount++;

            if (this.initRetryCount > 50) { // Max 5 seconds wait
                return;
            }

            setTimeout(() => this.init(), 100);
            return;
        }

        // Reset retry count on successful init
        this.initRetryCount = 0;

        try {
            this.bindSeriesButtons();
            this.bindQuickSubscribe();
            this.renderSubscribedSeries();
            this.generatePredictions();

            // Update series count
            this.updateSeriesCount();

            // Listen for state updates
            window.addEventListener('conferenceStateUpdate', (e) => {
                try {
                    if (e.detail && e.detail.type === 'followedSeries') {
                        this.updateSeriesCount();
                        this.renderSubscribedSeries();
                    }
                } catch (error) {
                    // Error handling state update
                }
            });
        } catch (error) {
            // Try to at least bind critical event handlers
            try {
                this.bindSeriesButtons();
            } catch (fallbackError) {
                // Critical SeriesManager initialization failure
            }
        }
    },

    /**
     * Bind click events to series buttons
     */
    bindSeriesButtons() {
        // Wait for ConferenceStateManager
        if (!window.confManager) {
            setTimeout(() => this.bindSeriesButtons(), 100);
            return;
        }

        $(document).on('click', '.series-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const $btn = $(this);
            const confName = $btn.data('conf-name');

            if (!confName || !window.confManager) return;

            if (window.confManager.isSeriesFollowed(confName)) {
                // Unfollow series
                window.confManager.unfollowSeries(confName);
                $btn.removeClass('subscribed');
                $btn.find('i').removeClass('fas').addClass('far');
                $btn.css('color', '#ccc');
            } else {
                // Follow series
                window.confManager.followSeries(confName);
                $btn.addClass('subscribed');
                $btn.find('i').removeClass('far').addClass('fas');
                $btn.css('color', '#007bff');
            }
        });
    },

    /**
     * Bind quick subscribe buttons
     */
    bindQuickSubscribe() {
        // Wait for ConferenceStateManager to be ready
        if (!window.confManager) {
            setTimeout(() => this.bindQuickSubscribe(), 100);
            return;
        }

        $('.quick-subscribe').on('click', function() {
            const $btn = $(this);
            const seriesName = $btn.data('series');

            if ($btn.hasClass('subscribed')) {
                // Unsubscribe
                if (window.confManager.unfollowSeries(seriesName)) {
                    $btn.removeClass('subscribed btn-primary').addClass('btn-outline-primary');
                    $btn.text(`+ ${$btn.text().replace('✓ ', '')}`);
                    SeriesManager.renderSubscribedSeries();
                    SeriesManager.updateSeriesCount();
                }
            } else {
                // Subscribe
                if (window.confManager.followSeries(seriesName)) {
                    $btn.removeClass('btn-outline-primary').addClass('btn-primary subscribed');
                    $btn.text(`✓ ${$btn.text().replace('+ ', '')}`);
                    SeriesManager.renderSubscribedSeries();
                    SeriesManager.updateSeriesCount();
                }
            }
        });

        // Initialize button states based on current subscriptions
        this.updateQuickSubscribeButtons();
    },

    /**
     * Update quick subscribe button states based on followed series
     */
    updateQuickSubscribeButtons() {
        if (!window.confManager) return;

        $('.quick-subscribe').each(function() {
            const $btn = $(this);
            const seriesName = $btn.data('series');

            if (window.confManager.isSeriesFollowed(seriesName)) {
                $btn.removeClass('btn-outline-primary').addClass('btn-primary subscribed');
                const currentText = $btn.text().trim();
                if (!currentText.startsWith('✓')) {
                    $btn.text(`✓ ${currentText.replace('+ ', '')}`);
                }
            } else {
                $btn.removeClass('subscribed btn-primary').addClass('btn-outline-primary');
                const currentText = $btn.text().trim();
                if (!currentText.startsWith('+')) {
                    $btn.text(`+ ${currentText.replace('✓ ', '')}`);
                }
            }
        });
    },

    /**
     * Render subscribed series list in dashboard
     */
    renderSubscribedSeries() {
        const container = $('#subscribed-series-list');
        if (!container.length) return;

        // Get followed series from ConferenceStateManager
        let followedSeriesData = [];
        if (window.confManager) {
            followedSeriesData = window.confManager.getFollowedSeries();
        }

        container.empty();

        if (followedSeriesData.length === 0) {
            container.html('<p class="text-muted small">No series subscriptions yet.</p>');
            return;
        }

        // Render each followed series
        followedSeriesData.forEach((seriesData) => {
            const seriesName = seriesData.name;
            const conferenceCount = seriesData.conferences.length;
            const pattern = seriesData.pattern;

            // Generate series page URL (slugify the series name)
            const seriesSlug = seriesName.toLowerCase()
                .replace(/\s+/g, '-')
                .replace(/[^a-z0-9-]/g, '');
            const seriesUrl = `/series/${seriesSlug}/`;

            const item = $(`
                <div class="series-item mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong><a href="${seriesUrl}" class="text-dark" title="View all ${seriesName} conferences">${seriesName}</a></strong>
                            <span class="badge badge-secondary ml-1">${conferenceCount} events</span>
                        </div>
                        <button class="btn btn-sm btn-link text-danger unsubscribe-series"
                                data-series-name="${seriesName}">
                            <i class="fa fa-times"></i>
                        </button>
                    </div>
                    ${pattern && pattern.pattern !== 'Not enough data' ? `
                    <div class="small text-muted">
                        <i class="fa fa-info-circle"></i> ${pattern.pattern}
                        ${pattern.confidence ? `(${pattern.confidence} confidence)` : ''}
                    </div>
                    ` : ''}
                </div>
            `);

            container.append(item);
        });

        // Bind unsubscribe events
        $('.unsubscribe-series').on('click', function() {
            const seriesName = $(this).data('series-name');
            if (window.confManager) {
                window.confManager.unfollowSeries(seriesName);
                // Refresh display
                SeriesManager.renderSubscribedSeries();
                SeriesManager.updateSeriesCount();
            }
        });
    },

    /**
     * Update series count in dashboard
     */
    updateSeriesCount() {
        let count = 0;
        if (window.confManager) {
            const followedSeries = window.confManager.getFollowedSeries();
            count = followedSeries.length;
        }
        $('#series-count').text(`${count} series subscription${count !== 1 ? 's' : ''}`);
    },

    /**
     * Generate predictions for subscribed series
     */
    generatePredictions() {
        const container = $('#predictions-container');
        if (!container.length || !window.confManager) return;

        // Get followed series with pattern analysis from ConferenceStateManager
        const followedSeries = window.confManager.getFollowedSeries();

        if (followedSeries.length === 0) {
            container.html('<p class="text-muted">No predictions available yet. Subscribe to conference series to see CFP opening predictions.</p>');
            return;
        }

        container.empty();

        // Render pattern analysis for each followed series
        followedSeries.forEach(seriesData => {
            const pattern = seriesData.pattern;

            // Only show if we have meaningful pattern data
            if (pattern && pattern.pattern !== 'Not enough data') {
                const card = $(`
                    <div class="alert alert-info">
                        <h6><i class="fa fa-chart-line"></i> ${seriesData.name}</h6>
                        <p class="mb-0">
                            <strong>${pattern.pattern}</strong><br>
                            ${pattern.daysBefore ? `<small class="text-muted">${pattern.daysBefore}</small><br>` : ''}
                            <small class="text-muted">Based on ${pattern.basedOn} (${pattern.confidence} confidence)</small>
                        </p>
                    </div>
                `);
                container.append(card);
            }
        });

        // If no patterns were shown, display a message
        if (container.children().length === 0) {
            container.html('<p class="text-muted">No predictions available yet. Pattern analysis requires at least 2 historical conferences.</p>');
        }
    }
};

// Initialize on document ready
$(document).ready(function() {
    SeriesManager.init();
});
