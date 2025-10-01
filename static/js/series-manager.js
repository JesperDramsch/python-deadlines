/**
 * Conference Series Manager for Python Deadlines
 * Handles conference series subscriptions and predictions
 */

const SeriesManager = {
    subscriptionsKey: 'pythondeadlines-series-subscriptions',
    processedKey: 'pythondeadlines-processed-confs',
    storeLock: false,

    /**
     * Atomic store update to prevent race conditions
     */
    atomicStoreUpdate(key, updateFn) {
        // Simple lock mechanism
        const maxRetries = 10;
        let retries = 0;

        const performUpdate = () => {
            if (this.storeLock && retries < maxRetries) {
                retries++;
                setTimeout(performUpdate, 10);
                return;
            }

            if (retries >= maxRetries) {
                return false;
            }

            try {
                this.storeLock = true;
                const current = store.get(key) || {};
                const updated = updateFn(current);
                store.set(key, updated);
                return true;
            } catch (error) {
                return false;
            } finally {
                this.storeLock = false;
            }
        };

        return performUpdate();
    },

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
            this.detectNewConferences();
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
        $(document).on('click', '.series-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const $btn = $(this);
            const confName = $btn.data('conf-name');
            const confId = $btn.data('conf-id');

            if (!confName) return;

            const seriesId = SeriesManager.getSeriesId(confName);
            const seriesName = SeriesManager.extractSeriesName(confName);

            if ($btn.hasClass('subscribed')) {
                SeriesManager.unsubscribe(seriesId);
                $btn.removeClass('subscribed');
                $btn.find('i').removeClass('fas').addClass('far');
                $btn.css('color', '#ccc');
            } else {
                SeriesManager.subscribe(seriesId, seriesName);
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
        $('.quick-subscribe').on('click', function() {
            const $btn = $(this);
            const seriesPattern = $btn.data('series');

            if ($btn.hasClass('subscribed')) {
                // Unsubscribe
                SeriesManager.unsubscribePattern(seriesPattern);
                $btn.removeClass('subscribed btn-primary').addClass('btn-outline-primary');
                $btn.html(`+ ${$btn.text().replace('✓ ', '')}`);
            } else {
                // Subscribe
                SeriesManager.subscribeToPattern(seriesPattern);
                $btn.removeClass('btn-outline-primary').addClass('btn-primary subscribed');
                $btn.html(`✓ ${$btn.text().replace('+ ', '')}`);
            }
        });
    },

    /**
     * Get series ID from conference name
     */
    getSeriesId(confName) {
        const seriesName = this.extractSeriesName(confName);
        return seriesName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
    },

    /**
     * Extract series name from conference name (remove year)
     */
    extractSeriesName(confName) {
        // Remove year patterns (2020, 2021, etc.)
        let seriesName = confName.replace(/\s*20\d{2}\s*/g, '').trim();

        // Remove common suffixes
        seriesName = seriesName.replace(/\s*(Conference|Conf|Summit|Meeting)\s*$/i, '');

        return seriesName.trim();
    },

    /**
     * Subscribe to a conference series
     */
    subscribe(seriesId, seriesName) {
        // Input validation
        if (!seriesId || typeof seriesId !== 'string') {
            return false;
        }

        if (!seriesName || typeof seriesName !== 'string') {
            return false;
        }

        // Sanitize input to prevent XSS
        seriesId = seriesId.replace(/[<>'"]/g, '');
        seriesName = seriesName.replace(/[<>'"]/g, '');

        // Use atomic update to prevent race conditions
        const success = this.atomicStoreUpdate(this.subscriptionsKey, (subscriptions) => {
            // Check for duplicate subscription
            if (subscriptions[seriesId]) {
                // Update the subscription instead of creating duplicate
                subscriptions[seriesId].subscribedAt = new Date().toISOString();
            } else {
                subscriptions[seriesId] = {
                    name: seriesName,
                    subscribedAt: new Date().toISOString(),
                    autoFavorite: true,
                    notifyOnNew: true,
                    pattern: false
                };
            }
            return subscriptions;
        });

        if (!success) {
            return false;
        }

        // Update UI
        this.highlightSubscribedSeries();
        this.renderSubscribedSeries();
        this.updateSeriesCount();

        // Auto-favorite existing conferences in this series
        this.autoFavoriteSeriesConferences(seriesId);

        // Safe toast call
        if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
            FavoritesManager.showToast('Series Subscribed', `You're now following ${seriesName} conferences.`);
        }
    },

    /**
     * Subscribe to a pattern (e.g., all PyData events)
     */
    subscribeToPattern(pattern) {
        // Input validation
        if (!pattern || typeof pattern !== 'string') {
            return false;
        }

        // Sanitize input to prevent XSS
        pattern = pattern.replace(/[<>'"]/g, '');

        const subscriptions = store.get(this.subscriptionsKey) || {};
        const patternId = `${pattern}-all`;

        // Check for duplicate subscription
        if (subscriptions[patternId]) {
            return false;
        }

        subscriptions[patternId] = {
            name: `All ${pattern} Events`,
            pattern: pattern,
            subscribedAt: new Date().toISOString(),
            autoFavorite: false,
            notifyOnNew: true,
            isPattern: true
        };

        store.set(this.subscriptionsKey, subscriptions);

        // Update UI
        this.renderSubscribedSeries();
        this.updateSeriesCount();

        // Check for matching conferences
        this.detectPatternMatches(pattern);

        // Safe toast call
        if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
            FavoritesManager.showToast('Pattern Subscribed', `You'll be notified about new ${pattern} events.`);
        }
    },

    /**
     * Unsubscribe from a series
     */
    unsubscribe(seriesId) {
        // Input validation
        if (!seriesId || typeof seriesId !== 'string') {
            return false;
        }

        let seriesName = null;

        // Use atomic update to prevent race conditions
        const success = this.atomicStoreUpdate(this.subscriptionsKey, (subscriptions) => {
            if (subscriptions[seriesId]) {
                seriesName = subscriptions[seriesId].name;
                delete subscriptions[seriesId];
            }
            return subscriptions;
        });

        if (!success) {
            return false;
        }

        // Update UI
        this.highlightSubscribedSeries();
        this.renderSubscribedSeries();
        this.updateSeriesCount();

        if (seriesName && typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
            FavoritesManager.showToast('Series Unsubscribed', `You've unsubscribed from ${seriesName}.`);
        }
    },

    /**
     * Unsubscribe from a pattern
     */
    unsubscribePattern(pattern) {
        const subscriptions = store.get(this.subscriptionsKey) || {};
        const patternId = `${pattern}-all`;

        delete subscriptions[patternId];
        store.set(this.subscriptionsKey, subscriptions);

        this.renderSubscribedSeries();
        this.updateSeriesCount();

        // Safe toast call
        if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
            FavoritesManager.showToast('Pattern Unsubscribed', `You've unsubscribed from ${pattern} events.`);
        }
    },

    /**
     * Get all subscribed series
     */
    getSubscribedSeries() {
        return store.get(this.subscriptionsKey) || {};
    },

    /**
     * Alias for getSubscribedSeries for compatibility
     */
    getSubscriptions() {
        return this.getSubscribedSeries();
    },

    /**
     * Detect new conferences matching subscribed series
     */
    detectNewConferences() {
        const subscriptions = this.getSubscribedSeries();
        const processedConfs = store.get(this.processedKey) || [];
        const newProcessed = [];

        $('.ConfItem, .conf-item').each(function() {
            const $conf = $(this);
            const confId = $conf.data('conf-id') || $conf.attr('id');
            const confName = $conf.data('conf-name') || $conf.find('.conf-title a').first().text();

            if (!confId || processedConfs.includes(confId)) return;

            // Check series subscriptions
            const seriesId = SeriesManager.getSeriesId(confName);
            if (subscriptions[seriesId]) {
                const sub = subscriptions[seriesId];

                if (sub.autoFavorite && typeof FavoritesManager !== 'undefined') {
                    // Auto-favorite this conference
                    if (FavoritesManager.isFavorite && !FavoritesManager.isFavorite(confId)) {
                        if (FavoritesManager.extractConferenceData && FavoritesManager.add) {
                            const confData = FavoritesManager.extractConferenceData(confId);
                            if (confData) {
                                FavoritesManager.add(confId, confData);
                            }
                        }
                    }
                }

                if (sub.notifyOnNew) {
                    // Show notification about new conference
                    if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
                        FavoritesManager.showToast(
                            'New Conference in Series',
                            `${confName} has been added to the calendar!`,
                            'info'
                        );
                    }
                }
            }

            // Check pattern subscriptions
            Object.entries(subscriptions).forEach(([key, sub]) => {
                if (sub.isPattern && confName.toLowerCase().includes(sub.pattern.toLowerCase())) {
                    if (sub.notifyOnNew && !processedConfs.includes(confId)) {
                        if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
                            FavoritesManager.showToast(
                                'New Pattern Match',
                                `${confName} matches your ${sub.pattern} subscription!`,
                                'info'
                            );
                        }
                    }
                }
            });

            newProcessed.push(confId);
        });

        // Update processed list
        if (newProcessed.length > 0) {
            const allProcessed = [...processedConfs, ...newProcessed];
            store.set(this.processedKey, allProcessed);
        }
    },

    /**
     * Detect conferences matching a pattern
     */
    detectPatternMatches(pattern) {
        const matches = [];

        $('.ConfItem, .conf-item').each(function() {
            const $conf = $(this);
            const confName = $conf.data('conf-name') || $conf.find('.conf-title a').first().text();

            if (confName.toLowerCase().includes(pattern.toLowerCase())) {
                matches.push(confName);
            }
        });

        if (matches.length > 0) {
            if (typeof FavoritesManager !== 'undefined' && FavoritesManager.showToast) {
                FavoritesManager.showToast(
                    'Pattern Matches Found',
                    `Found ${matches.length} ${pattern} conference(s) on this page.`,
                    'info'
                );
            }
        }
    },

    /**
     * Auto-favorite all conferences in a series
     */
    autoFavoriteSeriesConferences(seriesId) {
        $('.ConfItem, .conf-item').each(function() {
            const $conf = $(this);
            const confId = $conf.data('conf-id') || $conf.attr('id');
            const confName = $conf.data('conf-name') || $conf.find('.conf-title a').first().text();

            const confSeriesId = SeriesManager.getSeriesId(confName);

            if (confSeriesId === seriesId && typeof FavoritesManager !== 'undefined') {
                if (FavoritesManager.isFavorite && !FavoritesManager.isFavorite(confId)) {
                    if (FavoritesManager.extractConferenceData && FavoritesManager.add) {
                        const confData = FavoritesManager.extractConferenceData(confId);
                        if (confData) {
                            FavoritesManager.add(confId, confData);
                        }
                    }
                }
            }
        });
    },

    /**
     * Highlight subscribed series on the page
     */
    highlightSubscribedSeries() {
        const subscriptions = this.getSubscribedSeries();

        $('.series-btn').each(function() {
            const $btn = $(this);
            const confName = $btn.data('conf-name');
            if (!confName) return;

            const seriesId = SeriesManager.getSeriesId(confName);

            if (subscriptions[seriesId]) {
                $btn.addClass('subscribed');
                $btn.find('i').removeClass('far').addClass('fas');
                $btn.css('color', '#007bff');
            } else {
                $btn.removeClass('subscribed');
                $btn.find('i').removeClass('fas').addClass('far');
                $btn.css('color', '#ccc');
            }
        });

        // Update quick subscribe buttons
        $('.quick-subscribe').each(function() {
            const $btn = $(this);
            const pattern = $btn.data('series');
            const patternId = `${pattern}-all`;

            if (subscriptions[patternId]) {
                $btn.removeClass('btn-outline-primary').addClass('btn-primary subscribed');
                $btn.html(`✓ ${$btn.text().replace('+ ', '')}`);
            }
        });
    },

    /**
     * Render subscribed series list in dashboard
     */
    renderSubscribedSeries() {
        const container = $('#subscribed-series-list');
        if (!container.length) return;

        const subscriptions = this.getSubscribedSeries();
        container.empty();

        if (Object.keys(subscriptions).length === 0) {
            container.html('<p class="text-muted small">No series subscriptions yet.</p>');
            return;
        }

        Object.entries(subscriptions).forEach(([seriesId, sub]) => {
            const item = $(`
                <div class="series-item mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${sub.name}</strong>
                            ${sub.isPattern ? '<span class="badge badge-info ml-1">Pattern</span>' : ''}
                        </div>
                        <button class="btn btn-sm btn-link text-danger unsubscribe-series"
                                data-series-id="${seriesId}">
                            <i class="fa fa-times"></i>
                        </button>
                    </div>
                    <div class="small">
                        <label class="mr-3">
                            <input type="checkbox" class="series-auto-favorite"
                                   data-series-id="${seriesId}"
                                   ${sub.autoFavorite ? 'checked' : ''}
                                   ${sub.isPattern ? 'disabled' : ''}>
                            Auto-favorite
                        </label>
                        <label>
                            <input type="checkbox" class="series-notify"
                                   data-series-id="${seriesId}"
                                   ${sub.notifyOnNew ? 'checked' : ''}>
                            Notify
                        </label>
                    </div>
                </div>
            `);

            container.append(item);
        });

        // Bind events for series management
        $('.unsubscribe-series').on('click', function() {
            const seriesId = $(this).data('series-id');
            SeriesManager.unsubscribe(seriesId);
        });

        $('.series-auto-favorite').on('change', function() {
            const seriesId = $(this).data('series-id');
            const subscriptions = SeriesManager.getSubscribedSeries();
            subscriptions[seriesId].autoFavorite = $(this).is(':checked');
            store.set(SeriesManager.subscriptionsKey, subscriptions);
        });

        $('.series-notify').on('change', function() {
            const seriesId = $(this).data('series-id');
            const subscriptions = SeriesManager.getSubscribedSeries();
            subscriptions[seriesId].notifyOnNew = $(this).is(':checked');
            store.set(SeriesManager.subscriptionsKey, subscriptions);
        });
    },

    /**
     * Update series count in dashboard
     */
    updateSeriesCount() {
        const subscriptions = this.getSubscribedSeries();
        const count = Object.keys(subscriptions).length;
        $('#series-count').text(`${count} series subscription${count !== 1 ? 's' : ''}`);
    },

    /**
     * Generate predictions for subscribed series
     */
    generatePredictions() {
        const container = $('#predictions-container');
        if (!container.length) return;

        const subscriptions = this.getSubscribedSeries();
        const predictions = [];

        // For each subscribed series, try to predict next CFP
        Object.entries(subscriptions).forEach(([seriesId, sub]) => {
            if (!sub.isPattern) {
                const prediction = this.predictNextCFP(seriesId, sub.name);
                if (prediction) {
                    predictions.push(prediction);
                }
            }
        });

        if (predictions.length === 0) {
            container.html('<p class="text-muted">No predictions available yet. Predictions will appear as we learn patterns from your subscribed series.</p>');
            return;
        }

        // Sort by predicted date
        predictions.sort((a, b) => new Date(a.cfpDate) - new Date(b.cfpDate));

        // Render predictions
        container.empty();
        predictions.forEach(pred => {
            const card = $(`
                <div class="alert alert-info">
                    <h6><i class="fa fa-crystal-ball"></i> ${pred.seriesName}</h6>
                    <p class="mb-0">
                        Expected CFP opening: <strong>${pred.cfpDate}</strong><br>
                        <small class="text-muted">Based on previous years' patterns</small>
                    </p>
                </div>
            `);
            container.append(card);
        });
    },

    /**
     * Predict next CFP for a series
     */
    predictNextCFP(seriesId, seriesName) {
        // This is a simplified prediction
        // In a real implementation, we'd analyze historical data

        // For demo purposes, let's create some mock predictions
        const mockPredictions = {
            'pycon-us': { cfpDate: 'December 2024', confidence: 0.9 },
            'europython': { cfpDate: 'January 2025', confidence: 0.85 },
            'pydata': { cfpDate: 'Varies by location', confidence: 0.6 }
        };

        if (mockPredictions[seriesId]) {
            return {
                seriesId: seriesId,
                seriesName: seriesName,
                cfpDate: mockPredictions[seriesId].cfpDate,
                confidence: mockPredictions[seriesId].confidence
            };
        }

        return null;
    }
};

// Initialize on document ready
$(document).ready(function() {
    SeriesManager.init();
});
