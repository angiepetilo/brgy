"""
Read-only queries for the Blotter module. Every query starts from
policies.visible_cases(user), so scope and confidentiality are never skipped.
"""
import re
from datetime import date

from django.db.models import Prefetch, Q
from django.http import Http404

from apps.accounts.models import Purok
from apps.blotter import policies
from apps.blotter.models import BlotterCase, BlotterHearing, BlotterParty
from apps.history.models import ActivityLog

AUDIT_TYPE = 'Blotter Case'
STATUS_CHANGE_PREFIX = 'Status:'
HEARING_PREFIX = 'Hearing:'
MAX_SEARCH_LENGTH = 100
PAGE_SIZE = 20

_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class FilterError(ValueError):
    """A list filter has a bad value."""


def _parse_date(name, raw):
    if not _ISO_DATE.match(raw):
        raise FilterError(f'{name} must be an ISO date (YYYY-MM-DD).')
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise FilterError(f'{name} is not a valid calendar date.')


def parse_case_filters(params):
    """
    Clean list filters from a mapping such as request.GET. Raises FilterError for a bad
    value. Returns a dict with keys status, incident_type, purok (id), date_from,
    date_to (date) and q; missing filters are None / ''.
    """
    get = lambda key: str(params.get(key) or '').strip()  # noqa: E731
    status, incident_type, raw_purok = get('status'), get('incident_type'), get('purok')
    raw_from, raw_to, q = get('date_from'), get('date_to'), get('q')

    if status and status not in dict(BlotterCase.STATUS_CHOICES):
        raise FilterError('status is not a valid case status.')
    if incident_type and incident_type not in dict(BlotterCase.INCIDENT_TYPE_CHOICES):
        raise FilterError('incident_type is not a valid incident type.')
    purok = None
    if raw_purok:
        if not (raw_purok.isascii() and raw_purok.isdigit()) or len(raw_purok) > 9:
            raise FilterError('purok must be a purok id.')
        purok = int(raw_purok)
    date_from = _parse_date('date_from', raw_from) if raw_from else None
    date_to = _parse_date('date_to', raw_to) if raw_to else None
    if date_from and date_to and date_from > date_to:
        raise FilterError('date_from must not be after date_to.')
    if len(q) > MAX_SEARCH_LENGTH:
        raise FilterError(f'Search text may not exceed {MAX_SEARCH_LENGTH} characters.')
    return {
        'status': status, 'incident_type': incident_type, 'purok': purok,
        'date_from': date_from, 'date_to': date_to, 'q': q,
    }


def case_list(user, filters):
    """Visible cases matching cleaned filters (parse_case_filters), newest filing first."""
    qs = policies.visible_cases(user).select_related('purok')
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    if filters.get('incident_type'):
        qs = qs.filter(incident_type=filters['incident_type'])
    if filters.get('purok'):
        qs = qs.filter(purok_id=filters['purok'])
    if filters.get('date_from'):
        qs = qs.filter(incident_date__gte=filters['date_from'])
    if filters.get('date_to'):
        qs = qs.filter(incident_date__lte=filters['date_to'])
    if filters.get('q'):
        text = filters['q']
        matching = BlotterParty.objects.filter(full_name__icontains=text).values('case_id')
        qs = qs.filter(
            Q(case_no__icontains=text) | Q(narrative__icontains=text)
            | Q(location__icontains=text) | Q(pk__in=matching)
        )
    return qs.prefetch_related('parties').order_by('-filed_at', '-id')


def case_detail(user, pk):
    """The case with parties and hearings, or Http404 when it is not visible to the user."""
    case = (
        policies.visible_cases(user)
        .select_related('purok', 'handled_by', 'recorded_by')
        .prefetch_related(
            Prefetch('parties', queryset=BlotterParty.objects.select_related('resident').order_by('role', 'id')),
            Prefetch('hearings', queryset=BlotterHearing.objects.select_related('recorded_by').order_by('scheduled_at', 'id')),
        )
        .filter(pk=pk)
        .first()
    )
    if case is None:
        raise Http404('Blotter case not found.')
    return case


def puroks_for(user):
    """Puroks the user may pick (filters and the case form)."""
    qs = Purok.objects.order_by('name')
    names = policies.purok_scope(user)
    if names is None:
        return qs
    name_q = Q()
    for name in names:
        name_q |= Q(name__iexact=name)
    return qs.filter(name_q)


def handler_choices():
    """Active staff, kapitan and admin users who can be assigned as case handler."""
    from apps.accounts.models import User
    return User.objects.filter(
        status=User.STATUS_ACTIVE,
    ).filter(
        Q(role__in=[User.ROLE_STAFF, User.ROLE_KAPITAN, User.ROLE_ADMIN]) | Q(is_superuser=True)
    ).order_by('last_name', 'first_name', 'username')


def _actor_name(user):
    if user is None:
        return 'System'
    return user.get_full_name() or user.username


def status_timeline(case):
    """
    Chronological events: filing, hearings and status changes (from the audit log,
    which records who did it). Cases changed outside the services (no audit rows)
    fall back to the settled_at / escalated_at / closed_at stamps.
    """
    events = [{
        'at': case.filed_at, 'kind': 'filed', 'label': 'Case filed',
        'actor': _actor_name(case.recorded_by), 'notes': '',
    }]
    logs = [
        log for log in
        ActivityLog.objects.filter(action_type=AUDIT_TYPE, target_id=str(case.pk))
        .exclude(action=ActivityLog.ACTION_CREATE)
        .select_related('actor').order_by('created_at', 'id')
        if not log.details.startswith(HEARING_PREFIX)  # hearings come from BlotterHearing below
    ]
    status_logs = [log for log in logs if log.details.startswith(STATUS_CHANGE_PREFIX)]
    for log in logs:
        events.append({
            'at': log.created_at,
            'kind': 'status' if log in status_logs else 'update',
            'label': log.details.split('\n', 1)[0],
            'actor': _actor_name(log.actor),
            'notes': log.details.split('\n', 1)[1] if '\n' in log.details else '',
        })
    if not status_logs:
        for field, label in (('settled_at', 'Settled'), ('escalated_at', 'Escalated')):
            if getattr(case, field):
                events.append({'at': getattr(case, field), 'kind': 'status', 'label': label, 'actor': '', 'notes': ''})
        if case.closed_at and case.status in (BlotterCase.STATUS_DISMISSED, BlotterCase.STATUS_WITHDRAWN):
            events.append({'at': case.closed_at, 'kind': 'status', 'label': case.get_status_display(),
                           'actor': '', 'notes': ''})
    for hearing in case.hearings.all():
        events.append({
            'at': hearing.scheduled_at, 'kind': 'hearing', 'label': 'Hearing',
            'actor': _actor_name(hearing.recorded_by), 'notes': hearing.outcome_notes,
        })
    events.sort(key=lambda e: e['at'])
    return events
