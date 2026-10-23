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
    allMenus.forEach(function (m) {
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
window.addEventListener('scroll', function () {
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (el) {
        el.classList.remove('show');
    });
}, true);

window.addEventListener('resize', function () {
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (el) {
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
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) { m.classList.remove('show'); });
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
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) { m.classList.remove('show'); });
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
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) { m.classList.remove('show'); });
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
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) { m.classList.remove('show'); });
}
function closeEditHealthServiceModal() {
    document.getElementById('editHealthServiceModal').style.display = 'none';
}

function openDeleteHealthServiceModal(id, name) {
    document.getElementById('delete-svc-name').textContent = name;
    document.getElementById('deleteHealthServiceForm').action = '/appointments/services/' + id + '/delete/';
    document.getElementById('deleteHealthServiceModal').style.display = 'flex';
    document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) { m.classList.remove('show'); });
}
function closeDeleteHealthServiceModal() {
    document.getElementById('deleteHealthServiceModal').style.display = 'none';
}

document.addEventListener('click', function (e) {
    if (!e.target.closest('.action-dropdown-container')) {
        document.querySelectorAll('.action-dropdown-menu.show').forEach(function (m) {
            m.classList.remove('show');
        });
    }
});
var calState = {
    year: new Date().getFullYear(),
    month: new Date().getMonth(),
    selectedDate: null,
    hour: 8,
    minute: 0,
    ampm: 'AM'
};

// Dynamic health services loader (Strict CSP compliant: reads from JSON script tag)
function loadHealthServices() {
    var scriptEl = document.getElementById('health-services-data');
    if (!scriptEl) return [];
    try {
        var raw = JSON.parse(scriptEl.textContent.trim());
        if (Array.isArray(raw)) {
            var colors = ['dot-blue', 'dot-navy', 'dot-green', 'dot-red', 'dot-gray'];
            return raw.map(function (item, idx) {
                var days = [];
                var dText = (item.daysText || '').toLowerCase();
                if (dText.indexOf('mon') !== -1 && dText.indexOf('fri') !== -1) {
                    days = [1, 2, 3, 4, 5];
                } else {
                    if (dText.indexOf('mon') !== -1) days.push(1);
                    if (dText.indexOf('tue') !== -1) days.push(2);
                    if (dText.indexOf('wed') !== -1) days.push(3);
                    if (dText.indexOf('thu') !== -1) days.push(4);
                    if (dText.indexOf('fri') !== -1) days.push(5);
                    if (dText.indexOf('sat') !== -1) days.push(6);
                    if (dText.indexOf('sun') !== -1) days.push(0);
                }
                if (days.length === 0) days = [1, 2, 3, 4, 5];

                var timeText = item.timeText || '8:00 AM - 5:00 PM';
                var startHour = 8, startMin = 0, startAmpm = 'AM';
                var m = timeText.match(/(\d+):?(\d*)\s*(AM|PM)/i);
                if (m) {
                    startHour = parseInt(m[1], 10);
                    startMin = m[2] ? parseInt(m[2], 10) : 0;
                    startAmpm = m[3].toUpperCase();
                }

                return {
                    id: item.id,
                    name: item.name,
                    days: days,
                    daysText: item.daysText || 'Monday - Friday',
                    timeText: timeText,
                    startHour: startHour,
                    startMin: startMin,
                    startAmpm: startAmpm,
                    dotClass: colors[idx % colors.length],
                    is_free: item.is_free !== false
                };
            });
        }
    } catch (e) {
        console.warn('Could not parse health services data:', e);
    }
    return [];
}

var MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

function padZero(n) {
    return n < 10 ? '0' + n : '' + n;
}

function formatDateISO(d) {
    return d.getFullYear() + '-' + padZero(d.getMonth() + 1) + '-' + padZero(d.getDate());
}

