// Landing Page interactive logic (Strict CSP compliant: no inline scripts).

var calState = {
    year: new Date().getFullYear(),
    month: new Date().getMonth(),
    selectedDate: null,
    hour: 8,
    minute: 0,
    ampm: 'PM'
};

var HEALTH_SERVICES = [
    {
        id: 6,
        name: 'Child Immunization / Vaccination',
        days: [3, 5], // Wednesday & Friday
        daysText: 'Every Wednesday & Friday',
        timeText: '8:00 AM - 11:30 AM',
        startHour: 8,
        startMin: 0,
        startAmpm: 'AM',
        dotClass: 'dot-blue'
    },
    {
        id: 1,
        name: 'Dental Cleaning',
        days: [2, 4], // Tuesday & Thursday
        daysText: 'Every Tuesday & Thursday',
        timeText: '9:00 AM - 3:00 PM',
        startHour: 9,
        startMin: 0,
        startAmpm: 'AM',
        dotClass: 'dot-navy'
    },
    {
        id: 4,
        name: 'General Consultation',
        days: [1, 2, 3, 4, 5], // Monday - Friday
        daysText: 'Monday - Friday',
        timeText: '8:00 AM - 4:00 PM',
        startHour: 8,
        startMin: 0,
        startAmpm: 'AM',
        dotClass: 'dot-gray'
    },
    {
        id: 2,
        name: 'Health Check-up',
        days: [1, 2, 3, 4, 5], // Monday - Friday
        daysText: 'Monday - Friday',
        timeText: '8:00 AM - 12:00 PM',
        startHour: 8,
        startMin: 0,
        startAmpm: 'AM',
        dotClass: 'dot-gray'
    },
    {
        id: 5,
        name: 'Prenatal Check-up',
        days: [1, 4], // Monday & Thursday
        daysText: 'Every Monday & Thursday',
        timeText: '8:30 AM - 2:00 PM',
        startHour: 8,
        startMin: 30,
        startAmpm: 'AM',
        dotClass: 'dot-red'
    },
    {
        id: 3,
        name: 'Tooth Extraction',
        days: [2, 5], // Tuesday & Friday
        daysText: 'Every Tuesday & Friday',
        timeText: '1:00 PM - 4:30 PM',
        startHour: 1,
        startMin: 0,
        startAmpm: 'PM',
        dotClass: 'dot-green'
    }
];

var MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

var emailValidationTimeout = null;
var isEmailChecking = false;

// -----------------------------------------------------------------------------
// Format dates
// -----------------------------------------------------------------------------
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

// -----------------------------------------------------------------------------
// SCREENSHOT 2: CALENDAR RENDERING ENGINE
// -----------------------------------------------------------------------------
function renderCustomCalendar() {
    var monthSelect = document.getElementById('cal-month-select');
    var yearSelect = document.getElementById('cal-year-select');
    var grid = document.getElementById('custom-cal-grid');
    if (!grid) return;

    if (monthSelect) monthSelect.value = calState.month;
    if (yearSelect) yearSelect.value = calState.year;

    grid.innerHTML = '';

    var firstDayIndex = new Date(calState.year, calState.month, 1).getDay();
    var daysInMonth = new Date(calState.year, calState.month + 1, 0).getDate();
    var daysInPrevMonth = new Date(calState.year, calState.month, 0).getDate();

    var today = new Date();
    var todayISO = formatDateISO(today);

    // Default selectedDate to tomorrow if not set
    if (!calState.selectedDate) {
        var defaultDate = new Date();
        defaultDate.setDate(defaultDate.getDate() + 1);
        if (defaultDate.getDay() === 0) defaultDate.setDate(defaultDate.getDate() + 1);
        calState.selectedDate = formatDateISO(defaultDate);
        var dateInput = document.getElementById('modal-date-input');
        if (dateInput) dateInput.value = calState.selectedDate;
    }

    // 1. Prev month trailing days
    for (var i = firstDayIndex - 1; i >= 0; i--) {
        var prevNum = daysInPrevMonth - i;
        var prevCell = document.createElement('div');
        prevCell.className = 'cal-day-cell other-month';
        prevCell.innerHTML = '<span class="cal-day-num">' + padZero(prevNum) + '</span>';
        grid.appendChild(prevCell);
    }

    // 2. Current month days
    for (var d = 1; d <= daysInMonth; d++) {
        var cellDate = new Date(calState.year, calState.month, d);
        var cellISO = formatDateISO(cellDate);
        var dayOfWeek = cellDate.getDay();

        var cell = document.createElement('div');
        cell.className = 'cal-day-cell current-month';
        cell.setAttribute('data-date', cellISO);

        if (cellISO === calState.selectedDate) {
            cell.classList.add('selected');
        }

        // Active health services on this day of week (weekdays 1..5)
        var servicesForDay = HEALTH_SERVICES.filter(function(s) {
            return s.days.indexOf(dayOfWeek) !== -1;
        });

        if (servicesForDay.length > 0) {
            cell.classList.add('has-services');
        }

        var dotHtml = '';
        if (servicesForDay.length > 0) {
            var dotClass = servicesForDay[0].dotClass;
            dotHtml = '<span class="cal-day-dot ' + dotClass + '"></span>';
        }

        cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>' + dotHtml;

        cell.addEventListener('click', (function(iso, dow) {
            return function() {
                calState.selectedDate = iso;
                var dateInput = document.getElementById('modal-date-input');
                if (dateInput) dateInput.value = iso;
                renderCustomCalendar();
                renderHealthServicesList(iso, dow);
                updateSchedulePreview();
                fetchFreeHealthServices();
            };
        })(cellISO, dayOfWeek));

        grid.appendChild(cell);
    }

    // 3. Next month leading days (to fill 35 or 42 cells)
    var totalRendered = firstDayIndex + daysInMonth;
    var totalCells = totalRendered > 35 ? 42 : 35;
    var remaining = totalCells - totalRendered;
    for (var n = 1; n <= remaining; n++) {
        var nextCell = document.createElement('div');
        nextCell.className = 'cal-day-cell other-month';
        nextCell.innerHTML = '<span class="cal-day-num">' + padZero(n) + '</span>';
        grid.appendChild(nextCell);
    }

    // Update services list for currently selected date
    if (calState.selectedDate) {
        var parts = calState.selectedDate.split('-');
        var selD = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        renderHealthServicesList(calState.selectedDate, selD.getDay());
    }
}

