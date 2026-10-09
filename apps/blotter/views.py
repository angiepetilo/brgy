"""
HTML views for the Blotter module. Thin: permission decorator, form validation,
one selector or service call, render or redirect. Rules live in policies/services.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import BarangayInfo
from apps.accounts.permissions import require_perm
from apps.blotter import forms, policies, selectors, services
from apps.blotter.models import BlotterCase
from apps.core.ratelimit import ratelimit


def _apply_service_errors(exc, form):
    """Put a service ValidationError on the form; returns the party-level messages."""
    party_errors = []
    if hasattr(exc, 'error_dict'):
        for field, errors in exc.message_dict.items():
            if field == 'parties':
                party_errors.extend(errors)
            elif field in form.fields:
                for error in errors:
                    form.add_error(field, error)
            else:
                for error in errors:
                    form.add_error(None, error)
    else:
        for error in exc.messages:
            form.add_error(None, error)
    return party_errors


@require_perm('blotter', 'view')
@require_GET
def case_list(request):
    error = ''
    try:
        filters = selectors.parse_case_filters(request.GET)
    except selectors.FilterError as exc:
        error, filters = str(exc), selectors.parse_case_filters({})
    page = Paginator(selectors.case_list(request.user, filters), selectors.PAGE_SIZE).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'blotter/case_list.html', {
        'page_obj': page,
        'filters': filters,
        'filter_error': error,
        'query_string': query.urlencode(),
        'puroks': selectors.puroks_for(request.user),
        'status_choices': BlotterCase.STATUS_CHOICES,
        'type_choices': BlotterCase.INCIDENT_TYPE_CHOICES,
        'can_create': policies.can(request.user, 'create'),
    })


@require_perm('blotter', 'create')
@require_http_methods(['GET', 'POST'])
@ratelimit(key='user', rate='blotter_create')
def case_create(request):
    party_errors = []
    if request.method == 'POST':
        form = forms.BlotterCaseForm(request.POST, user=request.user)
        formset = forms.party_formset(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                case = services.create_case(
                    request.user, form.cleaned_data, forms.filled_parties(formset), request=request,
                )
            except ValidationError as exc:
                party_errors = _apply_service_errors(exc, form)
            except (PermissionDenied, ValueError) as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f'Case {case.case_no} has been filed.')
                return redirect('blotter:case_detail', pk=case.pk)
    else:
        form = forms.BlotterCaseForm(user=request.user)
        formset = forms.party_formset()
    return render(request, 'blotter/case_form.html', {
        'form': form, 'formset': formset, 'party_errors': party_errors, 'is_edit': False,
    })


@require_perm('blotter', 'edit')
@require_http_methods(['GET', 'POST'])
def case_edit(request, pk):
    case = selectors.case_detail(request.user, pk)
    if not policies.can_edit(request.user, case):
        messages.error(request, 'A closed case can no longer be edited.')
        return redirect('blotter:case_detail', pk=case.pk)
    if request.method == 'POST':
        form = forms.BlotterCaseForm(request.POST, instance=case, user=request.user)
        if form.is_valid():
            try:
                services.update_case(request.user, case, form.cleaned_data, request=request)
            except ValidationError as exc:
                _apply_service_errors(exc, form)
            except (PermissionDenied, ValueError) as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f'Case {case.case_no} has been updated.')
                return redirect('blotter:case_detail', pk=case.pk)
    else:
        form = forms.BlotterCaseForm(instance=case, user=request.user)
    return render(request, 'blotter/case_form.html', {
        'form': form, 'case': case, 'is_edit': True, 'party_errors': [],
    })


@require_perm('blotter', 'view')
@require_GET
def case_detail(request, pk):
    case = selectors.case_detail(request.user, pk)
    user = request.user
    return render(request, 'blotter/case_detail.html', {
        'case': case,
        'timeline': selectors.status_timeline(case),
        'transitions': policies.allowed_transitions(user, case),
        'can_add_hearing': policies.can_add_hearing(user, case),
        'can_edit': policies.can_edit(user, case),
        'can_delete': policies.can_delete(user, case),
        'hearing_form': forms.HearingForm(),
        'transition_form': forms.TransitionForm(),
    })


@require_perm('blotter', 'view')
@require_POST
def case_transition(request, pk):
    case = selectors.case_detail(request.user, pk)
    form = forms.TransitionForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a valid status.')
        return redirect('blotter:case_detail', pk=case.pk)
    try:
        case = services.transition_case(
            request.user, case, form.cleaned_data['to_status'], form.cleaned_data['notes'], request=request,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Case {case.case_no} is now {case.get_status_display().lower()}.')
    return redirect('blotter:case_detail', pk=case.pk)


@require_perm('blotter', 'mediate')
@require_POST
def hearing_add(request, pk):
    case = selectors.case_detail(request.user, pk)
    form = forms.HearingForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error if field == '__all__' else f'{form.fields[field].label}: {error}')
        return redirect('blotter:case_detail', pk=case.pk)
    try:
        services.add_hearing(request.user, case, form.cleaned_data, request=request)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Hearing recorded.')
    return redirect('blotter:case_detail', pk=case.pk)


@require_perm('blotter', 'delete')
@require_POST
def case_delete(request, pk):
    case = selectors.case_detail(request.user, pk)
    case_no = case.case_no
    services.delete_case(request.user, case, request=request)
    messages.success(request, f'Case {case_no} has been deleted.')
    return redirect('blotter:case_list')


@require_perm('blotter', 'view')
@require_GET
def case_print(request, pk):
    case = selectors.case_detail(request.user, pk)
    return render(request, 'blotter/case_print.html', {
        'case': case,
        'timeline': selectors.status_timeline(case),
        'info': BarangayInfo.get_solo(),
    })
