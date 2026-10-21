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

    // 3. Auto dismiss flash toasts and alerts after standard duration (4.5s)
    const toasts = document.querySelectorAll('.app-toast, .alert');
    toasts.forEach(toast => {
        if (toast.id === 'adminWelcomeBanner') return; // Handled specifically in home.js
        const duration = parseInt(toast.getAttribute('data-toast-auto-dismiss') || '4500', 10);
        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.add('toast-dismissing');
                toast.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                setTimeout(() => {
                    if (toast.parentElement) toast.remove();
                }, 350);
            }
        }, duration);
    });

    // 4. Smooth Sidebar Collapse / Expand Toggle
    const leftSidebar = document.getElementById('fb-left-sidebar');
    const mainContainer = document.getElementById('fb-main-container');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn') || document.getElementById('sidebar-collapse-btn');

    function applySidebarState(isCollapsed) {
        if (isCollapsed) {
            document.body.classList.add('sidebar-collapsed');
            if (leftSidebar) leftSidebar.classList.add('collapsed');
            if (mainContainer) mainContainer.classList.add('sidebar-collapsed');
        } else {
            document.body.classList.remove('sidebar-collapsed');
            if (leftSidebar) leftSidebar.classList.remove('collapsed');
            if (mainContainer) mainContainer.classList.remove('sidebar-collapsed');
        }
    }

    try {
        const savedState = localStorage.getItem('fb_sidebar_collapsed');
        if (savedState === 'true') {
            applySidebarState(true);
        }
    } catch (e) {}

    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const shouldCollapse = !document.body.classList.contains('sidebar-collapsed');
            applySidebarState(shouldCollapse);
            try {
                localStorage.setItem('fb_sidebar_collapsed', shouldCollapse ? 'true' : 'false');
            } catch (err) {}
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
                            newComment.style.cssText = 'padding: 0.65rem 0.85rem; background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px;';
                            newComment.innerHTML = `
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <span style="font-weight: 700; font-size: 0.75rem; color: #1F2937; background: #E5E7EB; padding: 2px 5px; border-radius: 4px;">
                                            ${data.initials || 'RD'}
                                        </span>
                                        <span style="font-weight: 700; font-size: 0.8125rem; color: #111827;">
                                            ${escapeHtml(data.author)}
                                        </span>
                                    </div>
                                    <span style="font-size: 0.7rem; color: #6B7280;">
                                        ${data.created_at}
                                    </span>
                                </div>
                                <div style="font-size: 0.8125rem; color: #374151; line-height: 1.4;">
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

// ==========================================
// Global In-App Confirmation Modal Dialog
// (Replaces native browser window.confirm / localhost popup)
// ==========================================
(function () {
    'use strict';

    var activeConfirm = null;
    var modalBackdrop = null;
    var titleEl, messageEl, iconBoxEl, cancelBtn, confirmBtn;

    function getIconSvg(name) {
        if (window.BrgyUI && typeof window.BrgyUI.icon === 'function') {
            return window.BrgyUI.icon(name);
        }
        var sprite = (document.body && document.body.dataset && document.body.dataset.iconSprite) || '/static/vendor/lucide/sprite.svg';
        return '<svg class="icon icon-' + name + '" width="22" height="22" aria-hidden="true"><use href="' + sprite + '#lucide-' + name + '"></use></svg>';
    }

    function initModal() {
        if (modalBackdrop) return true;
        modalBackdrop = document.getElementById('app-confirm-modal');
        if (!modalBackdrop) return false;

        titleEl = document.getElementById('app-confirm-title');
        messageEl = document.getElementById('app-confirm-message');
        iconBoxEl = document.getElementById('app-confirm-icon-box');
        cancelBtn = document.getElementById('app-confirm-btn-cancel');
        confirmBtn = document.getElementById('app-confirm-btn-confirm');

        cancelBtn.addEventListener('click', function () {
            closeModal(false);
        });

        confirmBtn.addEventListener('click', function () {
            closeModal(true);
        });

        modalBackdrop.addEventListener('click', function (e) {
            if (e.target === modalBackdrop) {
                closeModal(false);
            }
        });

        document.addEventListener('keydown', function (e) {
            if (!modalBackdrop || modalBackdrop.style.display === 'none') return;
            if (e.key === 'Escape' || e.key === 'Esc') {
                e.preventDefault();
                closeModal(false);
            } else if (e.key === 'Enter') {
                if (document.activeElement === cancelBtn) {
                    e.preventDefault();
                    closeModal(false);
                } else {
                    e.preventDefault();
                    closeModal(true);
                }
            }
        });

        return true;
    }

    function closeModal(confirmed) {
        if (!modalBackdrop) return;
        modalBackdrop.style.display = 'none';
        modalBackdrop.classList.remove('is-active');
        if (activeConfirm) {
            var cb = confirmed ? activeConfirm.onConfirm : activeConfirm.onCancel;
            activeConfirm = null;
            if (typeof cb === 'function') {
                cb();
            }
        }
    }

    window.showConfirmModal = function (opts) {
        if (!initModal()) {
            var fallbackMsg = (typeof opts === 'string' ? opts : (opts && opts.message)) || 'Are you sure?';
            if (window.confirm(fallbackMsg)) {
                if (opts && typeof opts.onConfirm === 'function') opts.onConfirm();
            } else {
                if (opts && typeof opts.onCancel === 'function') opts.onCancel();
            }
            return;
        }

        if (typeof opts === 'string') {
            opts = { message: opts };
        }
        opts = opts || {};
        var message = opts.message || 'Are you sure you want to proceed?';
        var lowerMsg = message.toLowerCase();

        var variant = opts.variant;
        var iconName = 'circle-alert';
        var title = opts.title || 'Confirm Action';

        if (!variant) {
            if (lowerMsg.indexOf('delete') !== -1 || lowerMsg.indexOf('reject') !== -1 || lowerMsg.indexOf('disable') !== -1 || lowerMsg.indexOf('discard') !== -1 || lowerMsg.indexOf('remove') !== -1 || lowerMsg.indexOf('no-show') !== -1) {
                variant = 'danger';
                iconName = 'triangle-alert';
                if (!opts.title) title = 'Confirm Action';
            } else if (lowerMsg.indexOf('complete') !== -1 || lowerMsg.indexOf('approve') !== -1 || lowerMsg.indexOf('issue') !== -1) {
                variant = 'success';
                iconName = 'circle-check';
                if (!opts.title) title = 'Confirm Action';
            } else {
                variant = 'primary';
                iconName = 'circle-alert';
            }
        }

        iconBoxEl.className = 'app-confirm-icon-box variant-' + variant;
        iconBoxEl.innerHTML = getIconSvg(iconName);

        titleEl.textContent = title;
        messageEl.textContent = message;

        cancelBtn.textContent = opts.cancelText || 'Cancel';
        confirmBtn.textContent = opts.confirmText || (variant === 'danger' ? 'Proceed' : (variant === 'success' ? 'Confirm' : 'OK'));
        confirmBtn.className = 'app-confirm-btn app-confirm-btn-confirm variant-' + variant;

        activeConfirm = opts;
        modalBackdrop.style.display = 'flex';
        void modalBackdrop.offsetWidth;
        modalBackdrop.classList.add('is-active');

        setTimeout(function () {
            if (confirmBtn) confirmBtn.focus();
        }, 50);
    };

    window.confirmModal = function (message, opts) {
        return new Promise(function (resolve) {
            var options = typeof opts === 'object' ? Object.assign({}, opts) : {};
            options.message = message;
            options.onConfirm = function () { resolve(true); };
            options.onCancel = function () { resolve(false); };
            window.showConfirmModal(options);
        });
    };
})();

// ==========================================
// Delegated page actions (CSP: no inline handlers in templates)
//   data-confirm="Message"   on a button/link (click) or a <form> (submit)
//   data-action="dismiss"    removes the closest [data-dismiss-target] or the parent element
//   data-action="print" | "back" | "reload"
//   data-action="scroll-to"  data-target="#id"
//   data-action="click-target" data-target="#id"  (e.g. open a hidden file input)
//   data-auto-submit         on a <select>/<input>: submit its form on change
// ==========================================
(function () {
    document.addEventListener('click', function (event) {
        // 1. Direct [data-confirm] or [data-confirm-button] on clicked element or parent
        var confirmEl = event.target.closest('[data-confirm], [data-confirm-button]');
        if (confirmEl && confirmEl.tagName !== 'FORM') {
            if (confirmEl.__isConfirmed) {
                confirmEl.__isConfirmed = false;
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();

            var message = confirmEl.getAttribute('data-confirm') || confirmEl.getAttribute('data-confirm-button');
            window.showConfirmModal({
                message: message,
                onConfirm: function () {
                    confirmEl.__isConfirmed = true;
                    if (confirmEl.form) {
                        confirmEl.form.__isConfirmed = true;
                    }
                    if (confirmEl.tagName === 'A' && confirmEl.href) {
                        window.location.assign(confirmEl.href);
                    } else if (confirmEl.type === 'submit' && confirmEl.form) {
                        if (typeof confirmEl.form.requestSubmit === 'function') {
                            confirmEl.form.requestSubmit(confirmEl);
                        } else {
                            confirmEl.form.submit();
                        }
                    } else {
                        confirmEl.click();
                    }
                }
            });
            return;
        }

        // 2. Submit button clicked inside a form[data-confirm]
        var submitBtn = event.target.closest('button, input[type="submit"]');
        if (submitBtn && submitBtn.form && submitBtn.form.hasAttribute('data-confirm')) {
            var parentForm = submitBtn.form;
            if (parentForm.__isConfirmed) {
                parentForm.__isConfirmed = false;
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();

            var formMsg = parentForm.getAttribute('data-confirm');
            window.showConfirmModal({
                message: formMsg,
                onConfirm: function () {
                    parentForm.__isConfirmed = true;
                    if (typeof parentForm.requestSubmit === 'function') {
                        parentForm.requestSubmit(submitBtn);
                    } else {
                        parentForm.submit();
                    }
                }
            });
            return;
        }

        var actionEl = event.target.closest('[data-action]');
        if (!actionEl) return;
        var action = actionEl.getAttribute('data-action');
        var targetSel = actionEl.getAttribute('data-target');
        switch (action) {
            case 'dismiss': {
                event.preventDefault();
                var box = actionEl.closest('[data-dismiss-target]') || actionEl.closest('.app-toast') || actionEl.parentElement;
                if (box) {
                    box.classList.add('toast-dismissing');
                    box.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    box.style.opacity = '0';
                    box.style.transform = 'translateX(40px)';
                    setTimeout(function() {
                        if (box.parentElement) box.remove();
                    }, 300);
                }
                break;
            }
            case 'print':
                event.preventDefault();
                window.print();
                break;
            case 'back':
                event.preventDefault();
                if (window.history.length > 1) {
                    window.history.back();
                } else {
                    window.location.assign('/');
                }
                break;
            case 'reload':
                event.preventDefault();
                window.location.reload();
                break;
            case 'scroll-to': {
                event.preventDefault();
                var target = targetSel && document.querySelector(targetSel);
                if (target) target.scrollIntoView({ behavior: 'smooth' });
                break;
            }
            case 'click-target': {
                event.preventDefault();
                var clickTarget = targetSel && document.querySelector(targetSel);
                if (clickTarget) clickTarget.click();
                break;
            }
            default:
                break;
        }
    });

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (form && form.hasAttribute && form.hasAttribute('data-confirm')) {
            if (form.__isConfirmed) {
                form.__isConfirmed = false;
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();

            var submitter = event.submitter;
            var message = form.getAttribute('data-confirm');
            window.showConfirmModal({
                message: message,
                onConfirm: function () {
                    form.__isConfirmed = true;
                    if (typeof form.requestSubmit === 'function') {
                        if (submitter) {
                            form.requestSubmit(submitter);
                        } else {
                            form.requestSubmit();
                        }
                    } else {
                        form.submit();
                    }
                }
            });
        }
    }, true);

    document.addEventListener('change', function (event) {
        var el = event.target;
        if (el && el.id === 'inv-category-filter' && el.value) {
            window.location.href = el.value;
            return;
        }
        if (el && el.hasAttribute && el.hasAttribute('data-auto-submit') && el.form) {
            if (typeof el.form.requestSubmit === 'function') {
                el.form.requestSubmit();
            } else {
                el.form.submit();
            }
        }
    });

    // Global 4-digit year constraint for date inputs
    document.addEventListener('input', function (event) {
        var el = event.target;
        if (el && el.type === 'date' && el.value) {
            var parts = el.value.split('-');
            if (parts[0] && parts[0].length > 4) {
                parts[0] = parts[0].slice(0, 4);
                el.value = parts.join('-');
            }
        }
    });

    document.addEventListener('focusin', function (event) {
        var el = event.target;
        if (el && el.type === 'date') {
            if (!el.getAttribute('min')) el.setAttribute('min', '1900-01-01');
            if (!el.getAttribute('max')) el.setAttribute('max', '9999-12-31');
        }
    });

    // Topbar Accessibility Font Switcher
    function initTopbarFontSwitcher() {
        var btnNormal = document.getElementById('btn-topbar-font-normal');
        var btnLarge = document.getElementById('btn-topbar-font-large');
        if (!btnNormal && !btnLarge) return;

        function applyFontSize(size) {
            if (size === 'large') {
                document.body.setAttribute('data-font-size', 'large');
                if (btnLarge) {
                    btnLarge.classList.add('active');
                    btnLarge.setAttribute('aria-pressed', 'true');
                }
                if (btnNormal) {
                    btnNormal.classList.remove('active');
                    btnNormal.setAttribute('aria-pressed', 'false');
                }
                try { localStorage.setItem('reg_font_size', 'large'); } catch (e) {}
            } else {
                document.body.removeAttribute('data-font-size');
                if (btnNormal) {
                    btnNormal.classList.add('active');
                    btnNormal.setAttribute('aria-pressed', 'true');
                }
                if (btnLarge) {
                    btnLarge.classList.remove('active');
                    btnLarge.setAttribute('aria-pressed', 'false');
                }
                try { localStorage.setItem('reg_font_size', 'normal'); } catch (e) {}
            }
        }

        try {
            if (localStorage.getItem('reg_font_size') === 'large') {
                applyFontSize('large');
            }
        } catch (e) {}

        if (btnNormal) {
            btnNormal.addEventListener('click', function () {
                applyFontSize('normal');
            });
        }
        if (btnLarge) {
            btnLarge.addEventListener('click', function () {
                applyFontSize('large');
            });
        }
    }
    initTopbarFontSwitcher();

    // Sidebar dynamic scrollbar: reveals scrollbar when user actively scrolls up/down
    function initSidebarScrollObserver() {
        var sidebarNav = document.querySelector('.hig-sidebar-nav');
        if (!sidebarNav) return;

        var scrollTimeout = null;
        sidebarNav.addEventListener('scroll', function () {
            sidebarNav.classList.add('is-scrolling');
            if (scrollTimeout) {
                clearTimeout(scrollTimeout);
            }
            scrollTimeout = setTimeout(function () {
                sidebarNav.classList.remove('is-scrolling');
            }, 800);
        }, { passive: true });
    }
    initSidebarScrollObserver();

    // Modal dynamic scrollbar: reveals scrollbar when user actively scrolls up/down in ANY modal
    function initModalScrollObserver() {
        var scrollTimeouts = new WeakMap();

        document.addEventListener('scroll', function (event) {
            var target = event.target;
            if (!target || target === document || target === window || typeof target.closest !== 'function') {
                return;
            }

            var isModalScroll = target.matches('.modal-scrollable, .reg-wizard-modal-scroll, .wizard-body, .wizard-container') ||
                                target.closest('.modal-overlay, [role="dialog"], .modal-dialog, .modal');

            if (!isModalScroll) return;

            if (target.scrollHeight > target.clientHeight) {
                target.classList.add('is-scrolling');
                var existingTimeout = scrollTimeouts.get(target);
                if (existingTimeout) {
                    clearTimeout(existingTimeout);
                }
                var timeoutId = setTimeout(function () {
                    target.classList.remove('is-scrolling');
                    scrollTimeouts.delete(target);
                }, 800);
                scrollTimeouts.set(target, timeoutId);
            }
        }, { passive: true, capture: true });
    }
    initModalScrollObserver();
})();
