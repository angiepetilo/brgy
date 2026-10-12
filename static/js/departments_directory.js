/*
 * Departments Directory & Assigned Staff Modal Controller
 * Strictly CSP-compliant: external JS file, no inline scripts.
 */
document.addEventListener('DOMContentLoaded', function() {
    var modal = document.getElementById('departmentStaffModal');
    var closeBtn = document.getElementById('btn-close-dept-modal');
    var closeFooterBtn = document.getElementById('btn-close-dept-modal-footer');

    function closeModal() {
        if (modal) {
            modal.style.display = 'none';
        }
    }

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (closeFooterBtn) closeFooterBtn.addEventListener('click', closeModal);

    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
            closeModal();
        }
    });

    var cards = document.querySelectorAll('.dept-card-interactive');
    cards.forEach(function(card) {
        card.addEventListener('click', function() {
            var d = card.dataset;

            // Header info
            var titleEl = document.getElementById('dept-modal-title');
            var codeEl = document.getElementById('dept-modal-code');
            var headEl = document.getElementById('dept-modal-head-line');
            var descEl = document.getElementById('dept-modal-desc');
            var locEl = document.getElementById('dept-modal-location');
            var hoursEl = document.getElementById('dept-modal-hours');
            var contactEl = document.getElementById('dept-modal-contact');
            var countEl = document.getElementById('dept-modal-staff-count');
            var iconBox = document.getElementById('dept-modal-icon-box');

            if (titleEl) titleEl.textContent = d.deptName || 'Department';
            if (codeEl) {
                codeEl.textContent = d.deptCode || '';
                codeEl.style.backgroundColor = (d.deptColor || '#1E3A8A') + '15';
                codeEl.style.color = d.deptColor || '#1E3A8A';
            }
            if (iconBox && d.deptColor) {
                iconBox.style.backgroundColor = d.deptColor + '15';
                iconBox.style.color = d.deptColor;
            }
            if (headEl) headEl.textContent = d.deptHead ? ('Head: ' + d.deptHead) : '';
            if (descEl) descEl.textContent = d.deptDesc || '';
            if (locEl) locEl.textContent = d.deptLocation || '--';
            if (hoursEl) hoursEl.textContent = d.deptHours || '--';
            if (contactEl) contactEl.textContent = d.deptContact || '--';

            // Services chips
            var servicesContainer = document.getElementById('dept-modal-services-chips');
            if (servicesContainer) {
                servicesContainer.innerHTML = '';
                var servicesList = [];
                try {
                    if (d.deptServices) {
                        servicesList = JSON.parse(d.deptServices);
                    }
                } catch (e) {
                    console.warn('Could not parse services JSON:', e);
                }

                if (servicesList && servicesList.length > 0) {
                    servicesList.forEach(function(srv) {
                        var chip = document.createElement('span');
                        chip.style.cssText = 'background: #F3F4F6; color: #374151; font-size: 0.75rem; font-weight: 600; padding: 4px 10px; border-radius: 6px; border: 1px solid #E5E7EB;';
                        chip.textContent = srv;
                        servicesContainer.appendChild(chip);
                    });
                }
            }

            // Staff Roster
            var staffContainer = document.getElementById('dept-modal-staff-list');
            if (staffContainer) {
                staffContainer.innerHTML = '';
                var staffList = [];
                try {
                    if (d.deptStaff) {
                        staffList = JSON.parse(d.deptStaff);
                    }
                } catch (e) {
                    console.warn('Could not parse staff JSON:', e);
                }

                if (countEl) {
                    countEl.textContent = staffList.length + ' Staff Assigned';
                }

                if (staffList && staffList.length > 0) {
                    staffList.forEach(function(staff) {
                        var item = document.createElement('div');
                        item.className = 'dept-staff-item';
                        item.style.cssText = 'background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; padding: 0.85rem 1rem; display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; transition: border-color 0.15s, box-shadow 0.15s;';
                        
                        // Left: Avatar + Details
                        var left = document.createElement('div');
                        left.style.cssText = 'display: flex; align-items: center; gap: 0.75rem; flex: 1; min-width: 0;';

                        // Avatar wrapper
                        var avatarWrap = document.createElement('div');
                        avatarWrap.style.cssText = 'position: relative; width: 42px; height: 42px; flex-shrink: 0;';

                        if (staff.avatar_url) {
                            var img = document.createElement('img');
                            img.src = staff.avatar_url;
                            img.alt = staff.name;
                            img.style.cssText = 'width: 42px; height: 42px; border-radius: 50%; object-fit: cover; border: 1px solid #E5E7EB;';
                            avatarWrap.appendChild(img);
                        } else {
                            var initialBox = document.createElement('div');
                            initialBox.style.cssText = 'width: 42px; height: 42px; border-radius: 50%; background: #EFF6FF; color: #1E3A8A; font-weight: 800; font-size: 0.85rem; display: flex; align-items: center; justify-content: center; border: 1px solid #DBEAFE;';
                            initialBox.textContent = staff.initials || 'ST';
                            avatarWrap.appendChild(initialBox);
                        }

                        // Duty status dot
                        var dot = document.createElement('span');
                        var isDuty = (staff.duty_status === 'on_duty');
                        dot.style.cssText = 'position: absolute; bottom: 0; right: 0; width: 10px; height: 10px; border-radius: 50%; border: 2px solid #FFFFFF; background-color: ' + (isDuty ? '#10B981' : '#9CA3AF') + ';';
                        avatarWrap.appendChild(dot);
                        left.appendChild(avatarWrap);

                        // Staff text info
                        var textWrap = document.createElement('div');
                        textWrap.style.cssText = 'min-width: 0; flex: 1;';

                        var nameEl = document.createElement('div');
                        nameEl.style.cssText = 'font-weight: 700; color: #111827; font-size: 0.875rem; display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;';
                        nameEl.textContent = staff.name;

                        if (isDuty) {
                            var dutyBadge = document.createElement('span');
                            dutyBadge.style.cssText = 'font-size: 0.65rem; font-weight: 700; background: #ECFDF5; color: #047857; padding: 1px 6px; border-radius: 4px; border: 1px solid #A7F3D0;';
                            dutyBadge.textContent = 'ON DUTY';
                            nameEl.appendChild(dutyBadge);
                        }
                        textWrap.appendChild(nameEl);

                        var roleEl = document.createElement('div');
                        roleEl.style.cssText = 'color: #4B5563; font-size: 0.78rem; font-weight: 600; margin-top: 0.1rem;';
                        roleEl.textContent = staff.role;
                        textWrap.appendChild(roleEl);

                        var metaEl = document.createElement('div');
                        metaEl.style.cssText = 'color: #6B7280; font-size: 0.72rem; margin-top: 0.2rem; display: flex; gap: 0.75rem; flex-wrap: wrap;';
                        if (staff.phone) {
                            metaEl.innerHTML += '<span>' + staff.phone + '</span>';
                        }
                        if (staff.email) {
                            metaEl.innerHTML += '<span>' + staff.email + '</span>';
                        }
                        textWrap.appendChild(metaEl);
                        left.appendChild(textWrap);
                        item.appendChild(left);

                        // Right: Actions (Message Button / Contact)
                        var right = document.createElement('div');
                        right.style.cssText = 'display: flex; gap: 0.4rem; align-items: center; flex-shrink: 0;';

                        if (staff.can_message && staff.id > 0) {
                            var msgBtn = document.createElement('a');
                            msgBtn.href = '/chat/' + staff.id + '/';
                            msgBtn.className = 'btn btn-primary';
                            msgBtn.style.cssText = 'font-size: 0.75rem; font-weight: 700; padding: 0.4rem 0.85rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.35rem; text-decoration: none; background: #1E3A8A; color: #FFFFFF;';
                            msgBtn.textContent = 'Message';
                            right.appendChild(msgBtn);
                        } else if (staff.phone) {
                            var callBtn = document.createElement('a');
                            var cleanPhone = staff.phone.replace(/[^0-9+]/g, '');
                            callBtn.href = 'tel:' + cleanPhone;
                            callBtn.className = 'btn btn-outline-secondary';
                            callBtn.style.cssText = 'font-size: 0.75rem; font-weight: 700; padding: 0.35rem 0.75rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.35rem; text-decoration: none; border: 1px solid #D1D5DB; color: #374151;';
                            callBtn.textContent = 'Call';
                            right.appendChild(callBtn);
                        }

                        item.appendChild(right);
                        staffContainer.appendChild(item);
                    });
                } else {
                    var emptyDiv = document.createElement('div');
                    emptyDiv.style.cssText = 'text-align: center; padding: 1.5rem; color: #9CA3AF; font-size: 0.85rem; background: #F9FAFB; border-radius: 8px;';
                    emptyDiv.textContent = 'No personnel currently listed for this department.';
                    staffContainer.appendChild(emptyDiv);
                }
            }

            // Open modal
            if (modal) {
                modal.style.display = 'flex';
            }
        });
    });

    // Directory & Officers Live Search Filter
    var searchInput = document.getElementById('dept-directory-search');
    var emptyState = document.getElementById('dept-search-empty');

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            var term = this.value.trim().toLowerCase();
            var visibleCount = 0;

            cards.forEach(function(card) {
                var text = (
                    (card.dataset.deptName || '') + ' ' +
                    (card.dataset.deptCode || '') + ' ' +
                    (card.dataset.deptDesc || '') + ' ' +
                    (card.dataset.deptHead || '') + ' ' +
                    (card.dataset.deptServices || '') + ' ' +
                    (card.dataset.deptStaff || '')
                ).toLowerCase();

                if (!term || text.indexOf(term) !== -1) {
                    card.style.display = 'flex';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });

            if (emptyState) {
                emptyState.style.display = (visibleCount === 0) ? 'block' : 'none';
            }
        });
    }
});
