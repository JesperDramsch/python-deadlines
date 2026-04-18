function getSeasonStyles() {
	const today = new Date();
	const month = today.getMonth() + 1; // 1-12
	const day = today.getDate();

	if (month === 4 && day === 21) {
		return {
			body: 'url(#earth-day)',
			tongue: 'blue',
		};
	}

	if (month === 7 && day === 22) {
		return {
			body: 'url(#party)',
			tongue: 'purple',
		};
	}

	if (month == 3 && day == 31) {
		return {
			body: 'url(#visibility)',
			tongue: 'purple',
		};
	}

	if (month === 3 && day === 8) {
		return {
			body: 'pink',
			tongue: 'red',
		};
	}

	if (month === 11 && day === 19) {
		return {
			body: 'lightblue',
			tongue: 'blue',
		};
	}

	if (month == 3 && day == 17) {
		return {
			body: 'lightgreen',
			tongue: 'green',
		};
	}

	if (month === 6) {
		return {
			body: 'url(#pride)',
			tongue: 'url(#progress)',
		};
	}

	// Halloween: October
	if (month === 10) {
		return {
			body: 'url(#spider-web)',
			tongue: 'black',
		};
	}

	// Christmas: December and first week of January
	if (month === 12 || (month === 1 && day <= 7)) {
		return {
			body: 'url(#candy-cane)',
			tongue: 'red',
		};
	}

	// Easter: March/April (needs to be calculated as it changes)
	// Function to calculate Easter for the current year
	function getEaster(year) {
		const a = year % 19;
		const b = Math.floor(year / 100);
		const c = year % 100;
		const d = Math.floor(b / 4);
		const e = b % 4;
		const f = Math.floor((b + 8) / 25);
		const g = Math.floor((b - f + 1) / 3);
		const h = (19 * a + b - d - g + 15) % 30;
		const i = Math.floor(c / 4);
		const k = c % 4;
		const l = (32 + 2 * e + 2 * i - h - k) % 7;
		const m = Math.floor((a + 11 * h + 22 * l) / 451);
		const month = Math.floor((h + l - 7 * m + 114) / 31) - 1;
		const day = ((h + l - 7 * m + 114) % 31) + 1;
		return { month, day };
	}

	// Check if it's Easter season (1 week around Easter Sunday)
	const easter = getEaster(today.getFullYear());
	const twoWeeksInMs = 7 * 24 * 60 * 60 * 1000;
	const easterDate = new Date(today.getFullYear(), easter.month, easter.day);
	const diff = Math.abs(today - easterDate);

	if (diff <= twoWeeksInMs) {
		return {
			body: 'url(#easter-eggs)',
			tongue: 'orange',
		};
	}

	// Default style for non-seasonal times
	return {
		body: '#646464',
		tongue: '#eea9b8',
	};
}

$(document).ready(function () {
	let clickCount = 0;

	$('#left-snek').on('click', function () {
		clickCount++;

		if (clickCount >= 5) {
			$(this).addClass('annoyed');
			$('#right-snek').addClass('annoyed');
		}
	});
});

$(function () {
	// Apply seasonal styles
	const styles = getSeasonStyles();

	// Add style tag for seasonal colors
	const styleTag = `
        <style id="seasonal-styles">
            #smol-snek-body path {
                fill: ${styles.body};
            }
            #smol-snek-tongue path {
                fill: ${styles.tongue};
            }
        </style>
    `;

	$('head').append(styleTag);

	// Rest of your existing code...
	setInterval(function () {
		$('#right-snek').addClass('wiggle');
		setTimeout(function () {
			$('#right-snek').removeClass('wiggle');
		}, 500);
	}, 15000);
	// Add wiggle animation every 5 seconds
	setInterval(function () {
		$('#right-snek').addClass('wiggle');
		setTimeout(function () {
			$('#right-snek').removeClass('wiggle');
		}, 500);
	}, 15000);

	// Add wiggle animation every 5 seconds
	setInterval(function () {
		$('#smol-snek-all').addClass('wiggle');
		setTimeout(function () {
			$('#smol-snek-all').removeClass('wiggle');
		}, 500);
	}, 31000);

	// Pin animation logic
	setTimeout(function () {
		$('#left-snek').show().addClass('visible');
	}, 2500);
	// Pin animation logic
	setTimeout(function () {
		$('#right-snek').show().addClass('visible');
	}, 3000);
	// Pin animation logic
	setTimeout(function () {
		$('#smol-snek-all').show().addClass('visible');
	}, 3250);

	// Speech bubble: announce the newsletter unless dismissed
	var speechDismissed = false;
	try {
		speechDismissed = localStorage.getItem('snek-speech-dismissed') === '1';
	} catch (e) {
		// localStorage unavailable (private mode); show the bubble anyway
	}

	if (!speechDismissed) {
		setTimeout(function () {
			$('#snek-speech').show();
			// next tick so the transition runs
			setTimeout(function () {
				$('#snek-speech').addClass('visible');
			}, 50);
		}, 4000);
	}

	function dismissSpeechBubble() {
		$('#snek-speech').removeClass('visible');
		setTimeout(function () {
			$('#snek-speech').hide();
		}, 400);
		try {
			localStorage.setItem('snek-speech-dismissed', '1');
		} catch (e) {
			// ignore
		}
	}

	$('#snek-speech-close').on('click', function (e) {
		e.preventDefault();
		dismissSpeechBubble();
	});

	$('.snek-speech-link').on('click', function () {
		dismissSpeechBubble();
	});

	// Show on scroll
	$(window).scroll(function () {
		if ($(window).scrollTop() > 100) {
			$('#location-pin').show().addClass('visible');
		}
	});
});
