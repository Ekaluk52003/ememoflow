import Alpine from 'alpinejs';

document.addEventListener('alpine:init', () => {
    Alpine.data('userSearch', (initialOptions = []) => ({
        search: '',
        focused: false,
        selected: null,
        options: initialOptions,
        isEditing: true, // Start in editing mode

        get filteredOptions() {
            if (!this.search) return this.options;
            return this.options.filter(option => 
                option.full_name.toLowerCase().includes(this.search.toLowerCase())
            );
        },

        selectUser(option) {
            this.selected = option.id;
            this.search = option.full_name;
            this.focused = false;
            this.isEditing = false;
        },

        startEditing() {
            this.isEditing = true;
            this.focused = true;
            if (this.selected !== null) {
                this.search = '';
                this.selected = null;
            }
        },

        reset() {
            this.search = '';
            this.selected = null;
            this.focused = false;
            this.isEditing = true; // Reset to editing mode
        }
    }));  
              
  
    Alpine.data('notificationSystem', () => ({
        isOpen: false,
        notifications: [],
        notificationCount: 0,
        soundEnabled: localStorage.getItem('soundEnabled') !== 'false',
        notificationSound: new Audio('/static/sounds/notification.mp3'),
        connectionStatus: 'disconnected',
        retryAttempts: 0,
        maxRetryAttempts: 5,
        retryDelay: 5000,
        eventSource: null,

        formatTimestamp(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        getConnectionStatusText() {
            switch(this.connectionStatus) {
                case 'connecting': return 'Connecting...';
                case 'error': return 'Connection error, retrying...';
                case 'failed': return 'Connection failed';
                default: return '';
            }
        },

        saveNotifications() {
            try {
                localStorage.setItem('notifications', JSON.stringify(this.notifications));
                localStorage.setItem('soundEnabled', this.soundEnabled);
            } catch (error) {
                console.error('Error saving notifications:', error);
                if (error.name === 'QuotaExceededError') {
                    this.notifications = this.notifications.slice(-50);
                    this.saveNotifications();
                }
            }
        },

        loadNotifications() {
            try {
                const stored = localStorage.getItem('notifications');
                if (stored) {
                    this.notifications = JSON.parse(stored);
                    this.notifications = this.notifications.filter(n => 
                        n && n.message && n.timestamp && n.url
                    );
                    this.notificationCount = this.notifications.length;
                }
            } catch (error) {
                console.error('Error loading notifications:', error);
                this.notifications = [];
                this.notificationCount = 0;
            }
        },

        clearAll() {
            this.notifications = [];
            this.notificationCount = 0;
            this.saveNotifications();
        },

        removeNotification(index, event) {
            if (event) event.stopPropagation();
            this.notifications.splice(index, 1);
            this.notificationCount = this.notifications.length;
            this.saveNotifications();
        },

        handleNotificationClick(index) {
            try {
                const notification = this.notifications[index];
                if (notification && notification.url) {
                    this.removeNotification(index);
                    window.location.href = notification.url;
                }
            } catch (error) {
                console.error('Error handling notification click:', error);
            }
        },

        playNotificationSound() {
            if (!this.soundEnabled) return;
            
            try {
                this.notificationSound.currentTime = 0;
                const playPromise = this.notificationSound.play();
                
                if (playPromise !== undefined) {
                    playPromise.catch(error => {
                        console.warn('Could not play notification sound:', error);
                    });
                }
            } catch (error) {
                console.error('Error playing notification sound:', error);
            }
        },

        toggleSound() {
            this.soundEnabled = !this.soundEnabled;
            localStorage.setItem('soundEnabled', this.soundEnabled);
        },

        connect() {
            if (this.eventSource) {
                this.eventSource.close();
            }

            try {
                this.connectionStatus = 'connecting';
                this.eventSource = new EventSource('/document/notifications/stream/');

                this.eventSource.onopen = () => {
                    console.log('SSE connection established');
                    this.connectionStatus = 'connected';
                    this.retryAttempts = 0;
                };

                this.eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        
                        if (data.type === 'ping') return;
                        if (data.type === 'error') {
                            console.error('Server error:', data.message);
                            return;
                        }
                        if (data.type === 'connection') {
                            this.connectionStatus = data.status;
                            return;
                        }

                        // Add new notification
                        this.notifications.unshift(data);
                        this.notificationCount = this.notifications.length;
                        this.saveNotifications();
                        this.playNotificationSound();
                    } catch (error) {
                        console.error('Error processing message:', error);
                    }
                };

                this.eventSource.onerror = (error) => {
                    console.error('SSE Error:', error);
                    this.connectionStatus = 'error';
                    this.eventSource.close();

                    if (this.retryAttempts < this.maxRetryAttempts) {
                        const delay = this.retryDelay * Math.pow(2, this.retryAttempts);
                        this.retryAttempts++;
                        setTimeout(() => this.connect(), delay);
                    } else {
                        this.connectionStatus = 'failed';
                        console.error('Max retry attempts reached');
                    }
                };
            } catch (error) {
                console.error('Error establishing SSE connection:', error);
                this.connectionStatus = 'failed';
            }
        },

        initNotifications() {
            this.loadNotifications();
            this.connect();

            // Reconnect when tab becomes visible
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible' && 
                    (this.connectionStatus === 'error' || this.connectionStatus === 'failed')) {
                    this.retryAttempts = 0;
                    this.connect();
                }
            });

            // Cleanup on page unload
            window.addEventListener('beforeunload', () => {
                if (this.eventSource) {
                    this.eventSource.close();
                }
            });
        }
    }));

});
