/**
 * Barangay.ph Sign-In Screen Controller
 * Handles password visibility toggle, accessibility font scaling, and submit states.
 * Adheres strictly to CSP (no inline scripts/handlers).
 */
document.addEventListener('DOMContentLoaded', function () {
    // Add page body class for CSS targeting
    document.body.classList.add('login-page-body');

    // --- Password Visibility Toggle ---
    var toggleBtn = document.getElementById('togglePasswordBtn');
    var passwordInput = document.getElementById('id_password');

    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', function () {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                toggleBtn.textContent = 'Hide';
                toggleBtn.setAttribute('aria-label', 'Hide password');
            } else {
                passwordInput.type = 'password';
                toggleBtn.textContent = 'Show';
                toggleBtn.setAttribute('aria-label', 'Show password');
            }
        });
    }

    // --- Accessibility Font Size Toggle (A / A) ---
    var btnFontNormal = document.getElementById('btn-font-normal');
    var btnFontLarge = document.getElementById('btn-font-large');
    var fullscreenRoot = document.getElementById('loginFullscreenRoot');

    function setFontSize(size) {
        if (size === 'large') {
            document.body.setAttribute('data-font-size', 'large');
            if (fullscreenRoot) fullscreenRoot.setAttribute('data-font-size', 'large');
            if (btnFontLarge) {
                btnFontLarge.classList.add('active');
                btnFontLarge.setAttribute('aria-pressed', 'true');
            }
            if (btnFontNormal) {
                btnFontNormal.classList.remove('active');
                btnFontNormal.setAttribute('aria-pressed', 'false');
            }
            try { localStorage.setItem('reg_font_size', 'large'); } catch (e) {}
        } else {
            document.body.removeAttribute('data-font-size');
            if (fullscreenRoot) fullscreenRoot.removeAttribute('data-font-size');
            if (btnFontNormal) {
                btnFontNormal.classList.add('active');
                btnFontNormal.setAttribute('aria-pressed', 'true');
            }
            if (btnFontLarge) {
                btnFontLarge.classList.remove('active');
                btnFontLarge.setAttribute('aria-pressed', 'false');
            }
            try { localStorage.setItem('reg_font_size', 'normal'); } catch (e) {}
        }
    }

    try {
        var savedSize = localStorage.getItem('reg_font_size');
        if (savedSize === 'large') {
            setFontSize('large');
        }
    } catch (e) {}

    if (btnFontNormal) {
        btnFontNormal.addEventListener('click', function () {
            setFontSize('normal');
        });
    }

    if (btnFontLarge) {
        btnFontLarge.addEventListener('click', function () {
            setFontSize('large');
        });
    }

    // --- Submit Button Feedback ---
    var loginForm = document.querySelector('.login-form');
    var submitBtn = document.getElementById('loginSubmitBtn');
    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', function () {
            var username = document.getElementById('id_username');
            var password = document.getElementById('id_password');
            if (username && username.value && password && password.value) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Signing in...';
            }
        });
    }
});