function formatDisplayDate(dateStr) {
    if (!dateStr) return '';
    var parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    var d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    var days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    return days[d.getDay()] + ', ' + MONTH_NAMES[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
}

function renderCustomCalendar() {
    var monthSelect = document.getElementById('cal-month-select');
    var yearSelect = document.getElementById('cal-year-select');
    var grid = document.getElementById('custom-cal-grid');
    if (!grid) return;

    refreshClosedDatesMap();
    ensureValidSelectedDate();

    if (monthSelect) monthSelect.value = calState.month;
    if (yearSelect) yearSelect.value = calState.year;

    grid.innerHTML = '';

    var firstDayIndex = new Date(calState.year, calState.month, 1).getDay();
    var daysInMonth = new Date(calState.year, calState.month + 1, 0).getDate();
    var daysInPrevMonth = new Date(calState.year, calState.month, 0).getDate();

    var today = new Date();
    var todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    // 1. Prev month trailing days
    for (var i = firstDayIndex - 1; i >= 0; i--) {
        var prevNum = daysInPrevMonth - i;
        var prevCell = document.createElement('div');
        prevCell.className = 'cal-day-cell other-month';
        prevCell.innerHTML = '<span class="cal-day-num">' + padZero(prevNum) + '</span>';
        grid.appendChild(prevCell);
    }

    var catInput = document.getElementById('modal-category-input');
    var currentCat = catInput ? catInput.value : 'document';
    var actSvc = (currentCat === 'healthcare') ? getActiveHealthService() : null;

    // 2. Current month days
    for (var d = 1; d <= daysInMonth; d++) {
        var cellDate = new Date(calState.year, calState.month, d);
        var cellISO = formatDateISO(cellDate);
        var dayOfWeek = cellDate.getDay();

        var cell = document.createElement('div');
        cell.className = 'cal-day-cell current-month';
        cell.setAttribute('data-date', cellISO);

        var isSelectable = isDateSelectable(cellISO, dayOfWeek);
        var isClosed = !!CLOSED_DATES_MAP[cellISO];
        var isPast = cellDate < todayMidnight;
        var isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);

        if (!isSelectable) {
            cell.classList.add('disabled-date');
            if (isClosed) {
                cell.classList.add('cal-day-closed');
                cell.title = 'Closed: ' + (CLOSED_DATES_MAP[cellISO] || 'Barangay Holiday');
                cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span><span class="cal-day-closed-tag">Closed</span>';
            } else if (isPast) {
                cell.classList.add('past');
                cell.title = 'Past date';
                cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>';
            } else if (isWeekend) {
                cell.classList.add('service-unavailable');
                cell.title = 'Barangay is closed on weekends';
                cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>';
            } else {
                cell.classList.add('service-unavailable');
                if (actSvc) {
                    cell.title = actSvc.name + ' is not available on ' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][dayOfWeek] + 's (' + actSvc.daysText + ')';
                }
                cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>';
            }
        } else {
            if (cellISO === calState.selectedDate) {
                cell.classList.add('selected');
            }

            var dotHtml = '';
            if (currentCat === 'healthcare' && actSvc) {
                dotHtml = '<span class="cal-day-dot ' + (actSvc.dotClass || 'dot-blue') + '"></span>';
            } else {
                var servicesForDay = HEALTH_SERVICES.filter(function (s) {
                    return s.days.indexOf(dayOfWeek) !== -1;
                });
                if (servicesForDay.length > 0) {
                    cell.classList.add('has-services');
                    dotHtml = '<span class="cal-day-dot ' + servicesForDay[0].dotClass + '"></span>';
                }
            }

            cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>' + dotHtml;

            cell.addEventListener('click', (function (iso, dow) {
                return function () {
                    calState.selectedDate = iso;
                    var dateInput = document.getElementById('modal-date-input');
                    if (dateInput) dateInput.value = iso;
                    renderCustomCalendar();
                    renderHealthServicesList(iso, dow);
                    updateSchedulePreview();
                };
            })(cellISO, dayOfWeek));
        }
        grid.appendChild(cell);
    }

    // 3. Next month leading days
    var totalRendered = firstDayIndex + daysInMonth;
    var totalCells = totalRendered > 35 ? 42 : 35;
    var remaining = totalCells - totalRendered;
    for (var n = 1; n <= remaining; n++) {
        var nextCell = document.createElement('div');
        nextCell.className = 'cal-day-cell other-month';
        nextCell.innerHTML = '<span class="cal-day-num">' + padZero(n) + '</span>';
        grid.appendChild(nextCell);
    }

    if (calState.selectedDate) {
        var parts = calState.selectedDate.split('-');
        var selD = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        renderHealthServicesList(calState.selectedDate, selD.getDay());
    }
}

var CLOSED_DATES_MAP = {};
function refreshClosedDatesMap() {
    try {
        var cTag = document.getElementById('brgy-closed-dates-data');
        if (cTag && cTag.textContent) {
            CLOSED_DATES_MAP = JSON.parse(cTag.textContent);
        }
    } catch (e) {
        CLOSED_DATES_MAP = {};
    }
}
refreshClosedDatesMap();

