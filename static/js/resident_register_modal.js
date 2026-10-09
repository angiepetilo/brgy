/*
 * Staff "Register Resident" modal (templates/accounts/residents_tabbed.html).
 * One delegated listener; no inline handlers. Opens on [data-action="open-register-resident"],
 * closes on [data-action="close-register-resident"], backdrop click or Escape, and returns
 * focus to the button that opened it.
 */
(function () {
    'use strict';

    var modal = null;
    var opener = null;

    function getModal() {
        if (!modal) {
            modal = document.getElementById('registerResidentModal');
        }
        return modal;
    }

    function openModal(trigger) {
        var el = getModal();
        if (!el) { return; }
        opener = trigger;
        el.style.display = 'flex';
        var first = el.querySelector('input, select, textarea');
        if (first) { first.focus(); }
    }

    function closeModal() {
        var el = getModal();
        if (!el || el.style.display === 'none') { return; }
        el.style.display = 'none';
        if (opener && typeof opener.focus === 'function') { opener.focus(); }
        opener = null;
    }

    document.addEventListener('click', function (event) {
        var target = event.target;
        var opens = target.closest('[data-action="open-register-resident"]');
        if (opens) {
            openModal(opens);
            return;
        }
        if (target.closest('[data-action="close-register-resident"]') || target === getModal()) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') { closeModal(); }
    });
})();
