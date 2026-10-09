"""
HTML views for the Statistics module. Thin by design: permissions, filters, then render.
All numbers come from apps.statistics.selectors (the same ones the JSON API serves).
"""
import csv

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.models import BarangayInfo, Purok
from apps.accounts.permissions import check_user_perm, require_perm
from apps.statistics import selectors
from apps.core.ratelimit import ratelimit

# Spreadsheet apps run cells that start with these as formulas.
_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _safe_cell(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _blank_if_none(value):
    return '' if value is None else value


def _filters_or_400(request):
    try:
        return selectors.parse_filters(request.GET), None
    except selectors.FilterError as exc:
        return None, HttpResponseBadRequest(str(exc), content_type='text/plain; charset=utf-8')


@require_perm('statistics', 'view')
@require_GET
def stats_overview(request):
    """Page shell only. The charts fetch their data from the JSON API."""
    error = ''
    try:
        filters = selectors.parse_filters(request.GET)
    except selectors.FilterError as exc:
        filters, error = None, str(exc)
    return render(request, 'statistics/overview.html', {
        'puroks': Purok.objects.order_by('name'),
        'date_from': '' if filters is None or filters.default_range else filters.date_from.isoformat(),
        'date_to': '' if filters is None or filters.default_range else filters.date_to.isoformat(),
        'selected_purok': filters.purok_id if filters else None,
        'filter_error': error,
        'can_export': check_user_perm(request.user, 'statistics', 'export'),
    })


def _csv_rows(report):
    """The report as (title, header, rows) sections. CSV is built from this and nothing else."""
    f = report['filters']
    s = report['summary']
    d = report['demographics']
    p = report['purok_density']
    a = report['appointments']
    r = report['revenue']
    b = report['blotter']
    return [
        ('REPORT', ['Field', 'Value'], [
            ['Date from', f['date_from']],
            ['Date to', f['date_to']],
            ['Purok', f['purok_name'] or 'All puroks'],
            ['Generated at', report['generated_at']],
        ]),
        ('SUMMARY', ['Metric', 'Value'], [
            ['Population', s['population']], ['Households', s['households']],
            ['Minors (0-17)', s['minors']], ['Seniors (60+)', s['seniors']],
            ['PWD', s['pwd']], ['Solo parents', s['solo_parents']], ['4Ps', s['four_ps']],
            ['Appointments', s['appointments_total']], ['Pending', s['appointments_pending']],
            ['Completed', s['appointments_completed']],
            ['Documents issued', s['documents_issued']],
            [f'Revenue ({s["currency"]})', s['revenue_total']],
            ['Blotter cases filed', s['blotter_cases']],
            ['Blotter settlement rate (%)', _blank_if_none(s['settlement_rate'])],
            ['Average days to settle', _blank_if_none(b['avg_days_to_settle'])],
        ]),
        ('GENDER', ['Gender', 'Count'], [[x['label'], x['count']] for x in d['gender']]),
        ('SECTORS', ['Sector', 'Count'], [[x['label'], x['count']] for x in d['sectors']]),
        ('CIVIL STATUS', ['Civil status', 'Count'], [[x['label'], x['count']] for x in d['civil_status']]),
        ('AGE BANDS', ['Age band', 'Count'], [[x['label'], x['count']] for x in d['age_bands']]),
        ('PUROK DENSITY', ['Rank', 'Purok', 'Households', '% of households', 'Residents', '% of population'], [
            [x['rank'] or '', x['name'], x['households'], x['pct_households'], x['residents'], x['pct_population']]
            for x in p['rows']
        ]),
        ('APPOINTMENTS BY STATUS', ['Status', 'Count'], [[x['label'], x['count']] for x in a['by_status']]),
        ('APPOINTMENTS BY CATEGORY', ['Category', 'Count'], [[x['label'], x['count']] for x in a['by_category']]),
        ('DOCUMENT REQUESTS', ['Document type', 'Count'], [[x['name'], x['count']] for x in a['by_document_type']]),
        ('HEALTH SERVICES', ['Health service', 'Count'], [[x['name'], x['count']] for x in a['by_health_service']]),
        ('REVENUE BY MONTH', ['Month', f'Revenue ({r["currency"]})', 'Completed documents'], [
            [x['label'], x['revenue'], x['count']] for x in r['months']
        ] + [['TOTAL', r['total'], r['count']]]),
        ('REVENUE BY DOCUMENT TYPE', ['Document type', f'Revenue ({r["currency"]})', 'Completed documents'], [
            [x['name'], x['revenue'], x['count']] for x in r['by_document_type']
        ]),
        ('BLOTTER BY STATUS', ['Status', 'Cases filed'], [[x['label'], x['count']] for x in b['by_status']]),
        ('BLOTTER BY TYPE', ['Incident type', 'Cases filed'], [[x['label'], x['count']] for x in b['by_type']]),
        ('BLOTTER BY PUROK', ['Purok', 'Cases filed'], [[x['name'], x['count']] for x in b['by_purok']]),
        ('BLOTTER MONTHLY', ['Month', 'Filed', 'Settled', 'Closed', 'Settlement rate (%)'], [
            [x['label'], x['filed'], x['settled'], x['closed'], _blank_if_none(x['settlement_rate'])]
            for x in b['months']
        ]),
    ]


@require_perm('statistics', 'export')
@require_GET
@ratelimit(key='user', rate='statistics_export', methods=('GET',))
def stats_export_excel(request):
    """CSV (opens in Excel) built from the same report the API serves."""
    filters, error = _filters_or_400(request)
    if error:
        return error
    report = selectors.build_report(filters)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="barangay_statistics_{filters.date_from:%Y%m%d}_{filters.date_to:%Y%m%d}.csv"'
    )
    response.write('\ufeff')  # BOM so Excel reads UTF-8 names correctly
    writer = csv.writer(response)
    for title, header, rows in _csv_rows(report):
        writer.writerow([title])
        writer.writerow(header)
        for row in rows:
            writer.writerow([_safe_cell(cell) for cell in row])
        writer.writerow([])
    return response


@require_perm('statistics', 'export')
@require_GET
@ratelimit(key='user', rate='statistics_export', methods=('GET',))
def stats_export_pdf(request):
    """Print-friendly report (browser Save as PDF)."""
    filters, error = _filters_or_400(request)
    if error:
        return error
    return render(request, 'statistics/print_report.html', {
        'report': selectors.build_report(filters),
        'info': BarangayInfo.get_solo(),
    })
