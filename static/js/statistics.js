/*
 * Statistics page. Endpoints come from data-* attributes on #stats-root.
 * Values are written with textContent only (never innerHTML).
 */
(function () {
  'use strict';

  // Print buttons on the standalone print report (no inline onclick there).
  document.querySelectorAll('[data-action="print"]').forEach(function (btn) {
    btn.addEventListener('click', function () { window.print(); });
  });

  var root = document.getElementById('stats-root');
  if (!root) { return; }

  // Design palette only: navy, gray, green, then neutral grays and red.
  // Index 0 (navy) = documents/primary series, index 2 (green) = health/second series.
  var PALETTE = ['#1E3A8A', '#9CA3AF', '#16A34A', '#374151', '#DC2626', '#D1D5DB', '#111827', '#6B7280'];
  // Highest-density purok bar stands out from the navy bars.
  var HIGHLIGHT = '#DC2626';
  var FILTER_KEYS = ['date_from', 'date_to', 'purok'];
  var ENDPOINTS = {
    summary: root.dataset.apiSummary,
    demographics: root.dataset.apiDemographics,
    density: root.dataset.apiPurokDensity,
    appointments: root.dataset.apiAppointments,
    revenue: root.dataset.apiRevenue,
    blotter: root.dataset.apiBlotter
  };

  var form = document.getElementById('stats-filters');
  var errorBox = document.getElementById('stats-error');
  var rangeBox = document.getElementById('stats-range');
  var charts = {};
  var requestId = 0;

  // ---------- helpers ----------
  var intFmt = new Intl.NumberFormat('en-PH');

  function fmtInt(n) { return intFmt.format(n); }

  // Settlement rates are null when no case is closed yet: show a dash, not 0%.
  function fmtRate(value) { return value === null || value === undefined ? '-' : value + '%'; }

  function fmtMoney(value, currency) {
    return new Intl.NumberFormat('en-PH', { style: 'currency', currency: currency || 'PHP' }).format(Number(value));
  }

  function currentFilters() {
    var params = new URLSearchParams();
    FILTER_KEYS.forEach(function (key) {
      var field = form.elements[key];
      if (field && field.value) { params.set(key, field.value); }
    });
    return params;
  }

  function withQuery(url, params) {
    var query = params.toString();
    return query ? url + '?' + query : url;
  }

  function cardFor(name) { return root.querySelector('[data-chart="' + name + '"]'); }

  function setState(name, state) {
    var card = cardFor(name);
    if (card) { card.setAttribute('data-state', state); }
  }

  function showError(message) {
    errorBox.textContent = message || '';
    errorBox.hidden = !message;
  }

  function sum(rows) {
    return rows.reduce(function (total, row) { return total + (Number(row.count) || 0); }, 0);
  }

  // ---------- fetching ----------
  var SESSION_EXPIRED = 'Your session expired, please log in again.';

  function sessionExpiredError() {
    var err = new Error(SESSION_EXPIRED);
    err.sessionExpired = true;
    return err;
  }

  function defaultLoginUrl() {
    return '/accounts/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search);
  }

  // Message plus a "Log in" link, built with DOM APIs (no innerHTML).
  function showSessionExpired() {
    errorBox.textContent = '';
    errorBox.appendChild(document.createTextNode(SESSION_EXPIRED + ' '));
    var link = document.createElement('a');
    // Always return to this page after login. The server's login_url points
    // at the API endpoint, which would land the user on raw JSON.
    link.href = defaultLoginUrl();
    link.textContent = 'Log in';
    errorBox.appendChild(link);
    errorBox.hidden = false;
  }

  function isJson(response) {
    return (response.headers.get('Content-Type') || '').indexOf('application/json') !== -1;
  }

  function fetchJson(url) {
    return fetch(url, {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (response) {
        // A redirect to the login page or any HTML body means the session is gone.
        if (response.redirected || (response.ok && !isJson(response))) {
          throw sessionExpiredError();
        }
        if (response.ok) { return response.json(); }
        if (response.status === 401) {
          throw sessionExpiredError();
        }
        return response.json().catch(function () { return {}; }).then(function (body) {
          if (response.status === 403) {
            throw new Error('You do not have permission to view statistics.');
          }
          throw new Error(body.error || ('The server could not load the statistics (HTTP ' + response.status + ').'));
        });
      }, function () {
        throw new Error('Could not reach the server. Check your connection and try again.');
      });
  }

  // ---------- tables ----------
  function renderTable(name, head, rows, classes) {
    var card = cardFor(name);
    if (!card) { return; }
    var thead = card.querySelector('thead');
    var tbody = card.querySelector('tbody');
    thead.textContent = '';
    tbody.textContent = '';
    var headRow = document.createElement('tr');
    head.forEach(function (label, index) {
      var th = document.createElement('th');
      th.scope = 'col';
      th.textContent = label;
      if (index > 0 && classes && classes[index] === 'num') { th.className = 'num'; }
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      if (row.highlight) { tr.className = 'is-highest'; }
      row.cells.forEach(function (value, index) {
        var td = document.createElement('td');
        td.textContent = String(value);
        if (classes && classes[index] === 'num') { td.className = 'num'; }
        if (row.flag && index === row.flagIndex) {
          var flag = document.createElement('span');
          flag.className = 'stats-flag';
          flag.textContent = row.flag;
          td.appendChild(flag);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  // ---------- charts ----------
  function draw(name, config) {
    var card = cardFor(name);
    if (!card) { return; }
    if (charts[name]) { charts[name].destroy(); delete charts[name]; }
    if (!window.Chart) { return; }
    charts[name] = new window.Chart(card.querySelector('canvas'), config);
  }

  function baseOptions(extra) {
    var options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { position: 'bottom' } }
    };
    return Object.assign(options, extra || {});
  }

  function pieChart(name, rows, type) {
    draw(name, {
      type: type,
      data: {
        labels: rows.map(function (r) { return r.label; }),
        datasets: [{ data: rows.map(function (r) { return r.count; }), backgroundColor: PALETTE }]
      },
      options: baseOptions()
    });
  }

  function barChart(name, rows, label, color) {
    draw(name, {
      type: 'bar',
      data: {
        labels: rows.map(function (r) { return r.label; }),
        datasets: [{ label: label, data: rows.map(function (r) { return r.count; }), backgroundColor: color || PALETTE[0] }]
      },
      options: baseOptions({
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      })
    });
  }

  function countRows(rows) {
    return rows.map(function (r) { return { cells: [r.label, fmtInt(r.count)] }; });
  }

  function simpleBlock(name, rows, title, kind) {
    if (sum(rows) === 0) {
      if (charts[name]) { charts[name].destroy(); delete charts[name]; }
      renderTable(name, [title, 'Count'], countRows(rows), { 1: 'num' });
      setState(name, 'empty');
      return;
    }
    setState(name, 'ready');
    if (kind === 'bar') { barChart(name, rows, title); } else { pieChart(name, rows, kind); }
    renderTable(name, [title, 'Count'], countRows(rows), { 1: 'num' });
  }

  // ---------- blocks ----------
  function renderSummary(data) {
    root.querySelectorAll('[data-kpi]').forEach(function (el) {
      var key = el.dataset.kpi;
      var value = data[key];
      if (key === 'revenue_total') {
        el.textContent = fmtMoney(value, data.currency);
      } else if (key === 'settlement_rate') {
        el.textContent = fmtRate(value);
      } else {
        el.textContent = fmtInt(value);
      }
    });
  }

  function renderDemographics(data) {
    simpleBlock('gender', data.gender, 'Gender', 'doughnut');
    simpleBlock('sectors', data.sectors, 'Sector', 'bar');
    simpleBlock('civil_status', data.civil_status, 'Civil status', 'bar');
    simpleBlock('age_bands', data.age_bands, 'Age band', 'bar');
  }

  function renderDensity(data) {
    var rows = data.rows.filter(function (r) {
      return !(r.purok_id === null && r.households === 0 && r.residents === 0);
    });
    var empty = rows.every(function (r) { return r.households === 0 && r.residents === 0; });
    var head = ['Rank', 'Purok', 'Households', '% households', 'Residents', '% population'];
    var tableRows = rows.map(function (r) {
      return {
        highlight: r.is_highest,
        flag: r.is_highest ? 'Highest' : '',
        flagIndex: 1,
        cells: [r.rank === null ? '-' : r.rank, r.name, fmtInt(r.households), r.pct_households + '%',
                fmtInt(r.residents), r.pct_population + '%']
      };
    });
    renderTable('purok_density', head, tableRows, { 0: 'num', 2: 'num', 3: 'num', 4: 'num', 5: 'num' });
    if (empty) {
      if (charts.purok_density) { charts.purok_density.destroy(); delete charts.purok_density; }
      setState('purok_density', 'empty');
      return;
    }
    setState('purok_density', 'ready');
    draw('purok_density', {
      type: 'bar',
      data: {
        labels: rows.map(function (r) { return r.name; }),
        datasets: [
          {
            label: 'Households',
            data: rows.map(function (r) { return r.households; }),
            backgroundColor: rows.map(function (r) { return r.is_highest ? HIGHLIGHT : PALETTE[0]; })
          },
          { label: 'Residents', data: rows.map(function (r) { return r.residents; }), backgroundColor: PALETTE[2] }
        ]
      },
      options: baseOptions({
        indexAxis: 'y',
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } }
      })
    });
  }

  function renderAppointments(data) {
    simpleBlock('appointment_status', data.by_status, 'Status', 'doughnut');

    var services = data.by_document_type.map(function (r) {
      return { group: 'Document', label: r.name, count: r.count };
    }).concat(data.by_health_service.map(function (r) {
      return { group: 'Health', label: r.name, count: r.count };
    }));
    renderTable('services', ['Type', 'Service', 'Requests'], services.map(function (r) {
      return { cells: [r.group, r.label, fmtInt(r.count)] };
    }), { 2: 'num' });
    if (sum(services) === 0) {
      if (charts.services) { charts.services.destroy(); delete charts.services; }
      setState('services', 'empty');
      return;
    }
    setState('services', 'ready');
    draw('services', {
      type: 'bar',
      data: {
        labels: services.map(function (r) { return r.label; }),
        datasets: [{
          label: 'Requests',
          data: services.map(function (r) { return r.count; }),
          backgroundColor: services.map(function (r) { return r.group === 'Document' ? PALETTE[0] : PALETTE[2]; })
        }]
      },
      options: baseOptions({
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } }
      })
    });
  }

  function renderRevenue(data) {
    var rows = data.months.map(function (m) {
      return { cells: [m.label, fmtMoney(m.revenue, data.currency), fmtInt(m.count)] };
    });
    renderTable('revenue', ['Month', 'Revenue', 'Completed documents'], rows, { 1: 'num', 2: 'num' });
    if (data.count === 0) {
      if (charts.revenue) { charts.revenue.destroy(); delete charts.revenue; }
      setState('revenue', 'empty');
      return;
    }
    setState('revenue', 'ready');
    draw('revenue', {
      type: 'line',
      data: {
        labels: data.months.map(function (m) { return m.label; }),
        datasets: [{
          label: 'Revenue (' + data.currency + ')',
          data: data.months.map(function (m) { return Number(m.revenue); }),
          borderColor: PALETTE[0],
          backgroundColor: 'rgba(30, 58, 138, 0.12)',
          fill: true,
          tension: 0.25
        }]
      },
      options: baseOptions({
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      })
    });
  }

  function renderBlotter(data) {
    var note = document.getElementById('stats-blotter-note');
    if (note) {
      note.textContent = 'Settlement rate ' + fmtRate(data.settlement_rate) +
        ' (settled / closed cases), average ' +
        (data.avg_days_to_settle === null ? '-' : data.avg_days_to_settle) + ' days to settle, ' +
        fmtInt(data.open) + ' open.';
    }
    var rows = data.months.map(function (m) {
      return { cells: [m.label, fmtInt(m.filed), fmtInt(m.settled), fmtInt(m.closed), fmtRate(m.settlement_rate)] };
    });
    renderTable('blotter', ['Month', 'Filed', 'Settled', 'Closed', 'Settlement rate'], rows,
      { 1: 'num', 2: 'num', 3: 'num', 4: 'num' });
    var activity = data.months.reduce(function (total, m) { return total + m.filed + m.settled + m.closed; }, 0);
    if (activity === 0) {
      if (charts.blotter) { charts.blotter.destroy(); delete charts.blotter; }
      setState('blotter', 'empty');
      return;
    }
    setState('blotter', 'ready');
    draw('blotter', {
      type: 'line',
      data: {
        labels: data.months.map(function (m) { return m.label; }),
        datasets: [
          { label: 'Filed', data: data.months.map(function (m) { return m.filed; }),
            borderColor: PALETTE[0], backgroundColor: PALETTE[0], tension: 0.25 },
          { label: 'Settled', data: data.months.map(function (m) { return m.settled; }),
            borderColor: PALETTE[2], backgroundColor: PALETTE[2], tension: 0.25 }
        ]
      },
      options: baseOptions({ scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } })
    });
  }

  // ---------- load ----------
  function syncLinks(params) {
    ['stats-export-csv', 'stats-export-print'].forEach(function (id) {
      var link = document.getElementById(id);
      if (!link) { return; }
      var base = id === 'stats-export-csv' ? root.dataset.exportCsv : root.dataset.exportPrint;
      link.setAttribute('href', withQuery(base, params));
    });
  }

  function describeRange(filters) {
    var text = 'Showing ' + filters.date_from + ' to ' + filters.date_to;
    text += filters.purok_name ? ' for ' + filters.purok_name : ' for all puroks';
    text += filters.default_range ? ' (last 12 months).' : '.';
    rangeBox.textContent = text;
  }

  function load() {
    var params = currentFilters();
    var thisRequest = ++requestId;
    syncLinks(params);
    showError('');
    Object.keys(charts).forEach(function (name) { charts[name].destroy(); delete charts[name]; });
    root.querySelectorAll('[data-chart]').forEach(function (card) { card.setAttribute('data-state', 'loading'); });

    var jobs = [
      ['summary', renderSummary],
      ['demographics', renderDemographics],
      ['density', renderDensity],
      ['appointments', renderAppointments],
      ['revenue', renderRevenue],
      ['blotter', renderBlotter]
    ];
    var failures = [];
    var requests = jobs.map(function (job) {
      return fetchJson(withQuery(ENDPOINTS[job[0]], params)).then(function (payload) {
        if (thisRequest !== requestId) { return; }
        describeRange(payload.filters);
        job[1](payload.data);
      }).catch(function (err) {
        failures.push(err);
      });
    });
    Promise.all(requests).then(function () {
      if (thisRequest !== requestId) { return; }
      if (failures.length) {
        // Session expiry wins over other errors: every later call fails the same way.
        var expired = failures.filter(function (err) { return err.sessionExpired; })[0];
        if (expired) {
          showSessionExpired();
        } else {
          showError(failures[0].message);
        }
        root.querySelectorAll('[data-chart][data-state="loading"]').forEach(function (card) {
          card.setAttribute('data-state', 'empty');
        });
      }
    });
  }

  // ---------- events ----------
  function pushUrl() {
    var query = currentFilters().toString();
    window.history.pushState({}, '', window.location.pathname + (query ? '?' + query : ''));
  }

  function fillFormFromUrl() {
    var params = new URLSearchParams(window.location.search);
    FILTER_KEYS.forEach(function (key) {
      var field = form.elements[key];
      if (field) { field.value = params.get(key) || ''; }
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    pushUrl();
    load();
  });

  document.getElementById('stats-reset').addEventListener('click', function (event) {
    event.preventDefault();
    form.reset();
    FILTER_KEYS.forEach(function (key) { if (form.elements[key]) { form.elements[key].value = ''; } });
    pushUrl();
    load();
  });

  window.addEventListener('popstate', function () {
    fillFormFromUrl();
    load();
  });

  root.querySelectorAll('[data-toggle-table]').forEach(function (button) {
    var wrap = button.closest('.stats-card').querySelector('.stats-table-wrap');
    button.addEventListener('click', function () {
      var open = wrap.hidden;
      wrap.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      button.textContent = open ? 'Hide table' : 'View as table';
    });
  });

  fillFormFromUrl();
  load();
})();
