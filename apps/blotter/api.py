"""
JSON API for the Blotter module (mounted under /blotter/api/).

    GET  cases/                      list; filters status, incident_type, purok, date_from,
                                     date_to, q; page (20 per page). 400 on a bad filter.
    POST cases/create/               file a case (JSON body or the HTML form fields).
                                     Rate limited per user (RATE_LIMITS['blotter_create']).
    GET  cases/<pk>/                 detail; 404 when the case is not visible to the caller.
    POST cases/<pk>/transition/      {"to_status": "...", "notes": "..."}

All routes need blotter.view (create needs blotter.create). Anonymous callers get 401
JSON, users without the right get 403 JSON. Validation errors are 400
{"errors": {field: [messages]}}; party errors are {"errors": {"parties": [{...}, ...]}}.
POSTs need the CSRF token (X-CSRFToken header) like every other session-authenticated form.
"""
import json
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_perm
from apps.blotter import forms, policies, selectors, services
from apps.core.http import json_error, json_forbidden
from apps.core.ratelimit import ratelimit


class BadPayload(ValueError):
    pass


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response


def _errors(status, errors):
    return _json({'errors': errors}, status=status)


def _form_errors(form):
    return {field: [str(m) for m in messages] for field, messages in form.errors.items()}


def _validation_errors(exc):
    if hasattr(exc, 'error_dict'):
        return {field: [str(m) for m in messages] for field, messages in exc.message_dict.items()}
    return {'__all__': [str(m) for m in exc.messages]}


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.localtime(value).isoformat()
    return value.isoformat()


def _payload(request):
    """Request body as a dict: JSON when the content type says so, else request.POST."""
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body or b'{}')
        except (ValueError, UnicodeDecodeError):
            raise BadPayload('The request body is not valid JSON.')
        if not isinstance(body, dict):
            raise BadPayload('The request body must be a JSON object.')
        return body
    return request.POST


def serialize_case(case):
    return {
        'id': case.pk,
        'case_no': case.case_no,
        'incident_type': case.incident_type,
        'incident_type_label': case.get_incident_type_display(),
        'incident_date': _iso(case.incident_date),
        'status': case.status,
        'status_label': case.get_status_display(),
        'purok': case.purok.name if case.purok else None,
        'filed_at': _iso(case.filed_at),
        'is_confidential': case.is_confidential,
        'parties': [{'role': p.role, 'full_name': p.full_name} for p in case.parties.all()],
        'url': reverse('blotter:case_detail', args=[case.pk]),
    }


def serialize_case_detail(user, case):
    data = serialize_case(case)
    data.update({
        'incident_time': case.incident_time.strftime('%H:%M') if case.incident_time else None,
        'location': case.location,
        'narrative': case.narrative,
        'resolution_notes': case.resolution_notes,
        'settled_at': _iso(case.settled_at),
        'escalated_at': _iso(case.escalated_at),
        'closed_at': _iso(case.closed_at),
        'handled_by': (case.handled_by.get_full_name() or case.handled_by.username) if case.handled_by else None,
        'parties': [
            {'id': p.pk, 'role': p.role, 'full_name': p.full_name, 'address': p.address,
             'contact_no': p.contact_no, 'resident': p.resident_id}
            for p in case.parties.all()
        ],
        'hearings': [
            {'id': h.pk, 'scheduled_at': _iso(h.scheduled_at), 'outcome_notes': h.outcome_notes,
             'complainant_attended': h.complainant_attended, 'respondent_attended': h.respondent_attended}
            for h in case.hearings.all()
        ],
        'allowed_transitions': [code for code, _label in policies.allowed_transitions(user, case)],
    })
    return data


@require_perm('blotter', 'view')
@require_GET
def api_list(request):
    try:
        filters = selectors.parse_case_filters(request.GET)
    except selectors.FilterError as exc:
        return json_error(400, str(exc))
    paginator = Paginator(selectors.case_list(request.user, filters), selectors.PAGE_SIZE)
    try:
        page = paginator.page(request.GET.get('page') or 1)
    except (PageNotAnInteger, EmptyPage):
        return json_error(400, 'page is out of range.')
    return _json({
        'count': paginator.count,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'results': [serialize_case(case) for case in page.object_list],
    })


@require_perm('blotter', 'view')
@require_GET
def api_detail(request, pk):
    try:
        case = selectors.case_detail(request.user, pk)
    except Http404:
        return json_error(404, 'Blotter case not found.')
    return _json(serialize_case_detail(request.user, case))


def _party_errors(raw_parties):
    """Validate a JSON list of parties with BlotterPartyForm. Returns (cleaned, errors)."""
    if not isinstance(raw_parties, list):
        return None, ['Send parties as a list of objects.']
    cleaned, errors, failed = [], [], False
    for raw in raw_parties:
        if not isinstance(raw, dict):
            errors.append({'__all__': ['Each party must be an object.']})
            failed = True
            continue
        form = forms.BlotterPartyForm(data=raw)
        if form.is_valid():
            cleaned.append(form.cleaned_data)
            errors.append({})
        else:
            errors.append(_form_errors(form))
            failed = True
    return cleaned, (errors if failed else None)


@require_perm('blotter', 'create')
@require_POST
@ratelimit(key='user', rate='blotter_create')
def api_create(request):
    try:
        data = _payload(request)
    except BadPayload as exc:
        return _errors(400, {'__all__': [str(exc)]})

    case_form = forms.BlotterCaseForm(data=data, user=request.user)
    if request.content_type == 'application/json':
        parties, party_errors = _party_errors(data.get('parties', []))
    else:
        formset = forms.party_formset(data)
        if formset.is_valid():
            parties, party_errors = forms.filled_parties(formset), None
        else:
            party_errors = [_form_errors(f) for f in formset.forms]
            if formset.non_form_errors():
                party_errors.append({'__all__': [str(e) for e in formset.non_form_errors()]})
            parties = None

    errors = {} if case_form.is_valid() else _form_errors(case_form)
    if party_errors:
        errors['parties'] = party_errors
    if errors:
        return _errors(400, errors)

    try:
        case = services.create_case(request.user, case_form.cleaned_data, parties, request=request)
    except ValidationError as exc:
        return _errors(400, _validation_errors(exc))
    except PermissionDenied as exc:
        return json_forbidden(str(exc))
    except ValueError as exc:
        return _errors(400, {'__all__': [str(exc)]})
    return _json({
        'id': case.pk,
        'case_no': case.case_no,
        'status': case.status,
        'url': reverse('blotter:case_detail', args=[case.pk]),
    }, status=201)


@require_perm('blotter', 'view')
@require_POST
def api_transition(request, pk):
    try:
        data = _payload(request)
    except BadPayload as exc:
        return _errors(400, {'__all__': [str(exc)]})
    try:
        case = selectors.case_detail(request.user, pk)
    except Http404:
        return json_error(404, 'Blotter case not found.')

    form = forms.TransitionForm(data=data)
    if not form.is_valid():
        return _errors(400, _form_errors(form))
    try:
        case = services.transition_case(
            request.user, case, form.cleaned_data['to_status'], form.cleaned_data['notes'], request=request,
        )
    except PermissionDenied as exc:
        return json_forbidden(str(exc))
    except ValueError as exc:
        return _errors(400, {'to_status': [str(exc)]})
    return _json({
        'id': case.pk,
        'case_no': case.case_no,
        'status': case.status,
        'status_label': case.get_status_display(),
        'settled_at': _iso(case.settled_at),
        'escalated_at': _iso(case.escalated_at),
        'closed_at': _iso(case.closed_at),
    })
