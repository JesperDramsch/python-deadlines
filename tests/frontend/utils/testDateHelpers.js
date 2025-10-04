/**
 * Helper functions for date handling in tests
 */

/**
 * Format a date as YYYY-MM-DD HH:mm:ss for CFP dates
 */
function formatCfpDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * Create a conference date that will calculate to exactly the specified days
 * when using Math.ceil((cfpDate - now) / (1000 * 60 * 60 * 24))
 *
 * @param {number} currentTimeMs - Current time in milliseconds
 * @param {number} daysInFuture - Number of days in the future (7, 3, 1, etc)
 * @returns {string} - Date string in YYYY-MM-DD HH:mm:ss format
 */
function createConferenceDateForThreshold(currentTimeMs, daysInFuture) {
  // To get exactly N days with Math.ceil, we need the date to be
  // just under N * 24 hours from now
  const targetMs = currentTimeMs + (daysInFuture * 24 * 60 * 60 * 1000) - 1000;
  return formatCfpDate(new Date(targetMs));
}

/**
 * Create test conference HTML element
 */
function createConferenceElement(id, name, cfpDate, additionalAttrs = {}) {
  const attrs = Object.entries(additionalAttrs)
    .map(([key, value]) => `data-${key}="${value}"`)
    .join(' ');

  return `<div class="ConfItem"
    id="${id}"
    data-conf-id="${id}"
    data-conf-name="${name}"
    data-cfp="${cfpDate}"
    ${attrs}>
  </div>`;
}

/**
 * Set up conferences at notification thresholds
 */
function setupConferencesAtThresholds(currentTimeMs, thresholds = [7, 3, 1]) {
  const elements = thresholds.map(days => {
    const cfpDate = createConferenceDateForThreshold(currentTimeMs, days);
    return createConferenceElement(
      `conf-${days}days`,
      `${days} Day Conference`,
      cfpDate
    );
  });

  document.body.innerHTML = elements.join('\n');
}

module.exports = {
  formatCfpDate,
  createConferenceDateForThreshold,
  createConferenceElement,
  setupConferencesAtThresholds
};
