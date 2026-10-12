/*
 * Staff "Register Resident" modal and "Data Privacy Notice" modal
 * (templates/accounts/residents_tabbed.html).
 * Delegated listeners; no inline handlers. CSP-compliant.
 */
(function () {
    'use strict';

    var regModal = null;
    var regOpener = null;
    var privacyModal = null;
    var privacyOpener = null;

    function getRegModal() {
        if (!regModal) {
            regModal = document.getElementById('registerResidentModal');
        }
        return regModal;
    }

    function getPrivacyModal() {
        if (!privacyModal) {
            privacyModal = document.getElementById('privacyNoticeModal');
        }
        return privacyModal;
    }

    function openRegModal(trigger) {
        var el = getRegModal();
        if (!el) { return; }
        regOpener = trigger;
        el.style.display = 'flex';
        var first = el.querySelector('input, select, textarea');
        if (first) { first.focus(); }
    }

    function closeRegModal() {
        var el = getRegModal();
        if (!el || el.style.display === 'none') { return; }
        el.style.display = 'none';
        if (regOpener && typeof regOpener.focus === 'function') { regOpener.focus(); }
        regOpener = null;
    }

    function openPrivacyModal(trigger) {
        var el = getPrivacyModal();
        if (!el) { return; }
        privacyOpener = trigger;
        el.style.display = 'flex';
        var dismissBtn = el.querySelector('#dismissPrivacyNoticeModalBtn, [data-action="close-privacy-notice"]');
        if (dismissBtn) { dismissBtn.focus(); }
    }

    function closePrivacyModal() {
        var el = getPrivacyModal();
        if (!el || el.style.display === 'none') { return; }
        el.style.display = 'none';
        if (privacyOpener && typeof privacyOpener.focus === 'function') { privacyOpener.focus(); }
        privacyOpener = null;
    }

    document.addEventListener('click', function (event) {
        var target = event.target;

        // Privacy Modal triggers
        var openPrivacy = target.closest('[data-action="open-privacy-notice"]') || (target.tagName === 'A' && target.getAttribute('href') === '#privacy-notice');
        if (openPrivacy) {
            event.preventDefault();
            openPrivacyModal(openPrivacy);
            return;
        }

        if (target.closest('[data-action="close-privacy-notice"]') || target === getPrivacyModal()) {
            closePrivacyModal();
            return;
        }

        // Register Resident triggers
        var opens = target.closest('[data-action="open-register-resident"]');
        if (opens) {
            openRegModal(opens);
            return;
        }
        if (target.closest('[data-action="close-register-resident"]') || target === getRegModal()) {
            closeRegModal();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            var priv = getPrivacyModal();
            if (priv && priv.style.display !== 'none') {
                closePrivacyModal();
                return;
            }
            closeRegModal();
        }
    });
})();