function parseDaysFromText(text) {
    if (!text) return [1, 2, 3, 4, 5];
    var t = text.toLowerCase();
    if (t.indexOf('everyday') !== -1 || t.indexOf('daily') !== -1 || t.indexOf('mon - fri') !== -1 || t.indexOf('monday - friday') !== -1 || t.indexOf('monday to friday') !== -1) {
        return [1, 2, 3, 4, 5];
    }
    var days = [];
    if (t.indexOf('sun') !== -1) days.push(0);
    if (t.indexOf('mon') !== -1) days.push(1);
    if (t.indexOf('tue') !== -1) days.push(2);
    if (t.indexOf('wed') !== -1) days.push(3);
    if (t.indexOf('thu') !== -1) days.push(4);
    if (t.indexOf('fri') !== -1) days.push(5);
    if (t.indexOf('sat') !== -1) days.push(6);
    return days.length > 0 ? days : [1, 2, 3, 4, 5];
}

function getActiveHealthService() {
    var sel = document.getElementById('modal-healthcare-select');
    if (!sel) return null;
    var val = sel.value;
    for (var i = 0; i < HEALTH_SERVICES.length; i++) {
        if (String(HEALTH_SERVICES[i].id) === String(val) || HEALTH_SERVICES[i].name === val) {
            return HEALTH_SERVICES[i];
        }
    }
    var opt = sel.options[sel.selectedIndex];
    if (opt) {
        var dateAttr = opt.getAttribute('data-service-date') || '';
        var timeAttr = opt.getAttribute('data-service-time') || '';
        return {
            id: val,
            name: opt.textContent.replace(' (Free)', '').trim(),
            days: parseDaysFromText(dateAttr),
            daysText: dateAttr || 'Monday - Friday',
            timeText: timeAttr || '8:00 AM - 4:00 PM',
            dotClass: 'dot-blue'
        };
    }
    return null;
}

function isDateSelectable(isoDateStr, dow) {
    if (!isoDateStr) return false;
    var today = new Date();
    var todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    var parts = isoDateStr.split('-');
    var dObj = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    if (dObj < todayMidnight) return false;

    if (CLOSED_DATES_MAP[isoDateStr]) return false;

    if (dow === undefined) dow = dObj.getDay();
    if (dow === 0 || dow === 6) return false;

    var catInput = document.getElementById('modal-category-input');
    var currentCat = catInput ? catInput.value : 'document';
    if (currentCat === 'healthcare') {
        var svc = getActiveHealthService();
        if (svc && svc.days && svc.days.length > 0) {
            if (svc.days.indexOf(dow) === -1) {
                return false;
            }
        }
    }
    return true;
}

function findNextSelectableDate() {
    var today = new Date();
    for (var i = 1; i <= 60; i++) {
        var testD = new Date(today.getFullYear(), today.getMonth(), today.getDate() + i);
        var iso = formatDateISO(testD);
        if (isDateSelectable(iso, testD.getDay())) {
            return iso;
        }
    }
    return null;
}

function ensureValidSelectedDate() {
    if (!calState.selectedDate || !isDateSelectable(calState.selectedDate)) {
        var nextValid = findNextSelectableDate();
        if (nextValid) {
            calState.selectedDate = nextValid;
            var dateInput = document.getElementById('modal-date-input');
            if (dateInput) dateInput.value = nextValid;
        }
    }
}

function onHealthServiceChanged() {
    var actSvc = getActiveHealthService();
    if (actSvc) {
        if (actSvc.startHour) {
            setTimePicker(actSvc.startHour, actSvc.startMin || 0, actSvc.startAmpm || 'AM');
        }
        var container = document.getElementById('cal-services-list');
        if (container) {
            var allCards = container.querySelectorAll('.cal-service-card');
            allCards.forEach(function (c) {
                if (String(c.getAttribute('data-service-id')) === String(actSvc.id)) {
                    c.classList.add('selected');
                } else {
                    c.classList.remove('selected');
                }
            });
        }
    }
    ensureValidSelectedDate();
    renderCustomCalendar();
    updateSchedulePreview();
}

