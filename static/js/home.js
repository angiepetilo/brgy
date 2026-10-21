// Home feed interactions (toggle comments, alert dismiss, etc.)
function toggleComments(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        const isHidden = el.style.display === 'none' || window.getComputedStyle(el).display === 'none';
        if (isHidden) {
            el.style.display = 'block';
            const input = el.querySelector('.comment-input');
            if (input) input.focus();
        } else {
            el.style.display = 'none';
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Welcome Toast Notification Auto-disappear & Dismissal
    var banner = document.getElementById('adminWelcomeBanner');
    var dismissBtn = document.getElementById('dismissWelcomeBannerBtn');

    if (banner) {
        try {
            if (sessionStorage.getItem('admin_welcome_dismissed') === 'true') {
                banner.remove();
                return;
            }
        } catch (e) {}

        var isDismissed = false;
        function dismissToast() {
            if (isDismissed || !banner) return;
            isDismissed = true;
            banner.classList.add('toast-dismissing');
            try {
                sessionStorage.setItem('admin_welcome_dismissed', 'true');
            } catch (e) {}
            setTimeout(function () {
                if (banner && banner.parentElement) {
                    banner.remove();
                }
            }, 350);
        }

        // Standard toast auto-dismiss (4.5 seconds)
        var autoTimer = setTimeout(dismissToast, 4500);

        if (dismissBtn) {
            dismissBtn.addEventListener('click', function (e) {
                e.preventDefault();
                clearTimeout(autoTimer);
                dismissToast();
            });
        }
    }
});

document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-toggle-comments]');
    if (btn) {
        toggleComments(btn.getAttribute('data-toggle-comments'));
    }
});
