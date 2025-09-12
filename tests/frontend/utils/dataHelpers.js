/**
 * Test data generators and helpers
 */

/**
 * Generate mock conference data
 */
function createMockConference(overrides = {}) {
  const baseDate = new Date();
  const cfpDate = new Date(baseDate);
  cfpDate.setDate(cfpDate.getDate() + 30); // CFP 30 days from now

  const startDate = new Date(cfpDate);
  startDate.setDate(startDate.getDate() + 60); // Conference 60 days after CFP

  const endDate = new Date(startDate);
  endDate.setDate(endDate.getDate() + 3); // 3-day conference

  return {
    id: `conf-${Math.random().toString(36).substr(2, 9)}`,
    conference: 'PyCon Test',
    year: baseDate.getFullYear(),
    name: `PyCon Test ${baseDate.getFullYear()}`,
    link: 'https://pycon-test.example.com',
    cfpLink: 'https://pycon-test.example.com/cfp',
    cfp: cfpDate.toISOString().split('T')[0] + ' 23:59:59',
    cfpExt: null,
    place: 'Virtual',
    location: 'Online',
    start: startDate.toISOString().split('T')[0],
    end: endDate.toISOString().split('T')[0],
    topics: ['python', 'web'],
    format: 'virtual',
    hasFinaid: true,
    hasWorkshop: true,
    hasSponsor: false,
    timezone: 'UTC',
    ...overrides
  };
}

/**
 * Create conference with specific days until deadline
 */
function createConferenceWithDeadline(daysUntilDeadline, overrides = {}) {
  const cfpDate = new Date();
  cfpDate.setDate(cfpDate.getDate() + daysUntilDeadline);
  // Keep the same time as current time to get exact day calculation
  // Don't change to 23:59:59 as that causes rounding issues with Math.ceil
  
  return createMockConference({
    cfp: cfpDate.toISOString().replace('T', ' ').split('.')[0],
    ...overrides
  });
}

/**
 * Create past conference
 */
function createPastConference(daysPast = 30, overrides = {}) {
  const cfpDate = new Date();
  cfpDate.setDate(cfpDate.getDate() - daysPast);

  return createMockConference({
    cfp: cfpDate.toISOString().replace('T', ' ').split('.')[0],
    ...overrides
  });
}

/**
 * Create DOM element for conference
 */
function createConferenceDOM(conference) {
  const div = document.createElement('div');
  div.className = 'ConfItem';
  div.id = conference.id;
  div.dataset.confId = conference.id;
  div.dataset.confName = conference.name || conference.conference;
  div.dataset.confYear = conference.year;
  div.dataset.location = conference.place;
  div.dataset.format = conference.format;
  div.dataset.topics = JSON.stringify(conference.topics || []);
  div.dataset.cfp = conference.cfp;
  div.dataset.cfpExt = conference.cfpExt || '';
  div.dataset.start = conference.start;
  div.dataset.end = conference.end;
  div.dataset.link = conference.link;
  div.dataset.cfpLink = conference.cfpLink || '';
  div.dataset.hasFinaid = conference.hasFinaid;
  div.dataset.hasWorkshop = conference.hasWorkshop;
  div.dataset.hasSponsor = conference.hasSponsor;

  div.innerHTML = `
    <div class="row conf-row">
      <div class="col">
        <div class="conf-title">
          <a href="${conference.link}" target="_blank">${conference.conference} ${conference.year}</a>
        </div>
        <div class="conf-details">
          <span class="conf-location">${conference.place}</span>
          <span class="conf-dates">${conference.start} - ${conference.end}</span>
        </div>
        <div class="conf-cfp">
          CFP: <span class="cfp-date">${conference.cfp}</span>
          <span class="countdown-display"
                data-deadline="${conference.cfp}"
                data-timezone="${conference.timezone || 'UTC'}">
          </span>
        </div>
      </div>
      <div class="col-auto">
        <button class="btn favorite-btn" data-conf-id="${conference.id}">
          <i class="far fa-star"></i>
        </button>
        <div class="action-indicator"
             data-conf-id="${conference.id}"
             data-conf-name="${conference.conference}"
             data-conf-cfp="${conference.cfp}"
             data-conf-place="${conference.place}">
        </div>
      </div>
    </div>
  `;

  return div;
}

/**
 * Create multiple conferences with varied deadlines
 */
function createConferenceSet() {
  return {
    upcoming7Days: createConferenceWithDeadline(7, {
      id: 'conf-7days',
      conference: 'PyCon Upcoming 7'
    }),
    upcoming3Days: createConferenceWithDeadline(3, {
      id: 'conf-3days',
      conference: 'PyCon Upcoming 3'
    }),
    upcoming1Day: createConferenceWithDeadline(1, {
      id: 'conf-1day',
      conference: 'PyCon Tomorrow'
    }),
    upcoming30Days: createConferenceWithDeadline(30, {
      id: 'conf-30days',
      conference: 'PyCon Future'
    }),
    past: createPastConference(7, {
      id: 'conf-past',
      conference: 'PyCon Past'
    })
  };
}

/**
 * Create saved conferences structure for localStorage
 */
function createSavedConferences(conferences) {
  const saved = {};
  conferences.forEach(conf => {
    saved[conf.id] = {
      ...conf,
      savedAt: new Date().toISOString(),
      addedAt: new Date().toISOString()
    };
  });
  return saved;
}

/**
 * Create series subscription data
 */
function createSeriesSubscription(seriesName, settings = {}) {
  return {
    [seriesName.toLowerCase()]: {
      name: seriesName,
      subscribedAt: new Date().toISOString(),
      autoFavorite: true,
      notifications: true,
      ...settings
    }
  };
}

/**
 * Setup DOM with multiple conferences
 */
function setupConferenceDOM(conferences) {
  const container = document.createElement('div');
  container.id = 'conference-list';
  container.className = 'conference-list';

  conferences.forEach(conf => {
    container.appendChild(createConferenceDOM(conf));
  });

  document.body.appendChild(container);

  // Add other required DOM elements
  const notificationPrompt = document.createElement('div');
  notificationPrompt.id = 'notification-prompt';
  notificationPrompt.style.display = 'none';
  document.body.appendChild(notificationPrompt);

  const toastContainer = document.createElement('div');
  toastContainer.id = 'toast-container';
  document.body.appendChild(toastContainer);

  return container;
}

// Export all data helpers
module.exports = {
  createMockConference,
  createConferenceWithDeadline,
  createPastConference,
  createConferenceDOM,
  createConferenceSet,
  createSavedConferences,
  createSeriesSubscription,
  setupConferenceDOM
};