function renderHealthServicesList(selectedDateISO, dayOfWeek) {
    var container = document.getElementById('cal-services-list');
    var counter = document.getElementById('cal-services-counter');
    if (!container) return;

    var services = loadHealthServices();

    if (services.length === 0) {
        if (counter) counter.textContent = '0 Available';
        container.innerHTML = '<div style="padding: 1.25rem 1rem; text-align: center; color: #6B7280; font-size: 0.8125rem; background: #F9FAFB; border-radius: 8px; border: 1px dashed #E5E7EB;">No health center services currently scheduled.</div>';
        return;
    }

    var openSvcs = services.filter(function (s) {
        return s.days.indexOf(dayOfWeek) !== -1;
    });

    var displayList = openSvcs.length > 0 ? openSvcs : services;

    if (counter) {
        counter.textContent = openSvcs.length > 0 ? openSvcs.length + ' Open Today' : services.length + ' Total';
    }

    container.innerHTML = '';

    displayList.forEach(function (svc) {
        var card = document.createElement('div');
        card.className = 'cal-service-card';
        card.setAttribute('data-service-id', svc.id);

        var dateLabel = selectedDateISO ? formatDisplayDate(selectedDateISO) : svc.daysText;

        card.innerHTML =
            '<div class="service-card-dot ' + (svc.dotClass || 'dot-blue') + '"></div>' +
            '<div style="flex: 1;">' +
            '<div class="service-card-datetime">' + dateLabel + ' • ' + svc.timeText + '</div>' +
            '<div class="service-card-name">' + svc.name + ' <span style="font-weight: 600; color: #111827;">(Free)</span></div>' +
            '</div>';

        card.addEventListener('click', function () {
            var healthSelect = document.getElementById('modal-healthcare-select');
            if (healthSelect) {
                healthSelect.value = svc.id;
            }
            switchModalCategory('healthcare');
            setTimePicker(svc.startHour, svc.startMin, svc.startAmpm);
            var allCards = container.querySelectorAll('.cal-service-card');
            allCards.forEach(function (c) { c.classList.remove('selected'); });
            card.classList.add('selected');
            onHealthServiceChanged();
        });

        container.appendChild(card);
    });
}

function renderTimePicker() {
    var badge = document.getElementById('time-picker-badge');
    var hourPrev = document.getElementById('time-hour-prev');
    var hourCurr = document.getElementById('time-hour-curr');
    var hourNext = document.getElementById('time-hour-next');

    var minPrev = document.getElementById('time-min-prev');
    var minCurr = document.getElementById('time-min-curr');
    var minNext = document.getElementById('time-min-next');

    var ampmPrev = document.getElementById('time-ampm-prev');
    var ampmCurr = document.getElementById('time-ampm-curr');
    var ampmNext = document.getElementById('time-ampm-next');

    var minStr = padZero(calState.minute);
    var timeStr = calState.hour + ':' + minStr + ' ' + calState.ampm;

    if (badge) badge.textContent = timeStr;

    var prevH = calState.hour === 1 ? 12 : calState.hour - 1;
    var nextH = calState.hour === 12 ? 1 : calState.hour + 1;
    if (hourPrev) hourPrev.textContent = prevH;
    if (hourCurr) hourCurr.textContent = calState.hour;
    if (hourNext) hourNext.textContent = nextH;

    var prevM = (calState.minute - 5 + 60) % 60;
    var nextM = (calState.minute + 5) % 60;
    if (minPrev) minPrev.textContent = padZero(prevM);
    if (minCurr) minCurr.textContent = minStr;
    if (minNext) minNext.textContent = padZero(nextM);

    var altAmpm = calState.ampm === 'PM' ? 'AM' : 'PM';
    if (ampmPrev) ampmPrev.textContent = altAmpm;
    if (ampmCurr) ampmCurr.textContent = calState.ampm;
    if (ampmNext) ampmNext.innerHTML = '&nbsp;';

    var timeSlotInput = document.getElementById('modal-time-slot');
    if (timeSlotInput) {
        var isMorning = (calState.ampm === 'AM' && calState.hour < 12) || (calState.ampm === 'PM' && calState.hour === 12);
        timeSlotInput.value = isMorning ? 'morning' : 'afternoon';
    }

    var exactInput = document.getElementById('modal-time-exact-value');
    if (exactInput) exactInput.value = timeStr;

    updateSchedulePreview();
}

function setTimePicker(h, m, ampm) {
    calState.hour = h;
    calState.minute = m;
    calState.ampm = ampm;
    renderTimePicker();
}

function stepHour(delta) {
    var newH = calState.hour + delta;
    if (newH < 1) newH = 12;
    if (newH > 12) newH = 1;
    calState.hour = newH;
    renderTimePicker();
}

