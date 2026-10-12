/*
 * Officers Permissions modal behaviors (CSP-compliant, external script).
 */
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('createOfficerModal');
    const openBtn = document.getElementById('btn-create-officer');
    const closeBtn = document.getElementById('closeCreateOfficerModal');
    const cancelBtn = document.getElementById('cancelCreateOfficerModal');
    const form = document.getElementById('createOfficerForm');

    if (!modal) return;

    let isDirty = false;
    if (form) {
        form.querySelectorAll('input, select').forEach(function(el) {
            el.addEventListener('input', function() { isDirty = true; });
            el.addEventListener('change', function() { isDirty = true; });
        });
    }

    function tryCloseModal() {
        function doClose() {
            modal.style.display = 'none';
            if (form) form.reset();
            isDirty = false;
        }
        if (isDirty) {
            if (typeof window.showConfirmModal === 'function') {
                window.showConfirmModal({
                    title: 'Discard Changes?',
                    message: 'You have unsaved changes. Are you sure you want to discard them?',
                    variant: 'danger',
                    confirmText: 'Discard',
                    cancelText: 'Keep Editing',
                    onConfirm: doClose
                });
                return;
            } else if (!confirm('You have unsaved changes. Are you sure you want to discard them?')) {
                return;
            }
        }
        doClose();
    }

    if (openBtn) {
        openBtn.addEventListener('click', function() {
            modal.style.display = 'flex';
            isDirty = false;
        });
    }

    document.querySelectorAll('.btn-open-create-officer').forEach(function(btn) {
        btn.addEventListener('click', function() {
            modal.style.display = 'flex';
            isDirty = false;
        });
    });

    if (closeBtn) closeBtn.addEventListener('click', tryCloseModal);
    if (cancelBtn) cancelBtn.addEventListener('click', tryCloseModal);

    modal.addEventListener('click', function(e) {
        if (e.target === modal) tryCloseModal();
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            tryCloseModal();
        }
    });

    if (form) {
        form.addEventListener('submit', function() {
            isDirty = false;
        });
    }
});
