/*
 * Blotter pages: dynamic party rows on the case form, confirmations and print buttons.
 * No inline handlers in the templates; everything is wired here.
 */
(function () {
  'use strict';

  // ---------- print (case summary) ----------
  document.querySelectorAll('[data-action="print"]').forEach(function (btn) {
    btn.addEventListener('click', function () { window.print(); });
  });

  // ---------- confirmations ----------
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.getAttribute('data-confirm'))) { event.preventDefault(); }
    });
  });
  document.querySelectorAll('[data-confirm-button]').forEach(function (button) {
    button.addEventListener('click', function (event) {
      if (!window.confirm(button.getAttribute('data-confirm-button'))) { event.preventDefault(); }
    });
  });

  // ---------- party rows ----------
  var rows = document.querySelector('[data-party-rows]');
  var template = document.getElementById('party-row-template');
  if (!rows || !template) { return; }

  var prefix = rows.getAttribute('data-prefix');
  var totalInput = document.getElementById('id_' + prefix + '-TOTAL_FORMS');
  var pattern = new RegExp('^' + prefix + '-(\\d+|__prefix__)-');
  var idPattern = new RegExp('^id_' + prefix + '-(\\d+|__prefix__)-');

  // Give every row consecutive indices so Django's formset reads them in order.
  function renumber() {
    var list = rows.querySelectorAll('[data-party-row]');
    list.forEach(function (row, index) {
      row.querySelectorAll('[name], [id], label[for]').forEach(function (el) {
        if (el.name) { el.name = el.name.replace(pattern, prefix + '-' + index + '-'); }
        if (el.id) { el.id = el.id.replace(idPattern, 'id_' + prefix + '-' + index + '-'); }
        var target = el.getAttribute('for');
        if (target) { el.setAttribute('for', target.replace(idPattern, 'id_' + prefix + '-' + index + '-')); }
      });
    });
    totalInput.value = String(list.length);
  }

  function wireRemove(row) {
    var button = row.querySelector('[data-remove-party]');
    if (!button) { return; }
    button.addEventListener('click', function () {
      if (rows.querySelectorAll('[data-party-row]').length <= 1) { return; }
      row.remove();
      renumber();
    });
  }

  rows.querySelectorAll('[data-party-row]').forEach(wireRemove);

  var addButton = document.querySelector('[data-add-party]');
  if (addButton) {
    addButton.addEventListener('click', function () {
      var fragment = template.content.cloneNode(true);
      var row = fragment.querySelector('[data-party-row]');
      rows.appendChild(fragment);
      wireRemove(row);
      renumber();
      var first = row.querySelector('select, input:not([type="hidden"])');
      if (first) { first.focus(); }
    });
  }
})();
