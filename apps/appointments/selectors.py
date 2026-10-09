"""
Read-only appointment helpers for templates.

The status stepper and the allowed action buttons are computed here so the
templates never compare status string literals. Transitions mirror the
services: pending -> approve/reject, approved -> complete/no_show; completed,
rejected and no_show are terminal.
"""

from apps.accounts.permissions import check_user_perm, check_staff_appointment_scope
from apps.appointments.models import Appointment

# Main lifecycle shown in the stepper.
_MAIN_STEPS = [
    (Appointment.STATUS_PENDING, 'Pending'),
    (Appointment.STATUS_APPROVED, 'Approved'),
    (Appointment.STATUS_COMPLETED, 'Completed'),
]

# status -> actions the services accept from that status.
_TRANSITIONS = {
    Appointment.STATUS_PENDING: ('approve', 'reject'),
    Appointment.STATUS_APPROVED: ('complete', 'no_show'),
}

# action -> permission action name in the 'appointments' module.
_ACTION_PERMS = {
    'approve': 'approve',
    'reject': 'reject',
    'complete': 'complete',
    'no_show': 'no_show',
}


# state -> existing stepper CSS modifier in main.css.
_STATE_CSS = {'done': 'completed', 'current': 'active', 'upcoming': ''}


def _step(code, label, state, css=None):
    return {'code': code, 'label': label, 'state': state, 'css': _STATE_CSS[state] if css is None else css}


def status_steps(appointment):
    """
    Return the stepper as a list of {code, label, state} dicts.

    state is 'done', 'current' or 'upcoming'. A no-show appointment shows
    Pending and Approved done, then a terminal 'No-Show' current step.
    Rejected appointments have no stepper (the template shows an alert).
    """
    status = appointment.status
    if status == Appointment.STATUS_REJECTED:
        return []
    if status == Appointment.STATUS_NO_SHOW:
        return [
            _step(Appointment.STATUS_PENDING, 'Pending', 'done'),
            _step(Appointment.STATUS_APPROVED, 'Approved', 'done'),
            _step(Appointment.STATUS_NO_SHOW, 'No-Show', 'current', css='rejected'),
        ]

    codes = [code for code, _ in _MAIN_STEPS]
    current_index = codes.index(status) if status in codes else 0
    steps = []
    for index, (code, label) in enumerate(_MAIN_STEPS):
        if index < current_index:
            state = 'done'
        elif index == current_index:
            # Completed is the end of the lifecycle, so it reads as done.
            state = 'done' if code == Appointment.STATUS_COMPLETED else 'current'
        else:
            state = 'upcoming'
        steps.append(_step(code, label, state))
    return steps


def get_viewable_appointment(user, pk, strict_scope=False):
    """
    The appointment ``pk`` if ``user`` may view it, with the detail page's rule:
    admin/kapitan any; resident only their own (404 otherwise, so ids are not
    confirmed); staff only within their scope (PermissionDenied).

    Note: User.is_kapitan_user is also True for role=staff, so on the detail
    page every staff member passes the first branch. ``strict_scope=True``
    (used for private files) treats only role=kapitan as kapitan, so other
    staff must pass check_staff_appointment_scope.
    """
    from django.core.exceptions import PermissionDenied
    from django.shortcuts import get_object_or_404
    from apps.accounts.models import User

    qs = Appointment.objects.select_related('resident', 'processed_by', 'document_type', 'healthcare_service')
    is_kapitan = (user.role == User.ROLE_KAPITAN) if strict_scope else user.is_kapitan_user
    if user.is_admin_user or is_kapitan:
        return get_object_or_404(qs, pk=pk)
    if user.role == User.ROLE_RESIDENT:
        return get_object_or_404(qs, pk=pk, resident=user)
    if user.is_staff_user:
        appointment = get_object_or_404(qs, pk=pk)
        if not check_staff_appointment_scope(user, appointment):
            raise PermissionDenied("You do not have permission to view appointments outside your scope.")
        return appointment
    raise PermissionDenied("Access denied.")


def allowed_actions(appointment, user):
    """Set of actions from {'approve','reject','complete','no_show'} the user may run now."""
    candidates = _TRANSITIONS.get(appointment.status, ())
    if not candidates or not user or not user.is_authenticated:
        return set()
    if not check_staff_appointment_scope(user, appointment):
        return set()
    return {
        action for action in candidates
        if check_user_perm(user, 'appointments', _ACTION_PERMS[action])
    }
