/**
 * Tests for NotificationManager
 */

const {
  mockNotificationAPI,
  mockStore,
  TimerController,
  mockBootstrapModal,
  mockPageVisibility
} = require('../utils/mockHelpers');

const {
  createConferenceWithDeadline,
  createSavedConferences,
  setupConferenceDOM,
  createConferenceSet
} = require('../utils/dataHelpers');

// We'll load the actual file in the test
let NotificationManager;

describe('NotificationManager', () => {
  let notificationMock;
  let storeMock;
  let timerController;
  let pageVisibility;

  beforeEach(() => {
    // Set up mocks
    notificationMock = mockNotificationAPI('default');
    storeMock = mockStore();
    timerController = new TimerController();
    pageVisibility = mockPageVisibility(true);
    mockBootstrapModal();

    // Set current time
    timerController.setCurrentTime('2024-01-15 12:00:00');

    // Mock FavoritesManager (dependency of NotificationManager)
    window.FavoritesManager = {
      getSavedConferences: jest.fn(() => ({})),
      showToast: jest.fn(),
      init: jest.fn()
    };

    // Mock jQuery ready to prevent auto-init
    const originalReady = $.fn.ready;
    $.fn.ready = jest.fn();

    // Load NotificationManager (it exposes itself to window)
    jest.isolateModules(() => {
      require('../../../static/js/notifications.js');
      NotificationManager = window.NotificationManager;
    });

    // Restore jQuery ready
    $.fn.ready = originalReady;
  });

  afterEach(() => {
    timerController.cleanup();
    notificationMock.clearInstances();
  });

  describe('Browser Support', () => {
    test('detects browser notification support', () => {
      NotificationManager.checkBrowserSupport();
      expect(console.log).toHaveBeenCalledWith('Browser supports notifications');
    });

    test('shows prompt when permission is default', () => {
      document.body.innerHTML = '<div id="notification-prompt" style="display:none"></div>';
      notificationMock.permission = 'default';

      NotificationManager.checkBrowserSupport();

      const prompt = document.getElementById('notification-prompt');
      expect(prompt.style.display).not.toBe('none');
    });

    test('hides prompt when permission is granted', () => {
      document.body.innerHTML = '<div id="notification-prompt" style="display:block"></div>';
      notificationMock.permission = 'granted';

      NotificationManager.checkBrowserSupport();

      const prompt = document.getElementById('notification-prompt');
      expect(prompt.style.display).toBe('none');
    });
  });

  describe('Permission Request', () => {
    test('requests notification permission', async () => {
      notificationMock.requestPermission.mockResolvedValue('granted');

      const result = await NotificationManager.requestPermission();

      expect(notificationMock.requestPermission).toHaveBeenCalled();
      expect(result).toBe('granted');
    });

    test('shows test notification when permission granted', async () => {
      notificationMock.requestPermission.mockResolvedValue('granted');
      notificationMock.permission = 'granted';

      await NotificationManager.requestPermission();

      // Should create a test notification
      expect(notificationMock.instances.length).toBe(1);
      expect(notificationMock.instances[0].title).toBe('Python Deadlines');
      expect(notificationMock.instances[0].body).toContain('Notifications are now enabled');
    });

    test('handles permission denial', async () => {
      notificationMock.requestPermission.mockResolvedValue('denied');
      document.body.innerHTML = '<div id="notification-prompt"></div>';

      const result = await NotificationManager.requestPermission();

      expect(result).toBe('denied');
      expect(document.getElementById('notification-prompt').style.display).toBe('none');
    });
  });

  describe('Deadline Notifications', () => {
    beforeEach(() => {
      notificationMock.permission = 'granted';

      // Set up default notification settings
      storeMock.set('pythondeadlines-notification-settings', {
        days: [14, 7, 3, 1],
        enabled: true
      });
    });

    test('sends notification 7 days before deadline', () => {
      const conf = createConferenceWithDeadline(7, { id: 'test-7day' });
      const saved = createSavedConferences([conf]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      NotificationManager.checkUpcomingDeadlines();

      expect(notificationMock.instances.length).toBe(1);
      const notification = notificationMock.instances[0];
      expect(notification.body).toContain('7 days until CFP deadline');
    });

    test('sends notification 3 days before deadline', () => {
      const conf = createConferenceWithDeadline(3, { id: 'test-3day' });
      const saved = createSavedConferences([conf]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      NotificationManager.checkUpcomingDeadlines();

      expect(notificationMock.instances.length).toBe(1);
      const notification = notificationMock.instances[0];
      expect(notification.body).toContain('3 days until CFP deadline');
    });

    test('sends urgent notification 1 day before deadline', () => {
      const conf = createConferenceWithDeadline(1, { id: 'test-1day' });
      const saved = createSavedConferences([conf]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      NotificationManager.checkUpcomingDeadlines();

      expect(notificationMock.instances.length).toBe(1);
      const notification = notificationMock.instances[0];
      expect(notification.body).toContain('1 day until CFP deadline');
      expect(notification.requireInteraction).toBe(true);
    });

    test('sends notification for deadline today', () => {
      const conf = createConferenceWithDeadline(0, { id: 'test-today' });
      const saved = createSavedConferences([conf]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      NotificationManager.checkUpcomingDeadlines();

      expect(notificationMock.instances.length).toBe(1);
      const notification = notificationMock.instances[0];
      expect(notification.body).toContain('CFP deadline is TODAY');
      expect(notification.requireInteraction).toBe(true);
    });

    test('does not send duplicate notifications', () => {
      const conf = createConferenceWithDeadline(7, { id: 'test-no-dup' });
      const saved = createSavedConferences([conf]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      // First check
      NotificationManager.checkUpcomingDeadlines();
      expect(notificationMock.instances.length).toBe(1);

      // Reset instances
      notificationMock.clearInstances();

      // Second check - should not send again
      NotificationManager.checkUpcomingDeadlines();
      expect(notificationMock.instances.length).toBe(0);
    });

    test('respects notification day settings', () => {
      // Only notify at 3 and 1 day marks
      storeMock.set('pythondeadlines-notification-settings', {
        days: [3, 1],
        enabled: true
      });

      const conf7 = createConferenceWithDeadline(7, { id: 'test-7' });
      const conf3 = createConferenceWithDeadline(3, { id: 'test-3' });
      const saved = createSavedConferences([conf7, conf3]);
      storeMock.set('pythondeadlines-saved-conferences', saved);

      NotificationManager.loadSettings();
      NotificationManager.checkUpcomingDeadlines();

      // Should only notify for 3-day conference
      expect(notificationMock.instances.length).toBe(1);
      expect(notificationMock.instances[0].body).toContain('3 days');
    });
  });

  describe('Action Bar Integration', () => {
    beforeEach(() => {
      notificationMock.permission = 'granted';

      // Set up conferences in DOM
      const conferences = createConferenceSet();
      setupConferenceDOM(Object.values(conferences));

      // Set up action bar preferences
      localStorage.setItem('pydeadlines_actionBarPrefs', JSON.stringify({
        'conf-7days': { save: true },
        'conf-3days': { save: true },
        'conf-1day': { save: true }
      }));
    });

    test('checks action bar notification preferences', () => {
      // Reset last check time to allow checking
      localStorage.removeItem('pydeadlines_lastNotifyCheck');

      NotificationManager.checkActionBarNotifications();

      // Should create notifications for saved conferences
      const notifications = notificationMock.instances.filter(n =>
        n.title === 'Python Deadlines Reminder'
      );

      expect(notifications.length).toBeGreaterThan(0);
    });

    test('respects 4-hour check interval', () => {
      const now = Date.now();
      localStorage.setItem('pydeadlines_lastNotifyCheck', (now - 2 * 60 * 60 * 1000).toString());

      NotificationManager.checkActionBarNotifications();

      // Should not check (less than 4 hours)
      expect(notificationMock.instances.length).toBe(0);
    });

    test('handles notification click to scroll to conference', () => {
      localStorage.removeItem('pydeadlines_lastNotifyCheck');

      const scrollSpy = jest.spyOn(Element.prototype, 'scrollIntoView');

      NotificationManager.checkActionBarNotifications();

      // Simulate click on notification
      if (notificationMock.instances.length > 0) {
        const notification = notificationMock.instances[0];
        notification.onclick();

        expect(window.focus).toHaveBeenCalled();
        expect(notification.close).toHaveBeenCalled();
      }

      scrollSpy.mockRestore();
    });
  });

  describe('Settings Management', () => {
    test('loads default settings', () => {
      NotificationManager.loadSettings();

      expect(NotificationManager.settings).toEqual({
        days: [14, 7, 3, 1],
        newEditions: true,
        autoFavorite: true,
        enabled: true,
        soundEnabled: false,
        emailEnabled: false
      });
    });

    test('saves settings to store', () => {
      NotificationManager.settings = {
        days: [7, 1],
        enabled: true
      };

      NotificationManager.saveSettings();

      expect(storeMock.set).toHaveBeenCalledWith(
        'pythondeadlines-notification-settings',
        expect.objectContaining({
          days: [7, 1],
          enabled: true
        })
      );
    });

    test('applies settings to UI elements', () => {
      document.body.innerHTML = `
        <input type="checkbox" class="notify-days" value="7" />
        <input type="checkbox" class="notify-days" value="3" />
        <input type="checkbox" class="notify-days" value="1" />
        <input type="checkbox" id="notify-new-editions" />
        <input type="checkbox" id="auto-favorite-series" />
      `;

      NotificationManager.settings = {
        days: [7, 1],
        newEditions: true,
        autoFavorite: false
      };

      NotificationManager.applySettingsToUI();

      const checkboxes = document.querySelectorAll('.notify-days:checked');
      expect(checkboxes.length).toBe(2);
      expect(document.getElementById('notify-new-editions').checked).toBe(true);
      expect(document.getElementById('auto-favorite-series').checked).toBe(false);
    });
  });

  describe('Periodic Checks', () => {
    test('schedules periodic checks', () => {
      const setIntervalSpy = jest.spyOn(global, 'setInterval');

      NotificationManager.schedulePeriodicChecks();

      // Should set up hourly check
      expect(setIntervalSpy).toHaveBeenCalledWith(
        expect.any(Function),
        60 * 60 * 1000
      );
    });

    test('checks on page visibility change', () => {
      const checkSpy = jest.spyOn(NotificationManager, 'checkUpcomingDeadlines');

      NotificationManager.schedulePeriodicChecks();

      // Simulate page becoming visible
      pageVisibility.setVisible(false);
      pageVisibility.setVisible(true);

      expect(checkSpy).toHaveBeenCalled();
    });

    test('checks on window focus', () => {
      const checkSpy = jest.spyOn(NotificationManager, 'checkUpcomingDeadlines');

      NotificationManager.schedulePeriodicChecks();

      // Simulate window focus
      window.focus();

      expect(checkSpy).toHaveBeenCalled();
    });
  });

  describe('Toast Notifications', () => {
    test('shows in-app notification toast', () => {
      NotificationManager.showInAppNotification(
        'Test Title',
        'Test Message',
        'warning'
      );

      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.querySelector('.toast-header')).toHaveTextContent('Test Title');
      expect(toast.querySelector('.toast-body')).toHaveTextContent('Test Message');
      expect(toast.querySelector('.toast-header')).toHaveClass('bg-warning');
    });

    test('creates toast container if not exists', () => {
      // Remove any existing container
      const existing = document.getElementById('toast-container');
      if (existing) existing.remove();

      NotificationManager.showInAppNotification('Test', 'Message');

      expect(document.getElementById('toast-container')).toBeTruthy();
    });
  });

  describe('Notification Cleanup', () => {
    test('cleans up old notifications after 30 days', () => {
      const oldDate = new Date();
      oldDate.setDate(oldDate.getDate() - 35);

      storeMock.set('pythondeadlines-notified-deadlines', {
        'old-notification': oldDate.toISOString(),
        'recent-notification': new Date().toISOString()
      });

      NotificationManager.checkUpcomingDeadlines();

      const notified = storeMock.get('pythondeadlines-notified-deadlines');
      expect(notified['old-notification']).toBeUndefined();
      expect(notified['recent-notification']).toBeDefined();
    });
  });
});