// -----------------------------------------------------------------------------
// SCREENSHOT 2: HEALTH SERVICES AVAILABLE / OPEN LIST
// -----------------------------------------------------------------------------
function renderHealthServicesList(selectedDateISO, dayOfWeek) {
    var container = document.getElementById('cal-services-list');
    var counter = document.getElementById('cal-services-counter');
    if (!container) return;

    // Filter services open on the selected weekday
    var openSvcs = HEALTH_SERVICES.filter(function(s) {
        return s.days.indexOf(dayOfWeek) !== -1;
    });

    var displayList = openSvcs.length > 0 ? openSvcs : HEALTH_SERVICES;

    if (counter) {
        counter.textContent = openSvcs.length > 0 ? openSvcs.length + ' Open Today' : 'All Clinics';
    }

    container.innerHTML = '';

    displayList.forEach(function(svc) {
        var card = document.createElement('div');
        card.className = 'cal-service-card';
        card.setAttribute('data-service-id', svc.id);

        var dateLabel = selectedDateISO ? formatDisplayDate(selectedDateISO) : svc.daysText;

        card.innerHTML =
            '<div class="service-card-dot ' + svc.dotClass + '"></div>' +
            '<div style="flex: 1;">' +
                '<div class="service-card-datetime">' + dateLabel + ' • ' + svc.timeText + '</div>' +
                '<div class="service-card-name">' + svc.name + ' <span style="font-weight: 700; color: #111827;">(Free)</span></div>' +
            '</div>';

        card.addEventListener('click', function() {
            // Select in health dropdown
            var healthSelect = document.getElementById('modal-health-select');
            if (healthSelect) {
                healthSelect.value = svc.id;
            }

            // Switch category to healthcare
            switchCategory('healthcare');

            // Sync time picker to this service start time
            setTimePicker(svc.startHour, svc.startMin, svc.startAmpm);

            // Highlight this card
            var allCards = container.querySelectorAll('.cal-service-card');
            allCards.forEach(function(c) { c.classList.remove('selected'); });
            card.classList.add('selected');

            updateSchedulePreview();
        });

        container.appendChild(card);
    });
}

