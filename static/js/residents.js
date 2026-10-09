// Moved from templates/accounts/residents_tabbed.html (inline scripts are blocked by the CSP).
function toggleActionMenu(event, btn) {
    event.stopPropagation();
    var menu = btn.nextElementSibling;
    if (!menu) return;
    var isOpen = menu.classList.contains('show');
    
    // Close any other open dropdowns
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
        el.classList.remove('show');
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

// Close dropdowns on outside click
document.addEventListener('click', function(e) {
    if (!e.target.closest('.action-dropdown-container') && !e.target.closest('.action-dropdown-menu')) {
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
            el.classList.remove('show');
        });
    }
});

function openResidentModal(data) {
    document.getElementById('m-name').textContent = data.name;
    document.getElementById('m-username').textContent = '@' + data.username;
    document.getElementById('m-phone').textContent = data.phone;
    document.getElementById('m-email').textContent = data.email;
    document.getElementById('m-birthdate').textContent = data.birthdate || 'N/A';
    document.getElementById('m-age').textContent = data.age || 'N/A';
    document.getElementById('m-purok').textContent = data.purok;
    document.getElementById('m-date').textContent = data.date;
    document.getElementById('m-address').textContent = data.address;

    var idProofContainer = document.getElementById('m-idproof-container');
    if (data.idproof && data.idproof.charAt(0) === '/' && data.idproof.charAt(1) !== '/') {
        // Built with DOM APIs so the URL is never parsed as HTML.
        idProofContainer.textContent = '';
        var link = document.createElement('a');
        link.href = data.idproof;
        link.target = '_blank';
        link.rel = 'noopener';
        link.style.textDecoration = 'none';
        var img = document.createElement('img');
        img.src = data.idproof;
        img.alt = 'Uploaded proof of identity';
        img.style.cssText = 'max-height: 220px; max-width: 100%; border-radius: 4px; box-shadow: none;';
        var caption = document.createElement('div');
        caption.style.cssText = 'margin-top:0.5rem; font-size:0.75rem; font-weight:700; color:#1E3A8A;';
        var icon = BrgyUI.iconElement('arrow-up-right');
        caption.appendChild(icon);
        caption.appendChild(document.createTextNode(' Open Full Image'));
        link.appendChild(img);
        link.appendChild(caption);
        idProofContainer.appendChild(link);
    } else {
        idProofContainer.innerHTML = '<span class="badge badge-danger">NO PROOF UPLOADED</span>';
    }

    var pendingActions = document.getElementById('m-pending-actions');
    var rejectedActions = document.getElementById('m-rejected-actions');
    var approvedActions = document.getElementById('m-approved-actions');
    var rejectionBox = document.getElementById('m-rejection-box');

    pendingActions.style.display = 'none';
    rejectedActions.style.display = 'none';
    approvedActions.style.display = 'none';
    rejectionBox.style.display = 'none';

    if (data.status === 'pending') {
        document.getElementById('m-applicant-title').textContent = 'Verify Resident Applicant';
        pendingActions.style.display = 'block';
        toggleRejectReasonInput(false);
        document.getElementById('m-approve-form').action = '/accounts/residents/' + data.id + '/approve/';
        document.getElementById('m-reject-form').action = '/accounts/residents/' + data.id + '/reject/';

        var matchBanner = document.getElementById('m-possible-match-banner');
        var linkInput = document.getElementById('m-link-resident-input');
        var linkCheckbox = document.getElementById('m-confirm-link-checkbox');
        if (matchBanner) {
            if (data.matchId) {
                matchBanner.style.display = 'block';
                document.getElementById('m-match-details').textContent = data.matchName + ' (DOB: ' + data.matchDob + ')';
                linkCheckbox.setAttribute('data-link-id', data.matchId);
                linkCheckbox.checked = false;
                linkInput.value = '';
            } else {
                matchBanner.style.display = 'none';
                linkInput.value = '';
            }
        }
    } else if (data.status === 'rejected') {
        document.getElementById('m-applicant-title').textContent = 'Declined Resident Application';
        rejectedActions.style.display = 'block';
        if (data.reason) {
            rejectionBox.style.display = 'block';
            document.getElementById('m-rejection-text').textContent = data.reason;
        }
        document.getElementById('m-reeval-approve-form').action = '/accounts/residents/' + data.id + '/reevaluate/';
        document.getElementById('m-reeval-pending-form').action = '/accounts/residents/' + data.id + '/reevaluate/';
    } else {
        document.getElementById('m-applicant-title').textContent = 'Verified Resident Profile';
        approvedActions.style.display = 'block';
    }

    var modal = document.getElementById('residentDetailModal');
    modal.style.display = 'flex';
}

function onRejectPresetSelected(selectEl) {
    var input = document.getElementById('m-rejection-input-field');
    if (!input) return;
    if (selectEl.value === '__other__') {
        input.value = '';
        input.placeholder = 'Write it so the resident can understand it.';
        input.focus();
    } else if (selectEl.value) {
        input.value = selectEl.value;
    }
}

function toggleRejectReasonInput(force) {
    var box = document.getElementById('m-reject-expandable-box');
    var input = document.getElementById('m-rejection-input-field');
    var select = document.getElementById('m-rejection-preset-select');
    if (!box) return;
    if (force === false) {
        box.style.display = 'none';
        if (input) input.value = '';
        if (select) select.value = '';
    } else {
        var isHidden = (box.style.display === 'none' || !box.style.display);
        box.style.display = isHidden ? 'block' : 'none';
        if (isHidden && input) {
            input.focus();
        }
    }
}

