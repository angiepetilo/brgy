/*
 * Official Print Document & Letter Customization Controller
 * Strictly CSP-compliant: external JS file, no inline scripts or handlers.
 */
document.addEventListener('DOMContentLoaded', function() {
    var toggleBtn = document.getElementById('btn-toggle-customize');
    var cancelBtn = document.getElementById('btn-cancel-customize');
    var container = document.getElementById('customize-container');
    var resetBtn = document.getElementById('btn-reset-template');
    var form = document.getElementById('custom-letter-form');

    var printButtons = document.querySelectorAll('#btn-do-print, [data-action="print"]');
    printButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            window.print();
        });
    });

    if (toggleBtn && container) {
        toggleBtn.addEventListener('click', function() {
            var isHidden = (container.style.display === 'none' || container.style.display === '');
            container.style.display = isHidden ? 'block' : 'none';
            if (isHidden) {
                var textarea = document.getElementById('custom-body-textarea');
                if (textarea) {
                    textarea.focus();
                }
            }
        });
    }

    if (cancelBtn && container) {
        cancelBtn.addEventListener('click', function() {
            container.style.display = 'none';
        });
    }

    // Track active/focused input in customization form
    var lastFocusedCustomInput = null;
    var customInputIds = ['custom-header-input', 'custom-title-input', 'custom-body-textarea', 'custom-footer-input'];
    document.addEventListener('focusin', function(e) {
        if (e.target && customInputIds.indexOf(e.target.id) !== -1) {
            lastFocusedCustomInput = e.target;
        }
    });

    // Tag pills click handler for print document customization
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.doc-tag-insert-btn');
        if (!btn) { return; }
        e.preventDefault();
        var tag = btn.getAttribute('data-tag');
        var targetInput = lastFocusedCustomInput || document.getElementById('custom-body-textarea');
        if (!targetInput || !tag) { return; }
        var start = targetInput.selectionStart || 0;
        var end = targetInput.selectionEnd || 0;
        var val = targetInput.value;
        targetInput.value = val.substring(0, start) + tag + val.substring(end);
        targetInput.selectionStart = targetInput.selectionEnd = start + tag.length;
        targetInput.focus();
    });

    if (resetBtn && form) {
        resetBtn.addEventListener('click', function(e) {
            if (window.showConfirmModal) {
                e.preventDefault();
                window.showConfirmModal(
                    'Reset this document back to the original standard template? Any custom wording will be discarded.',
                    function() {
                        var hiddenAction = document.createElement('input');
                        hiddenAction.type = 'hidden';
                        hiddenAction.name = 'action';
                        hiddenAction.value = 'reset';
                        form.appendChild(hiddenAction);
                        form.submit();
                    }
                );
            }
        });
    }
});