function stepMinute(delta) {
    var newM = (calState.minute + delta * 5 + 60) % 60;
    calState.minute = newM;
    renderTimePicker();
}

function toggleAmpm() {
    calState.ampm = calState.ampm === 'PM' ? 'AM' : 'PM';
    renderTimePicker();
}

function updateSchedulePreview() {
    var preview = document.getElementById('selected-schedule-preview');
    if (!preview) return;
    var minStr = padZero(calState.minute);
    var timeStr = calState.hour + ':' + minStr + ' ' + calState.ampm;
    var dateLabel = formatDisplayDate(calState.selectedDate) || 'No date selected';
    preview.textContent = dateLabel + ' at ' + timeStr;
}

function fetchFreeHealthServices() {
    var dateVal = document.getElementById('modal-date-input') ? document.getElementById('modal-date-input').value : '';
    var timeSlotSelect = document.getElementById('modal-time-slot');
    var windowVal = timeSlotSelect ? timeSlotSelect.value : 'morning';
    var selectEl = document.getElementById('modal-healthcare-select');
    if (!selectEl) return;

    fetch('/appointments/api/services/?category=healthcare&date=' + encodeURIComponent(dateVal) + '&window=' + encodeURIComponent(windowVal), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.status === 'ok' && data.health_services && data.health_services.length > 0) {
                selectEl.innerHTML = '';
                data.health_services.forEach(function (svc) {
                    var opt = document.createElement('option');
                    opt.value = svc.id;
                    opt.textContent = svc.name + ' (Free)';
                    selectEl.appendChild(opt);
                });
            }
        })
        .catch(function (err) {
            console.warn('Could not fetch free health services:', err);
        });
}

function openAddAppointmentModal(docPreset, isHealth, serviceId) {
    var modal = document.getElementById('moduleAddAppointmentModal');
    var form = document.getElementById('module-appointment-form');
    var formWrapper = document.getElementById('modal-form-wrapper');
    var successWrapper = document.getElementById('modal-success-wrapper');
    if (formWrapper) formWrapper.style.display = 'block';
    if (successWrapper) successWrapper.style.display = 'none';

    if (form && (!form.dataset.dirty || form.dataset.dirty === 'false')) {
        form.reset();
    }

    var dateInput = document.getElementById('modal-date-input');
    if (dateInput && !dateInput.value) {
        var tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        if (tomorrow.getDay() === 0) tomorrow.setDate(tomorrow.getDate() + 1);
        calState.selectedDate = formatDateISO(tomorrow);
        dateInput.value = calState.selectedDate;
    }

    renderCustomCalendar();
    renderTimePicker();

    if (isHealth) {
        switchModalCategory('healthcare');
        if (serviceId) {
            var healthSel = document.getElementById('modal-healthcare-select');
            if (healthSel) healthSel.value = serviceId;
        }
    } else {
        switchModalCategory('document');
        if (docPreset) {
            var docSel = document.getElementById('modal-document-select');
            if (docSel) docSel.value = docPreset;
        }
    }

    if (modal) modal.style.display = 'flex';
}

function closeAddAppointmentModal(force) {
    var form = document.getElementById('module-appointment-form');
    var modal = document.getElementById('moduleAddAppointmentModal');
    function doClose() {
        if (form) {
            form.dataset.dirty = 'false';
            form.reset();
        }
        if (modal) modal.style.display = 'none';
    }
    if (!force && form && form.dataset.dirty === 'true') {
        if (typeof window.showConfirmModal === 'function') {
            window.showConfirmModal({
                title: 'Discard Changes?',
                message: 'You have unsaved changes in your appointment form. Discard changes?',
                variant: 'danger',
                confirmText: 'Discard',
                cancelText: 'Keep Editing',
                onConfirm: doClose
            });
            return;
        } else if (!window.confirm("You have unsaved changes in your appointment form. Discard changes?")) {
            return;
        }
    }
    doClose();
}

function closeAndReload() {
    closeAddAppointmentModal(true);
    window.location.reload();
}

function resetModalForm() {
    var form = document.getElementById('module-appointment-form');
    if (form) {
        form.dataset.dirty = 'false';
        form.reset();
    }
    var formWrapper = document.getElementById('modal-form-wrapper');
    var successWrapper = document.getElementById('modal-success-wrapper');
    if (formWrapper) formWrapper.style.display = 'block';
    if (successWrapper) successWrapper.style.display = 'none';
    renderCustomCalendar();
    renderTimePicker();
    switchModalCategory('document');
}

