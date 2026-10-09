"""
Read-only aggregates for the Statistics module.

Nothing here touches HTTP or writes to the database. The JSON API, the CSV export and the
print report all call `build_report()` (or one of the block functions), so every surface
shows exactly the same numbers.

Filters
-------
date_from / date_to  Inclusive ISO dates. They bound Appointment.appt_date (appointments,
                     issued documents, revenue) and the blotter filed/settled/closed dates
                     (Asia/Manila days). Residents and households are a live snapshot, so
                     dates do not change them.
purok                Purok id. Limits residents, households, appointments (through the
                     resident's purok), revenue and blotter cases. The purok density block
                     still ranks against every purok and only trims the rows.
Default range: the last 12 months ending with the current Asia/Manila month.

Extending
---------
`build_report()` returns one dict with a key per block (demographics, purok_density,
appointments, revenue, blotter). A new block is one more key plus one more function here.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.accounts import selectors as resident_selectors
from apps.accounts.models import Purok
from apps.appointments.models import (
    Appointment, DocumentType, HealthCareService, IssuedDocumentLog,
)
from apps.blotter.models import BlotterCase

DEFAULT_MONTHS = 12
MAX_RANGE_DAYS = 3660  # ten years; keeps the zero-filled revenue series bounded
CURRENCY = 'PHP'
UNASSIGNED = 'Unassigned'
UNSPECIFIED = 'Unspecified'

_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_MONTH_ABBR = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
_FEE = DecimalField(max_digits=12, decimal_places=2)
_CENTS = Decimal('0.01')


class FilterError(ValueError):
    """A filter value is missing its format, out of range or points to nothing."""


@dataclass(frozen=True)
class Filters:
    date_from: date
    date_to: date
    purok_id: int = None
    purok_name: str = ''
    default_range: bool = True

    def as_dict(self):
        return {
            'date_from': self.date_from.isoformat(),
            'date_to': self.date_to.isoformat(),
            'purok': self.purok_id,
            'purok_name': self.purok_name,
            'default_range': self.default_range,
        }


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _month_start(day, months_back=0):
    index = day.year * 12 + (day.month - 1) - months_back
    return date(index // 12, index % 12 + 1, 1)


def _month_end(day):
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def _parse_iso_date(name, raw):
    raw = (raw or '').strip()
    if not _ISO_DATE.match(raw):
        raise FilterError(f'{name} must be an ISO date (YYYY-MM-DD).')
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise FilterError(f'{name} is not a valid calendar date.')


def parse_filters(params, today=None):
    """
    Build Filters from a mapping such as request.GET. Raises FilterError (never anything
    else) for a bad date, date_from after date_to, a range over ten years, or a bad purok.
    """
    today = today or timezone.localdate()
    raw_from = str(params.get('date_from') or '').strip()
    raw_to = str(params.get('date_to') or '').strip()
    raw_purok = str(params.get('purok') or '').strip()

    date_from = _parse_iso_date('date_from', raw_from) if raw_from else None
    date_to = _parse_iso_date('date_to', raw_to) if raw_to else None

    if date_from is None and date_to is None:
        date_to = _month_end(today)
        date_from = _month_start(today, DEFAULT_MONTHS - 1)
    elif date_to is None:
        date_to = _month_end(today)
    elif date_from is None:
        date_from = _month_start(date_to, DEFAULT_MONTHS - 1)

    if date_from > date_to:
        raise FilterError('date_from must not be after date_to.')
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise FilterError('The date range may not exceed 10 years.')

    purok_id, purok_name = None, ''
    if raw_purok:
        if not (raw_purok.isascii() and raw_purok.isdigit()) or len(raw_purok) > 9:
            raise FilterError('purok must be a purok id.')
        purok = Purok.objects.filter(pk=int(raw_purok)).first()
        if purok is None:
            raise FilterError('purok does not exist.')
        purok_id, purok_name = purok.pk, purok.name

    return Filters(
        date_from=date_from,
        date_to=date_to,
        purok_id=purok_id,
        purok_name=purok_name,
        default_range=not (raw_from or raw_to),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _money(value):
    return f'{(value or Decimal("0")).quantize(_CENTS):.2f}'


def _percent(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def _appointments(filters):
    """Appointments inside the filter window (and purok). Ordering cleared for GROUP BY."""
    qs = Appointment.objects.filter(
        appt_date__gte=filters.date_from, appt_date__lte=filters.date_to,
    )
    if filters.purok_id:
        qs = qs.filter(resident__resident_profile__purok_id=filters.purok_id)
    return qs.order_by()


def _choice_rows(counts, choices):
    return [
        {'code': code, 'label': str(label), 'count': counts.get(code, 0)}
        for code, label in choices
    ]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def demographics(filters):
    """Population, gender, sectors, civil status and age bands (Resident is the only source)."""
    purok_id = filters.purok_id
    bands = resident_selectors.age_bands(purok_id)
    gender = [
        {
            'code': row['code'] or 'unspecified',
            'label': row['label'],
            'count': row['count'],
        }
        for row in resident_selectors.by_gender(purok_id)
    ]
    return {
        'population': resident_selectors.population(purok_id),
        'minors': bands['minors'],
        'gender': gender,
        'sectors': resident_selectors.by_sector(purok_id),
        'civil_status': resident_selectors.by_civil_status(purok_id),
        'age_bands': bands['bands'],
    }


def purok_density(filters):
    """
    Residents and households per purok, ranked by households (then residents, then name).
    Real puroks are ranked; the Unassigned bucket is appended unranked. The top purok is
    flagged `is_highest` only when it actually holds something.
    """
    residents = {row['purok_id']: row['count'] for row in resident_selectors.population_per_purok()}
    households = resident_selectors.households_per_purok()
    total_residents = sum(residents.values())
    total_households = sum(row['households'] for row in households)

    rows = []
    for row in households:
        rows.append({
            'purok_id': row['purok_id'],
            'name': row['name'],
            'residents': residents.get(row['purok_id'], 0),
            'households': row['households'],
        })
    real = sorted((r for r in rows if r['purok_id'] is not None),
                  key=lambda r: (-r['households'], -r['residents'], r['name'].lower()))
    unassigned = [r for r in rows if r['purok_id'] is None]

    ranked = []
    for position, row in enumerate(real, start=1):
        ranked.append({**row, 'rank': position,
                       'is_highest': position == 1 and (row['households'] or row['residents']) > 0})
    for row in unassigned:
        ranked.append({**row, 'rank': None, 'is_highest': False})
    for row in ranked:
        row['pct_population'] = _percent(row['residents'], total_residents)
        row['pct_households'] = _percent(row['households'], total_households)

    highest = next((r for r in ranked if r['is_highest']), None)
    if filters.purok_id:
        ranked = [r for r in ranked if r['purok_id'] == filters.purok_id]
    return {
        'total_residents': total_residents,
        'total_households': total_households,
        'highest': highest,
        'rows': ranked,
    }


def appointments(filters):
    """Requests by status, category, document type and health service, plus issued documents."""
    qs = _appointments(filters)
    by_status = dict(qs.values_list('status').annotate(n=Count('id')))
    by_category = dict(qs.values_list('category').annotate(n=Count('id')))

    doc_counts = {
        row['document_type_id']: row['n']
        for row in qs.values('document_type_id').annotate(n=Count('id'))
    }
    documents = [
        {'id': dt.pk, 'name': dt.name, 'count': doc_counts.get(dt.pk, 0)}
        for dt in DocumentType.objects.order_by('order', 'name')
        if dt.is_active or doc_counts.get(dt.pk)
    ]
    # Document requests whose type was deleted (FK set to NULL) are still real requests.
    unspecified = qs.filter(
        category=Appointment.CATEGORY_DOCUMENT, document_type__isnull=True,
    ).count()
    if unspecified:
        documents.append({'id': None, 'name': UNSPECIFIED, 'count': unspecified})

    svc_counts = {
        row['healthcare_service_id']: row['n']
        for row in qs.values('healthcare_service_id').annotate(n=Count('id'))
    }
    services = [
        {'id': svc.pk, 'name': svc.name, 'count': svc_counts.get(svc.pk, 0)}
        for svc in HealthCareService.objects.order_by('name')
        if svc.is_active or svc_counts.get(svc.pk)
    ]
    unspecified = qs.filter(
        category=Appointment.CATEGORY_HEALTHCARE, healthcare_service__isnull=True,
    ).count()
    if unspecified:
        services.append({'id': None, 'name': UNSPECIFIED, 'count': unspecified})
    issued = IssuedDocumentLog.objects.filter(
        appointment__appt_date__gte=filters.date_from,
        appointment__appt_date__lte=filters.date_to,
    )
    if filters.purok_id:
        issued = issued.filter(appointment__resident__resident_profile__purok_id=filters.purok_id)

    return {
        'total': sum(by_status.values()),
        'by_status': _choice_rows(by_status, Appointment.STATUS_CHOICES),
        'by_category': _choice_rows(by_category, Appointment.CATEGORY_CHOICES),
        'by_document_type': documents,
        'by_health_service': services,
        'issued_documents': issued.count(),
    }


def _month_keys(date_from, date_to):
    key, last = date_from.replace(day=1), date_to.replace(day=1)
    while key <= last:
        yield key
        key = _month_start(key, -1)


def revenue(filters):
    """
    Fees from completed document appointments: the fee frozen at booking, else the
    document type's current fee. Grouped by appointment month; months without revenue
    are present with 0.00. Months are plain calendar months of the Manila appt_date.
    """
    fee = Coalesce('fee_at_booking', 'document_type__fee', Value(Decimal('0')), output_field=_FEE)
    paid = _appointments(filters).filter(
        status=Appointment.STATUS_COMPLETED, category=Appointment.CATEGORY_DOCUMENT,
    ).annotate(fee=fee)

    by_month = {
        row['month']: row
        for row in paid.annotate(month=TruncMonth('appt_date')).values('month')
        .annotate(total=Sum('fee'), n=Count('id')).order_by()
    }
    months, grand_total, grand_count = [], Decimal('0'), 0
    for key in _month_keys(filters.date_from, filters.date_to):
        row = by_month.get(key, {})
        total = row.get('total') or Decimal('0')
        count = row.get('n', 0)
        grand_total += total
        grand_count += count
        months.append({
            'month': key.strftime('%Y-%m'),
            'label': f'{_MONTH_ABBR[key.month - 1]} {key.year}',
            'revenue': _money(total),
            'count': count,
        })

    per_type = {
        row['document_type_id']: row
        for row in paid.values('document_type_id').annotate(total=Sum('fee'), n=Count('id')).order_by()
    }
    by_document_type = []
    for dt in DocumentType.objects.order_by('order', 'name'):
        row = per_type.pop(dt.pk, None)
        if dt.is_active or row:
            by_document_type.append({
                'id': dt.pk, 'name': dt.name,
                'revenue': _money(row['total'] if row else None),
                'count': row['n'] if row else 0,
            })
    orphan = per_type.get(None)
    if orphan:
        by_document_type.append({
            'id': None, 'name': UNSPECIFIED,
            'revenue': _money(orphan['total']), 'count': orphan['n'],
        })

    return {
        'currency': CURRENCY,
        'total': _money(grand_total),
        'count': grand_count,
        'months': months,
        'by_document_type': by_document_type,
    }


def _day_bounds(filters):
    """Aware [start, end) datetimes for the filter dates in the Manila timezone (portable, no tz SQL)."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(filters.date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(filters.date_to + timedelta(days=1), time.min), tz)
    return start, end


