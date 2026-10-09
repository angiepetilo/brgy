"""
Permission and scope rules for the Blotter module. No writes, no HTTP.

Who sees what
-------------
* blotter.<action> PermissionRules decide what a user may do (apps.accounts.permissions).
  Residents never get access, even if a rule would allow it.
* Purok scope mirrors check_staff_appointment_scope: admin and superuser see every purok.
  A staff user with a purok StaffAssignment sees only cases of those puroks, unless they
  also hold a service-area assignment of 'all' / 'general' / 'punong barangay'. Everyone
  else holding blotter.view sees every purok.
* Confidential cases are hidden unless the user holds blotter.view_confidential.
"""
from django.db.models import Q

from apps.accounts.models import StaffAssignment, User
from apps.accounts.permissions import check_user_perm
from apps.blotter.models import BlotterCase

MODULE = 'blotter'
ALL_SCOPE_VALUES = frozenset({'all', 'general', 'punong barangay'})

# Permission needed to move a case INTO each status.
ACTION_FOR_STATUS = {
    BlotterCase.STATUS_UNDER_MEDIATION: 'mediate',
    BlotterCase.STATUS_SETTLED: 'settle',
    BlotterCase.STATUS_ESCALATED: 'escalate',
    BlotterCase.STATUS_DISMISSED: 'edit',
    BlotterCase.STATUS_WITHDRAWN: 'edit',
}


def can(user, action):
    """blotter.<action> for this user. Residents are always denied."""
    if not user or not user.is_authenticated or user.is_resident_user:
        return False
    return check_user_perm(user, MODULE, action)


def purok_scope(user):
    """
    None when the user may see every purok, otherwise the list of purok names
    (as stored on their StaffAssignments) they are limited to.
    """
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return None
    puroks = []
    for assignment in StaffAssignment.objects.filter(user=user):
        value = assignment.scope_value.strip()
        if assignment.scope_type == StaffAssignment.SCOPE_SERVICE_AREA and value.lower() in ALL_SCOPE_VALUES:
            return None
        if assignment.scope_type == StaffAssignment.SCOPE_PUROK:
            if value.lower() == 'all':
                return None
            puroks.append(value)
    return puroks or None


def scope_filter(user):
    """Q limiting cases to the user's puroks, or None for all puroks."""
    puroks = purok_scope(user)
    if puroks is None:
        return None
    q = Q()
    for name in puroks:
        q |= Q(purok__name__iexact=name)
    return q


def purok_allowed(user, purok):
    """May the user file / move a case into `purok` (a Purok or None)?"""
    puroks = purok_scope(user)
    if puroks is None:
        return True
    return purok is not None and purok.name.strip().lower() in {p.lower() for p in puroks}


def visible_cases(user):
    """Every BlotterCase this user may open. Empty for anyone without blotter.view."""
    if not can(user, 'view'):
        return BlotterCase.objects.none()
    qs = BlotterCase.objects.all()
    q = scope_filter(user)
    if q is not None:
        qs = qs.filter(q)
    if not can(user, 'view_confidential'):
        qs = qs.exclude(is_confidential=True)
    return qs


def can_see(user, case):
    return visible_cases(user).filter(pk=case.pk).exists()


def can_transition(user, case, to_status):
    """Legal next status AND the matching permission (scope is checked by can_see)."""
    if to_status not in case.next_statuses:
        return False
    return can(user, ACTION_FOR_STATUS[to_status])


def allowed_transitions(user, case):
    """[(status, label), ...] the user may move this case to, in TRANSITIONS order."""
    return [
        (status, BlotterCase.status_label(status))
        for status in case.next_statuses
        if can(user, ACTION_FOR_STATUS[status])
    ]


def can_add_hearing(user, case):
    return not case.is_terminal and can(user, 'mediate')


def can_edit(user, case):
    return not case.is_terminal and can(user, 'edit')


def can_delete(user, case):
    return can(user, 'delete')
