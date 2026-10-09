/**
 * Login Page Password Visibility Toggle
 * Compliant with CSP ('self' only).
 */
document.addEventListener('DOMContentLoaded', function () {
    var toggleBtn = document.getElementById('togglePasswordBtn');
    var passwordInput = document.getElementById('id_password');
    var eyeOpen = document.getElementById('eyeIconOpen');
    var eyeClosed = document.getElementById('eyeIconClosed');

    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', function () {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                if (eyeOpen) eyeOpen.style.display = 'none';
                if (eyeClosed) eyeClosed.style.display = 'inline-flex';
            } else {
                passwordInput.type = 'password';
                if (eyeOpen) eyeOpen.style.display = 'inline-flex';
                if (eyeClosed) eyeClosed.style.display = 'none';
            }
        });
    }
});
