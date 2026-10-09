// Moved from templates/chat/inbox.html (inline scripts are blocked by the CSP).
function openStaffRosterModal() {
    var modal = document.getElementById('staffRosterModal');
    if (modal) modal.style.display = 'flex';
}

function closeStaffRosterModal() {
    var modal = document.getElementById('staffRosterModal');
    if (modal) modal.style.display = 'none';
}

function filterMessengerContacts(val) {
    var query = val.toLowerCase().trim();
    var items = document.querySelectorAll('.messenger-contact-item');
    items.forEach(function(item) {
        var name = item.getAttribute('data-name') || '';
        if (name.indexOf(query) !== -1) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Close roster modal on click outside
    var rosterModal = document.getElementById('staffRosterModal');
    if (rosterModal) {
        rosterModal.addEventListener('click', (e) => {
            if (e.target === rosterModal) closeStaffRosterModal();
        });
    }

    const currentUserId = document.body.dataset.userId || '';
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }
    const searchBox = document.getElementById('messenger-search-box');
    if (searchBox) {
        searchBox.addEventListener('input', () => filterMessengerContacts(searchBox.value));
    }
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-inbox-action="close-roster"]')) closeStaffRosterModal();
        if (e.target.closest('[data-inbox-action="open-roster"]')) openStaffRosterModal();
    });
    let currentChatSocket = null;

    function bindChatSession() {
        if (currentChatSocket) {
            try { currentChatSocket.close(); } catch(err) {}
            currentChatSocket = null;
        }

        const mainPane = document.getElementById('messenger-main-pane');
        if (!mainPane) return;

        const otherUserId = mainPane.getAttribute('data-other-user-id');
        if (!otherUserId) return;

        const messagesContainer = document.getElementById('chatMessagesBody') || document.getElementById('chat-messages-container');
        const form = document.getElementById('chat-form');
        const input = document.getElementById('chat-message-input');
        const placeholder = document.getElementById('no-messages-placeholder');

        function scrollToBottom() {
            if (messagesContainer) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }
        scrollToBottom();

        // WebSocket connection for real-time 1-on-1 direct chat
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const chatWsUrl = `${protocol}//${window.location.host}/ws/chat/${otherUserId}/`;
        currentChatSocket = new WebSocket(chatWsUrl);

        currentChatSocket.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'error' && data.error === 'rate_limited') {
                    alert(data.message || 'You are sending messages too quickly. Please wait a moment.');
                    return;
                }
                if (data.type === 'chat_message') {
                    if (placeholder) placeholder.remove();

                    const isSentByMe = String(data.sender_id) === String(currentUserId);
                    const row = document.createElement('div');
                    row.className = `message-row ${isSentByMe ? 'outgoing' : 'incoming'}`;
                    
                    if (isSentByMe) {
                        row.innerHTML = `
                            <div class="message-bubble">
                                <p class="message-text">${escapeHtml(data.content)}</p>
                                <span class="message-time">
                                    <span class="icon-labelled" title="Delivered">${BrgyUI.icon('check', 'icon-sm')}<span class="sr-only">Delivered</span></span>
                                    ${escapeHtml(data.created_at)}
                                </span>
                            </div>
                        `;
                    } else {
                        const initials = data.sender_initials || (data.sender_name ? data.sender_name.slice(0, 2).toUpperCase() : 'U');
                        row.innerHTML = `
                            <div class="message-avatar">${escapeHtml(initials)}</div>
                            <div class="message-bubble">
                                <p class="message-text">${escapeHtml(data.content)}</p>
                                <span class="message-time">${escapeHtml(data.created_at)}</span>
                            </div>
                        `;
                    }

                    messagesContainer.appendChild(row);
                    scrollToBottom();
                }
            } catch (err) {
                console.error("Error processing incoming chat message:", err);
            }
        };

        if (form && input) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const content = input.value.trim();
                if (!content) return;

                if (currentChatSocket && currentChatSocket.readyState === WebSocket.OPEN) {
                    currentChatSocket.send(JSON.stringify({
                        'message': content
                    }));
                    input.value = '';
                    input.focus();
                } else {
                    alert("Chat socket reconnecting. Please wait a moment.");
                }
            });
        }
    }

    // Attach dynamic click to contacts to keep display intact without moving
    function attachContactItemHandlers() {
        document.querySelectorAll('.messenger-contact-item').forEach(item => {
            item.onclick = function(e) {
                e.preventDefault();
                const url = this.getAttribute('href');
                if (!url) return;

                document.querySelectorAll('.messenger-contact-item').forEach(el => el.classList.remove('active'));
                this.classList.add('active');

                // Remove unread dot if present
                const dot = this.querySelector('.contact-unread-dot');
                if (dot) dot.remove();

                const mainPane = document.getElementById('messenger-main-pane');
                if (!mainPane) return;

                fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(res => {
                        if (!res.ok) throw new Error("HTTP " + res.status);
                        return res.text();
                    })
                    .then(html => {
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const newPane = doc.getElementById('messenger-main-pane');
                        if (newPane) {
                            mainPane.innerHTML = newPane.innerHTML;
                            mainPane.setAttribute('data-other-user-id', newPane.getAttribute('data-other-user-id') || '');
                            window.history.pushState({ url: url }, '', url);
                            bindChatSession();
                        } else {
                            window.location.href = url;
                        }
                    })
                    .catch(err => {
                        console.error("Error loading chat conversation:", err);
                        window.location.href = url;
                    });
            };
        });
    }

    attachContactItemHandlers();
    bindChatSession();

    window.addEventListener('popstate', () => {
        window.location.reload();
    });
});
