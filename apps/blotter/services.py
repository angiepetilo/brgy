"""
Write operations for the Blotter module. Every function checks permission and scope
(policies), validates with full_clean, writes inside a transaction and records an
ActivityLog row. Audit details never contain the narrative or party names, and notes
of confidential cases are not copied into the audit log.

Errors: PermissionDenied (no right / out of scope), ValidationError (bad data),
ValueError (illegal status change or other rule).
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.functions import Length
from django.utils import timezone

from apps.blotter import policies
from apps.blotter.models import BlotterCase, BlotterHearing, BlotterParty
from apps.blotter.selectors import AUDIT_TYPE, HEARING_PREFIX, STATUS_CHANGE_PREFIX
from apps.history.models import ActivityLog
from apps.history.utils import log_activity

CASE_FIELDS = (
    'incident_type', 'incident_date', 'incident_time', 'location', 'purok',
    'narrative', 'is_confidential', 'handled_by',
)
PARTY_FIELDS = ('role', 'full_name', 'address', 'contact_no', 'resident')
HEARING_FIELDS = ('scheduled_at', 'outcome_notes', 'complainant_attended', 'respondent_attended')
MAX_CASE_NO_ATTEMPTS = 5


def _today():
    return timezone.localdate()


def _deny(message):
    raise PermissionDenied(message)


def _require(actor, action):
    if not policies.can(actor, action):
        _deny(f"You do not have permission to perform '{action}' on 'blotter'.")


def _require_visible(actor, case):
    if not policies.can_see(actor, case):
        _deny('This blotter case is outside your scope.')


def _audit(actor, action, case, details, request=None):
    log_activity(
        actor, action, AUDIT_TYPE,
        target_id=case.pk, target_name=case.case_no, details=details, request=request,
    )


# ---------------------------------------------------------------------------
# Case numbers: BLT-YYYY-NNNN, sequential per filing year
# ---------------------------------------------------------------------------

def _prefix(year):
    return f'{BlotterCase.CASE_NO_PREFIX}-{year}-'


def _last_number(year):
    """Highest NNNN used in `year` (0 when none). Longest first so 10000 sorts after 9999."""
    prefix = _prefix(year)
    last = (
        BlotterCase.objects.filter(case_no__startswith=prefix)
        .order_by(Length('case_no').desc(), '-case_no')
        .values_list('case_no', flat=True).first()
    )
    suffix = last[len(prefix):] if last else ''
    return int(suffix) if suffix.isdigit() else 0


def _is_case_no_clash(exc, case_no):
    return 'case_no' in str(exc).lower() or BlotterCase.objects.filter(case_no=case_no).exists()


def _save_with_case_no(case, year):
    """
    Save a new case with the next free number. A concurrent insert of the same number
    hits the unique constraint; that savepoint is rolled back and the next number is
    tried (counting up from the first candidate, so a stale read snapshot cannot make
    every retry pick the same number).
    """
    first = _last_number(year) + 1
    for attempt in range(MAX_CASE_NO_ATTEMPTS):
        case.case_no = f'{_prefix(year)}{first + attempt:04d}'
        try:
            with transaction.atomic():
                case.save(force_insert=True)
            return case
        except IntegrityError as exc:
            case.pk = None
            case._state.adding = True
            if not _is_case_no_clash(exc, case.case_no):
                raise
    raise ValueError('Could not assign a case number. Please try again.')


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def _check_parties(parties):
    roles = [p.get('role') for p in parties]
    errors = []
    if BlotterParty.ROLE_COMPLAINANT not in roles:
        errors.append('Add at least one complainant.')
    if BlotterParty.ROLE_RESPONDENT not in roles:
        errors.append('Add at least one respondent.')
    if errors:
        raise ValidationError({'parties': errors})


def _check_case_scope(actor, purok, is_confidential):
    if not policies.purok_allowed(actor, purok):
        _deny('You can only record cases for your assigned purok.')
    if is_confidential and not policies.can(actor, 'view_confidential'):
        _deny('You do not have permission to mark a case as confidential.')


def create_case(actor, data, parties, request=None):
    """
    File a new case with its parties. `data` holds CASE_FIELDS, `parties` is a list of
    dicts with PARTY_FIELDS. Needs at least one complainant and one respondent.
    """
    _require(actor, 'create')
    values = {key: data.get(key) for key in CASE_FIELDS if key in data}
    values['is_confidential'] = bool(values.get('is_confidential'))
    _check_case_scope(actor, values.get('purok'), values['is_confidential'])

    parties = [{key: p.get(key) for key in PARTY_FIELDS if key in p} for p in parties]
    _check_parties(parties)

    case = BlotterCase(**values, status=BlotterCase.STATUS_FILED, recorded_by=actor)
    case.full_clean(exclude=['case_no'])
    party_rows = []
    for party in parties:
        party = {k: ('' if v is None and k in ('address', 'contact_no') else v) for k, v in party.items()}
        row = BlotterParty(**party)
        row.full_clean(exclude=['case'])
        party_rows.append(row)

    with transaction.atomic():
        _save_with_case_no(case, _today().year)
        for row in party_rows:
            row.case = case
        BlotterParty.objects.bulk_create(party_rows)
        _audit(actor, ActivityLog.ACTION_CREATE, case,
               f'Filed {case.get_incident_type_display()} case with {len(party_rows)} parties.', request)
    return case


def update_case(actor, case, data, request=None):
    """Edit the incident details of an open case (not its parties or status)."""
    _require(actor, 'edit')
    _require_visible(actor, case)
    if case.is_terminal:
        raise ValueError('A closed case can no longer be edited.')
    values = {key: data[key] for key in CASE_FIELDS if key in data}
    if 'is_confidential' in values:
        values['is_confidential'] = bool(values['is_confidential'])
    _check_case_scope(actor, values.get('purok', case.purok),
                      values.get('is_confidential', case.is_confidential))
    if case.is_confidential and values.get('is_confidential') is False:
        if not policies.can(actor, 'view_confidential'):
            _deny('You do not have permission to change the confidentiality of a case.')

    with transaction.atomic():
        locked = BlotterCase.objects.select_for_update().get(pk=case.pk)
        changed = sorted(k for k, v in values.items() if getattr(locked, k) != v)
        for key, value in values.items():
            setattr(locked, key, value)
        locked.full_clean(exclude=['case_no'])
        locked.save()
        _audit(actor, ActivityLog.ACTION_UPDATE, locked,
               'Updated case details' + (f": {', '.join(changed)}." if changed else '.'), request)
    return locked


def transition_case(actor, case, to_status, notes='', request=None):
    """
    Move a case to `to_status` if TRANSITIONS allows it and the user holds the matching
    permission. Settled stamps settled_at, escalated stamps escalated_at, and every
    terminal status stamps closed_at. Notes of a terminal move become resolution_notes.
    """
    notes = (notes or '').strip()
    if to_status not in dict(BlotterCase.STATUS_CHOICES):
        raise ValueError('Unknown case status.')
    _require(actor, policies.ACTION_FOR_STATUS.get(to_status, 'edit'))
    _require_visible(actor, case)

    with transaction.atomic():
        locked = BlotterCase.objects.select_for_update().get(pk=case.pk)
        old = locked.status
        if to_status not in locked.next_statuses:
            raise ValueError(
                f'A {locked.get_status_display().lower()} case cannot be moved to '
                f'{BlotterCase.status_label(to_status).lower()}.'
            )
        now = timezone.now()
        locked.status = to_status
        if to_status == BlotterCase.STATUS_SETTLED:
            locked.settled_at = now
        if to_status == BlotterCase.STATUS_ESCALATED:
            locked.escalated_at = now
        if to_status in BlotterCase.TERMINAL:
            locked.closed_at = now
            if notes:
                locked.resolution_notes = notes
        if to_status == BlotterCase.STATUS_UNDER_MEDIATION and locked.handled_by_id is None:
            locked.handled_by = actor
        locked.save()
        details = f'{STATUS_CHANGE_PREFIX} {BlotterCase.status_label(old)} -> {BlotterCase.status_label(to_status)}'
        if notes and not locked.is_confidential:
            details += '\n' + notes
        _audit(actor, ActivityLog.ACTION_UPDATE, locked, details, request)
    return locked


def add_hearing(actor, case, data, request=None):
    """Record a mediation hearing. Needs blotter.mediate; closed cases take no hearings."""
    _require(actor, 'mediate')
    _require_visible(actor, case)
    if case.is_terminal:
        raise ValueError('Hearings cannot be added to a closed case.')
    values = {key: data[key] for key in HEARING_FIELDS if key in data}
    values['outcome_notes'] = values.get('outcome_notes') or ''
    hearing = BlotterHearing(case=case, recorded_by=actor, **values)
    hearing.full_clean(exclude=['case'])
    with transaction.atomic():
        hearing.save()
        when = timezone.localtime(hearing.scheduled_at).strftime('%Y-%m-%d %H:%M')
        _audit(actor, ActivityLog.ACTION_UPDATE, case, f'{HEARING_PREFIX} recorded for {when}.', request)
    return hearing


def delete_case(actor, case, request=None):
    """Delete a case with its parties and hearings (blotter.delete)."""
    _require(actor, 'delete')
    _require_visible(actor, case)
    with transaction.atomic():
        _audit(actor, ActivityLog.ACTION_DELETE, case, f'Deleted case {case.case_no}.', request)
        case.delete()