// -----------------------------------------------------------------------------
// SCREENSHOT 3: TIME PICKER COMPONENT
// -----------------------------------------------------------------------------
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

    // Hour column
    var prevH = calState.hour === 1 ? 12 : calState.hour - 1;
    var nextH = calState.hour === 12 ? 1 : calState.hour + 1;
    if (hourPrev) hourPrev.textContent = prevH;
    if (hourCurr) hourCurr.textContent = calState.hour;
    if (hourNext) hourNext.textContent = nextH;

    // Minute column (5-min intervals)
    var prevM = (calState.minute - 5 + 60) % 60;
    var nextM = (calState.minute + 5) % 60;
    if (minPrev) minPrev.textContent = padZero(prevM);
    if (minCurr) minCurr.textContent = minStr;
    if (minNext) minNext.textContent = padZero(nextM);

    // AM/PM column
    var altAmpm = calState.ampm === 'PM' ? 'AM' : 'PM';
    if (ampmPrev) ampmPrev.textContent = altAmpm;
    if (ampmCurr) ampmCurr.textContent = calState.ampm;
    if (ampmNext) ampmNext.innerHTML = '&nbsp;';

    // Sync form inputs
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

// -----------------------------------------------------------------------------
// MODAL CONTROLS & EVENT BINDINGS
// -----------------------------------------------------------------------------
function openBookAppointmentModal() {
    var modal = document.getElementById('bookAppointmentModal');
    var bodyContainer = document.getElementById('modal-body-container');
    var successContainer = document.getElementById('modal-success-container');

    if (bodyContainer) bodyContainer.style.display = 'block';
    if (successContainer) successContainer.style.display = 'none';
    if (modal) modal.style.display = 'flex';

    // Initialize calendar and time picker
    renderCustomCalendar();
    renderTimePicker();

    var currentCat = document.getElementById('form-category-input') ? document.getElementById('form-category-input').value : 'document';
    switchCategory(currentCat || 'document');
}

function closeBookAppointmentModal() {
    var modal = document.getElementById('bookAppointmentModal');
    if (modal) modal.style.display = 'none';
}

function fetchFreeHealthServices() {
    var dateVal = document.getElementById('modal-date-input') ? document.getElementById('modal-date-input').value : '';
    var timeSlotSelect = document.getElementById('modal-time-slot');
    var windowVal = timeSlotSelect ? timeSlotSelect.value : 'morning';
    var selectEl = document.getElementById('modal-health-select');
    if (!selectEl) return;

    fetch('/appointments/api/services/?category=healthcare&date=' + encodeURIComponent(dateVal) + '&window=' + encodeURIComponent(windowVal), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.status === 'ok' && data.health_services && data.health_services.length > 0) {
            selectEl.innerHTML = '';
            data.health_services.forEach(function(svc) {
                var opt = document.createElement('option');
                opt.value = svc.id;
                opt.textContent = svc.name + ' (Free)';
                selectEl.appendChild(opt);
            });
        }
    })
    .catch(function(err) {
        console.warn('Could not fetch free health services:', err);
    });
}

function switchCategory(cat) {
    var pillDoc = document.getElementById('pill-doc');
    var pillHealth = document.getElementById('pill-health');
    var catInput = document.getElementById('form-category-input');
    var docContainer = document.getElementById('subservice-doc-container');
    var healthContainer = document.getElementById('subservice-health-container');
    var purposeContainer = document.getElementById('landing-purpose-container');
    var purposeInput = document.getElementById('input_purpose');
    var healthServicesSection = document.getElementById('health-services-section');

    if (cat === 'document') {
        if (pillDoc) pillDoc.classList.add('active');
        if (pillHealth) pillHealth.classList.remove('active');
        if (catInput) catInput.value = 'document';
        if (docContainer) docContainer.style.display = 'block';
        if (healthContainer) healthContainer.style.display = 'none';
        if (purposeContainer) purposeContainer.style.display = 'block';
        if (purposeInput) purposeInput.required = true;
        if (healthServicesSection) healthServicesSection.style.display = 'none';
    } else {
        if (pillHealth) pillHealth.classList.add('active');
        if (pillDoc) pillDoc.classList.remove('active');
        if (catInput) catInput.value = 'healthcare';
        if (docContainer) docContainer.style.display = 'none';
        if (healthContainer) healthContainer.style.display = 'block';
        if (purposeContainer) purposeContainer.style.display = 'none';
        if (purposeInput) {
            purposeInput.required = false;
            purposeInput.value = '';
        }
        if (healthServicesSection) healthServicesSection.style.display = 'block';
        fetchFreeHealthServices();
    }
}