function switchModalCategory(cat) {
    var pillDoc = document.getElementById('modal-pill-doc');
    var pillHealth = document.getElementById('modal-pill-health');
    var catInput = document.getElementById('modal-category-input');
    var docBox = document.getElementById('modal-doc-type-box');
    var healthBox = document.getElementById('modal-health-type-box');
    var purposeBox = document.getElementById('module-purpose-group');
    var purposeInput = document.getElementById('module_input_purpose');
    var healthServicesSection = document.getElementById('health-services-section');

    if (cat === 'document') {
        if (pillDoc) pillDoc.classList.add('active');
        if (pillHealth) pillHealth.classList.remove('active');
        if (catInput) catInput.value = 'document';
        if (docBox) docBox.style.display = 'block';
        if (healthBox) healthBox.style.display = 'none';
        if (purposeBox) purposeBox.style.display = 'block';
        if (purposeInput) purposeInput.required = true;
        if (healthServicesSection) healthServicesSection.style.display = 'none';
        ensureValidSelectedDate();
        renderCustomCalendar();
        updateSchedulePreview();
    } else {
        if (pillHealth) pillHealth.classList.add('active');
        if (pillDoc) pillDoc.classList.remove('active');
        if (catInput) catInput.value = 'healthcare';
        if (docBox) docBox.style.display = 'none';
        if (healthBox) healthBox.style.display = 'block';
        if (purposeBox) purposeBox.style.display = 'none';
        if (purposeInput) {
            purposeInput.required = false;
            purposeInput.value = '';
        }
        if (healthServicesSection) healthServicesSection.style.display = 'block';
        fetchFreeHealthServices();
        onHealthServiceChanged();
    }
}

function enforceModalPhone11Digits(input) {
    var val = input.value.replace(/[^0-9]/g, '');
    if (val.length > 11) {
        val = val.substring(0, 11);
    }
    input.value = val;

    var feedback = document.getElementById('modal-phone-feedback');
    if (!feedback) return;

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

    if (!feedback || !emailInput) return;

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

    var phoneInput = document.getElementById('modal_input_phone');
    var phoneVal = phoneInput ? phoneInput.value : '';
    if (!/^09\d{9}$/.test(phoneVal)) {
        if (errBanner) errBanner.style.display = 'block';
        if (errText) errText.innerText = "Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567).";
        return;
    }

    btn.disabled = true;
    btn.innerHTML = BrgyUI.icon('loader-circle', 'icon-spin') + ' Submitting Request...';
    if (errBanner) errBanner.style.display = 'none';

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
            btn.innerHTML = BrgyUI.icon('send') + ' Submit Appointment Request';

            if (res.ok && res.data.status === 'ok') {
                var refEl = document.getElementById('modal-success-ref');
                if (refEl) refEl.innerText = res.data.ref_number || 'REF #APT-NEW';
                var nameEl = document.getElementById('modal-summary-applicant-name');
                if (nameEl) nameEl.innerText = res.data.applicant_name;
                var titleEl = document.getElementById('modal-summary-service-title');
                if (titleEl) titleEl.innerText = res.data.service_title;
                var schedEl = document.getElementById('modal-summary-schedule');
                if (schedEl) schedEl.innerText = res.data.scheduled_date + ' (' + res.data.time_slot + ')';
                var contactEl = document.getElementById('modal-summary-contact');
                if (contactEl) contactEl.innerText = res.data.applicant_email + ' | ' + res.data.applicant_phone;

                var formWrap = document.getElementById('modal-form-wrapper');
                var succWrap = document.getElementById('modal-success-wrapper');
                if (formWrap) formWrap.style.display = 'none';
                if (succWrap) succWrap.style.display = 'block';
                form.reset();
                form.dataset.dirty = 'false';
            } else {
                if (errBanner) errBanner.style.display = 'block';
                if (res.data.errors) {
                    var firstKey = Object.keys(res.data.errors)[0];
                    if (errText) errText.innerText = res.data.errors[firstKey];
                } else {
                    if (errText) errText.innerText = res.data.message || 'Error saving appointment.';
                }
            }
        })
        .catch(function () {
            btn.disabled = false;
            btn.innerHTML = BrgyUI.icon('send') + ' Submit Appointment Request';
            if (errBanner) errBanner.style.display = 'block';
            if (errText) errText.innerText = 'Network error. Please try again.';
        });
}

