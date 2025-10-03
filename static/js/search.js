// Enhanced Search Functionality for Python Deadlines

(function() {
    'use strict';

    // Conference type mappings (will be populated from Jekyll)
    const conferenceTypes = {};

    // Translation strings (will be populated from Jekyll)
    const translations = {
        noResults: 'No results found',
        error: 'Error loading search results',
        loading: 'Loading...',
        clickToFilter: 'Click to filter by'
    };

    /**
     * Create calendar buttons for a conference
     * @param {Object} conf - Conference data
     * @returns {HTMLElement} Calendar container element
     */
    function createCalendarButtons(conf) {
        const container = document.createElement('div');
        container.className = 'calendar';

        try {
            // Parse date with timezone handling
            let cfpDate;
            if (conf.cfp && conf.cfp !== 'TBA' && conf.cfp !== 'Cancelled' && conf.cfp !== 'None') {
                // Use Luxon if available, fallback to Date
                if (typeof luxon !== 'undefined') {
                    const DateTime = luxon.DateTime;
                    cfpDate = conf.timezone
                        ? DateTime.fromSQL(conf.cfp, { zone: conf.timezone })
                        : DateTime.fromSQL(conf.cfp, { zone: 'UTC-12' });

                    if (cfpDate.invalid) {
                        cfpDate = DateTime.fromSQL(conf.cfp);
                    }
                    cfpDate = cfpDate.toJSDate();
                } else {
                    cfpDate = new Date(conf.cfp);
                }

                // Create calendar with ouical if available
                if (typeof createCalendarFromObject === 'function' && cfpDate && !isNaN(cfpDate)) {
                    const calendar = createCalendarFromObject({
                        id: conf.id || `${conf.conference}-${conf.year}`,
                        title: `${conf.conference} ${conf.year} deadline`,
                        start_date: cfpDate,
                        duration: 60,
                        place: conf.place || '',
                        link: conf.link || ''
                    });
                    container.appendChild(calendar);
                } else {
                    // Fallback to simple text
                    const span = document.createElement('span');
                    span.className = 'calendar-fallback';
                    span.textContent = 'Calendar not available';
                    container.appendChild(span);
                }
            }
        } catch (err) {
            const span = document.createElement('span');
            span.className = 'calendar-error';
            span.textContent = 'Calendar error';
            container.appendChild(span);
        }

        return container;
    }

    /**
     * Format conference date for display
     * @param {string} date - Date string
     * @param {string} timezone - Timezone string
     * @returns {string} Formatted date
     */
    function formatDate(date, timezone) {
        if (!date || date === 'TBA' || date === 'Cancelled' || date === 'None') {
            return date || 'TBA';
        }

        try {
            if (typeof luxon !== 'undefined') {
                const DateTime = luxon.DateTime;
                let dt = timezone
                    ? DateTime.fromSQL(date, { zone: timezone })
                    : DateTime.fromSQL(date, { zone: 'UTC-12' });

                if (dt.invalid) {
                    dt = DateTime.fromSQL(date);
                }

                return dt.toLocaleString(DateTime.DATETIME_HUGE);
            } else {
                // Fallback to native Date
                const d = new Date(date);
                if (!isNaN(d)) {
                    return d.toLocaleString();
                }
            }
        } catch (err) {
            // Date formatting failed, return original
        }

        return date;
    }

    /**
     * Create countdown timer for conference
     * @param {string} cfp - CFP deadline
     * @param {string} timezone - Timezone
     * @returns {string} Timer HTML or deadline text
     */
    function createTimer(cfp, timezone) {
        if (!cfp || cfp === 'TBA' || cfp === 'Cancelled' || cfp === 'None') {
            return cfp || 'TBA';
        }

        try {
            if (typeof luxon !== 'undefined') {
                const DateTime = luxon.DateTime;
                let cfpDate = timezone
                    ? DateTime.fromSQL(cfp, { zone: timezone })
                    : DateTime.fromSQL(cfp, { zone: 'UTC-12' });

                if (cfpDate.invalid) {
                    cfpDate = DateTime.fromSQL(cfp);
                }

                const diff = cfpDate.diffNow('seconds').toObject().seconds;

                if (diff > 0) {
                    // Create timer element
                    const timer = document.createElement('span');
                    timer.className = 'search-timer';
                    timer.setAttribute('data-deadline', cfpDate.toISO());

                    // Initialize countdown if jQuery countdown is available
                    if (typeof $ !== 'undefined' && $.fn.countdown) {
                        $(timer).countdown(cfpDate.toJSDate(), function(event) {
                            $(this).html(event.strftime('%D days %Hh %Mm %Ss'));
                        });
                    } else {
                        timer.textContent = formatDate(cfp, timezone);
                    }

                    return timer.outerHTML;
                } else {
                    return `<span class="deadline-passed">Deadline passed</span>`;
                }
            }
        } catch (err) {
            console.error('Error creating timer:', err);
        }

        return formatDate(cfp, timezone);
    }

    /**
     * Display search results with enhanced features
     * @param {Array} results - Search results from Lunr
     * @param {Object} docs - Document store
     */
    window.displaySearchResults = function(results, docs) {
        const searchResults = document.getElementById('search-results');

        if (!searchResults) return;

        // Show loading state
        searchResults.innerHTML = `<div class="search-loading">${translations.loading}</div>`;

        if (results.length) {
            let html = '';

            for (let i = 0; i < results.length; i++) {
                const item = docs[results[i].ref];

                // Error handling for malformed data
                if (!item) {
                    console.error(`Missing document for ref: ${results[i].ref}`);
                    continue;
                }

                // Process submission types
                const subs = (item.subs || '').split(',').map(s => s.trim()).filter(s => s);
                const subClasses = subs.map(sub => `${sub}-conf`).join(' ');

                // Create conference item HTML
                html += `
                    <div id="${results[i].ref}" class="ConfItem ${subClasses}">
                        <div class="row conf-row">
                            <div class="col-12 col-sm-6">
                                <span class="conf-title">
                                    <a title="Deadline Details" href="${item.url || '#'}">${item.title || 'Untitled'}</a>
                                </span>
                                <span class="conf-title-small">
                                    <a title="Deadline Details" href="${item.url || '#'}">${item.title || 'Untitled'}</a>
                                </span>
                                ${item.link ? `
                                    <span class="conf-title-icon">
                                        <a title="Conference Website" href="${item.link}" target="_blank" rel="noopener">
                                            <img src="/static/img/203-earth.svg" class="badge-link" alt="Link to Conference Website" width="16" height="16" />
                                        </a>
                                    </span>
                                ` : ''}
                            </div>
                            <div class="col-12 col-sm-6">
                                <div class="deadline">
                                    <div class="timer">
                                        ${createTimer(item.cfp || item.date, item.timezone)}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12 col-sm-6">
                                <div class="meta">
                                    <span class="conf-place">
                                        ${item.content ? (item.content.length > 150
                                            ? item.content.substring(0, 150) + '... '
                                            : item.content + ', ') : ''}
                                        ${item.place ? (item.place === 'Online'
                                            ? `<a href="#">${item.place}</a>`
                                            : `<a href="https://maps.google.com/?q=${encodeURIComponent(item.place)}" target="_blank" rel="noopener">${item.place}</a>`)
                                            : ''}
                                    </span>
                                </div>
                            </div>
                            <div class="col-12 col-sm-6">
                                <div class="deadline">
                                    <div>
                                        <span class="deadline-time">${formatDate(item.cfp || item.date, item.timezone)}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-6">
                                ${subs.map(sub => {
                                    const type = conferenceTypes[sub] || { name: sub, color: '#666' };
                                    return `
                                        <span
                                            title="${translations.clickToFilter} ${type.name}"
                                            data-sub="${sub}"
                                            class="badge badge-light conf-sub ${sub}-tag"
                                            style="color: ${type.color}"
                                        >${type.name}</span>
                                    `;
                                }).join('')}
                            </div>
                            <div class="col-6">
                                <div class="search-calendar-${i}"></div>
                            </div>
                        </div>
                        <hr />
                    </div>
                `;
            }

            searchResults.innerHTML = html;

            // Add calendar buttons after rendering
            for (let i = 0; i < results.length; i++) {
                const item = docs[results[i].ref];
                const calendarContainer = document.querySelector(`.search-calendar-${i}`);
                if (calendarContainer && item) {
                    const calendar = createCalendarButtons(item);
                    calendarContainer.appendChild(calendar);
                }
            }

            // Add click handlers for conference type badges
            document.querySelectorAll('.conf-sub').forEach(badge => {
                badge.addEventListener('click', function(e) {
                    const sub = this.getAttribute('data-sub');
                    if (sub && typeof window.filterBySub === 'function') {
                        window.filterBySub(sub);
                    }
                });
            });

        } else {
            searchResults.innerHTML = `<div class="no-results">${translations.noResults}</div>`;
        }
    };

    /**
     * Get query parameter from URL
     * @param {string} variable - Parameter name
     * @returns {string|null} Parameter value
     */
    window.getQueryVariable = function(variable) {
        const query = window.location.search.substring(1);
        const vars = query.split('&');

        for (let i = 0; i < vars.length; i++) {
            const pair = vars[i].split('=');
            if (pair[0] === variable) {
                return decodeURIComponent(pair[1].replace(/\+/g, '%20'));
            }
        }
        return null;
    };

    /**
     * Initialize conference types from Jekyll data
     */
    window.initializeConferenceTypes = function(types) {
        types.forEach(type => {
            conferenceTypes[type.sub] = type;
        });
    };

    /**
     * Set translation strings
     */
    window.setSearchTranslations = function(trans) {
        Object.assign(translations, trans);
    };

})();