// Phone number restriction: strictly 11 digits
function enforcePhone11Digits(input) {
    var val = input.value.replace(/[^0-9]/g, '');
    if (val.length > 11) {
        val = val.substring(0, 11);
    }
    input.value = val;

    var feedback = document.getElementById('phone-feedback');
    if (!feedback) return;

    if (val.length === 11) {
        if (val.startsWith('09')) {
            feedback.innerHTML = '<span style="color: #111827;">' + BrgyUI.icon('check') + ' Valid 11-digit mobile number</span>';
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

// Live Abstract API Email validation
function validateEmailLive(email) {
    var feedback = document.getElementById('email-verification-feedback');
    var emailInput = document.getElementById('input_email');
    email = (email || '').trim();

    if (!feedback || !emailInput) return;

    if (!email) {
        feedback.innerHTML = '';
        emailInput.classList.remove('input-error');
        return;
    }

    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        feedback.innerHTML = '<span style="color: #DC2626;">' + BrgyUI.icon('triangle-alert') + ' Invalid email format</span>';
        emailInput.classList.add('input-error');
        return;
    }

    feedback.innerHTML = '';
    emailInput.classList.remove('input-error');
}

// Handle AJAX booking submission
function handlePublicBookingSubmit(e) {
    e.preventDefault();
    var form = document.getElementById('public-booking-form');
    var btn = document.getElementById('btn-submit-public-booking');
    var errBanner = document.getElementById('booking-error-banner');
    var errText = document.getElementById('booking-error-text');

    var phoneInput = document.getElementById('input_phone_number');
    var phoneVal = phoneInput ? phoneInput.value : '';
    if (!/^09\d{9}$/.test(phoneVal)) {
        if (errBanner) errBanner.style.display = 'block';
        if (errText) errText.innerText = "Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567).";
        return;
    }

    btn.disabled = true;
    btn.innerHTML = BrgyUI.icon('loader-circle') + ' Submitting Request...';
    if (errBanner) errBanner.style.display = 'none';

    var formData = new FormData(form);

    fetch('/appointments/api/public-book/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(function(response) {
        return response.json().then(function(data) {
            return { ok: response.ok, data: data };
        });
    })
    .then(function(res) {
        btn.disabled = false;
        btn.innerHTML = BrgyUI.icon('send') + ' Submit Appointment Request';

        if (res.ok && res.data.status === 'ok') {
            document.getElementById('success-ref-badge').innerText = res.data.ref_number || 'REF #APT-NEW';
            document.getElementById('summary-applicant-name').innerText = res.data.applicant_name;
            document.getElementById('summary-service-title').innerText = res.data.service_title;
            document.getElementById('summary-schedule').innerText = res.data.scheduled_date + ' (' + res.data.time_slot + ')';
            document.getElementById('summary-contact').innerText = res.data.applicant_email + ' | ' + res.data.applicant_phone;
            var msgEl = document.getElementById('success-required-message');
            msgEl.textContent = 'Wait for the email sent for approved your appointment date. We will notify via email please keep track on you email. Thank you if you have any question please contact ';
            var phoneStrong = document.createElement('strong');
            phoneStrong.textContent = res.data.admin_phone || '';
            msgEl.appendChild(phoneStrong);
            msgEl.appendChild(document.createTextNode('.'));

            document.getElementById('modal-body-container').style.display = 'none';
            document.getElementById('modal-success-container').style.display = 'block';
            form.reset();
        } else {
            if (errBanner) errBanner.style.display = 'block';
            if (res.data.errors) {
                var firstErrKey = Object.keys(res.data.errors)[0];
                if (errText) errText.innerText = res.data.errors[firstErrKey];
            } else {
                if (errText) errText.innerText = res.data.message || res.data.error || 'Error booking appointment. Please review the form.';
            }
        }
    })
    .catch(function(err) {
        btn.disabled = false;
        btn.innerHTML = BrgyUI.icon('send') + ' Submit Appointment Request';
        if (errBanner) errBanner.style.display = 'block';
        if (errText) errText.innerText = 'Network error or connection timed out. Please try again.';
    });
}

function resetAndBookAnother() {
    document.getElementById('modal-body-container').style.display = 'block';
    document.getElementById('modal-success-container').style.display = 'none';
    renderCustomCalendar();
    renderTimePicker();
}

// -----------------------------------------------------------------------------
// DOM INITIALIZATION
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
    // Month dropdown change
    var monthSelect = document.getElementById('cal-month-select');
    if (monthSelect) {
        monthSelect.addEventListener('change', function() {
            calState.month = parseInt(this.value, 10);
            renderCustomCalendar();
        });
    }

    // Year dropdown change
    var yearSelect = document.getElementById('cal-year-select');
    if (yearSelect) {
        yearSelect.addEventListener('change', function() {
            calState.year = parseInt(this.value, 10);
            renderCustomCalendar();
        });
    }

    // Today button
    var todayBtn = document.getElementById('cal-today-btn');
    if (todayBtn) {
        todayBtn.addEventListener('click', function() {
            var now = new Date();
            calState.year = now.getFullYear();
            calState.month = now.getMonth();
            calState.selectedDate = formatDateISO(now);
            var dateInput = document.getElementById('modal-date-input');
            if (dateInput) dateInput.value = calState.selectedDate;
            renderCustomCalendar();
        });
    }

    // Circular arrow navigation
    var prevBtn = document.getElementById('cal-prev-btn');
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
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
        nextBtn.addEventListener('click', function() {
            if (calState.month === 11) {
                calState.month = 0;
                calState.year += 1;
            } else {
                calState.month += 1;
            }
            renderCustomCalendar();
        });
    }

    // Time picker click steppers
    var hourPrev = document.getElementById('time-hour-prev');
    if (hourPrev) hourPrev.addEventListener('click', function() { stepHour(-1); });
    var hourNext = document.getElementById('time-hour-next');
    if (hourNext) hourNext.addEventListener('click', function() { stepHour(1); });
    var hourCurr = document.getElementById('time-hour-curr');
    if (hourCurr) hourCurr.addEventListener('click', function() { stepHour(1); });

    var minPrev = document.getElementById('time-min-prev');
    if (minPrev) minPrev.addEventListener('click', function() { stepMinute(-1); });
    var minNext = document.getElementById('time-min-next');
    if (minNext) minNext.addEventListener('click', function() { stepMinute(1); });
    var minCurr = document.getElementById('time-min-curr');
    if (minCurr) minCurr.addEventListener('click', function() { stepMinute(1); });

    var ampmPrev = document.getElementById('time-ampm-prev');
    if (ampmPrev) ampmPrev.addEventListener('click', toggleAmpm);
    var ampmCurr = document.getElementById('time-ampm-curr');
    if (ampmCurr) ampmCurr.addEventListener('click', toggleAmpm);

    // Time picker mouse wheel support
    var colHour = document.getElementById('drum-col-hour');
    if (colHour) {
        colHour.addEventListener('wheel', function(e) {
            e.preventDefault();
            stepHour(e.deltaY < 0 ? -1 : 1);
        });
    }

    var colMin = document.getElementById('drum-col-min');
    if (colMin) {
        colMin.addEventListener('wheel', function(e) {
            e.preventDefault();
            stepMinute(e.deltaY < 0 ? -1 : 1);
        });
    }

    var colAmpm = document.getElementById('drum-col-ampm');
    if (colAmpm) {
        colAmpm.addEventListener('wheel', function(e) {
            e.preventDefault();
            toggleAmpm();
        });
    }

    // Delegated actions
    var LANDING_CALLABLE = {
        openBookAppointmentModal: openBookAppointmentModal,
        closeBookAppointmentModal: closeBookAppointmentModal,
        switchCategory: switchCategory,
        resetAndBookAnother: resetAndBookAnother
    };

    document.addEventListener('click', function(e) {
        var callEl = e.target.closest('[data-call]');
        if (!callEl) return;
        var fn = LANDING_CALLABLE[callEl.getAttribute('data-call')];
        if (!fn) return;
        e.preventDefault();
        var arg = callEl.getAttribute('data-arg');
        if (arg === null) { fn(); } else { fn(arg); }
    });

    document.addEventListener('submit', function(e) {
        if (e.target && e.target.id === 'public-booking-form') {
            handlePublicBookingSubmit(e);
        }
    });

    document.addEventListener('focusout', function(e) {
        if (e.target && e.target.id === 'input_email') {
            validateEmailLive(e.target.value);
        }
    });

    document.addEventListener('input', function(e) {
        if (e.target && e.target.id === 'input_phone_number') {
            enforcePhone11Digits(e.target);
        }
    });

    // Close on backdrop click
    document.addEventListener('click', function(e) {
        var bookModal = document.getElementById('bookAppointmentModal');
        if (e.target === bookModal) closeBookAppointmentModal();
    });

    // Render calendar and time picker immediately on DOM ready
    renderCustomCalendar();
    renderTimePicker();
    switchCategory('document');

    if (window.location.hash === '#bookAppointmentModal') {
        openBookAppointmentModal();
    }

    window.addEventListener('hashchange', function() {
        if (window.location.hash === '#bookAppointmentModal') {
            openBookAppointmentModal();
        }
    });
});

