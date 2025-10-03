// Constants and variables
const TOTAL_SLIDES = 8;
let currentSlide = 1;
let isPresentation = false;

// DOM elements
const body = document.body;
const slides = document.querySelectorAll('.slide');
const prevBtn = document.getElementById('prev-slide');
const nextBtn = document.getElementById('next-slide');
const slideIndicator = document.getElementById('slide-indicator');
const presentationToggle = document.getElementById('presentation-toggle');
const slideNavigation = document.querySelector('.slide-navigation');
const footer = document.querySelector('footer');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
	// Check URL params for presentation mode
	const urlParams = new URLSearchParams(window.location.search);
	if (urlParams.get('presentation') === 'true') {
		enterPresentationMode();
	} else {
		// For normal viewing, show all slides
		slides.forEach((slide) => (slide.style.display = 'block'));

		// Animate elements when they enter viewport
		animateOnScroll();
		window.addEventListener('scroll', animateOnScroll);
	}

	// Setup event listeners
	presentationToggle.addEventListener('click', toggleFullScreen);
	prevBtn.addEventListener('click', prevSlide);
	nextBtn.addEventListener('click', nextSlide);
	document.addEventListener('keydown', handleKeyPress);
});

// Toggle fullscreen
function toggleFullScreen() {
	if (!document.fullscreenElement) {
		document.documentElement
			.requestFullscreen()
			.then(() => enterPresentationMode())
			.catch(() => {});
	} else {
		if (document.exitFullscreen) {
			document
				.exitFullscreen()
				.then(() => exitPresentationMode())
				.catch(() => {});
		}
	}
}

// Enter presentation mode
function enterPresentationMode() {
	isPresentation = true;
	body.classList.add('presentation-mode');
	body.setAttribute('data-slide', currentSlide);
	slideNavigation.style.display = 'flex';
	footer.style.display = 'none';

	// Hide all slides first
	slides.forEach((slide) => {
		slide.style.display = 'flex';
		slide.classList.remove('active');
	});

	// Show only current slide
	showSlide(currentSlide);

	// Make all interactive elements visible immediately
	document.querySelectorAll('.feature, .stat, .testimonial, .use-case').forEach((el) => {
		el.classList.add('visible');
	});
}

// Exit presentation mode
function exitPresentationMode() {
	isPresentation = false;
	body.classList.remove('presentation-mode');
	slideNavigation.style.display = 'none';
	footer.style.display = 'block';

	// Show all slides
	slides.forEach((slide) => {
		slide.style.display = 'block';
		slide.classList.remove('active');
	});

	// Reset scroll position
	window.scrollTo(0, 0);

	// Re-enable scroll animation
	animateOnScroll();
}

// Show a specific slide
function showSlide(number) {
	if (number < 1) number = 1;
	if (number > TOTAL_SLIDES) number = TOTAL_SLIDES;

	currentSlide = number;

	if (isPresentation) {
		// Update body attribute for progress bar
		body.setAttribute('data-slide', currentSlide);

		// Update all slides
		slides.forEach((slide, index) => {
			if (index + 1 === currentSlide) {
				slide.classList.add('active');
			} else {
				slide.classList.remove('active');
			}
		});

		// Update slide indicator
		slideIndicator.textContent = `${currentSlide}/${TOTAL_SLIDES}`;
	}
}

// Navigation functions
function nextSlide() {
	if (currentSlide < TOTAL_SLIDES) {
		showSlide(currentSlide + 1);
	}
}

function prevSlide() {
	if (currentSlide > 1) {
		showSlide(currentSlide - 1);
	}
}

// Keyboard navigation
function handleKeyPress(e) {
	if (isPresentation) {
		switch (e.key) {
			case 'ArrowRight':
			case 'ArrowDown':
			case ' ':
			case 'Enter':
				if (currentSlide === TOTAL_SLIDES) {
					exitPresentationMode();
					toggleFullScreen();
				} else {
					nextSlide();
				}
				break;
			case 'ArrowLeft':
			case 'ArrowUp':
				prevSlide();
				break;
			case 'Home':
				showSlide(1);
				break;
			case 'End':
				showSlide(TOTAL_SLIDES);
				break;
			case 'Escape':
				exitPresentationMode();
				toggleFullScreen();
				break;
		}
	}
}

// Animate elements when scrolling
function animateOnScroll() {
	const elements = document.querySelectorAll('.feature, .stat, .testimonial, .use-case');

	elements.forEach((element) => {
		const rect = element.getBoundingClientRect();
		const windowHeight = window.innerHeight;

		// Add visible class when element is in viewport
		if (rect.top < windowHeight * 0.85) {
			element.classList.add('visible');
		}
	});
}
