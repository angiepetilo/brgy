// ==========================================
// Barangay System Main JavaScript
// Mobile-First Architecture & Drawer Controls
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // 1. Quick-Access Slide-Over Drawer Controls
    const drawerBtn = document.getElementById('drawer-menu-btn');
    const drawer = document.getElementById('slide-drawer');
    const backdrop = document.getElementById('drawer-backdrop');
    const closeBtn = document.getElementById('drawer-close-btn');

    function openDrawer() {
        if (drawer) drawer.classList.add('active');
        if (backdrop) backdrop.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeDrawer() {
        if (drawer) drawer.classList.remove('active');
        if (backdrop) backdrop.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (drawerBtn) {
        drawerBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            openDrawer();
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeDrawer();
        });
    }

    if (backdrop) {
        backdrop.addEventListener('click', closeDrawer);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawer && drawer.classList.contains('active')) {
            closeDrawer();
        }
    });

    // 2. Notification "Mark as Read" Inline Actions in Drawer
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const markReadButtons = document.querySelectorAll('.mark-read-btn');
    markReadButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const notifId = btn.getAttribute('data-notif-id');
            if (!notifId) return;

            try {
                const csrfToken = getCookie('csrftoken');
                const response = await fetch(`/chat/notifications/${notifId}/read/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.ok) {
                    const row = document.getElementById(`notif-row-${notifId}`);
                    if (row) {
                        row.style.opacity = '0.5';
                        btn.textContent = 'DONE';
                        btn.disabled = true;
                    }
                }
            } catch (err) {
                console.error('Failed to mark notification as read:', err);
            }
        });
    });

    // 3. Auto dismiss flash alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentElement) {
                alert.style.transition = 'opacity 0.4s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 400);
            }
        }, 5000);
    });

    // 4. Facebook-Style Left Sidebar Collapse Controls
    const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
    const leftSidebar = document.getElementById('fb-left-sidebar');
    const mainContainer = document.getElementById('fb-main-container');

    function setSidebarState(collapsed) {
        if (!leftSidebar || !mainContainer) return;
        if (collapsed) {
            leftSidebar.classList.add('collapsed');
            mainContainer.classList.add('sidebar-collapsed');
            localStorage.setItem('fb_sidebar_collapsed', '1');
        } else {
            leftSidebar.classList.remove('collapsed');
            mainContainer.classList.remove('sidebar-collapsed');
            localStorage.setItem('fb_sidebar_collapsed', '0');
        }
    }

    if (sidebarCollapseBtn && leftSidebar && mainContainer) {
        // Initialize from saved state on wide viewports
        if (window.innerWidth >= 1024 && localStorage.getItem('fb_sidebar_collapsed') === '1') {
            setSidebarState(true);
        }

        sidebarCollapseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isCurrentlyCollapsed = leftSidebar.classList.contains('collapsed');
            setSidebarState(!isCurrentlyCollapsed);
        });
    }

    // 5. Facebook-Style Live Reactions (Instant Flat Counters)
    const reactionForms = document.querySelectorAll('.feed-reaction-form');
    reactionForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const postId = form.getAttribute('data-post-id');
            const reactionType = form.getAttribute('data-type');
            const submitBtn = form.querySelector('button[type="submit"]');
            const url = form.getAttribute('action');
            const csrfToken = getCookie('csrftoken');

            try {
                const formData = new FormData(form);
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'ok') {
                        const postCard = document.getElementById(`post-${postId}`);
                        if (postCard) {
                            const likeCounter = postCard.querySelector('.like-counter');
                            const supportCounter = postCard.querySelector('.support-counter');
                            const importantCounter = postCard.querySelector('.important-counter');
                            if (likeCounter) likeCounter.textContent = data.likes_count;
                            if (supportCounter) supportCounter.textContent = data.supports_count;
                            if (importantCounter) importantCounter.textContent = data.importants_count;

                            const allReactionBtns = postCard.querySelectorAll('.feed-reaction-form button');
                            allReactionBtns.forEach(btn => {
                                btn.classList.remove('btn-primary', 'btn-danger');
                                btn.classList.add('btn-secondary');
                            });

                            if (data.user_has_reacted) {
                                if (data.reaction_type === 'important') {
                                    submitBtn.classList.remove('btn-secondary');
                                    submitBtn.classList.add('btn-danger');
                                } else {
                                    submitBtn.classList.remove('btn-secondary');
                                    submitBtn.classList.add('btn-primary');
                                }
                            }
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to submit reaction:', err);
            }
        });
    });

    // 6. Facebook-Style Live Comments (Instant Live Posting)
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    const commentForms = document.querySelectorAll('.feed-comment-form');
    commentForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const postId = form.getAttribute('data-post-id');
            const input = form.querySelector('.comment-input');
            const content = input ? input.value.trim() : '';
            if (!content) return;

            const url = form.getAttribute('action');
            const csrfToken = getCookie('csrftoken');

            try {
                const formData = new FormData(form);
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'ok') {
                        const list = document.getElementById(`comments-list-${postId}`);
                        if (list) {
                            const hint = list.querySelector('.empty-comments-hint');
                            if (hint) hint.remove();

                            const newComment = document.createElement('div');
                            newComment.className = 'comment-item';
                            newComment.style.cssText = 'padding: 0.65rem 0.75rem; background: #F8FAFC; border: 1px solid #E2E8F0;';
                            newComment.innerHTML = `
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <span style="font-weight: 700; font-size: 0.75rem; color: #1B2430; background: #E2E8F0; padding: 2px 5px;">
                                            [${data.initials || 'RD'}]
                                        </span>
                                        <span style="font-weight: 700; font-size: 0.8125rem; color: #0F172A;">
                                            ${escapeHtml(data.author)}
                                        </span>
                                    </div>
                                    <span style="font-size: 0.7rem; color: #94A3B8;">
                                        ${data.created_at}
                                    </span>
                                </div>
                                <div style="font-size: 0.8125rem; color: #334155; line-height: 1.4;">
                                    ${escapeHtml(data.content)}
                                </div>
                            `;
                            list.appendChild(newComment);
                        }

                        const counter = document.querySelector(`.comments-counter-${postId}`);
                        if (counter) {
                            const current = parseInt(counter.textContent) || 0;
                            counter.textContent = current + 1;
                        }

                        if (input) input.value = '';
                    }
                }
            } catch (err) {
                console.error('Failed to post comment:', err);
            }
        });
    });

    // 6. Facebook-Style Topbar Floating Action Dropdowns
    const messagesToggle = document.getElementById('fb-messages-toggle');
    const notifsToggle = document.getElementById('fb-notifs-toggle');
    const profileToggle = document.getElementById('fb-profile-toggle');

    const messagesDropdown = document.getElementById('fb-dropdown-messages');
    const notifsDropdown = document.getElementById('fb-dropdown-notifications');
    const profileDropdown = document.getElementById('fb-dropdown-profile');

    const allDropdowns = [messagesDropdown, notifsDropdown, profileDropdown].filter(Boolean);

    function closeAllDropdowns() {
        allDropdowns.forEach(dd => dd.classList.remove('show'));
    }

    function toggleDropdown(target) {
        if (!target) return;
        const isOpen = target.classList.contains('show');
        closeAllDropdowns();
        if (!isOpen) {
            target.classList.add('show');
        }
    }

    if (messagesToggle && messagesDropdown) {
        messagesToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(messagesDropdown);
        });
    }

    if (notifsToggle && notifsDropdown) {
        notifsToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(notifsDropdown);
        });
    }

    if (profileToggle && profileDropdown) {
        profileToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(profileDropdown);
        });
    }

    // Close when clicking outside
    document.addEventListener('click', (e) => {
        let insideDropdown = false;
        allDropdowns.forEach(dd => {
            if (dd.contains(e.target)) insideDropdown = true;
        });
        if (
            (messagesToggle && messagesToggle.contains(e.target)) ||
            (notifsToggle && notifsToggle.contains(e.target)) ||
            (profileToggle && profileToggle.contains(e.target))
        ) {
            insideDropdown = true;
        }

        if (!insideDropdown) {
            closeAllDropdowns();
        }
    });

    // Chats filter tabs: All vs Unread
    const tabChatsAll = document.getElementById('btn-tab-chats-all');
    const tabChatsUnread = document.getElementById('btn-tab-chats-unread');
    const chatItems = document.querySelectorAll('.fb-chat-item');

    if (tabChatsAll && tabChatsUnread) {
        tabChatsAll.addEventListener('click', () => {
            tabChatsAll.classList.add('active');
            tabChatsUnread.classList.remove('active');
            chatItems.forEach(item => item.style.display = 'flex');
        });

        tabChatsUnread.addEventListener('click', () => {
            tabChatsUnread.classList.add('active');
            tabChatsAll.classList.remove('active');
            chatItems.forEach(item => {
                if (item.getAttribute('data-unread') === 'true') {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    // Search Messenger
    const searchMessengerInput = document.getElementById('fb-messenger-search-input');
    if (searchMessengerInput) {
        searchMessengerInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            chatItems.forEach(item => {
                const name = item.getAttribute('data-name') || '';
                if (!query || name.includes(query)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    // Notifications filter tabs: All vs Unread
    const tabNotifsAll = document.getElementById('btn-tab-notifs-all');
    const tabNotifsUnread = document.getElementById('btn-tab-notifs-unread');
    const notifItems = document.querySelectorAll('.fb-notif-item');
    const groupHeadings = document.querySelectorAll('#fb-notifs-list .fb-group-heading');

    if (tabNotifsAll && tabNotifsUnread) {
        tabNotifsAll.addEventListener('click', () => {
            tabNotifsAll.classList.add('active');
            tabNotifsUnread.classList.remove('active');
            notifItems.forEach(item => item.style.display = 'flex');
            groupHeadings.forEach(h => h.style.display = 'flex');
        });

        tabNotifsUnread.addEventListener('click', () => {
            tabNotifsUnread.classList.add('active');
            tabNotifsAll.classList.remove('active');
            notifItems.forEach(item => {
                if (item.getAttribute('data-unread') === 'true') {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
            groupHeadings.forEach(h => h.style.display = 'none');
        });
    }
});