def _rate(settled, closed):
    return round(settled / closed * 100, 1) if closed else None


def _local_month(value):
    return timezone.localtime(value).date().replace(day=1)


def blotter(filters):
    """
    Blotter aggregates (counts only: no case numbers, names or narratives, so confidential
    cases are counted without exposing anything about them).

    by_status / by_type / by_purok  cases FILED in the period (filed_at), zero-filled.
    settlement_rate                 settled / closed among those cases, where closed is
                                    settled + escalated + dismissed + withdrawn; % with one
                                    decimal, None when nothing is closed.
    avg_days_to_settle              mean days from filed_at to settled_at of those cases.
    months                          per calendar month: filed (filed_at month), settled
                                    (settled_at month), closed (closed_at month) and that
                                    month's settlement_rate = settled / closed.
    """
    start, end = _day_bounds(filters)
    cases = BlotterCase.objects.order_by()
    if filters.purok_id:
        cases = cases.filter(purok_id=filters.purok_id)
    filed = cases.filter(filed_at__gte=start, filed_at__lt=end)

    by_status = dict(filed.values_list('status').annotate(n=Count('id')))
    by_type = dict(filed.values_list('incident_type').annotate(n=Count('id')))
    per_purok = dict(filed.values_list('purok_id').annotate(n=Count('id')))

    puroks = Purok.objects.order_by('name')
    if filters.purok_id:
        puroks = puroks.filter(pk=filters.purok_id)
    by_purok = [{'purok_id': p.pk, 'name': p.name, 'count': per_purok.get(p.pk, 0)} for p in puroks]
    if not filters.purok_id and per_purok.get(None):
        by_purok.append({'purok_id': None, 'name': UNASSIGNED, 'count': per_purok[None]})

    settled = by_status.get(BlotterCase.STATUS_SETTLED, 0)
    closed = sum(by_status.get(code, 0) for code in BlotterCase.TERMINAL)

    durations = [
        (settled_at - filed_at).total_seconds() / 86400
        for filed_at, settled_at in filed.filter(settled_at__isnull=False).values_list('filed_at', 'settled_at')
    ]

    buckets = {}
    for field, key in (('filed_at', 'filed'), ('settled_at', 'settled'), ('closed_at', 'closed')):
        window = {f'{field}__gte': start, f'{field}__lt': end}
        for value in cases.filter(**window).values_list(field, flat=True):
            month = _local_month(value)
            buckets.setdefault(month, {'filed': 0, 'settled': 0, 'closed': 0})[key] += 1
    months = []
    for key in _month_keys(filters.date_from, filters.date_to):
        row = buckets.get(key, {'filed': 0, 'settled': 0, 'closed': 0})
        months.append({
            'month': key.strftime('%Y-%m'),
            'label': f'{_MONTH_ABBR[key.month - 1]} {key.year}',
            'filed': row['filed'],
            'settled': row['settled'],
            'closed': row['closed'],
            'settlement_rate': _rate(row['settled'], row['closed']),
        })

    return {
        'total': sum(by_status.values()),
        'open': by_status.get(BlotterCase.STATUS_FILED, 0) + by_status.get(BlotterCase.STATUS_UNDER_MEDIATION, 0),
        'settled': settled,
        'closed': closed,
        'settlement_rate': _rate(settled, closed),
        'avg_days_to_settle': round(sum(durations) / len(durations), 1) if durations else None,
        'by_status': _choice_rows(by_status, BlotterCase.STATUS_CHOICES),
        'by_type': _choice_rows(by_type, BlotterCase.INCIDENT_TYPE_CHOICES),
        'by_purok': by_purok,
        'months': months,
    }


