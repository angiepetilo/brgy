/**
 * Philippine mobile number inputs (input[data-phone]).
 * Keeps only digits and at most 11 of them while typing or pasting, and shows
 * the browser's validation message when the value is not 09XXXXXXXXX.
 * The server validates again (apps.core.validators.validate_ph_mobile).
 */
(function () {
    'use strict';

    var PH_MOBILE = /^09\d{9}$/;
    var MESSAGE = 'Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567).';

    function clean(input) {
        var digits = input.value.replace(/\D/g, '').slice(0, 11);
        if (digits !== input.value) {
            input.value = digits;
        }
        if (!digits || PH_MOBILE.test(digits)) {
            input.setCustomValidity('');
        } else {
            input.setCustomValidity(MESSAGE);
        }
        var feedbackId = input.getAttribute('data-phone-feedback');
        var feedback = feedbackId ? document.getElementById(feedbackId) : null;
        if (feedback) {
            if (!digits) {
                feedback.textContent = 'Required: 11 digits starting with 09.';
                feedback.style.color = '#6B7280';
            } else if (PH_MOBILE.test(digits)) {
                feedback.textContent = 'Valid mobile number.';
                feedback.style.color = '#111827';
            } else {
                feedback.textContent = digits.length + ' of 11 digits. Must start with 09.';
                feedback.style.color = '#DC2626';
            }
        }
    }

    document.addEventListener('input', function (event) {
        var el = event.target;
        if (el && el.matches && el.matches('input[data-phone]')) {
            clean(el);
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('input[data-phone]').forEach(function (input) {
            if (input.value) clean(input);
        });
    });

    window.BrgyPhoneInput = { clean: clean, isValid: function (v) { return PH_MOBILE.test(v || ''); } };
})();
