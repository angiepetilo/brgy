// Moved from templates/appointments/appointment_list.html (inline scripts are blocked by the CSP).
    function openAddDocumentModal() {
        document.getElementById('addDocumentModal').style.display = 'flex';
    }
    function closeAddDocumentModal() {
        document.getElementById('addDocumentModal').style.display = 'none';
    }
    function openAddHealthServiceModal() {
        document.getElementById('addHealthServiceModal').style.display = 'flex';
    }
    function closeAddHealthServiceModal() {
        document.getElementById('addHealthServiceModal').style.display = 'none';
    }

    function toggleCustomDocMode() {
        var customWrapper = document.getElementById('custom_doc_wrapper');
        var customInput = document.getElementById('custom_doc_input');
        var select = document.getElementById('doc_type_select');
        var toggleText = document.getElementById('toggle-doc-text');

        if (customWrapper.style.display === 'none') {
            customWrapper.style.display = 'block';
            customInput.required = true;
            select.removeAttribute('required');
            toggleText.textContent = "Select from standard list";
            customInput.focus();
        } else {
            customWrapper.style.display = 'none';
            customInput.required = false;
            select.setAttribute('required', 'required');
            toggleText.textContent = "+ Add Another / Custom Document";
        }
    }

    function handleDocSelectChange(val) {
        var customWrapper = document.getElementById('custom_doc_wrapper');
        var customInput = document.getElementById('custom_doc_input');
        var toggleText = document.getElementById('toggle-doc-text');
        if (val === '__custom__') {
            customWrapper.style.display = 'block';
            customInput.required = true;
            toggleText.textContent = "Select from standard list";
            customInput.focus();
        } else {
            customWrapper.style.display = 'none';
            customInput.required = false;
            toggleText.textContent = "+ Add Another / Custom Document";
        }
    }

    function toggleActionMenu(event, btn) {
        event.stopPropagation();
        var menu = btn.nextElementSibling;
        if (!menu) return;
        var isOpen = menu.classList.contains('show');

        var allMenus = document.querySelectorAll('.action-dropdown-menu');
        allMenus.forEach(function(m) {
            m.classList.remove('show');
        });

        if (!isOpen) {
            menu.classList.add('show');

            // Break completely out of table-responsive / overflow containers using fixed viewport coordinates
            var rect = btn.getBoundingClientRect();
            menu.style.position = 'fixed';
            menu.style.zIndex = '99999';

            var menuWidth = menu.offsetWidth || 140;
            var menuHeight = menu.offsetHeight || 135;

            // Align right edge of menu to right edge of button
            var left = rect.right - menuWidth;
            if (left < 10) left = 10;
            menu.style.left = left + 'px';
            menu.style.right = 'auto';

            // Check if menu goes below bottom of viewport
            if (rect.bottom + menuHeight > window.innerHeight && rect.top > menuHeight) {
                menu.style.top = (rect.top - menuHeight - 4) + 'px';
            } else {
                menu.style.top = (rect.bottom + 4) + 'px';
            }
        }
    }

    // Close dropdowns on scroll or resize so fixed menu doesn't detach
    window.addEventListener('scroll', function() {
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
            el.classList.remove('show');
        });
    }, true);

    window.addEventListener('resize', function() {
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
            el.classList.remove('show');
        });
    });

    function openEditAppointmentModal(btnOrData) {
        var data = (btnOrData && btnOrData.dataset) ? {
            id: btnOrData.dataset.id,
            ref: btnOrData.dataset.ref,
            name: btnOrData.dataset.name,
            date: btnOrData.dataset.date,
            slot: btnOrData.dataset.slot,
            status: btnOrData.dataset.status,
            purpose: btnOrData.dataset.purpose,
            notes: btnOrData.dataset.notes
        } : btnOrData;

        document.getElementById('edit-apt-title').textContent = 'Edit ' + (data.ref || 'Appointment');
        document.getElementById('edit-apt-subtitle').textContent = 'Applicant: ' + (data.name || '');
        document.getElementById('edit-apt-date').value = data.date || '';
        document.getElementById('edit-apt-slot').value = data.slot || 'morning';
        document.getElementById('edit-apt-purpose').value = data.purpose || '';
        document.getElementById('edit-apt-notes').value = data.notes || '';
        document.getElementById('editAppointmentForm').action = '/appointments/' + data.id + '/edit/';
        document.getElementById('editAppointmentModal').style.display = 'flex';
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) { m.classList.remove('show'); });
    }
    function closeEditAppointmentModal() {
        document.getElementById('editAppointmentModal').style.display = 'none';
    }

    function openDeleteAppointmentModal(btnOrId, ref, name) {
        var id = btnOrId;
        if (btnOrId && btnOrId.dataset) {
            id = btnOrId.dataset.id;
            ref = btnOrId.dataset.ref;
            name = btnOrId.dataset.name;
        }
        document.getElementById('delete-apt-ref').textContent = ref;
        document.getElementById('delete-apt-name').textContent = name;
        document.getElementById('deleteAppointmentForm').action = '/appointments/' + id + '/delete/';
        document.getElementById('deleteAppointmentModal').style.display = 'flex';
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) { m.classList.remove('show'); });
    }
    function closeDeleteAppointmentModal() {
        document.getElementById('deleteAppointmentModal').style.display = 'none';
    }

    function openViewHealthServiceModal(data) {
        document.getElementById('view-svc-name').textContent = data.name;
        document.getElementById('view-svc-date').textContent = data.date || 'Monday - Friday';
        document.getElementById('view-svc-time').textContent = data.time || '8:00 AM - 5:00 PM';
        document.getElementById('view-svc-desc').textContent = data.desc || 'Available for community residents at the Barangay Health Center.';
        var badge = document.getElementById('view-svc-status-badge');
        if (data.active) {
            badge.className = 'badge badge-success';
            badge.textContent = 'Active';
        } else {
            badge.className = 'badge badge-secondary';
            badge.textContent = 'Inactive';
        }
        document.getElementById('viewHealthServiceModal').style.display = 'flex';
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) { m.classList.remove('show'); });
    }
    function closeViewHealthServiceModal() {
        document.getElementById('viewHealthServiceModal').style.display = 'none';
    }

    function openEditHealthServiceModal(data) {
        document.getElementById('edit-svc-name').value = data.name;
        document.getElementById('edit-svc-date').value = data.date || '';
        document.getElementById('edit-svc-time').value = data.time || '';
        document.getElementById('edit-svc-desc').value = data.desc || '';
        document.getElementById('edit-svc-active').checked = !!data.active;
        document.getElementById('editHealthServiceForm').action = '/appointments/services/' + data.id + '/edit/';
        document.getElementById('editHealthServiceModal').style.display = 'flex';
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) { m.classList.remove('show'); });
    }
    function closeEditHealthServiceModal() {
        document.getElementById('editHealthServiceModal').style.display = 'none';
    }

    function openDeleteHealthServiceModal(id, name) {
        document.getElementById('delete-svc-name').textContent = name;
        document.getElementById('deleteHealthServiceForm').action = '/appointments/services/' + id + '/delete/';
        document.getElementById('deleteHealthServiceModal').style.display = 'flex';
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) { m.classList.remove('show'); });
    }
    function closeDeleteHealthServiceModal() {
        document.getElementById('deleteHealthServiceModal').style.display = 'none';
    }

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.action-dropdown-container')) {
            document.querySelectorAll('.action-dropdown-menu.show').forEach(function(m) {
                m.classList.remove('show');
            });
        }
    });
    function openAddAppointmentModal(docPreset, isHealth, serviceId) {
        var modal = document.getElementById('moduleAddAppointmentModal');
        document.getElementById('modal-form-wrapper').style.display = 'block';
        document.getElementById('modal-success-wrapper').style.display = 'none';

        var dateInput = document.getElementById('modal-pref-date');
        if (dateInput && !dateInput.value) {
            var tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            dateInput.min = new Date().toISOString().split('T')[0];
        }

        if (isHealth) {
            switchModalCategory('healthcare');
            if (serviceId) {
                document.getElementById('modal-healthcare-select').value = serviceId;
            }
        } else {
            switchModalCategory('document');
            if (docPreset) {
                document.getElementById('modal-document-select').value = docPreset;
            }
        }

        modal.style.display = 'flex';
    }

    function closeAddAppointmentModal() {
        document.getElementById('moduleAddAppointmentModal').style.display = 'none';
    }

    function closeAndReload() {
        closeAddAppointmentModal();
        window.location.reload();
    }

    function resetModalForm() {
        document.getElementById('module-appointment-form').reset();
        document.getElementById('modal-form-wrapper').style.display = 'block';
        document.getElementById('modal-success-wrapper').style.display = 'none';
    }

    function switchModalCategory(cat) {
        var pillDoc = document.getElementById('modal-pill-doc');
        var pillHealth = document.getElementById('modal-pill-health');
        var catInput = document.getElementById('modal-category-input');
        var docBox = document.getElementById('modal-doc-type-box');
        var healthBox = document.getElementById('modal-health-type-box');
        var purposeBox = document.getElementById('module-purpose-group');
        var purposeInput = document.getElementById('module_input_purpose');

        if (cat === 'document') {
            pillDoc.classList.add('active');
            pillHealth.classList.remove('active');
            catInput.value = 'document';
            docBox.style.display = 'block';
            healthBox.style.display = 'none';
            if (purposeBox) purposeBox.style.display = 'block';
            if (purposeInput) purposeInput.required = true;
        } else {
            pillHealth.classList.add('active');
            pillDoc.classList.remove('active');
            catInput.value = 'healthcare';
            docBox.style.display = 'none';
            healthBox.style.display = 'block';
            if (purposeBox) purposeBox.style.display = 'none';
            if (purposeInput) {
                purposeInput.required = false;
                purposeInput.value = '';
            }
        }
    }

    function enforceModalPhone11Digits(input) {
        var val = input.value.replace(/[^0-9]/g, '');
        if (val.length > 11) {
            val = val.substring(0, 11);
        }
        input.value = val;

        var feedback = document.getElementById('modal-phone-feedback');
        if (val.length === 11) {
            if (val.startsWith('09')) {
                feedback.innerHTML = '<span style="color: #111827;">' + BrgyUI.icon('check', 'icon-success') + ' Valid 11-digit mobile number</span>';
                input.classList.remove('input-error');
            } else {
                feedback.innerHTML = '<span style="color: #DC2626;">' + BrgyUI.icon('x') + ' Must start with 09 (e.g. 09171234567)</span>';
                input.classList.add('input-error');
            }
        } else if (val.length > 0) {
            feedback.innerHTML = '<span style="color: #374151;">' + val.length + '/11 digits entered</span>';
        } else {
            feedback.innerHTML = 'Must be 11 digits starting with 09';
            input.classList.remove('input-error');
        }
    }

    function validateModalEmailLive(email) {
        var feedback = document.getElementById('modal-email-feedback');
        var emailInput = document.getElementById('modal_input_email');
        email = (email || '').trim();

        if (!email) {
            feedback.innerHTML = '';
            emailInput.classList.remove('input-error');
            return;
        }

        var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            feedback.innerHTML = '<span style="color: #DC2626;">' + BrgyUI.icon('circle-alert') + ' Invalid email format</span>';
            emailInput.classList.add('input-error');
            return;
        }

        feedback.innerHTML = '';
        emailInput.classList.remove('input-error');
    }

    function handleModuleAppointmentSubmit(e) {
        e.preventDefault();
        var form = document.getElementById('module-appointment-form');
        var btn = document.getElementById('btn-submit-modal-appointment');
        var errBanner = document.getElementById('modal-error-banner');
        var errText = document.getElementById('modal-error-text');

        var phoneVal = document.getElementById('modal_input_phone').value;
        if (!/^09\d{9}$/.test(phoneVal)) {
            errBanner.style.display = 'block';
            errText.innerText = "Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567).";
            return;
        }

        btn.disabled = true;
        btn.innerHTML = BrgyUI.icon('loader-circle', 'icon-spin') + ' Submitting & Verifying...';
        errBanner.style.display = 'none';

        var formData = new FormData(form);

        fetch('/appointments/api/public-book/', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (res) {
                return res.json().then(function (data) { return { ok: res.ok, data: data }; });
            })
            .then(function (res) {
                btn.disabled = false;
                btn.innerHTML = BrgyUI.icon('send') + ' Book Appointment Now';

                if (res.ok && res.data.status === 'ok') {
                    document.getElementById('modal-success-ref').innerText = res.data.ref_number || 'REF #APT-NEW';
                    document.getElementById('modal-form-wrapper').style.display = 'none';
                    document.getElementById('modal-success-wrapper').style.display = 'block';
                    form.reset();
                } else {
                    errBanner.style.display = 'block';
                    if (res.data.errors) {
                        var firstKey = Object.keys(res.data.errors)[0];
                        errText.innerText = res.data.errors[firstKey];
                    } else {
                        errText.innerText = res.data.message || 'Error saving appointment.';
                    }
                }
            })
            .catch(function () {
                btn.disabled = false;
                btn.innerHTML = BrgyUI.icon('send') + ' Book Appointment Now';
                errBanner.style.display = 'block';
                errText.innerText = 'Network error. Please try again.';
            });
    }

    document.addEventListener('click', function (e) {
        var modal = document.getElementById('moduleAddAppointmentModal');
        if (e.target === modal) closeAddAppointmentModal();
    });

    // ------------------------------------------------------------------
    // Delegated listeners (CSP: the template has no inline handlers)
    //   data-call="fnName" [data-arg="x"]  calls one of the functions below
    //   data-row-action="..."               table/service row menus
    // ------------------------------------------------------------------
    var CALLABLE = {
        openAddAppointmentModal: openAddAppointmentModal,
        closeAddAppointmentModal: closeAddAppointmentModal,
        openAddDocumentModal: openAddDocumentModal,
        closeAddDocumentModal: closeAddDocumentModal,
        openAddHealthServiceModal: openAddHealthServiceModal,
        closeAddHealthServiceModal: closeAddHealthServiceModal,
        closeEditAppointmentModal: closeEditAppointmentModal,
        closeDeleteAppointmentModal: closeDeleteAppointmentModal,
        closeViewHealthServiceModal: closeViewHealthServiceModal,
        closeEditHealthServiceModal: closeEditHealthServiceModal,
        closeDeleteHealthServiceModal: closeDeleteHealthServiceModal,
        switchModalCategory: switchModalCategory,
        toggleCustomDocMode: toggleCustomDocMode,
        resetModalForm: resetModalForm,
        closeAndReload: closeAndReload
    };

    function serviceData(el) {
        return {
            id: el.dataset.id,
            name: el.dataset.name || '',
            date: el.dataset.date || '',
            time: el.dataset.time || '',
            desc: el.dataset.desc || '',
            active: el.dataset.active === 'true'
        };
    }

    document.addEventListener('click', function (e) {
        var callEl = e.target.closest('[data-call]');
        if (callEl) {
            var fn = CALLABLE[callEl.getAttribute('data-call')];
            if (fn) {
                e.preventDefault();
                var arg = callEl.getAttribute('data-arg');
                if (arg === null) { fn(); } else { fn(arg); }
            }
            return;
        }
        var rowEl = e.target.closest('[data-row-action]');
        if (!rowEl) return;
        var action = rowEl.getAttribute('data-row-action');
        if (action === 'toggle-menu') {
            toggleActionMenu(e, rowEl);
        } else if (action === 'edit-appointment') {
            openEditAppointmentModal(rowEl);
        } else if (action === 'delete-appointment') {
            openDeleteAppointmentModal(rowEl);
        } else if (action === 'view-service') {
            openViewHealthServiceModal(serviceData(rowEl));
        } else if (action === 'edit-service') {
            openEditHealthServiceModal(serviceData(rowEl));
        } else if (action === 'delete-service') {
            openDeleteHealthServiceModal(rowEl.dataset.id, rowEl.dataset.name || '');
        }
    function openReviewAppointmentModal(btn) {
        var d = btn.dataset;
        var catEl = document.getElementById('rev-category');
        var titleEl = document.getElementById('rev-title');
        var appEl = document.getElementById('rev-applicant');
        var timeEl = document.getElementById('rev-time');
        var statusPill = document.getElementById('rev-status-pill');
        var rejectForm = document.getElementById('rev-reject-form');
        var approveForm = document.getElementById('rev-approve-form');
        var detailLink = document.getElementById('rev-detail-link');

        if (catEl) catEl.textContent = 'Category: ' + (d.category || 'Appointment') + ' / ' + (d.service || '');
        if (titleEl) titleEl.textContent = d.title || d.service || '-';
        if (appEl) appEl.textContent = d.applicant || '-';
        if (timeEl) timeEl.textContent = d.time || '-';

        if (statusPill) {
            var badgeBg = '#FEF3C7';
            var badgeCol = '#92400E';
            if (d.status === 'approved') { badgeBg = '#D1FAE5'; badgeCol = '#065F46'; }
            else if (d.status === 'completed') { badgeBg = '#E0E7FF'; badgeCol = '#3730A3'; }
            else if (d.status === 'rejected') { badgeBg = '#FEE2E2'; badgeCol = '#991B1B'; }
            statusPill.innerHTML = '<span class="badge" style="background:' + badgeBg + '; color:' + badgeCol + '; font-size:0.75rem; padding:2px 8px; border-radius:9999px; font-weight:500;">' + (d.statusDisplay || d.status) + '</span>';
        }

        if (rejectForm) rejectForm.action = '/appointments/' + d.id + '/reject/';
        if (approveForm) {
            approveForm.action = '/appointments/' + d.id + '/approve/';
            approveForm.style.display = (d.canApprove === 'true') ? 'inline-block' : 'none';
        }
        if (detailLink) detailLink.href = '/appointments/' + d.id + '/';

        var modal = document.getElementById('reviewAppointmentModal');
        if (modal) modal.style.display = 'flex';
    }

    function closeReviewAppointmentModal() {
        var modal = document.getElementById('reviewAppointmentModal');
        if (modal) modal.style.display = 'none';
    }

    document.addEventListener('click', function(e) {
        var revBtn = e.target.closest('[data-appt-action="review"]');
        if (revBtn) {
            openReviewAppointmentModal(revBtn);
            return;
        }
        var delBtn = e.target.closest('[data-appt-action="delete"]');
        if (delBtn) {
            openDeleteAppointmentModal(delBtn);
            return;
        }
        if (e.target.closest('[data-appt-action="close-review"]')) {
            closeReviewAppointmentModal();
            return;
        }
        var revModal = document.getElementById('reviewAppointmentModal');
        if (revModal && e.target === revModal) {
            closeReviewAppointmentModal();
        }
    });

    document.addEventListener('submit', function (e) {
        if (e.target && e.target.id === 'module-appointment-form') {
            handleModuleAppointmentSubmit(e);
        }
    });

    document.addEventListener('focusout', function (e) {
        if (e.target && e.target.id === 'modal_input_email') {
            validateModalEmailLive(e.target.value);
        }
    });

    document.addEventListener('input', function (e) {
        if (e.target && e.target.id === 'modal_input_phone') {
            enforceModalPhone11Digits(e.target);
        }
    });

    document.addEventListener('change', function (e) {
        if (e.target && e.target.id === 'doc_type_select') {
            handleDocSelectChange(e.target.value);
        }
    });