function closeResidentModal() {
    toggleRejectReasonInput(false);
    var modal = document.getElementById('residentDetailModal');
    modal.style.display = 'none';
}

function openEditResidentModal(data) {
    // Close any open menus
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
        el.classList.remove('show');
    });
    
    var form = document.getElementById('editResidentForm');
    form.action = '/accounts/residents/' + data.id + '/edit/';
    
    document.getElementById('edit-res-first-name').value = data.first_name || '';
    document.getElementById('edit-res-last-name').value = data.last_name || '';
    document.getElementById('edit-res-email').value = data.email === 'N/A' ? '' : (data.email || '');
    document.getElementById('edit-res-phone').value = data.phone === 'N/A' ? '' : (data.phone || '');
    document.getElementById('edit-res-purok').value = data.purok === 'Unassigned' ? '' : (data.purok || '');
    document.getElementById('edit-res-address').value = data.address === 'N/A' ? '' : (data.address || '');
    
    var civilSelect = document.getElementById('edit-res-civil');
    if (civilSelect) {
        civilSelect.value = data.civil || 'single';
    }
    document.getElementById('edit-res-gender').value = data.gender || '';
    document.getElementById('edit-res-solo').checked = !!data.solo;
    document.getElementById('edit-res-pwd').checked = !!data.pwd;
    document.getElementById('edit-res-4ps').checked = !!data.fourps;
    
    var modal = document.getElementById('editResidentModal');
    modal.style.display = 'flex';
}

function closeEditResidentModal() {
    document.getElementById('editResidentModal').style.display = 'none';
}

function openDeleteResidentModal(id, name) {
    // Close any open menus
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
        el.classList.remove('show');
    });
    
    var form = document.getElementById('deleteResidentForm');
    form.action = '/accounts/residents/' + id + '/delete/';
    document.getElementById('delete-resident-name').textContent = name;
    
    var modal = document.getElementById('deleteResidentModal');
    modal.style.display = 'flex';
}

function closeDeleteResidentModal() {
    document.getElementById('deleteResidentModal').style.display = 'none';
}

// Delegated listeners for the buttons and fields that used inline handlers.
document.addEventListener('click', function(e) {
    var rowBtn = e.target.closest('[data-row-action]');
    if (rowBtn) {
        var rowAction = rowBtn.getAttribute('data-row-action');
        if (rowAction === 'toggle-menu') {
            toggleActionMenu(e, rowBtn);
        } else if (rowAction === 'edit-resident') {
            var d = rowBtn.dataset;
            openEditResidentModal({
                id: d.id, first_name: d.firstName, last_name: d.lastName, username: d.username,
                email: d.email, phone: d.phone, address: d.address, purok: d.purok,
                civil: d.civil, gender: d.gender,
                solo: d.solo === 'true', pwd: d.pwd === 'true', fourps: d.fourps === 'true'
            });
        } else if (rowAction === 'delete-resident') {
            openDeleteResidentModal(rowBtn.dataset.id, rowBtn.dataset.name || '');
        }
        return;
    }
    var resBtn = e.target.closest('[data-res-action]');
    if (!resBtn) return;
    var resAction = resBtn.getAttribute('data-res-action');
    if (resAction === 'close-detail') {
        closeResidentModal();
    } else if (resAction === 'toggle-reject') {
        toggleRejectReasonInput();
    } else if (resAction === 'cancel-reject') {
        toggleRejectReasonInput(false);
    } else if (resAction === 'close-edit') {
        closeEditResidentModal();
    } else if (resAction === 'close-delete') {
        closeDeleteResidentModal();
    }
});

document.addEventListener('change', function(e) {
    var el = e.target;
    if (el.id === 'm-confirm-link-checkbox') {
        var linkInput = document.getElementById('m-link-resident-input');
        if (linkInput) linkInput.value = el.checked ? (el.getAttribute('data-link-id') || '') : '';
    } else if (el.id === 'm-rejection-preset-select') {
        onRejectPresetSelected(el);
    }
});

document.addEventListener('DOMContentLoaded', function() {
    var buttons = document.querySelectorAll('.open-resident-modal-btn');
    buttons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            // Close any open menus
            document.querySelectorAll('.action-dropdown-menu.show').forEach(function(el) {
                el.classList.remove('show');
            });
            var data = {
                id: this.getAttribute('data-id'),
                name: this.getAttribute('data-name'),
                username: this.getAttribute('data-username'),
                email: this.getAttribute('data-email'),
                phone: this.getAttribute('data-phone'),
                address: this.getAttribute('data-address'),
                purok: this.getAttribute('data-purok'),
                date: this.getAttribute('data-date'),
                idproof: this.getAttribute('data-idproof'),
                matchId: this.getAttribute('data-match-id'),
                matchName: this.getAttribute('data-match-name'),
                matchDob: this.getAttribute('data-match-dob'),
                reason: this.getAttribute('data-reason'),
                status: this.getAttribute('data-status')
            };
            openResidentModal(data);
        });
    });

    // Close on backdrop click for all modals
    ['residentDetailModal', 'editResidentModal', 'deleteResidentModal'].forEach(function(modalId) {
        var modal = document.getElementById(modalId);
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        }
    });
});
