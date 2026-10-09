/*
 * Appointment detail page: the reject reason box.
 * Delegated listeners replace the old inline onclick handlers.
 *   <form data-confirm="...">          confirm dialog, handled globally by main.js
 *   [data-action="toggle-reject"]      shows the reject box and hides itself
 *   [data-action="cancel-reject"]      hides the reject box again
 */
(function () {
    'use strict';

    var BOX_ID = 'rejectReasonBox';

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-action]');
        if (!trigger) return;
        var box = document.getElementById(BOX_ID);
        var action = trigger.getAttribute('data-action');

        if (action === 'toggle-reject' && box) {
            box.style.display = 'block';
            trigger.style.display = 'none';
            var reason = box.querySelector('textarea');
            if (reason) reason.focus();
        } else if (action === 'cancel-reject' && box) {
            box.style.display = 'none';
            var toggle = document.querySelector('[data-action="toggle-reject"]');
            if (toggle) toggle.style.display = '';
        }
    });
})();