// Initialize calendar & time drum event controls
document.addEventListener('DOMContentLoaded', function () {
    var monthSelect = document.getElementById('cal-month-select');
    if (monthSelect) {
        monthSelect.addEventListener('change', function () {
            calState.month = parseInt(this.value, 10);
            renderCustomCalendar();
        });
    }
    var yearSelect = document.getElementById('cal-year-select');
    if (yearSelect) {
        yearSelect.addEventListener('change', function () {
            calState.year = parseInt(this.value, 10);
            renderCustomCalendar();
        });
    }
    var todayBtn = document.getElementById('cal-today-btn');
    if (todayBtn) {
        todayBtn.addEventListener('click', function () {
            var now = new Date();
            calState.year = now.getFullYear();
            calState.month = now.getMonth();
            calState.selectedDate = formatDateISO(now);
            var dateInput = document.getElementById('modal-date-input');
            if (dateInput) dateInput.value = calState.selectedDate;
            renderCustomCalendar();
        });
    }
    var prevBtn = document.getElementById('cal-prev-btn');
    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            if (calState.month === 0) {
                calState.month = 11;
                calState.year -= 1;
            } else {
                calState.month -= 1;
            }
            renderCustomCalendar();
        });
    }
    var nextBtn = document.getElementById('cal-next-btn');
    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            if (calState.month === 11) {
                calState.month = 0;
                calState.year += 1;
            } else {
                calState.month += 1;
            }
            renderCustomCalendar();
        });
    }

    // Time picker steppers
    var hourPrev = document.getElementById('time-hour-prev');
    if (hourPrev) hourPrev.addEventListener('click', function () { stepHour(-1); });
    var hourNext = document.getElementById('time-hour-next');
    if (hourNext) hourNext.addEventListener('click', function () { stepHour(1); });
    var hourCurr = document.getElementById('time-hour-curr');
    if (hourCurr) hourCurr.addEventListener('click', function () { stepHour(1); });

    var minPrev = document.getElementById('time-min-prev');
    if (minPrev) minPrev.addEventListener('click', function () { stepMinute(-1); });
    var minNext = document.getElementById('time-min-next');
    if (minNext) minNext.addEventListener('click', function () { stepMinute(1); });
    var minCurr = document.getElementById('time-min-curr');
    if (minCurr) minCurr.addEventListener('click', function () { stepMinute(1); });

    var ampmPrev = document.getElementById('time-ampm-prev');
    if (ampmPrev) ampmPrev.addEventListener('click', toggleAmpm);
    var ampmCurr = document.getElementById('time-ampm-curr');
    if (ampmCurr) ampmCurr.addEventListener('click', toggleAmpm);

    // Time picker wheel support
    var colHour = document.getElementById('drum-col-hour');
    if (colHour) {
        colHour.addEventListener('wheel', function (e) {
            e.preventDefault();
            stepHour(e.deltaY < 0 ? -1 : 1);
        });
    }
    var colMin = document.getElementById('drum-col-min');
    if (colMin) {
        colMin.addEventListener('wheel', function (e) {
            e.preventDefault();
            stepMinute(e.deltaY < 0 ? -1 : 1);
        });
    }
    var colAmpm = document.getElementById('drum-col-ampm');
    if (colAmpm) {
        colAmpm.addEventListener('wheel', function (e) {
            e.preventDefault();
            toggleAmpm();
        });
    }
});

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
    openBookAppointmentModal: openAddAppointmentModal,
    closeBookAppointmentModal: closeAddAppointmentModal,
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
    switchCategory: switchModalCategory,
    toggleCustomDocMode: toggleCustomDocMode,
    resetModalForm: resetModalForm,
    resetAndBookAnother: resetModalForm,
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
});

