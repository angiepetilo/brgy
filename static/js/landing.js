// Landing Page interactive logic (Strict CSP compliant: no inline scripts).

var calState = {
    year: new Date().getFullYear(),
    month: new Date().getMonth(),
    selectedDate: null,
    hour: 8,
    minute: 0,
    ampm: 'PM'
};

// Dynamic health services loader (Strict CSP compliant: reads from JSON script tag)
function loadHealthServices() {
    var scriptEl = document.getElementById('health-services-data');
    if (!scriptEl) return [];
    try {
        var raw = JSON.parse(scriptEl.textContent.trim());
        if (Array.isArray(raw)) {
            var colors = ['dot-blue', 'dot-navy', 'dot-green', 'dot-red', 'dot-gray'];
            return raw.map(function(item, idx) {
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
                if (days.length === 0) {
                    days = [1, 2, 3, 4, 5];
                }

                var timeText = item.timeText || '8:00 AM - 5:00 PM';
                var startHour = 8;
                var startMin = 0;
                var startAmpm = 'AM';
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
// CALENDAR RENDERING ENGINE (Shadcn Calendar mode="single" captionLayout="dropdown")
// -----------------------------------------------------------------------------
function renderCustomCalendar() {
    var monthSelect = document.getElementById('cal-month-select');
    var yearSelect = document.getElementById('cal-year-select');
    var grid = document.getElementById('custom-cal-grid');
    if (!grid) return;

    // Populate year dropdown if needed
    if (yearSelect && yearSelect.options.length <= 1) {
        var currentY = new Date().getFullYear();
        yearSelect.innerHTML = '';
        for (var yr = currentY - 1; yr <= currentY + 6; yr++) {
            var opt = document.createElement('option');
            opt.value = yr;
            opt.textContent = yr;
            yearSelect.appendChild(opt);
        }
    }

    if (monthSelect) monthSelect.value = calState.month;
    if (yearSelect) yearSelect.value = calState.year;

    grid.innerHTML = '';

    var firstDayIndex = new Date(calState.year, calState.month, 1).getDay();
    var daysInMonth = new Date(calState.year, calState.month + 1, 0).getDate();
    var daysInPrevMonth = new Date(calState.year, calState.month, 0).getDate();

    var today = new Date();
    today.setHours(0, 0, 0, 0);
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

    // Load active services dynamically from DOM
    var dynamicServices = loadHealthServices();

    // 1. Prev month trailing days
    for (var i = firstDayIndex - 1; i >= 0; i--) {
        var prevNum = daysInPrevMonth - i;
        var prevDate = new Date(calState.year, calState.month - 1, prevNum);
        prevDate.setHours(0, 0, 0, 0);
        var prevISO = formatDateISO(prevDate);
        var isPastPrev = prevDate < today;

        var prevCell = document.createElement('div');
        prevCell.className = 'cal-day-cell other-month' + (isPastPrev ? ' past' : '');
        prevCell.setAttribute('data-date', prevISO);
        prevCell.innerHTML = '<span class="cal-day-num">' + padZero(prevNum) + '</span>';

        if (!isPastPrev) {
            prevCell.addEventListener('click', (function(pDate, pISO) {
                return function() {
                    calState.year = pDate.getFullYear();
                    calState.month = pDate.getMonth();
                    calState.selectedDate = pISO;
                    var dateInput = document.getElementById('modal-date-input');
                    if (dateInput) dateInput.value = pISO;
                    renderCustomCalendar();
                    updateSchedulePreview();
                    fetchFreeHealthServices();
                };
            })(prevDate, prevISO));
        }

        grid.appendChild(prevCell);
    }

    // 2. Current month days (mode="single")
    for (var d = 1; d <= daysInMonth; d++) {
        var cellDate = new Date(calState.year, calState.month, d);
        cellDate.setHours(0, 0, 0, 0);
        var cellISO = formatDateISO(cellDate);
        var dayOfWeek = cellDate.getDay();
        var isPast = cellDate < today;
        var isToday = cellISO === todayISO;
        var isSelected = cellISO === calState.selectedDate;

        var cell = document.createElement('div');
        cell.className = 'cal-day-cell current-month';
        cell.setAttribute('data-date', cellISO);

        if (isPast) cell.classList.add('past');
        if (isToday) cell.classList.add('today');
        if (isSelected) cell.classList.add('selected');

        // Active health services on this day of week (strictly dynamic)
        var servicesForDay = dynamicServices.filter(function(s) {
            return s.days.indexOf(dayOfWeek) !== -1;
        });

        var dotHtml = '';
        if (servicesForDay.length > 0 && !isPast) {
            cell.classList.add('has-services');
            var dotClass = servicesForDay[0].dotClass || 'dot-blue';
            dotHtml = '<span class="cal-day-dot ' + dotClass + '"></span>';
        }

        cell.innerHTML = '<span class="cal-day-num">' + padZero(d) + '</span>' + dotHtml;

        if (!isPast) {
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
        }

        grid.appendChild(cell);
    }

    // 3. Next month leading days (to fill 35 or 42 cells)
    var totalRendered = firstDayIndex + daysInMonth;
    var totalCells = totalRendered > 35 ? 42 : 35;
    var remaining = totalCells - totalRendered;
    for (var n = 1; n <= remaining; n++) {
        var nextDate = new Date(calState.year, calState.month + 1, n);
        nextDate.setHours(0, 0, 0, 0);
        var nextISO = formatDateISO(nextDate);

        var nextCell = document.createElement('div');
        nextCell.className = 'cal-day-cell other-month';
        nextCell.setAttribute('data-date', nextISO);
        nextCell.innerHTML = '<span class="cal-day-num">' + padZero(n) + '</span>';

        nextCell.addEventListener('click', (function(nDate, nISO) {
            return function() {
                calState.year = nDate.getFullYear();
                calState.month = nDate.getMonth();
                calState.selectedDate = nISO;
                var dateInput = document.getElementById('modal-date-input');
                if (dateInput) dateInput.value = nISO;
                renderCustomCalendar();
                updateSchedulePreview();
                fetchFreeHealthServices();
            };
        })(nextDate, nextISO));

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
// DYNAMIC HEALTH SERVICES AVAILABLE / OPEN LIST
// -----------------------------------------------------------------------------
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

    // Filter services open on the selected weekday
    var openSvcs = services.filter(function(s) {
        return s.days.indexOf(dayOfWeek) !== -1;
    });

    var displayList = openSvcs.length > 0 ? openSvcs : services;

    if (counter) {
        counter.textContent = openSvcs.length > 0 ? openSvcs.length + ' Open Today' : services.length + ' Total';
    }

    container.innerHTML = '';

    displayList.forEach(function(svc) {
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

        card.addEventListener('click', function() {
            var healthSelect = document.getElementById('modal-health-select');
            if (healthSelect) {
                healthSelect.value = svc.id;
            }

            switchCategory('healthcare');
            setTimePicker(svc.startHour, svc.startMin, svc.startAmpm);

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

// =============================================================================
// SIMPLIFIED 5-STEP ACCESSIBLE BOOKING WIZARD (<BookingWizard />)
// =============================================================================
var BookingWizard = (function() {
    var state = {
        step: 1,
        category: null,      // 'healthcare' or 'document'
        serviceId: null,
        serviceName: '',
        serviceHours: '8:00 AM to 5:00 PM',
        serviceDays: 'Monday - Friday',
        isFree: true,
        fee: 0,
        date: null,          // 'YYYY-MM-DD'
        dateDisplay: '',     // 'Thursday, October 24, 2026'
        timeWindow: 'morning',
        timeExact: null,     // e.g. '09:00 AM'
        calYear: new Date().getFullYear(),
        calMonth: new Date().getMonth(),
        details: {
            firstName: '',
            middleName: '',
            lastName: '',
            age: '',
            address: '',
            phone: '',
            email: ''
        }
    };

    var WIZ_MONTH_NAMES = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    var WIZ_DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

    function padZero(n) {
        return n < 10 ? '0' + n : '' + n;
    }

    function formatDateISO(d) {
        return d.getFullYear() + '-' + padZero(d.getMonth() + 1) + '-' + padZero(d.getDate());
    }

    function init() {
        bindHeaderActions();
        bindStep1();
        bindStep2();
        bindStep3();
        bindStep4();
        bindStep5();
        bindFooter();
    }

    function openModal() {
        var modal = document.getElementById('bookAppointmentModal');
        if (!modal) return;
        modal.style.display = 'flex';
        goToStep(state.step || 1);
        var container = document.getElementById('wizard-container');
        if (container) container.focus();
    }

    function closeModal() {
        var modal = document.getElementById('bookAppointmentModal');
        if (modal) modal.style.display = 'none';
    }

    function bindHeaderActions() {
        var btnNorm = document.getElementById('wizard-font-normal');
        var btnLrg = document.getElementById('wizard-font-large');
        var container = document.getElementById('wizard-container');

        if (btnNorm && btnLrg && container) {
            btnNorm.addEventListener('click', function() {
                container.setAttribute('data-font-size', 'normal');
                btnNorm.classList.add('active');
                btnNorm.setAttribute('aria-pressed', 'true');
                btnLrg.classList.remove('active');
                btnLrg.setAttribute('aria-pressed', 'false');
            });

            btnLrg.addEventListener('click', function() {
                container.setAttribute('data-font-size', 'large');
                btnLrg.classList.add('active');
                btnLrg.setAttribute('aria-pressed', 'true');
                btnNorm.classList.remove('active');
                btnNorm.setAttribute('aria-pressed', 'false');
            });
        }

        var closeBtn = document.getElementById('wizard-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeModal);
        }
    }

    function goToStep(n) {
        state.step = n;
        for (var i = 1; i <= 5; i++) {
            var stepEl = document.getElementById('wizard-step-' + i);
            if (stepEl) stepEl.style.display = (i === n ? 'block' : 'none');
        }
        var successEl = document.getElementById('wizard-success-screen');
        if (successEl) successEl.style.display = 'none';

        for (var s = 1; s <= 5; s++) {
            var seg = document.getElementById('progress-seg-' + s);
            if (seg) {
                seg.className = 'wizard-progress-segment';
                if (s < n) seg.classList.add('completed');
                else if (s === n) seg.classList.add('current');
                else seg.classList.add('upcoming');
            }
        }
        var counter = document.getElementById('wizard-step-counter');
        if (counter) counter.textContent = 'Step ' + n + ' of 5';

        var progSection = document.getElementById('wizard-progress-section');
        if (progSection) progSection.style.display = 'flex';

        var helpBox = document.getElementById('wizard-help-box');
        if (helpBox) helpBox.style.display = (n <= 4 ? 'flex' : 'none');

        var footer = document.getElementById('wizard-footer');
        if (footer) footer.style.display = 'flex';

        var backBtn = document.getElementById('wizard-btn-back');
        if (backBtn) backBtn.style.display = (n > 1 ? 'inline-flex' : 'none');

        var nextBtn = document.getElementById('wizard-btn-next');
        if (nextBtn) {
            if (n === 5) {
                nextBtn.innerHTML = 'Send request ' + (window.BrgyUI ? BrgyUI.icon('send') : '');
                nextBtn.disabled = false;
            } else {
                nextBtn.innerHTML = 'Next ' + (window.BrgyUI ? BrgyUI.icon('chevron-right') : '');
                updateNextButtonState();
            }
        }

        if (n === 2) {
            renderCalendar();
        } else if (n === 3) {
            renderTimeSlots();
        } else if (n === 5) {
            populateSummary();
        }

        var body = document.getElementById('wizard-body');
        if (body) body.scrollTop = 0;
    }

    function updateNextButtonState() {
        var nextBtn = document.getElementById('wizard-btn-next');
        if (!nextBtn) return;
        if (state.step === 1) {
            nextBtn.disabled = !state.serviceId;
        } else if (state.step === 2) {
            nextBtn.disabled = !state.date;
        } else if (state.step === 3) {
            nextBtn.disabled = !state.timeExact;
        } else if (state.step === 4) {
            nextBtn.disabled = false;
        } else if (state.step === 5) {
            nextBtn.disabled = false;
        }
    }

    function bindStep1() {
        var cardHealth = document.getElementById('card-cat-health');
        var cardDoc = document.getElementById('card-cat-doc');
        var subSection = document.getElementById('subservices-section');
        var groupHealth = document.getElementById('health-services-radiogroup');
        var groupDoc = document.getElementById('document-services-radiogroup');

        function selectCategory(cat) {
            state.category = cat;
            state.serviceId = null;
            state.serviceName = '';
            updateNextButtonState();

            if (cat === 'healthcare') {
                if (cardHealth) { cardHealth.classList.add('selected'); cardHealth.setAttribute('aria-checked', 'true'); }
                if (cardDoc) { cardDoc.classList.remove('selected'); cardDoc.setAttribute('aria-checked', 'false'); }
                if (subSection) subSection.style.display = 'block';
                if (groupHealth) groupHealth.style.display = 'flex';
                if (groupDoc) groupDoc.style.display = 'none';
            } else {
                if (cardDoc) { cardDoc.classList.add('selected'); cardDoc.setAttribute('aria-checked', 'true'); }
                if (cardHealth) { cardHealth.classList.remove('selected'); cardHealth.setAttribute('aria-checked', 'false'); }
                if (subSection) subSection.style.display = 'block';
                if (groupHealth) groupHealth.style.display = 'none';
                if (groupDoc) groupDoc.style.display = 'flex';
            }

            var cards = document.querySelectorAll('.wizard-service-card');
            cards.forEach(function(c) {
                c.classList.remove('selected');
                c.setAttribute('aria-checked', 'false');
            });

            var catInput = document.getElementById('form-category-input');
            if (catInput) catInput.value = cat;
        }

        if (cardHealth) {
            cardHealth.addEventListener('click', function() { selectCategory('healthcare'); });
            cardHealth.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectCategory('healthcare'); } });
        }
        if (cardDoc) {
            cardDoc.addEventListener('click', function() { selectCategory('document'); });
            cardDoc.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectCategory('document'); } });
        }

        document.addEventListener('click', function(e) {
            var card = e.target.closest('.wizard-service-card');
            if (!card) return;
            var group = card.closest('.wizard-services-list');
            if (group) {
                group.querySelectorAll('.wizard-service-card').forEach(function(c) {
                    c.classList.remove('selected');
                    c.setAttribute('aria-checked', 'false');
                });
            }
            card.classList.add('selected');
            card.setAttribute('aria-checked', 'true');

            state.serviceId = card.getAttribute('data-service-id');
            state.serviceName = card.getAttribute('data-service-name');
            state.serviceHours = card.getAttribute('data-service-hours') || '8:00 AM to 5:00 PM';
            state.serviceDays = card.getAttribute('data-service-days') || 'Monday - Friday';
            state.isFree = card.getAttribute('data-is-free') === 'true';

            var docInput = document.getElementById('form-doc-input');
            var healthInput = document.getElementById('form-health-input');
            if (state.category === 'document') {
                if (docInput) docInput.value = state.serviceId;
                if (healthInput) healthInput.value = '';
            } else {
                if (healthInput) healthInput.value = state.serviceId;
                if (docInput) docInput.value = '';
            }

            updateNextButtonState();
        });
    }

    function bindStep2() {
        var prevBtn = document.getElementById('wizard-cal-prev');
        var nextBtn = document.getElementById('wizard-cal-next');

        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                var now = new Date();
                var curY = now.getFullYear();
                var curM = now.getMonth();
                if (state.calYear < curY || (state.calYear === curY && state.calMonth <= curM)) {
                    return;
                }
                if (state.calMonth === 0) {
                    state.calMonth = 11;
                    state.calYear -= 1;
                } else {
                    state.calMonth -= 1;
                }
                renderCalendar();
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (state.calMonth === 11) {
                    state.calMonth = 0;
                    state.calYear += 1;
                } else {
                    state.calMonth += 1;
                }
                renderCalendar();
            });
        }
    }

    function renderCalendar() {
        var monthTitle = document.getElementById('wizard-cal-month-title');
        var prevBtn = document.getElementById('wizard-cal-prev');
        var grid = document.getElementById('wizard-cal-grid');
        if (!grid) return;

        var now = new Date();
        var curY = now.getFullYear();
        var curM = now.getMonth();

        if (monthTitle) {
            monthTitle.textContent = WIZ_MONTH_NAMES[state.calMonth] + ' ' + state.calYear;
        }

        if (prevBtn) {
            prevBtn.disabled = (state.calYear < curY || (state.calYear === curY && state.calMonth <= curM));
        }

        grid.innerHTML = '';

        var firstDayIdx = new Date(state.calYear, state.calMonth, 1).getDay();
        var daysInMonth = new Date(state.calYear, state.calMonth + 1, 0).getDate();

        var today = new Date();
        today.setHours(0, 0, 0, 0);

        for (var i = firstDayIdx - 1; i >= 0; i--) {
            var blank = document.createElement('div');
            blank.className = 'wizard-cal-day other-month';
            grid.appendChild(blank);
        }

        var activeDays = [1, 2, 3, 4, 5];
        var daysStr = (state.serviceDays || '').toLowerCase();
        if (daysStr) {
            if (daysStr.indexOf('mon') !== -1 && daysStr.indexOf('fri') !== -1) {
                activeDays = [1, 2, 3, 4, 5];
            } else {
                var parsed = [];
                if (daysStr.indexOf('mon') !== -1) parsed.push(1);
                if (daysStr.indexOf('tue') !== -1) parsed.push(2);
                if (daysStr.indexOf('wed') !== -1) parsed.push(3);
                if (daysStr.indexOf('thu') !== -1) parsed.push(4);
                if (daysStr.indexOf('fri') !== -1) parsed.push(5);
                if (daysStr.indexOf('sat') !== -1) parsed.push(6);
                if (daysStr.indexOf('sun') !== -1) parsed.push(0);
                if (parsed.length > 0) activeDays = parsed;
            }
        }

        for (var d = 1; d <= daysInMonth; d++) {
            var cellDate = new Date(state.calYear, state.calMonth, d);
            cellDate.setHours(0, 0, 0, 0);
            var iso = formatDateISO(cellDate);
            var dow = cellDate.getDay();
            var isPast = cellDate <= today;
            var isOpen = (!isPast && activeDays.indexOf(dow) !== -1);
            var isSelected = (state.date === iso);

            var cell = document.createElement('div');
            cell.className = 'wizard-cal-day';
            cell.textContent = d;
            cell.setAttribute('data-date', iso);

            if (isSelected) {
                cell.classList.add('day-selected');
                cell.setAttribute('aria-selected', 'true');
            } else if (isOpen) {
                cell.classList.add('day-open');
                cell.setAttribute('tabindex', '0');
                cell.setAttribute('role', 'button');
                cell.setAttribute('aria-label', WIZ_DAY_NAMES[dow] + ', ' + WIZ_MONTH_NAMES[state.calMonth] + ' ' + d + ', open');
                cell.addEventListener('click', (function(dateIso, dayOfWeek, dayNum) {
                    return function() {
                        selectDay(dateIso, dayOfWeek, dayNum);
                    };
                })(iso, dow, d));
            } else {
                cell.classList.add('day-closed');
                cell.setAttribute('aria-disabled', 'true');
            }

            grid.appendChild(cell);
        }

        updateDateConfirmation();
    }

    function selectDay(iso, dow, dayNum) {
        state.date = iso;
        state.dateDisplay = WIZ_DAY_NAMES[dow] + ', ' + WIZ_MONTH_NAMES[state.calMonth] + ' ' + dayNum + ', ' + state.calYear;

        var dateInput = document.getElementById('modal-date-input');
        if (dateInput) dateInput.value = iso;

        renderCalendar();
        updateDateConfirmation();
        updateNextButtonState();
    }

    function updateDateConfirmation() {
        var box = document.getElementById('wizard-day-confirmation');
        var text = document.getElementById('wizard-confirmed-day-text');
        if (!box || !text) return;
        if (state.date && state.dateDisplay) {
            box.style.display = 'flex';
            text.textContent = state.dateDisplay;
        } else {
            box.style.display = 'none';
        }
    }

    function bindStep3() {}

    function renderTimeSlots() {
        var morningGrid = document.getElementById('wizard-time-morning-grid');
        var afternoonGrid = document.getElementById('wizard-time-afternoon-grid');
        if (!morningGrid || !afternoonGrid) return;

        morningGrid.innerHTML = '';
        afternoonGrid.innerHTML = '';

        var startH = 8;
        var endH = 17;

        var m = (state.serviceHours || '').match(/(\d+):?(\d*)\s*(AM|PM)\s*(-|to)\s*(\d+):?(\d*)\s*(AM|PM)/i);
        if (m) {
            var h1 = parseInt(m[1], 10);
            var ampm1 = m[3].toUpperCase();
            var h2 = parseInt(m[5], 10);
            var ampm2 = m[7].toUpperCase();
            if (ampm1 === 'PM' && h1 < 12) h1 += 12;
            if (ampm1 === 'AM' && h1 === 12) h1 = 0;
            if (ampm2 === 'PM' && h2 < 12) h2 += 12;
            if (ampm2 === 'AM' && h2 === 12) h2 = 0;
            startH = h1;
            endH = h2;
        }

        var latestStart = endH - 1;

        for (var h = startH; h <= latestStart; h++) {
            var isMorning = h < 12;
            var displayH = h % 12 === 0 ? 12 : h % 12;
            var ampm = h < 12 ? 'AM' : 'PM';
            var timeString = displayH + ':00 ' + ampm;
            var isSelected = (state.timeExact === timeString);

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'wizard-time-btn' + (isSelected ? ' selected' : '');
            btn.textContent = timeString;
            btn.setAttribute('role', 'radio');
            btn.setAttribute('aria-checked', isSelected ? 'true' : 'false');

            btn.addEventListener('click', (function(timeStr, morningFlag) {
                return function() {
                    selectTime(timeStr, morningFlag);
                };
            })(timeString, isMorning));

            if (isMorning) {
                morningGrid.appendChild(btn);
            } else {
                afternoonGrid.appendChild(btn);
            }
        }

        updateTimeConfirmation();
    }

    function selectTime(timeStr, isMorning) {
        state.timeExact = timeStr;
        state.timeWindow = isMorning ? 'morning' : 'afternoon';

        var timeSlotInput = document.getElementById('modal-time-slot');
        if (timeSlotInput) timeSlotInput.value = state.timeWindow;

        var timeExactInput = document.getElementById('modal-time-exact-value');
        if (timeExactInput) timeExactInput.value = state.timeExact;

        renderTimeSlots();
        updateTimeConfirmation();
        updateNextButtonState();
    }

    function updateTimeConfirmation() {
        var box = document.getElementById('wizard-time-confirmation');
        var text = document.getElementById('wizard-confirmed-time-text');
        if (!box || !text) return;
        if (state.timeExact) {
            box.style.display = 'flex';
            text.textContent = state.timeExact + ' (' + (state.timeWindow === 'morning' ? 'Morning' : 'Afternoon') + ')';
        } else {
            box.style.display = 'none';
        }
    }

    function bindStep4() {
        var phoneInput = document.getElementById('wizard-phone');
        var ageInput = document.getElementById('wizard-age');

        if (phoneInput) {
            phoneInput.addEventListener('input', function() {
                var val = this.value.replace(/[^0-9]/g, '');
                if (val.length > 11) val = val.substring(0, 11);
                this.value = val;

                var help = document.getElementById('help-phone');
                var err = document.getElementById('error-phone');
                if (err) { err.textContent = ''; err.classList.remove('visible'); }
                this.classList.remove('input-error');

                if (help) {
                    if (val.length === 11 && val.startsWith('09')) {
                        help.innerHTML = '<span class="valid-help">✓ Looks good</span>';
                    } else {
                        help.textContent = '11 numbers, starting with 09';
                    }
                }
            });
        }

        if (ageInput) {
            ageInput.addEventListener('input', function() {
                this.value = this.value.replace(/[^0-9]/g, '').substring(0, 3);
                var err = document.getElementById('error-age');
                if (err) { err.textContent = ''; err.classList.remove('visible'); }
                this.classList.remove('input-error');
            });
        }
    }

    function validateStep4() {
        var valid = true;
        var firstInvalidInput = null;

        function checkField(id, errId, condition, errMsg) {
            var input = document.getElementById(id);
            var errEl = document.getElementById(errId);
            if (!input || !errEl) return;
            if (!condition(input.value.trim())) {
                valid = false;
                input.classList.add('input-error');
                errEl.textContent = errMsg;
                errEl.classList.add('visible');
                if (!firstInvalidInput) firstInvalidInput = input;
            } else {
                input.classList.remove('input-error');
                errEl.textContent = '';
                errEl.classList.remove('visible');
            }
        }

        checkField('wizard-first-name', 'error-first-name', function(v) { return v.length > 0; }, 'Please enter your first name.');
        checkField('wizard-last-name', 'error-last-name', function(v) { return v.length > 0; }, 'Please enter your last name.');
        checkField('wizard-age', 'error-age', function(v) {
            var n = parseInt(v, 10);
            return !isNaN(n) && n > 0 && n <= 125;
        }, 'Please enter a valid age (1-125).');
        checkField('wizard-address', 'error-address', function(v) { return v.length > 0; }, 'Please enter your home address.');
        checkField('wizard-phone', 'error-phone', function(v) {
            return /^09\d{9}$/.test(v);
        }, 'Please enter an 11-digit mobile number starting with 09.');

        var emailInput = document.getElementById('wizard-email');
        var emailErr = document.getElementById('error-email');
        if (emailInput && emailErr) {
            var em = emailInput.value.trim();
            if (em.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) {
                valid = false;
                emailInput.classList.add('input-error');
                emailErr.textContent = 'Please enter a valid email address or leave blank.';
                emailErr.classList.add('visible');
                if (!firstInvalidInput) firstInvalidInput = emailInput;
            } else {
                emailInput.classList.remove('input-error');
                emailErr.textContent = '';
                emailErr.classList.remove('visible');
            }
        }

        if (!valid && firstInvalidInput) {
            firstInvalidInput.focus();
        }

        if (valid) {
            state.details.firstName = document.getElementById('wizard-first-name').value.trim();
            state.details.middleName = document.getElementById('wizard-middle-name') ? document.getElementById('wizard-middle-name').value.trim() : '';
            state.details.lastName = document.getElementById('wizard-last-name').value.trim();
            state.details.age = document.getElementById('wizard-age').value.trim();
            state.details.address = document.getElementById('wizard-address').value.trim();
            state.details.phone = document.getElementById('wizard-phone').value.trim();
            state.details.email = emailInput ? emailInput.value.trim() : '';
        }

        return valid;
    }

    function bindStep5() {
        document.addEventListener('click', function(e) {
            var jumpBtn = e.target.closest('[data-jump-step]');
            if (!jumpBtn) return;
            var targetStep = parseInt(jumpBtn.getAttribute('data-jump-step'), 10);
            if (targetStep >= 1 && targetStep <= 4) {
                goToStep(targetStep);
            }
        });

        var bookAnother = document.getElementById('wizard-btn-book-another');
        if (bookAnother) {
            bookAnother.addEventListener('click', function() {
                var form = document.getElementById('public-booking-form');
                if (form) form.reset();
                state.serviceId = null;
                state.serviceName = '';
                state.date = null;
                state.timeExact = null;
                goToStep(1);
            });
        }

        var doneBtn = document.getElementById('wizard-btn-success-done');
        if (doneBtn) {
            doneBtn.addEventListener('click', closeModal);
        }
    }

    function populateSummary() {
        var valWhat = document.getElementById('summary-val-what');
        var valDay = document.getElementById('summary-val-day');
        var valTime = document.getElementById('summary-val-time');
        var valName = document.getElementById('summary-val-name');
        var valAge = document.getElementById('summary-val-age');
        var valAddr = document.getElementById('summary-val-address');
        var valMobile = document.getElementById('summary-val-mobile');
        var valEmail = document.getElementById('summary-val-email');

        if (valWhat) valWhat.textContent = state.serviceName + (state.isFree ? ' (Free)' : '');
        if (valDay) valDay.textContent = state.dateDisplay || state.date;
        if (valTime) valTime.textContent = state.timeExact + ' (' + (state.timeWindow === 'morning' ? 'Morning' : 'Afternoon') + ')';
        var fullName = state.details.firstName + (state.details.middleName ? ' ' + state.details.middleName : '') + ' ' + state.details.lastName;
        if (valName) valName.textContent = fullName;
        if (valAge) valAge.textContent = state.details.age + ' yrs old';
        if (valAddr) valAddr.textContent = state.details.address;
        if (valMobile) valMobile.textContent = state.details.phone;
        if (valEmail) valEmail.textContent = state.details.email || 'Not provided';
    }

    function submitBooking() {
        var form = document.getElementById('public-booking-form');
        var nextBtn = document.getElementById('wizard-btn-next');
        var errBanner = document.getElementById('wizard-api-error-banner');
        var errText = document.getElementById('wizard-api-error-text');

        if (errBanner) errBanner.style.display = 'none';

        nextBtn.disabled = true;
        nextBtn.innerHTML = (window.BrgyUI ? BrgyUI.icon('loader-circle') : '') + ' Sending request...';

        var formData = new FormData(form);

        fetch('/appointments/api/public-book/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(function(res) {
            return res.json().then(function(data) {
                return { ok: res.ok, data: data };
            });
        })
        .then(function(res) {
            nextBtn.disabled = false;
            nextBtn.innerHTML = 'Send request ' + (window.BrgyUI ? BrgyUI.icon('send') : '');

            if (res.ok && res.data.status === 'ok') {
                showSuccessScreen(res.data);
            } else {
                if (errBanner) errBanner.style.display = 'flex';
                var msg = 'We could not send your request. Please try again.';
                if (res.data.errors) {
                    var k = Object.keys(res.data.errors)[0];
                    msg = res.data.errors[k];
                } else if (res.data.message || res.data.error) {
                    msg = res.data.message || res.data.error;
                }
                if (errText) errText.textContent = msg;
            }
        })
        .catch(function(err) {
            nextBtn.disabled = false;
            nextBtn.innerHTML = 'Send request ' + (window.BrgyUI ? BrgyUI.icon('send') : '');
            if (errBanner) errBanner.style.display = 'flex';
            if (errText) errText.textContent = 'Network error or connection timed out. Please try again.';
        });
    }

    function showSuccessScreen(data) {
        for (var i = 1; i <= 5; i++) {
            var stepEl = document.getElementById('wizard-step-' + i);
            if (stepEl) stepEl.style.display = 'none';
        }
        var prog = document.getElementById('wizard-progress-section');
        if (prog) prog.style.display = 'none';
        var footer = document.getElementById('wizard-footer');
        if (footer) footer.style.display = 'none';
        var help = document.getElementById('wizard-help-box');
        if (help) help.style.display = 'none';

        var successScreen = document.getElementById('wizard-success-screen');
        if (successScreen) successScreen.style.display = 'block';

        var refEl = document.getElementById('wizard-success-ref');
        var svcEl = document.getElementById('wizard-success-service');
        var schEl = document.getElementById('wizard-success-schedule');
        var nameEl = document.getElementById('wizard-success-name');

        if (refEl) refEl.textContent = data.ref_number || 'REF-APT-CONFIRMED';
        if (svcEl) svcEl.textContent = data.service_title || state.serviceName;
        if (schEl) schEl.textContent = (data.scheduled_date || state.dateDisplay) + ' (' + (data.time_slot || state.timeExact) + ')';
        if (nameEl) nameEl.textContent = data.applicant_name || (state.details.firstName + ' ' + state.details.lastName);
    }

    function bindFooter() {
        var backBtn = document.getElementById('wizard-btn-back');
        var nextBtn = document.getElementById('wizard-btn-next');

        if (backBtn) {
            backBtn.addEventListener('click', function() {
                if (state.step > 1) {
                    goToStep(state.step - 1);
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (state.step === 4) {
                    if (validateStep4()) {
                        goToStep(5);
                    }
                } else if (state.step === 5) {
                    submitBooking();
                } else {
                    goToStep(state.step + 1);
                }
            });
        }
    }

    return {
        init: init,
        open: openModal,
        close: closeModal,
        goToStep: goToStep,
        state: state
    };
})();

window.BookingWizard = BookingWizard;

function openBookAppointmentModal() {
    if (window.BookingWizard) {
        BookingWizard.open();
        return;
    }
    var modal = document.getElementById('bookAppointmentModal');
    if (modal) modal.style.display = 'flex';
}

function closeBookAppointmentModal() {
    if (window.BookingWizard) {
        BookingWizard.close();
        return;
    }
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
        if (data.status === 'ok') {
            selectEl.innerHTML = '';
            if (data.health_services && data.health_services.length > 0) {
                data.health_services.forEach(function(svc) {
                    var opt = document.createElement('option');
                    opt.value = svc.id;
                    opt.textContent = svc.name + ' (Free)';
                    selectEl.appendChild(opt);
                });
            } else {
                var opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No health services currently available';
                selectEl.appendChild(opt);
            }
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

    // Initialize 5-step booking wizard
    if (window.BookingWizard) {
        BookingWizard.init();
    }
    renderCustomCalendar();
    renderTimePicker();
    switchCategory('document');

    if (window.location.hash === '#bookAppointmentModal') {
        openBookAppointmentModal();
    }

    // Modal dynamic scrollbar: reveals scrollbar when user actively scrolls up/down in ANY modal
    (function initModalScrollObserver() {
        var scrollTimeouts = new WeakMap();

        document.addEventListener('scroll', function (event) {
            var target = event.target;
            if (!target || target === document || target === window || typeof target.closest !== 'function') {
                return;
            }

            var isModalScroll = target.matches('.modal-scrollable, .reg-wizard-modal-scroll, .wizard-body, .wizard-container') ||
                                target.closest('.modal-overlay, [role="dialog"], .modal-dialog, .modal');

            if (!isModalScroll) return;

            if (target.scrollHeight > target.clientHeight) {
                target.classList.add('is-scrolling');
                var existingTimeout = scrollTimeouts.get(target);
                if (existingTimeout) {
                    clearTimeout(existingTimeout);
                }
                var timeoutId = setTimeout(function () {
                    target.classList.remove('is-scrolling');
                    scrollTimeouts.delete(target);
                }, 800);
                scrollTimeouts.set(target, timeoutId);
            }
        }, { passive: true, capture: true });
    })();
});

