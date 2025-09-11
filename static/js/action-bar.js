/**
 * Minimal Action Bar Handler
 * Progressive disclosure design with colored line indicator
 */
(function() {
    'use strict';
    
    const STORAGE_KEY = 'pythondeadlines-favorites'; // Use existing storage key
    const SERIES_KEY = 'pythondeadlines-series-subscriptions';
    const SAVED_CONFERENCES_KEY = 'pythondeadlines-saved-conferences';
    let currentPopover = null;
    let isMobile = window.innerWidth <= 768;
    
    // Load saved preferences from existing system
    function getPrefs() {
        try {
            // Get favorites from existing FavoritesManager format
            const favorites = store.get(STORAGE_KEY) || [];
            const savedConferences = store.get(SAVED_CONFERENCES_KEY) || {};
            const series = store.get(SERIES_KEY) || {};
            
            // Convert to our format
            const prefs = {};
            favorites.forEach(confId => {
                prefs[confId] = { saved: true };
                // Check if this conference's series is subscribed
                const conf = savedConferences[confId];
                if (conf && conf.conference) {
                    const seriesName = conf.conference.toLowerCase();
                    if (series[seriesName]) {
                        prefs[confId].series = true;
                    }
                }
            });
            
            return prefs;
        } catch(e) {
            console.error('Error loading preferences:', e);
            return {};
        }
    }
    
    // Save preferences using existing system
    function savePrefs(prefs) {
        try {
            // Convert our format to FavoritesManager format
            const favorites = [];
            const savedConferences = store.get(SAVED_CONFERENCES_KEY) || {};
            
            Object.keys(prefs).forEach(confId => {
                if (prefs[confId].saved) {
                    favorites.push(confId);
                    
                    // Get conference data from page if not already saved
                    if (!savedConferences[confId]) {
                        const indicator = document.querySelector(`.action-indicator[data-conf-id="${confId}"]`);
                        if (indicator) {
                            savedConferences[confId] = {
                                id: confId,
                                name: indicator.dataset.confName || confId,
                                cfp: indicator.dataset.confCfp,
                                place: indicator.dataset.confPlace,
                                savedAt: new Date().toISOString()
                            };
                        }
                    }
                }
            });
            
            // Save using existing storage keys
            store.set(STORAGE_KEY, favorites);
            store.set(SAVED_CONFERENCES_KEY, savedConferences);
            
            // Fire events for other components
            window.dispatchEvent(new CustomEvent('favoritesUpdated', {
                detail: { favorites, savedConferences }
            }));
        } catch(e) {
            console.error('Error saving preferences:', e);
        }
    }
    
    // Initialize action indicators
    function initializeIndicators() {
        const prefs = getPrefs();
        
        document.querySelectorAll('.action-indicator').forEach(indicator => {
            const confId = indicator.dataset.confId;
            if (!confId) return;
            
            const conf = prefs[confId] || {};
            
            // Update indicator state
            if (conf.saved && conf.series) {
                indicator.classList.add('series');
                indicator.classList.remove('saved');
            } else if (conf.saved) {
                indicator.classList.add('saved');
                indicator.classList.remove('series');
            } else {
                indicator.classList.remove('saved', 'series');
            }
            
            // Update icon
            const icon = indicator.querySelector('.action-icon');
            if (icon && conf.saved) {
                icon.className = 'fas fa-bookmark action-icon';
            }
        });
        
        // Initialize mobile bookmarks
        document.querySelectorAll('.mobile-action-bookmark').forEach(btn => {
            const confId = btn.dataset.confId;
            if (!confId) return;
            
            const conf = prefs[confId] || {};
            if (conf.saved) {
                btn.classList.add('saved');
                btn.querySelector('i').className = 'fas fa-bookmark';
            }
        });
    }
    
    // Handle action indicator clicks (desktop)
    document.addEventListener('click', function(e) {
        // Close popover when clicking outside
        if (currentPopover && !e.target.closest('.action-indicator') && !e.target.closest('.action-popover')) {
            currentPopover.classList.remove('show');
            currentPopover = null;
            return;
        }
        
        // Handle indicator click
        const indicator = e.target.closest('.action-indicator');
        if (indicator) {
            e.preventDefault();
            e.stopPropagation();
            
            const confId = indicator.dataset.confId;
            const popover = document.querySelector(`.action-popover[data-conf-id="${confId}"]`);
            
            if (popover) {
                // Close any open popover
                if (currentPopover && currentPopover !== popover) {
                    currentPopover.classList.remove('show');
                }
                
                // Toggle this popover
                popover.classList.toggle('show');
                currentPopover = popover.classList.contains('show') ? popover : null;
                
                // Update popover items state
                updatePopoverState(popover, confId);
            }
        }
        
        // Handle popover item clicks
        const popoverItem = e.target.closest('.action-popover-item');
        if (popoverItem && !popoverItem.classList.contains('action-popover-calendar')) {
            e.preventDefault();
            handleAction(popoverItem);
        }
        
        // Handle calendar option clicks
        const calendarOption = e.target.closest('.calendar-option');
        if (calendarOption) {
            e.preventDefault();
            const calendarType = calendarOption.dataset.calendar;
            const popover = calendarOption.closest('.action-popover');
            const confId = popover.dataset.confId;
            const indicator = document.querySelector(`.action-indicator[data-conf-id="${confId}"]`);
            generateCalendarLinks(null, indicator, calendarType);
            
            // Close popover after selection
            popover.classList.remove('show');
            currentPopover = null;
        }
        
        // Handle mobile bookmark click
        const mobileBookmark = e.target.closest('.mobile-action-bookmark');
        if (mobileBookmark) {
            e.preventDefault();
            handleMobileBookmark(mobileBookmark);
        }
    });
    
    // Update popover state based on saved preferences
    function updatePopoverState(popover, confId) {
        const prefs = getPrefs();
        const conf = prefs[confId] || {};
        
        popover.querySelectorAll('.action-popover-item').forEach(item => {
            const action = item.dataset.action;
            const icon = item.querySelector('i');
            
            if (action === 'save' && conf.saved) {
                item.classList.add('active');
                if (icon) icon.className = 'fas fa-bookmark';
            } else if (action === 'series' && conf.series) {
                item.classList.add('active');
                if (icon) icon.className = 'fas fa-bell';
            } else if (icon) {
                item.classList.remove('active');
                if (action === 'save') icon.className = 'far fa-bookmark';
                if (action === 'series') icon.className = 'far fa-bell';
            }
        });
    }
    
    // Handle action from popover
    function handleAction(item) {
        const action = item.dataset.action;
        const popover = item.closest('.action-popover');
        const confId = popover.dataset.confId;
        const indicator = document.querySelector(`.action-indicator[data-conf-id="${confId}"]`);
        
        const prefs = getPrefs();
        if (!prefs[confId]) prefs[confId] = {};
        
        if (action === 'save') {
            prefs[confId].saved = !prefs[confId].saved;
            
            // Update indicator
            if (prefs[confId].saved) {
                indicator.classList.add('saved');
                item.classList.add('active');
                item.querySelector('i').className = 'fas fa-bookmark';
            } else {
                indicator.classList.remove('saved', 'series');
                item.classList.remove('active');
                item.querySelector('i').className = 'far fa-bookmark';
                // If unsaving, also remove series
                prefs[confId].series = false;
            }
        } else if (action === 'series') {
            prefs[confId].series = !prefs[confId].series;
            
            // Series requires saved
            if (prefs[confId].series) {
                prefs[confId].saved = true;
                indicator.classList.add('series');
                indicator.classList.remove('saved');
                item.classList.add('active');
                item.querySelector('i').className = 'fas fa-bell';
                
                // Also update save button
                const saveItem = popover.querySelector('[data-action="save"]');
                if (saveItem) {
                    saveItem.classList.add('active');
                    saveItem.querySelector('i').className = 'fas fa-bookmark';
                }
            } else {
                indicator.classList.remove('series');
                if (prefs[confId].saved) {
                    indicator.classList.add('saved');
                }
                item.classList.remove('active');
                item.querySelector('i').className = 'far fa-bell';
            }
        }
        
        savePrefs(prefs);
        
        // Fire event for other components using existing event names
        window.dispatchEvent(new CustomEvent('favoritesUpdated', {
            detail: { confId, action, value: prefs[confId][action] }
        }));
    }
    
    // Handle mobile bookmark
    function handleMobileBookmark(btn) {
        const confId = btn.dataset.confId;
        const prefs = getPrefs();
        
        if (!prefs[confId]) prefs[confId] = {};
        prefs[confId].saved = !prefs[confId].saved;
        
        if (prefs[confId].saved) {
            btn.classList.add('saved');
            btn.querySelector('i').className = 'fas fa-bookmark';
        } else {
            btn.classList.remove('saved');
            btn.querySelector('i').className = 'far fa-bookmark';
            prefs[confId].series = false; // Unsaving removes series too
        }
        
        savePrefs(prefs);
        
        // Show mobile action sheet for more options if saving
        if (prefs[confId].saved && isMobile) {
            showMobileActionSheet(confId);
        }
    }
    
    // Show mobile action sheet
    function showMobileActionSheet(confId) {
        // Create sheet if it doesn't exist
        let sheet = document.querySelector('.mobile-action-sheet');
        if (!sheet) {
            sheet = document.createElement('div');
            sheet.className = 'mobile-action-sheet';
            sheet.innerHTML = `
                <div class="mobile-action-sheet-header">
                    <h3 class="mobile-action-sheet-title">Conference Actions</h3>
                    <button class="mobile-action-sheet-close">&times;</button>
                </div>
                <div class="mobile-action-sheet-items"></div>
            `;
            document.body.appendChild(sheet);
            
            // Bind close button
            sheet.querySelector('.mobile-action-sheet-close').addEventListener('click', () => {
                sheet.classList.remove('show');
            });
        }
        
        // Update items
        const prefs = getPrefs();
        const conf = prefs[confId] || {};
        const itemsContainer = sheet.querySelector('.mobile-action-sheet-items');
        
        itemsContainer.innerHTML = `
            <a href="#" class="mobile-action-sheet-item ${conf.saved ? 'active' : ''}" data-action="save" data-conf-id="${confId}">
                <i class="${conf.saved ? 'fas' : 'far'} fa-bookmark"></i>
                <span>Save to Favorites</span>
            </a>
            <a href="#" class="mobile-action-sheet-item ${conf.series ? 'active' : ''}" data-action="series" data-conf-id="${confId}">
                <i class="${conf.series ? 'fas' : 'far'} fa-bell"></i>
                <span>Follow Series</span>
            </a>
            <a href="#" class="mobile-action-sheet-item" data-action="calendar" data-conf-id="${confId}">
                <i class="far fa-calendar-plus"></i>
                <span>Add to Calendar</span>
            </a>
        `;
        
        // Show sheet
        setTimeout(() => sheet.classList.add('show'), 10);
    }
    
    // Handle mobile action sheet clicks
    document.addEventListener('click', function(e) {
        const item = e.target.closest('.mobile-action-sheet-item');
        if (item) {
            e.preventDefault();
            const action = item.dataset.action;
            const confId = item.dataset.confId;
            
            if (action === 'calendar') {
                // For mobile, show calendar options in action sheet
                showMobileCalendarOptions(confId);
            } else {
                // Toggle action
                const prefs = getPrefs();
                if (!prefs[confId]) prefs[confId] = {};
                
                if (action === 'save') {
                    prefs[confId].saved = !prefs[confId].saved;
                } else if (action === 'series') {
                    prefs[confId].series = !prefs[confId].series;
                    if (prefs[confId].series) prefs[confId].saved = true;
                }
                
                savePrefs(prefs);
                
                // Update UI
                initializeIndicators();
                
                // Update sheet items
                const sheet = document.querySelector('.mobile-action-sheet');
                if (sheet) {
                    showMobileActionSheet(confId);
                }
            }
        }
    });
    
    // Generate calendar links based on calendar type
    function generateCalendarLinks(element, indicator, calendarType) {
        const confId = indicator ? indicator.dataset.confId : element.dataset.confId;
        const confName = indicator ? indicator.dataset.confName : 'Conference';
        const cfpDate = indicator ? indicator.dataset.confCfp : null;
        const confPlace = indicator ? indicator.dataset.confPlace : '';
        
        // Format the date for calendar
        const eventDate = cfpDate ? new Date(cfpDate) : new Date();
        const startDate = eventDate.toISOString().replace(/-|:|\.\d\d\d/g, '');
        
        // Create event details
        const eventDetails = {
            title: `${confName} - CFP Deadline`,
            details: `Call for Proposals deadline for ${confName}`,
            location: confPlace,
            startDate: startDate,
            endDate: startDate
        };
        
        let calendarUrl = '';
        
        switch(calendarType) {
            case 'google':
                calendarUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(eventDetails.title)}&details=${encodeURIComponent(eventDetails.details)}&location=${encodeURIComponent(eventDetails.location)}&dates=${startDate}/${eventDetails.endDate}`;
                window.open(calendarUrl, '_blank');
                break;
                
            case 'outlook':
                calendarUrl = `https://outlook.live.com/calendar/0/deeplink/compose?subject=${encodeURIComponent(eventDetails.title)}&body=${encodeURIComponent(eventDetails.details)}&location=${encodeURIComponent(eventDetails.location)}&startdt=${startDate}&enddt=${eventDetails.endDate}`;
                window.open(calendarUrl, '_blank');
                break;
                
            case 'apple':
                // For Apple Calendar, we'll download an ICS file
                generateICSFile(eventDetails);
                break;
                
            case 'ics':
                generateICSFile(eventDetails);
                break;
        }
        
        // Show success message
        showNotification('Calendar event created!', 'success');
    }
    
    // Generate ICS file for download
    function generateICSFile(eventDetails) {
        const icsContent = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PythonDeadlines//Conference CFP//EN
BEGIN:VEVENT
UID:${Date.now()}@pythondeadlin.es
DTSTAMP:${new Date().toISOString().replace(/-|:|\.\d\d\d/g, '')}
DTSTART:${eventDetails.startDate}
DTEND:${eventDetails.endDate}
SUMMARY:${eventDetails.title}
DESCRIPTION:${eventDetails.details}
LOCATION:${eventDetails.location}
END:VEVENT
END:VCALENDAR`;
        
        const blob = new Blob([icsContent], { type: 'text/calendar' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${eventDetails.title.replace(/[^a-z0-9]/gi, '_')}.ics`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
    
    // Show notification message
    function showNotification(text, type = 'info') {
        const message = document.createElement('div');
        message.textContent = text;
        const bgColor = type === 'success' ? '#28a745' : '#17a2b8';
        message.style.cssText = `position: fixed; top: 20px; right: 20px; background: ${bgColor}; color: white; padding: 10px 20px; border-radius: 4px; z-index: 9999; animation: slideIn 0.3s ease;`;
        document.body.appendChild(message);
        setTimeout(() => {
            message.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => message.remove(), 300);
        }, 2000);
    }
    
    // Show mobile calendar options
    function showMobileCalendarOptions(confId) {
        const sheet = document.querySelector('.mobile-action-sheet');
        if (!sheet) return;
        
        const itemsContainer = sheet.querySelector('.mobile-action-sheet-items');
        const indicator = document.querySelector(`.action-indicator[data-conf-id="${confId}"]`);
        
        itemsContainer.innerHTML = `
            <div class="mobile-action-sheet-back">
                <i class="fas fa-arrow-left"></i>
                <span>Back</span>
            </div>
            <a href="#" class="mobile-action-sheet-item" data-action="calendar-google" data-conf-id="${confId}">
                <i class="fab fa-google"></i>
                <span>Google Calendar</span>
            </a>
            <a href="#" class="mobile-action-sheet-item" data-action="calendar-outlook" data-conf-id="${confId}">
                <i class="fab fa-microsoft"></i>
                <span>Outlook</span>
            </a>
            <a href="#" class="mobile-action-sheet-item" data-action="calendar-apple" data-conf-id="${confId}">
                <i class="fab fa-apple"></i>
                <span>Apple Calendar</span>
            </a>
            <a href="#" class="mobile-action-sheet-item" data-action="calendar-ics" data-conf-id="${confId}">
                <i class="fas fa-download"></i>
                <span>Download .ics</span>
            </a>
        `;
        
        // Handle back button
        const backBtn = itemsContainer.querySelector('.mobile-action-sheet-back');
        backBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showMobileActionSheet(confId);
        });
        
        // Handle calendar option clicks
        itemsContainer.querySelectorAll('[data-action^="calendar-"]').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                const calendarType = option.dataset.action.replace('calendar-', '');
                generateCalendarLinks(null, indicator, calendarType);
                sheet.classList.remove('show');
            });
        });
    }
    
    // Handle keyboard navigation
    document.addEventListener('keydown', function(e) {
        const indicator = document.activeElement.closest('.action-indicator');
        if (indicator && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            indicator.click();
        }
    });
    
    // Handle window resize
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            isMobile = window.innerWidth <= 768;
        }, 100);
    });
    
    // Initialize on DOM ready (only enhance existing HTML)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeIndicators);
    } else {
        initializeIndicators();
    }
    
    // Export API for other components
    window.minimalActionAPI = {
        getPrefs: getPrefs,
        isConferenceSaved: function(confId) {
            const prefs = getPrefs();
            return prefs[confId]?.saved || false;
        },
        getSeriesFollowed: function() {
            const prefs = getPrefs();
            return Object.keys(prefs).filter(id => prefs[id].series);
        }
    };
})();