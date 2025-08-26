/**
 * Theme Toggle for Python Deadlines
 * Handles dark/light mode switching with localStorage persistence
 */

(function() {
    'use strict';

    // Constants
    const STORAGE_KEY = 'pythondeadlines-theme';
    const THEME_DARK = 'dark';
    const THEME_LIGHT = 'light';
    const THEME_AUTO = 'auto';

    // State
    let currentTheme = THEME_AUTO;
    let systemPrefersDark = false;

    /**
     * Initialize theme system
     */
    function initTheme() {
        // Check system preference
        systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        // Get stored preference
        const storedTheme = localStorage.getItem(STORAGE_KEY);
        if (storedTheme && [THEME_DARK, THEME_LIGHT, THEME_AUTO].includes(storedTheme)) {
            currentTheme = storedTheme;
        }

        // Apply theme
        applyTheme();

        // Create toggle button
        createThemeToggle();

        // Listen for system preference changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            systemPrefersDark = e.matches;
            if (currentTheme === THEME_AUTO) {
                applyTheme();
            }
        });
    }

    /**
     * Apply the current theme
     */
    function applyTheme() {
        let effectiveTheme;

        if (currentTheme === THEME_AUTO) {
            effectiveTheme = systemPrefersDark ? THEME_DARK : THEME_LIGHT;
        } else {
            effectiveTheme = currentTheme;
        }

        // Set data attribute on root element
        document.documentElement.setAttribute('data-theme', effectiveTheme);

        // Update toggle button icon
        updateToggleIcon(effectiveTheme);

        // Emit custom event
        const event = new CustomEvent('themeChanged', {
            detail: { theme: effectiveTheme, preference: currentTheme }
        });
        document.dispatchEvent(event);
    }

    /**
     * Create theme toggle button in navbar
     */
    function createThemeToggle() {
        // Check if toggle already exists
        if (document.getElementById('theme-toggle-container')) {
            return;
        }

        // Find navbar
        const navbar = document.querySelector('.navbar-nav.ml-auto') ||
                      document.querySelector('.navbar-nav:last-child');

        if (!navbar) {
            console.warn('Could not find navbar to insert theme toggle');
            return;
        }

        // Create toggle button HTML
        const toggleContainer = document.createElement('li');
        toggleContainer.className = 'nav-item';
        toggleContainer.id = 'theme-toggle-container';
        toggleContainer.innerHTML = `
            <button
                id="theme-toggle"
                class="btn btn-link nav-link theme-toggle-btn"
                aria-label="Toggle dark mode"
                title="Toggle dark mode"
            >
                <span class="theme-icon">
                    <svg class="icon-sun" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="5"></circle>
                        <line x1="12" y1="1" x2="12" y2="3"></line>
                        <line x1="12" y1="21" x2="12" y2="23"></line>
                        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                        <line x1="1" y1="12" x2="3" y2="12"></line>
                        <line x1="21" y1="12" x2="23" y2="12"></line>
                        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                    </svg>
                    <svg class="icon-moon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: none;">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                    </svg>
                    <svg class="icon-auto" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: none;">
                        <circle cx="12" cy="12" r="11"></circle>
                        <path d="M12 1v22"></path>
                        <path d="M12 1a11 11 0 0 1 0 22" fill="currentColor" opacity="0.3"></path>
                    </svg>
                </span>
            </button>
        `;

        // Insert before language selector
        const langSelector = navbar.querySelector('.dropdown');
        if (langSelector) {
            navbar.insertBefore(toggleContainer, langSelector);
        } else {
            navbar.appendChild(toggleContainer);
        }

        // Add click handler
        const toggleBtn = document.getElementById('theme-toggle');
        toggleBtn.addEventListener('click', cycleTheme);

        // Add CSS for the toggle button
        addToggleStyles();
    }

    /**
     * Cycle through theme options
     */
    function cycleTheme() {
        // Cycle: auto -> light -> dark -> auto
        if (currentTheme === THEME_AUTO) {
            currentTheme = THEME_LIGHT;
        } else if (currentTheme === THEME_LIGHT) {
            currentTheme = THEME_DARK;
        } else {
            currentTheme = THEME_AUTO;
        }

        // Save preference
        localStorage.setItem(STORAGE_KEY, currentTheme);

        // Apply theme
        applyTheme();
    }

    /**
     * Update toggle button icon based on current theme
     */
    function updateToggleIcon(effectiveTheme) {
        const sunIcon = document.querySelector('.icon-sun');
        const moonIcon = document.querySelector('.icon-moon');
        const autoIcon = document.querySelector('.icon-auto');

        if (!sunIcon || !moonIcon || !autoIcon) return;

        // Hide all icons
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'none';
        autoIcon.style.display = 'none';

        // Show appropriate icon
        if (currentTheme === THEME_AUTO) {
            autoIcon.style.display = 'block';
        } else if (effectiveTheme === THEME_DARK) {
            moonIcon.style.display = 'block';
        } else {
            sunIcon.style.display = 'block';
        }
    }

    /**
     * Add CSS styles for the toggle button
     */
    function addToggleStyles() {
        if (document.getElementById('theme-toggle-styles')) {
            return;
        }

        const styles = document.createElement('style');
        styles.id = 'theme-toggle-styles';
        styles.textContent = `
            .theme-toggle-btn {
                padding: 0.5rem;
                border: none;
                background: transparent;
                color: inherit;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                transition: opacity 0.3s ease;
            }

            .theme-toggle-btn:hover {
                opacity: 0.8;
            }

            .theme-toggle-btn:focus {
                outline: 2px solid var(--color-primary);
                outline-offset: 2px;
            }

            .theme-icon {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 20px;
                height: 20px;
            }

            .theme-icon svg {
                transition: transform 0.3s ease;
            }

            .theme-toggle-btn:hover .theme-icon svg {
                transform: rotate(180deg);
            }

            @media (max-width: 991px) {
                #theme-toggle-container {
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                    margin-top: 1rem;
                    padding-top: 1rem;
                }

                .theme-toggle-btn {
                    width: 100%;
                    text-align: left;
                    padding: 0.5rem 0;
                }

                .theme-toggle-btn::after {
                    content: 'Toggle Theme';
                    margin-left: 1rem;
                }
            }
        `;

        document.head.appendChild(styles);
    }

    /**
     * Get current theme
     */
    window.getTheme = function() {
        return currentTheme;
    };

    /**
     * Set theme programmatically
     */
    window.setTheme = function(theme) {
        if ([THEME_DARK, THEME_LIGHT, THEME_AUTO].includes(theme)) {
            currentTheme = theme;
            localStorage.setItem(STORAGE_KEY, currentTheme);
            applyTheme();
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }

})();
