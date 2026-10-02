// ==========================================
// Barangay Real-Time WebSocket Handler
// Handles global notifications & live status broadcasts
// ==========================================

class BarangayNotificationSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectInterval = 2000;
        this.init();
    }

    init() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log("WebSocket connected to Barangay Notification Channel.");
            this.reconnectAttempts = 0;
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (err) {
                console.error("Error parsing WS message:", err);
            }
        };

        this.socket.onclose = () => {
            console.warn("WebSocket closed. Attempting reconnect...");
            this.attemptReconnect();
        };

        this.socket.onerror = (err) => {
            console.error("WebSocket error:", err);
            this.socket.close();
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const timeout = this.reconnectInterval * Math.min(this.reconnectAttempts, 5);
            setTimeout(() => this.init(), timeout);
        }
    }

    handleMessage(data) {
        if (data.type === 'notification') {
            this.showToast(data.title, data.message, data.notification_type, data.link_url);
            this.bumpNotificationCounter();
            this.prependNotificationDropdown(data);
        } else if (data.type === 'kapitan_status') {
            this.updateKapitanPill(data);
            this.showToast(
                "Kapitan Status Updated",
                `Barangay Kapitan is now ${data.status_display}${data.leave_reason ? ': ' + data.leave_reason : ''}`,
                data.status === 'on_duty' ? 'success' : 'warning'
            );
        } else if (data.type === 'announcement') {
            this.showToast(
                "New Announcement Published",
                data.title,
                "info",
                `/announcements/#announcement-${data.announcement_id}`
            );
        }
    }

    updateKapitanPill(data) {
        const pill = document.getElementById('kapitan-live-status-pill');
        const textSpan = document.getElementById('kapitan-status-text');
        if (!pill || !textSpan) return;

        pill.className = `kapitan-status-pill ${data.status}`;
        textSpan.textContent = `KAPITAN: ${data.status_display.toUpperCase()}`;

        if (data.status === 'on_leave' && data.return_date) {
            pill.title = `On Leave until ${data.return_date}. Reason: ${data.leave_reason}`;
        } else {
            pill.title = "Barangay Kapitan is currently On Duty";
        }
    }

    bumpNotificationCounter() {
        const countSpan = document.getElementById('notification-count-num');
        const btn = document.getElementById('notification-bell-btn');
        if (countSpan) {
            let count = parseInt(countSpan.textContent.trim()) || 0;
            count += 1;
            countSpan.textContent = count;
        }
        if (btn) {
            btn.classList.add('has-unread');
        }
        const badge = document.getElementById('unread-notification-badge');
        if (badge) {
            let count = parseInt(badge.textContent.trim()) || 0;
            count += 1;
            badge.textContent = count;
            badge.style.display = 'inline';
        }
    }

    prependNotificationDropdown(data) {
        const container = document.getElementById('notification-dropdown-body');
        if (!container) return;

        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const item = document.createElement('a');
        item.href = data.link_url || '#';
        item.className = 'notification-item unread';
        item.innerHTML = `
            <div class="item-title">${this.escapeHtml(data.title)}</div>
            <div class="item-desc">${this.escapeHtml(data.message)}</div>
            <div class="item-time">Just now</div>
        `;
        container.prepend(item);
    }

    showToast(title, message, type = 'info', linkUrl = null) {
        let toastContainer = document.getElementById('global-toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'global-toast-container';
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        const toast = document.createElement('div');
        const typeClass = type === 'success' ? 'toast-success' : (type === 'warning' ? 'toast-warning' : (type === 'danger' ? 'toast-danger' : ''));
        toast.className = `toast ${typeClass}`;

        toast.innerHTML = `
            <div class="toast-content" ${linkUrl ? `onclick="window.location.href='${linkUrl}'" style="cursor:pointer;"` : ''}>
                <div class="toast-title">${this.escapeHtml(title)}</div>
                <div class="toast-body">${this.escapeHtml(message)}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">CLOSE</button>
        `;

        toastContainer.appendChild(toast);

        // Auto remove after 5.5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }
        }, 5500);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.authenticated === "true") {
        window.barangayWS = new BarangayNotificationSocket();
    }
});
