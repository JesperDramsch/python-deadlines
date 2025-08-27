function update_filtering(data) {
	// Defensive check for data parameter
	if (!data || typeof data !== 'object') {
		console.error('update_filtering called with invalid data:', data);
		return;
	}

	// Ensure required properties exist
	if (!data.subs || !Array.isArray(data.subs)) {
		console.error('update_filtering: data.subs is not an array:', data.subs);
		return;
	}

	if (!data.all_subs || !Array.isArray(data.all_subs)) {
		console.error('update_filtering: data.all_subs is not an array:', data.all_subs);
		return;
	}

	var page_url = window.location.pathname;
	store.set('{{site.domain}}-subs', { subs: data.subs, timestamp: new Date().getTime() });

	$('.confItem').hide();

	// Loop through selected values in data.subs
	for (const s of data.subs) {
		// Show elements with class .s-conf (where s is the selected value)
		$('.' + s + '-conf').show();
	}

	if (data.subs.length === 0 || data.subs.length == data.all_subs.length) {
		window.history.pushState('', '', page_url);
	} else {
		// Join the selected values into a query parameter
		window.history.pushState('', '', page_url + '?sub=' + data.subs.join());
	}
}

function isDataExpired(data) {
	const EXPIRATION_PERIOD = 1 * 17 * 60 * 60 * 1000; // 1 day in milliseconds
	const now = new Date().getTime();
	if (data.timestamp && now - data.timestamp > EXPIRATION_PERIOD) {
		return true;
	}
	return false;
}

function createCalendarFromObject(data) {
	return createCalendar({
		options: {
			class: 'calendar-obj',

			// You can pass an ID. If you don't, one will be generated for you
			id: data.id,
		},
		data: {
			// Event title
			title: data.title,

			// Event start date
			start: data.start_date,

			// Event duration (minutes)
			duration: 60,

			// You can also choose to set an end time
			// If an end time is set, this will take precedence over duration
			end: data.end_date,

			// Event Address
			address: data.place,

			// Event Description
			description: '<a href=' + data.link + '>' + data.title + '</a>',
		},
	});
}
