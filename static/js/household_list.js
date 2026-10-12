/*
 * Household List & Master-Detail Interactive Controller
 * Strictly CSP-compliant: external JS file, no inline scripts.
 */
document.addEventListener('DOMContentLoaded', function() {
    // -------------------------------------------------------------
    // DYNAMIC HOUSEHOLD MEMBER ROW BUILDER
    // -------------------------------------------------------------
    var REL_OPTIONS = [
        'Head',
        'Spouse',
        'Son',
        'Daughter',
        'Parent',
        'Sibling',
        'Grandparent',
        'Grandchild',
        'Relative',
        'Other'
    ];

    function calculateAge(birthdateStr) {
        if (!birthdateStr) return '';
        var bd = new Date(birthdateStr);
        if (isNaN(bd.getTime())) return '';
        var today = new Date();
        var age = today.getFullYear() - bd.getFullYear();
        var m = today.getMonth() - bd.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < bd.getDate())) {
            age--;
        }
        return (age >= 0 && age < 150) ? age : '';
    }

    function createMemberRow(firstName, lastName, relationship, birthdate, isPwd, isSoloParent, is4ps) {
        var tr = document.createElement('tr');
        tr.className = 'member-input-row';
        tr.style.borderBottom = '1px solid #F3F4F6';

        // 1. First Name
        var tdFirst = document.createElement('td');
        tdFirst.style.padding = '0.35rem 0.4rem';
        var inFirst = document.createElement('input');
        inFirst.type = 'text';
        inFirst.name = 'member_first_name[]';
        inFirst.className = 'form-control';
        inFirst.placeholder = 'First Name';
        inFirst.value = firstName || '';
        inFirst.required = true;
        inFirst.style.cssText = 'width: 100%; height: 32px; font-size: 0.8125rem; border-radius: 6px; border: 1px solid #D1D5DB; padding: 0 0.5rem; box-sizing: border-box;';
        tdFirst.appendChild(inFirst);

        // 2. Last Name
        var tdLast = document.createElement('td');
        tdLast.style.padding = '0.35rem 0.4rem';
        var inLast = document.createElement('input');
        inLast.type = 'text';
        inLast.name = 'member_last_name[]';
        inLast.className = 'form-control';
        inLast.placeholder = 'Last Name';
        inLast.value = lastName || '';
        inLast.required = true;
        inLast.style.cssText = 'width: 100%; height: 32px; font-size: 0.8125rem; border-radius: 6px; border: 1px solid #D1D5DB; padding: 0 0.5rem; box-sizing: border-box;';
        tdLast.appendChild(inLast);

        // 3. Relationship
        var tdRel = document.createElement('td');
        tdRel.style.padding = '0.35rem 0.4rem';
        var selRel = document.createElement('select');
        selRel.name = 'member_relationship[]';
        selRel.className = 'form-control';
        selRel.style.cssText = 'width: 100%; height: 32px; font-size: 0.8125rem; border-radius: 6px; border: 1px solid #D1D5DB; padding: 0 0.35rem; box-sizing: border-box;';
        REL_OPTIONS.forEach(function(opt) {
            var op = document.createElement('option');
            op.value = opt;
            op.textContent = opt;
            if (relationship && relationship.toLowerCase() === opt.toLowerCase()) {
                op.selected = true;
            }
            selRel.appendChild(op);
        });
        tdRel.appendChild(selRel);

        // 4. Birthdate
        var tdBirth = document.createElement('td');
        tdBirth.style.padding = '0.35rem 0.4rem';
        var inBirth = document.createElement('input');
        inBirth.type = 'date';
        inBirth.name = 'member_birthdate[]';
        inBirth.className = 'form-control';
        inBirth.value = birthdate || '';
        inBirth.style.cssText = 'width: 100%; height: 32px; font-size: 0.8125rem; border-radius: 6px; border: 1px solid #D1D5DB; padding: 0 0.35rem; box-sizing: border-box;';
        tdBirth.appendChild(inBirth);

        // 5. Age (Auto calculated)
        var tdAge = document.createElement('td');
        tdAge.style.padding = '0.35rem 0.25rem';
        tdAge.style.textAlign = 'center';
        var spanAge = document.createElement('span');
        spanAge.className = 'member-age-display';
        spanAge.style.cssText = 'font-weight: 700; color: #1E3A8A; font-size: 0.825rem; display: inline-block; min-width: 20px; text-align: center;';
        var initialAge = calculateAge(birthdate);
        spanAge.textContent = initialAge !== '' ? initialAge : '--';
        tdAge.appendChild(spanAge);

        // Auto calculate age on input change
        function updateAge() {
            var calculated = calculateAge(inBirth.value);
            spanAge.textContent = calculated !== '' ? calculated : '--';
        }
        inBirth.addEventListener('input', updateAge);
        inBirth.addEventListener('change', updateAge);

        // 6. Sector Toggles (PWD, Solo Parent, 4Ps)
        var tdSector = document.createElement('td');
        tdSector.style.padding = '0.35rem 0.4rem';
        var divSector = document.createElement('div');
        divSector.style.cssText = 'display: flex; gap: 0.45rem; align-items: center; flex-wrap: wrap; font-size: 0.75rem;';

        function createSectorToggle(labelTxt, hiddenName, initialChecked, activeColor) {
            var wrap = document.createElement('label');
            wrap.style.cssText = 'display: inline-flex; align-items: center; gap: 0.2rem; cursor: pointer; user-select: none; font-size: 0.75rem; font-weight: 600; color: #4B5563; margin: 0;';

            var hid = document.createElement('input');
            hid.type = 'hidden';
            hid.name = hiddenName;
            hid.value = initialChecked ? '1' : '0';

            var chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.checked = !!initialChecked;
            chk.style.cssText = 'margin: 0; cursor: pointer; accent-color: ' + activeColor + '; width: 13px; height: 13px;';

            var txt = document.createElement('span');
            txt.textContent = labelTxt;

            function updateLabel() {
                hid.value = chk.checked ? '1' : '0';
                if (chk.checked) {
                    txt.style.color = activeColor;
                    txt.style.fontWeight = '700';
                } else {
                    txt.style.color = '#4B5563';
                    txt.style.fontWeight = '600';
                }
            }

            chk.addEventListener('change', updateLabel);
            if (initialChecked) {
                txt.style.color = activeColor;
                txt.style.fontWeight = '700';
            }

            wrap.appendChild(hid);
            wrap.appendChild(chk);
            wrap.appendChild(txt);
            wrap._chk = chk;
            wrap._hid = hid;
            wrap._update = updateLabel;
            return wrap;
        }

        var togPwd = createSectorToggle('PWD', 'member_is_pwd[]', isPwd, '#9D174D');
        var togSolo = createSectorToggle('Solo', 'member_is_solo_parent[]', isSoloParent, '#3730A3');
        var tog4ps = createSectorToggle('4Ps', 'member_is_4ps[]', is4ps, '#065F46');

        divSector.appendChild(togPwd);
        divSector.appendChild(togSolo);
        divSector.appendChild(tog4ps);
        tdSector.appendChild(divSector);

        // 7. Action (Remove row)
        var tdAction = document.createElement('td');
        tdAction.style.padding = '0.35rem 0.25rem';
        tdAction.style.textAlign = 'center';
        var btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.innerHTML = '&times;';
        btnDel.title = 'Remove Member';
        btnDel.style.cssText = 'background: none; border: none; color: #DC2626; font-size: 1.25rem; line-height: 1; cursor: pointer; padding: 2px 4px; font-weight: bold;';
        btnDel.addEventListener('click', function() {
            var tbody = tr.parentElement;
            if (tbody && tbody.children.length > 1) {
                tr.remove();
            } else {
                inFirst.value = '';
                inLast.value = '';
                selRel.value = 'Head';
                inBirth.value = '';
                spanAge.textContent = '--';
                togPwd._chk.checked = false;
                togPwd._update();
                togSolo._chk.checked = false;
                togSolo._update();
                tog4ps._chk.checked = false;
                tog4ps._update();
            }
        });
        tdAction.appendChild(btnDel);

        tr.appendChild(tdFirst);
        tr.appendChild(tdLast);
        tr.appendChild(tdRel);
        tr.appendChild(tdBirth);
        tr.appendChild(tdAge);
        tr.appendChild(tdSector);
        tr.appendChild(tdAction);
        return tr;
    }

    // Modal elements
    var regModal = document.getElementById('registerHouseholdModal');
    var editModal = document.getElementById('editHouseholdModal');
    var delModal = document.getElementById('deleteHouseholdModal');
    var regForm = document.getElementById('registerHouseholdForm');
    var editForm = document.getElementById('editHouseholdForm');
    var delForm = document.getElementById('deleteHouseholdForm');

    var regMembersTbody = document.getElementById('reg-members-table-body');
    var editMembersTbody = document.getElementById('edit-members-table-body');
    var btnAddMemberReg = document.getElementById('btn-add-member-reg');
    var btnAddMemberEdit = document.getElementById('btn-add-member-edit');

    // Add Member in Register Modal
    if (btnAddMemberReg && regMembersTbody) {
        btnAddMemberReg.addEventListener('click', function() {
            regMembersTbody.appendChild(createMemberRow('', '', 'Other', '', false, false, false));
        });
    }

    // Add Member in Edit Modal
    if (btnAddMemberEdit && editMembersTbody) {
        btnAddMemberEdit.addEventListener('click', function() {
            var defaultLast = '';
            var lastNameInp = document.getElementById('edit_family_name');
            if (lastNameInp && lastNameInp.value) {
                defaultLast = lastNameInp.value.replace(/ Family$/i, '');
            }
            editMembersTbody.appendChild(createMemberRow('', defaultLast, 'Other', '', false, false, false));
        });
    }

    // Track dirty changes
    if (regForm) {
        regForm.addEventListener('input', function() { regForm.dataset.dirty = 'true'; });
        regForm.addEventListener('change', function() { regForm.dataset.dirty = 'true'; });
    }
    if (editForm) {
        editForm.addEventListener('input', function() { editForm.dataset.dirty = 'true'; });
        editForm.addEventListener('change', function() { editForm.dataset.dirty = 'true'; });
    }

    function closeRegModal() {
        function doClose() {
            if (regForm) {
                regForm.dataset.dirty = 'false';
                regForm.reset();
            }
            if (regMembersTbody) {
                regMembersTbody.innerHTML = '';
            }
            if (regModal) regModal.style.display = 'none';
        }
        if (regForm && regForm.dataset.dirty === 'true') {
            if (typeof window.showConfirmModal === 'function') {
                window.showConfirmModal({
                    title: 'Discard Changes?',
                    message: 'You have unsaved changes in this household registration. Discard changes?',
                    variant: 'danger',
                    confirmText: 'Discard',
                    cancelText: 'Keep Editing',
                    onConfirm: doClose
                });
                return;
            } else if (!confirm('You have unsaved changes in this household registration. Discard changes?')) {
                return;
            }
        }
        doClose();
    }

    function closeEditModal() {
        function doClose() {
            if (editForm) {
                editForm.dataset.dirty = 'false';
                editForm.reset();
            }
            if (editMembersTbody) {
                editMembersTbody.innerHTML = '';
            }
            if (editModal) editModal.style.display = 'none';
        }
        if (editForm && editForm.dataset.dirty === 'true') {
            if (typeof window.showConfirmModal === 'function') {
                window.showConfirmModal({
                    title: 'Discard Changes?',
                    message: 'You have unsaved changes. Discard changes?',
                    variant: 'danger',
                    confirmText: 'Discard',
                    cancelText: 'Keep Editing',
                    onConfirm: doClose
                });
                return;
            } else if (!confirm('You have unsaved changes. Discard changes?')) {
                return;
            }
        }
        doClose();
    }

    // Close buttons
    var closeRegBtn = document.getElementById('btn-close-register-household');
    var cancelRegBtn = document.getElementById('btn-cancel-register-household');
    if (closeRegBtn) closeRegBtn.addEventListener('click', closeRegModal);
    if (cancelRegBtn) cancelRegBtn.addEventListener('click', closeRegModal);

    var closeEditBtn = document.getElementById('btn-close-edit-household');
    var cancelEditBtn = document.getElementById('btn-cancel-edit-household');
    if (closeEditBtn) closeEditBtn.addEventListener('click', closeEditModal);
    if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeEditModal);

    var cancelDelBtn = document.getElementById('btn-cancel-delete-household');
    if (cancelDelBtn) {
        cancelDelBtn.addEventListener('click', function() {
            if (delModal) delModal.style.display = 'none';
        });
    }

    // Backdrop dismissal
    window.addEventListener('click', function(e) {
        if (e.target === regModal) closeRegModal();
        if (e.target === editModal) closeEditModal();
        if (delModal && e.target === delModal) delModal.style.display = 'none';
    });

    // -------------------------------------------------------------
    // MASTER-DETAIL SELECTION & ROW SWITCHING
    // -------------------------------------------------------------
    var rows = document.querySelectorAll('.hh-row-item');
    var currentSelectedRow = document.querySelector('.hh-row-item.selected-hh-row') || (rows.length > 0 ? rows[0] : null);

    function displayHouseholdDetails(row) {
        if (!row) return;
        currentSelectedRow = row;

        // Highlight selected row in table
        rows.forEach(function(r) { r.classList.remove('selected-hh-row'); });
        row.classList.add('selected-hh-row');

        var d = row.dataset;

        // Top Subcards
        var setText = function(id, val) {
            var el = document.getElementById(id);
            if (el) el.textContent = val || '--';
        };

        setText('view-hh-id', d.id);
        setText('view-hh-number', d.householdNumber || d.householdId || ('HM-2025-' + d.id));
        setText('view-hh-ownership', d.ownershipStatus || 'Owned');

        setText('view-hh-interviewed', d.interviewedBy || '--');
        setText('view-hh-reviewed', d.reviewedBy || '--');
        setText('view-hh-visit', d.dateOfVisit || '--');

        // Bottom Audit Subcards
        setText('view-encoded-date', d.encodedDate || '--');
        setText('view-encoded-by', d.encodedBy || '--');
        setText('view-updated-date', d.updatedDate || '--');
        setText('view-updated-by', d.updatedBy || '--');

        // Household Members Table
        var tbody = document.getElementById('view-members-tbody');
        if (tbody) {
            tbody.innerHTML = '';
            var membersList = [];
            try {
                if (d.members) {
                    membersList = JSON.parse(d.members);
                }
            } catch (err) {
                console.warn('Could not parse household members JSON:', err);
            }

            if (membersList && membersList.length > 0) {
                membersList.forEach(function(m) {
                    var tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid #F3F4F6';

                    var tdFirst = document.createElement('td');
                    tdFirst.style.padding = '0.65rem 0.75rem';
                    tdFirst.style.color = '#111827';
                    tdFirst.style.fontWeight = '500';
                    tdFirst.style.borderRight = '1px solid #F3F4F6';
                    tdFirst.textContent = m.first_name || '';

                    var tdLast = document.createElement('td');
                    tdLast.style.padding = '0.65rem 0.75rem';
                    tdLast.style.color = '#111827';
                    tdLast.style.fontWeight = '500';
                    tdLast.style.borderRight = '1px solid #F3F4F6';
                    tdLast.textContent = m.last_name || '';

                    var tdRel = document.createElement('td');
                    tdRel.style.padding = '0.65rem 0.75rem';
                    tdRel.style.color = '#4B5563';
                    tdRel.style.fontWeight = '600';
                    tdRel.style.borderRight = '1px solid #F3F4F6';
                    tdRel.textContent = m.relationship || 'Member';

                    var tdBirth = document.createElement('td');
                    tdBirth.style.padding = '0.65rem 0.75rem';
                    tdBirth.style.color = '#4B5563';
                    tdBirth.style.fontWeight = '500';
                    tdBirth.style.borderRight = '1px solid #F3F4F6';
                    tdBirth.textContent = m.birthdate || '--';

                    var computedAge = (m.age !== undefined && m.age !== null && m.age !== '') ? m.age : calculateAge(m.birthdate);
                    var tdAge = document.createElement('td');
                    tdAge.style.padding = '0.65rem 0.5rem';
                    tdAge.style.color = '#111827';
                    tdAge.style.fontWeight = '700';
                    tdAge.style.textAlign = 'center';
                    tdAge.style.borderRight = '1px solid #F3F4F6';
                    tdAge.textContent = (computedAge !== '' && computedAge !== null && computedAge !== undefined) ? computedAge : '--';

                    // Sector / Classification Badges
                    var tdSector = document.createElement('td');
                    tdSector.style.padding = '0.65rem 0.75rem';
                    var divBadges = document.createElement('div');
                    divBadges.style.cssText = 'display: flex; gap: 0.3rem; flex-wrap: wrap; align-items: center;';

                    var hasBadge = false;
                    var isSenior = (m.is_senior || (computedAge !== '' && parseInt(computedAge, 10) >= 60));

                    if (isSenior) {
                        var bSenior = document.createElement('span');
                        bSenior.style.cssText = 'background: #FEF3C7; color: #92400E; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; font-weight: 700;';
                        bSenior.textContent = 'Senior';
                        divBadges.appendChild(bSenior);
                        hasBadge = true;
                    }
                    if (m.is_pwd) {
                        var bPwd = document.createElement('span');
                        bPwd.style.cssText = 'background: #FCE7F3; color: #9D174D; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; font-weight: 700;';
                        bPwd.textContent = 'PWD';
                        divBadges.appendChild(bPwd);
                        hasBadge = true;
                    }
                    if (m.is_solo_parent) {
                        var bSolo = document.createElement('span');
                        bSolo.style.cssText = 'background: #E0E7FF; color: #3730A3; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; font-weight: 700;';
                        bSolo.textContent = 'Solo Parent';
                        divBadges.appendChild(bSolo);
                        hasBadge = true;
                    }
                    if (m.is_4ps) {
                        var b4ps = document.createElement('span');
                        b4ps.style.cssText = 'background: #D1FAE5; color: #065F46; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; font-weight: 700;';
                        b4ps.textContent = '4Ps';
                        divBadges.appendChild(b4ps);
                        hasBadge = true;
                    }
                    if (!hasBadge) {
                        var bNone = document.createElement('span');
                        bNone.style.cssText = 'color: #9CA3AF; font-size: 0.75rem;';
                        bNone.textContent = '--';
                        divBadges.appendChild(bNone);
                    }
                    tdSector.appendChild(divBadges);

                    tr.appendChild(tdFirst);
                    tr.appendChild(tdLast);
                    tr.appendChild(tdRel);
                    tr.appendChild(tdBirth);
                    tr.appendChild(tdAge);
                    tr.appendChild(tdSector);
                    tbody.appendChild(tr);
                });
            } else {
                var emptyTr = document.createElement('tr');
                var emptyTd = document.createElement('td');
                emptyTd.colSpan = 6;
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '2rem 1rem';
                emptyTd.style.color = '#9CA3AF';
                emptyTd.textContent = 'No members registered for this household.';
                emptyTr.appendChild(emptyTd);
                tbody.appendChild(emptyTr);
            }
        }
    }

    // Bind row click handlers
    rows.forEach(function(row) {
        row.addEventListener('click', function() {
            displayHouseholdDetails(row);
        });
    });

    // Initial setup if rows exist
    if (currentSelectedRow) {
        displayHouseholdDetails(currentSelectedRow);
    }

    // -------------------------------------------------------------
    // TOP ACTION BUTTONS (REGISTER, UPDATE, REMOVE)
    // -------------------------------------------------------------
    var btnRegister = document.getElementById('btn-top-register-hh');
    if (btnRegister) {
        btnRegister.addEventListener('click', function() {
            var visitInput = document.getElementById('hh_date_of_visit');
            if (visitInput && !visitInput.value) {
                visitInput.value = new Date().toISOString().split('T')[0];
            }
            if (regMembersTbody && regMembersTbody.children.length === 0) {
                regMembersTbody.appendChild(createMemberRow('', '', 'Head', '', false, false, false));
            }
            if (regModal) regModal.style.display = 'flex';
        });
    }

    var btnUpdate = document.getElementById('btn-top-update-hh');
    if (btnUpdate) {
        btnUpdate.addEventListener('click', function() {
            if (!currentSelectedRow) {
                alert('Please select a household to update.');
                return;
            }
            var d = currentSelectedRow.dataset;

            var titleEl = document.getElementById('edit-hh-header-title');
            if (titleEl) {
                titleEl.textContent = 'Update Household ' + (d.householdNumber || d.householdId || ('#' + d.id));
            }

            var setVal = function(id, val) {
                var el = document.getElementById(id);
                if (el) el.value = val || '';
            };

            setVal('edit_household_number', d.householdNumber);
            setVal('edit_family_name', d.familyName);
            setVal('edit_purok', d.purokId);
            setVal('edit_street', d.street);
            setVal('edit_ownership_status', d.ownershipStatus || 'Owned');
            setVal('edit_interviewed_by', d.interviewedBy);
            setVal('edit_reviewed_by', d.reviewedBy);
            setVal('edit_date_of_visit', d.dateOfVisitRaw || d.dateOfVisit);

            // Populate members in Edit modal
            if (editMembersTbody) {
                editMembersTbody.innerHTML = '';
                var membersList = [];
                try {
                    if (d.members) {
                        membersList = JSON.parse(d.members);
                    }
                } catch (e) {
                    console.warn('Could not parse members:', e);
                }

                if (membersList && membersList.length > 0) {
                    membersList.forEach(function(m) {
                        editMembersTbody.appendChild(createMemberRow(m.first_name, m.last_name, m.relationship, m.birthdate, m.is_pwd, m.is_solo_parent, m.is_4ps));
                    });
                } else {
                    editMembersTbody.appendChild(createMemberRow(d.firstName, d.lastName, d.relationship || 'Head', d.birthdate, false, false, false));
                }
            }

            if (editForm) {
                editForm.action = '/accounts/households/' + d.id + '/edit/';
                editForm.dataset.dirty = 'false';
            }

            if (editModal) editModal.style.display = 'flex';
        });
    }

    var btnRemove = document.getElementById('btn-top-remove-hh');
    if (btnRemove) {
        btnRemove.addEventListener('click', function() {
            if (!currentSelectedRow) {
                alert('Please select a household to remove.');
                return;
            }
            var d = currentSelectedRow.dataset;
            var numEl = document.getElementById('delete-hh-number');
            var idEl = document.getElementById('delete-hh-id');
            if (numEl) numEl.textContent = d.householdNumber || d.householdId || ('#' + d.id);
            if (idEl) idEl.textContent = 'Database ID: ' + d.id;
            if (delForm) delForm.action = '/accounts/households/' + d.id + '/delete/';
            if (delModal) delModal.style.display = 'flex';
        });
    }
});