def _summarise(demo, density, appts, rev, blot):
    """Headline KPIs, derived from the other blocks so they can never disagree."""
    sectors = {row['code']: row['count'] for row in demo['sectors']}
    status = {row['code']: row['count'] for row in appts['by_status']}
    return {
        'population': demo['population'],
        'households': sum(row['households'] for row in density['rows']),
        'minors': demo['minors'],
        'seniors': sectors['senior'],
        'pwd': sectors['pwd'],
        'solo_parents': sectors['solo_parent'],
        'four_ps': sectors['4ps'],
        'appointments_total': appts['total'],
        'appointments_pending': status[Appointment.STATUS_PENDING],
        'appointments_completed': status[Appointment.STATUS_COMPLETED],
        'documents_issued': appts['issued_documents'],
        'revenue_total': rev['total'],
        'currency': rev['currency'],
        'blotter_cases': blot['total'],
        'settlement_rate': blot['settlement_rate'],
    }


def summary_block(filters):
    """Headline KPIs only (computes the blocks they are derived from)."""
    return _summarise(demographics(filters), purok_density(filters), appointments(filters), revenue(filters),
                      blotter(filters))


def build_report(filters):
    """Every block for the given Filters. The CSV export and print page read this."""
    demo = demographics(filters)
    density = purok_density(filters)
    appts = appointments(filters)
    rev = revenue(filters)
    blot = blotter(filters)
    return {
        'filters': filters.as_dict(),
        'generated_at': timezone.now().isoformat(),
        'summary': _summarise(demo, density, appts, rev, blot),
        'demographics': demo,
        'purok_density': density,
        'appointments': appts,
        'revenue': rev,
        'blotter': blot,
    }