function openReviewAppointmentModal(btn) {
    var d = btn.dataset;
    var catEl = document.getElementById('rev-category');
    var titleEl = document.getElementById('rev-title');
    var appEl = document.getElementById('rev-applicant');
    var ageEl = document.getElementById('rev-age');
    var addressEl = document.getElementById('rev-address');
    var phoneEl = document.getElementById('rev-phone');
    var emailEl = document.getElementById('rev-email');
    var timeEl = document.getElementById('rev-time');
    var purposeEl = document.getElementById('rev-purpose');
    var refEl = document.getElementById('rev-ref');
    var statusPill = document.getElementById('rev-status-pill');
    var rejectForm = document.getElementById('rev-reject-form');
    var approveForm = document.getElementById('rev-approve-form');
    var detailLink = document.getElementById('rev-detail-link');

    if (refEl) refEl.textContent = d.ref ? ('#' + d.ref) : '';
    if (catEl) catEl.textContent = 'Category: ' + (d.category || 'Appointment') + (d.service ? (' / ' + d.service) : '');
    if (titleEl) titleEl.textContent = d.service || d.title || '-';
    if (appEl) appEl.textContent = d.applicant || '-';
    if (ageEl) ageEl.textContent = d.age ? (d.age + ' years old') : 'Not specified';
    if (addressEl) addressEl.textContent = d.address || 'Barangay Address';
    if (phoneEl) phoneEl.textContent = d.phone || '-';
    if (emailEl) emailEl.textContent = d.email || '-';
    if (timeEl) timeEl.textContent = d.time || '-';
    if (purposeEl) purposeEl.textContent = d.purpose || 'Standard Request';

    if (statusPill) {
        var badgeBg = '#FEF3C7';
        var badgeCol = '#92400E';
        if (d.status === 'approved') { badgeBg = '#D1FAE5'; badgeCol = '#065F46'; }
        else if (d.status === 'completed') { badgeBg = '#E0E7FF'; badgeCol = '#3730A3'; }
        else if (d.status === 'rejected') { badgeBg = '#FEE2E2'; badgeCol = '#991B1B'; }
        statusPill.innerHTML = '<span class="badge" style="background:' + badgeBg + '; color:' + badgeCol + '; font-size:0.75rem; padding:2px 8px; border-radius:9999px; font-weight:500;">' + (d.statusDisplay || d.status) + '</span>';
    }

    var isPending = (d.status === 'pending');
    var allowApprove = isPending && (d.canApprove !== 'false');
    var allowReject = isPending && (d.canReject !== 'false');

    if (rejectForm) {
        rejectForm.action = '/appointments/' + d.id + '/reject/';
        rejectForm.style.display = allowReject ? 'inline-block' : 'none';
    }
    if (approveForm) {
        approveForm.action = '/appointments/' + d.id + '/approve/';
        approveForm.style.display = allowApprove ? 'inline-block' : 'none';
    }
    if (detailLink) detailLink.href = '/appointments/' + d.id + '/';

    var modal = document.getElementById('reviewAppointmentModal');
    if (modal) modal.style.display = 'flex';
}

function closeReviewAppointmentModal() {
    var modal = document.getElementById('reviewAppointmentModal');
    if (modal) modal.style.display = 'none';
}

// Modal action listener & backdrop dismissal with dirty changes guard
document.addEventListener('click', function (e) {
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
        return;
    }
    var addModal = document.getElementById('moduleAddAppointmentModal');
    if (addModal && e.target === addModal) {
        closeAddAppointmentModal();
        return;
    }
    var delModal = document.getElementById('deleteAppointmentModal');
    if (delModal && e.target === delModal) {
        closeDeleteAppointmentModal();
        return;
    }
});

// Track dirty changes on the booking form
document.addEventListener('input', function (e) {
    if (e.target && e.target.closest('#module-appointment-form')) {
        var form = document.getElementById('module-appointment-form');
        if (form) form.dataset.dirty = 'true';
    }
    if (e.target && e.target.id === 'modal_input_phone') {
        enforceModalPhone11Digits(e.target);
    }
});

document.addEventListener('change', function (e) {
    if (e.target && e.target.closest('#module-appointment-form')) {
        var form = document.getElementById('module-appointment-form');
        if (form) form.dataset.dirty = 'true';
    }
    if (e.target && e.target.id === 'doc_type_select') {
        handleDocSelectChange(e.target.value);
    }
    if (e.target && e.target.id === 'modal-healthcare-select') {
        onHealthServiceChanged();
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

// Escape key handling with dirty confirmation
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
        var addModal = document.getElementById('moduleAddAppointmentModal');
        if (addModal && addModal.style.display === 'flex') {
            closeAddAppointmentModal();
        }
        var revModal = document.getElementById('reviewAppointmentModal');
        if (revModal && revModal.style.display === 'flex') {
            closeReviewAppointmentModal();
        }
        var delModal = document.getElementById('deleteAppointmentModal');
        if (delModal && delModal.style.display === 'flex') {
            closeDeleteAppointmentModal();
        }
    }
});
