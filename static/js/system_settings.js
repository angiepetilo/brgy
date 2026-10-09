/*
 * System Settings page behaviour (templates/accounts/system/system_dashboard.html).
 *
 * - Endpoints come from data-* attributes on #system-settings-config (no template tags here).
 * - One delegated click listener handles every data-action button.
 * - All text from the server is written with textContent / .value, never innerHTML.
 */
(function () {
    'use strict';

    var config = document.getElementById('system-settings-config');
    if (!config) { return; }

    var lastOpener = null;

    function url(key, replacement, placeholder) {
        var template = config.getAttribute('data-' + key) || '';
        if (replacement === undefined) { return template; }
        return template.replace(placeholder || '/0/', '/' + encodeURIComponent(replacement) + '/');
    }

    function byId(id) { return document.getElementById(id); }

    function setChecked(id, value) {
        var el = byId(id);
        if (el) { el.checked = value === true || value === '1'; }
    }

    function setValue(id, value) {
        var el = byId(id);
        if (el) { el.value = value == null ? '' : value; }
    }

    function sourceValue(elementId) {
        var el = elementId ? byId(elementId) : null;
        return el ? el.value : '';
    }

    // ----- Modal open / close -------------------------------------------------
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])';

    function openModal(id, opener) {
        var modal = byId(id);
        if (!modal) { return; }
        lastOpener = opener || document.activeElement;
        modal.style.display = 'flex';
        var first = modal.querySelector('input:not([type="hidden"]), select, textarea');
        if (first) { first.focus(); }
    }

    function closeModal(modal) {
        if (!modal) { return; }
        modal.style.display = 'none';
        if (lastOpener && typeof lastOpener.focus === 'function') { lastOpener.focus(); }
        lastOpener = null;
    }

    function openModalFromElement(modal) { return modal && modal.style.display === 'flex'; }

    function openedModal() {
        var modals = document.querySelectorAll('[data-modal]');
        for (var i = 0; i < modals.length; i++) {
            if (openModalFromElement(modals[i])) { return modals[i]; }
        }
        return null;
    }

    // ----- Form helpers -------------------------------------------------------
    function openForm(opts, opener) {
        var form = byId(opts.formId);
        if (!form) { return; }
        byId(opts.titleId).textContent = opts.title;
        form.setAttribute('action', opts.action);
        openModal(opts.modalId, opener);
    }

    function resetForm(formId) {
        var form = byId(formId);
        if (form) { form.reset(); }
    }

    var HANDLERS = {
        'close-modal': function (el) {
            closeModal(el.closest('[data-modal]'));
        },

        // Post categories
        'new-post-category': function (el) {
            resetForm('postCategoryForm');
            openForm({
                formId: 'postCategoryForm', modalId: 'postCategoryModal', titleId: 'cat-modal-title',
                title: 'New Post Category', action: url('post-category-create-url')
            }, el);
        },
        'edit-post-category': function (el) {
            var d = el.dataset;
            resetForm('postCategoryForm');
            setValue('cat-name-input', d.name);
            setValue('cat-order-input', d.order);
            setValue('cat-end-select', d.defaultEnd);
            setChecked('cat-expires-input', d.expires);
            setChecked('cat-notify-input', d.notify);
            setChecked('cat-active-input', d.active);
            openForm({
                formId: 'postCategoryForm', modalId: 'postCategoryModal', titleId: 'cat-modal-title',
                title: 'Edit Post Category: ' + d.name, action: url('post-category-edit-url', d.id)
            }, el);
        },

        // Document types
        'new-document-type': function (el) {
            resetForm('docTypeForm');
            openForm({
                formId: 'docTypeForm', modalId: 'docTypeModal', titleId: 'doc-modal-title',
                title: 'New Document Type', action: url('document-type-create-url')
            }, el);
        },
        'edit-document-type': function (el) {
            var d = el.dataset;
            resetForm('docTypeForm');
            setValue('doc-name-input', d.name);
            setValue('doc-code-input', d.code);
            setValue('doc-fee-input', d.fee);
            setValue('doc-order-input', d.order);
            setValue('doc-desc-input', sourceValue(d.descriptionSource));
            setValue('doc-req-input', sourceValue(d.requirementsSource).replace(/\s+$/, ''));
            setChecked('doc-active-input', d.active);
            openForm({
                formId: 'docTypeForm', modalId: 'docTypeModal', titleId: 'doc-modal-title',
                title: 'Edit Document Type: ' + d.name, action: url('document-type-edit-url', d.id)
            }, el);
        },

        // Health services
        'new-health-service': function (el) {
            resetForm('healthSvcForm');
            openForm({
                formId: 'healthSvcForm', modalId: 'healthSvcModal', titleId: 'hsvc-modal-title',
                title: 'New Health Care Service', action: url('health-service-create-url')
            }, el);
        },
        'edit-health-service': function (el) {
            var d = el.dataset;
            resetForm('healthSvcForm');
            setValue('hsvc-name-input', d.name);
            setValue('hsvc-desc-input', sourceValue(d.descriptionSource));
            setValue('hsvc-days-input', d.days);
            setValue('hsvc-time-input', d.time);
            setChecked('hsvc-free-input', d.free);
            setChecked('hsvc-active-input', d.active);
            openForm({
                formId: 'healthSvcForm', modalId: 'healthSvcModal', titleId: 'hsvc-modal-title',
                title: 'Edit Health Care Service: ' + d.name, action: url('health-service-edit-url', d.id)
            }, el);
        },

        // Concern categories
        'new-concern-category': function (el) {
            resetForm('concernCatForm');
            openForm({
                formId: 'concernCatForm', modalId: 'concernCatModal', titleId: 'ccat-modal-title',
                title: 'New Concern Category', action: url('concern-category-create-url')
            }, el);
        },
        'edit-concern-category': function (el) {
            var d = el.dataset;
            resetForm('concernCatForm');
            setValue('ccat-name-input', d.name);
            setValue('ccat-desc-input', sourceValue(d.descriptionSource));
            setValue('ccat-type-select', d.routingType);
            setValue('ccat-val-input', d.routingValue);
            setChecked('ccat-active-input', d.active);
            openForm({
                formId: 'concernCatForm', modalId: 'concernCatModal', titleId: 'ccat-modal-title',
                title: 'Edit Concern Category: ' + d.name, action: url('concern-category-edit-url', d.id)
            }, el);
        },

        // Staff
        'new-staff': function (el) {
            openModal('staffModal', el);
        },

        // Email templates
        'email-preview': function (el) { previewEmail(el.dataset.template, el); },
        'email-edit': function (el) { editEmail(el.dataset.template, el.dataset.title, el); }
    };

    // ----- Email templates (fetch JSON) ---------------------------------------
    function showStatus(message, isError) {
        var region = byId('email-status');
        if (!region) { return; }
        region.textContent = message;
        region.hidden = false;
        region.style.background = isError ? '#FFFFFF' : '#FFFFFF';
        region.style.border = '1px solid ' + (isError ? '#DC2626' : '#16A34A');
        region.style.color = isError ? '#DC2626' : '#111827';
    }

    function getJson(endpoint) {
        return fetch(endpoint, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                if (!response.ok && !data.error) { data.error = 'Request failed (' + response.status + ').'; }
                return data;
            });
        });
    }

    function previewEmail(name, opener) {
        getJson(url('email-preview-url', name, '/__name__/')).then(function (data) {
            if (data.error) { showStatus(data.error, true); return; }
            byId('ep-title').textContent = 'Template Preview: ' + data.template_name;
            byId('ep-subject').textContent = data.subject;
            byId('ep-body').textContent = data.body;
            openModal('emailPreviewModal', opener);
        }).catch(function () {
            showStatus('Could not load the preview. Check your connection and try again.', true);
        });
    }

    function editEmail(name, title, opener) {
        getJson(url('email-edit-url', name, '/__name__/')).then(function (data) {
            if (data.error) { showStatus(data.error, true); return; }
            byId('ee-title').textContent = 'Edit Template: ' + (title || data.template_name);
            byId('ee-filename').textContent = data.template_name;
            var hasSubject = data.has_subject !== false;
            byId('ee-subject-group').hidden = !hasSubject;
            byId('ee-subject').required = hasSubject;
            byId('ee-subject').value = hasSubject ? (data.subject || '') : '';
            byId('ee-body').value = data.body || '';
            byId('ee-error').hidden = true;
            byId('emailEditForm').setAttribute('data-template-name', name);
            openModal('emailEditModal', opener);
        }).catch(function () {
            showStatus('Could not load the template. Check your connection and try again.', true);
        });
    }

    function submitEmailEdit(form) {
        var name = form.getAttribute('data-template-name');
        var saveBtn = byId('ee-save-btn');
        var errorBox = byId('ee-error');
        var label = saveBtn.textContent;
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
        errorBox.hidden = true;

        var payload = new FormData();
        if (!byId('ee-subject-group').hidden) {
            payload.append('subject', byId('ee-subject').value);
        }
        payload.append('body', byId('ee-body').value);
        payload.append('csrfmiddlewaretoken', form.querySelector('[name=csrfmiddlewaretoken]').value);

        fetch(url('email-edit-url', name, '/__name__/'), {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: payload
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                if (!response.ok && !data.error) { data.error = 'Request failed (' + response.status + ').'; }
                return data;
            });
        }).then(function (data) {
            if (data.error) {
                errorBox.textContent = data.error;
                errorBox.hidden = false;
                return;
            }
            closeModal(byId('emailEditModal'));
            showStatus('Template updated successfully.', false);
        }).catch(function () {
            errorBox.textContent = 'Could not save the template. Check your connection and try again.';
            errorBox.hidden = false;
        }).then(function () {
            saveBtn.disabled = false;
            saveBtn.textContent = label;
        });
    }

    // ----- Delegated listeners ------------------------------------------------
    document.addEventListener('click', function (event) {
        var actionEl = event.target.closest('[data-action]');
        if (actionEl && HANDLERS[actionEl.getAttribute('data-action')]) {
            event.preventDefault();
            HANDLERS[actionEl.getAttribute('data-action')](actionEl);
            return;
        }
        // Backdrop click closes the modal (only when the backdrop itself is the target).
        if (event.target.hasAttribute && event.target.hasAttribute('data-modal')) {
            closeModal(event.target);
        }
    });

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (form.id === 'emailEditForm') {
            event.preventDefault();
            submitEmailEdit(form);
        }
        // <form data-confirm="..."> dialogs are handled globally by main.js.
    });

    document.addEventListener('keydown', function (event) {
        var modal = openedModal();
        if (!modal) { return; }
        if (event.key === 'Escape') {
            event.preventDefault();
            closeModal(modal);
            return;
        }
        if (event.key === 'Tab') {
            var items = Array.prototype.filter.call(modal.querySelectorAll(FOCUSABLE), function (el) {
                return el.offsetParent !== null;
            });
            if (!items.length) { return; }
            var first = items[0];
            var last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    // Logo preview: show the chosen file before saving.
    document.addEventListener('change', function (event) {
        var input = event.target;
        if (!input.hasAttribute || !input.hasAttribute('data-logo-input')) { return; }
        var preview = byId('bi-logo-preview');
        var empty = byId('bi-logo-empty');
        var file = input.files && input.files[0];
        if (!preview || !file || !/^image\//.test(file.type)) { return; }
        var reader = new FileReader();
        reader.onload = function () {
            preview.src = reader.result;
            preview.hidden = false;
            if (empty) { empty.hidden = true; }
        };
        reader.readAsDataURL(file);
    });
})();
