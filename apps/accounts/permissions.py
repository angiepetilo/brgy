"""
Central Permission System & Code Registry for BARANGAY.PH.
Modules register actions dynamically.
Enforces permissions in views with @require_perm(module, action).
Admin and superusers are unconditionally allowed (no Officer record needed).
Staff rights are computed as the union of rules across all their StaffAssignments (no assignment = deny by default).
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.accounts.models import User, Officer, StaffAssignment, PermissionRule, Purok


class PermissionRegistry:
    """
    In-code registry where each module registers its available actions.
    The admin permission page is dynamically generated from this registry.
    """
    def __init__(self):
        self._registry = {}

    def register(self, module, actions):
        """
        Registers a list of actions under a module key.
        """
        if module not in self._registry:
            self._registry[module] = set()
        self._registry[module].update(actions)

    def get_modules(self):
        """Returns sorted dict: {module: sorted([action1, action2, ...])}"""
        res = {k: set(v) for k, v in self._registry.items()}
        try:
            from apps.communications.models import PostCategory
            for cat in PostCategory.objects.filter(is_active=True):
                slug = cat.slug or cat.name.lower().replace(' ', '_')
                res['communications'].add(f"post_{slug}")
        except Exception:
            pass
        return {k: sorted(list(v)) for k, v in sorted(res.items())}

    def get_actions(self, module):
        return self.get_modules().get(module, [])

    @classmethod
    def get_actions_for_module(cls, module):
        return registry.get_modules().get(module, [])


registry = PermissionRegistry()

# Register core application modules and actions:
registry.register('accounts', ['view', 'create', 'edit', 'approve', 'reject', 'delete', 'resend_password'])
registry.register('appointments', ['view', 'create', 'approve', 'reject', 'complete', 'no_show', 'manage_schedule', 'manage_services'])
registry.register('health_center', ['view', 'create', 'approve', 'reject', 'complete', 'no_show', 'manage_schedule', 'manage_services'])
registry.register('communications', [
    'view', 'create', 'edit', 'delete', 'post_category',
    'post_announcement', 'post_health', 'post_emergency',
    'post_education', 'post_event', 'post_concern'
])
registry.register('chat', ['view', 'message', 'resolve'])
registry.register('residents', ['view', 'create', 'edit', 'delete', 'assign', 'view_needs', 'edit_needs'])
registry.register('officers', ['view', 'edit', 'assign_permissions'])
registry.register('statistics', ['view', 'export'])
registry.register('blotter', ['view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential'])
registry.register('system', [
    'view', 'edit', 'manage_categories', 'manage_documents',
    'manage_health_services', 'manage_concerns', 'manage_staff', 'preview_emails'
])


def seed_default_permissions():
    """
    Seeds baseline officer records and editable default PermissionRules for:
    - Punong Barangay: all registered modules and actions
    - Secretary: broad operational access
    - Treasurer: finance/accounts/appointments view
    - Kagawad committees: Health, Peace & Order, Education, Infrastructure
    - BHW & Tanod
    - Purok Leader
    """
    for pos_key, pos_label in Officer.POSITION_CHOICES:
        if not Officer.objects.filter(position=pos_label).exists():
            Officer.objects.create(position=pos_label)

    # Committee-specific Kagawad positions
    committees = ['Health', 'Peace and Order', 'Education', 'Infrastructure']
    for comm in committees:
        if not Officer.objects.filter(position='Kagawad', committee=comm).exists():
            Officer.objects.create(position='Kagawad', committee=comm)

    all_mods = registry.get_modules()

    # 1. Punong Barangay (Kapitan): full access to all
    pb = Officer.objects.filter(position=Officer.POSITION_PUNONG_BARANGAY).first()
    if pb:
        for mod, acts in all_mods.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=pb, module=mod, action=act, defaults={'allowed': True})

    # 2. Secretary: broad operational access
    sec = Officer.objects.filter(position=Officer.POSITION_SECRETARY).first()
    if sec:
        sec_allowed = {
            'accounts': ['view', 'create', 'edit', 'approve', 'reject', 'resend_password'],
            'appointments': ['view', 'create', 'approve', 'reject', 'complete', 'no_show', 'manage_schedule', 'manage_services'],
            'communications': ['view', 'create', 'edit', 'delete', 'post_category', 'post_announcement', 'post_health', 'post_emergency', 'post_education', 'post_event', 'post_concern'],
            'chat': ['view', 'message', 'resolve'],
            'residents': ['view', 'create', 'edit', 'view_needs'],
            'officers': ['view'],
            'system': ['view'],
            'statistics': ['view', 'export'],
            'blotter': ['view', 'create', 'edit'],
        }
        for mod, acts in sec_allowed.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=sec, module=mod, action=act, defaults={'allowed': True})

    # 3. Treasurer
    treas = Officer.objects.filter(position=Officer.POSITION_TREASURER).first()
    if treas:
        treas_allowed = {
            'accounts': ['view'],
            'appointments': ['view'],
            'communications': ['view', 'post_announcement'],
            'chat': ['view', 'message'],
            'residents': ['view'],
        }
        for mod, acts in treas_allowed.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=treas, module=mod, action=act, defaults={'allowed': True})

    # 4. Kagawad - Health & BHW
    for health_pos, health_comm in [('Kagawad', 'Health'), ('BHW', '')]:
        q = Officer.objects.filter(position=health_pos)
        if health_comm:
            q = q.filter(committee=health_comm)
        h_officer = q.first()
        if h_officer:
            h_allowed = {
                'appointments': ['view', 'create', 'approve', 'reject', 'complete', 'no_show', 'manage_schedule', 'manage_services'],
                'communications': ['view', 'create', 'post_health', 'post_announcement'],
                'chat': ['view', 'message'],
                'residents': ['view', 'view_needs'],
            }
            for mod, acts in h_allowed.items():
                for act in acts:
                    PermissionRule.objects.get_or_create(officer=h_officer, module=mod, action=act, defaults={'allowed': True})

    # 5. Kagawad - Peace and Order & Tanod (blotter rights differ: the Tanod only records)
    blotter_by_position = {
        'Kagawad': ['view', 'create', 'edit', 'mediate', 'settle', 'escalate'],
        'Tanod': ['view', 'create'],
    }
    for po_pos, po_comm in [('Kagawad', 'Peace and Order'), ('Tanod', '')]:
        q = Officer.objects.filter(position=po_pos)
        if po_comm:
            q = q.filter(committee=po_comm)
        po_officer = q.first()
        if po_officer:
            po_allowed = {
                'communications': ['view', 'create', 'post_emergency', 'post_announcement'],
                'chat': ['view', 'message'],
                'residents': ['view'],
                'blotter': blotter_by_position[po_pos],
            }
            for mod, acts in po_allowed.items():
                for act in acts:
                    PermissionRule.objects.get_or_create(officer=po_officer, module=mod, action=act, defaults={'allowed': True})

    # 6. Kagawad - Education
    edu_officer = Officer.objects.filter(position='Kagawad', committee='Education').first()
    if edu_officer:
        edu_allowed = {
            'communications': ['view', 'create', 'post_education', 'post_announcement'],
            'chat': ['view', 'message'],
            'residents': ['view'],
        }
        for mod, acts in edu_allowed.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=edu_officer, module=mod, action=act, defaults={'allowed': True})

    # 7. Kagawad - Infrastructure
    infra_officer = Officer.objects.filter(position='Kagawad', committee='Infrastructure').first()
    if infra_officer:
        infra_allowed = {
            'communications': ['view', 'create', 'post_announcement'],
            'chat': ['view', 'message'],
            'residents': ['view'],
        }
        for mod, acts in infra_allowed.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=infra_officer, module=mod, action=act, defaults={'allowed': True})

    # 8. Purok Leader
    pl = Officer.objects.filter(position=Officer.POSITION_PUROK_LEADER).first()
    if pl:
        pl_allowed = {
            'communications': ['view', 'create', 'post_concern'],
            'chat': ['view', 'message'],
            'residents': ['view'],
        }
        for mod, acts in pl_allowed.items():
            for act in acts:
                PermissionRule.objects.get_or_create(officer=pl, module=mod, action=act, defaults={'allowed': True})


def check_user_perm(user, module, action):
    """
    Evaluates whether a user has permission to perform an action on a module.
    1. Admin / superuser: unconditionally True (no Officer record needed).
    2. Kapitan: evaluated through Punong Barangay PermissionRules.
    3. Staff: computed as the union of rules across all their StaffAssignments.
       No assignment = deny by default (False).
    4. Residents: False for staff/admin actions.
    """
    if not user or not user.is_authenticated:
        return False

    if user.status != User.STATUS_ACTIVE:
        return False

    # 1. Admin and superusers unconditionally allowed (no Officer record needed)
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return True

    # 2. Kapitan is evaluated through Punong Barangay PermissionRules
    if user.role == User.ROLE_KAPITAN:
        pb_officer = Officer.objects.filter(position=Officer.POSITION_PUNONG_BARANGAY).first()
        if pb_officer:
            rule = PermissionRule.objects.filter(
                officer=pb_officer,
                module=module,
                action=action
            ).first()
            return rule.allowed if rule else False

    # 3. Staff user rights computed as the union of rules across all their StaffAssignments.
    # No assignment = deny by default.
    assignments = StaffAssignment.objects.filter(user=user)
    if not assignments.exists():
        return False

    assigned_officer_ids = list(assignments.values_list('officer_id', flat=True))

    # Check if ANY assigned officer has allowed=True for module and action (union of permissions)
    has_allowed_rule = PermissionRule.objects.filter(
        officer_id__in=assigned_officer_ids,
        module=module,
        action=action,
        allowed=True
    ).exists()

    return has_allowed_rule


has_perm = check_user_perm


def require_perm(module, action):
    """
    Universal decorator for views.
    Raises PermissionDenied (HTTP 403) if the user does not have permission.
    JSON callers (apps.core.http.wants_json) get 401/403 JSON instead of a
    login redirect or an HTML 403 page.
    """
    from apps.core.http import json_forbidden, json_login_required, wants_json

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if wants_json(request):
                    return json_login_required(request)
                return redirect(f"/accounts/login/?next={request.path}")
            if not check_user_perm(request.user, module, action):
                message = f"You do not have permission to perform '{action}' on '{module}'."
                if wants_json(request):
                    return json_forbidden(message)
                raise PermissionDenied(message)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def can_manage_service_area(user, service_area_name):
    """
    Staff act only inside their assignment.
    Checks if user is admin, superuser, or has a matching service_area StaffAssignment.
    """
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return True

    return StaffAssignment.objects.filter(
        user=user,
        scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
        scope_value__iexact=service_area_name
    ).exists() or StaffAssignment.objects.filter(
        user=user,
        scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
        scope_value__iexact='All'
    ).exists()


def can_manage_purok(user, purok):
    """
    Purok leader to residents is derived from Resident.purok or Purok.leader.
    Admin and superuser have global purok scope.
    """
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return True

    purok_name = purok.name if hasattr(purok, 'name') else str(purok)

    if Purok.objects.filter(name=purok_name, leader__user=user).exists():
        return True

    return StaffAssignment.objects.filter(
        user=user,
        scope_type=StaffAssignment.SCOPE_PUROK,
        scope_value__iexact=purok_name
    ).exists() or StaffAssignment.objects.filter(
        user=user,
        scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
        scope_value__iexact='All'
    ).exists()


def check_staff_appointment_scope(user, appointment):
    """
    Checks if a staff user has jurisdiction over an appointment by evaluating
    the union of their StaffAssignments.

    RULES FOR COMBINED SERVICE-AREA AND PUROK ASSIGNMENTS:
    1. Unconditional bypass:
       - Only admin (role=admin) and superuser (is_superuser=True) bypass scope checks.
       - Kapitan / Punong Barangay must have a StaffAssignment (e.g. scope_value='All' or committee-specific).
    2. Service-area jurisdiction:
       - If staff has a service-area assignment (e.g. 'Health'), they have jurisdiction
         over ALL appointments in that category across all puroks.
    3. Purok jurisdiction:
       - If staff has a purok assignment (e.g. 'Purok 1'), they have jurisdiction over
         any appointment where the resident belongs to 'Purok 1', even if the service area
         is outside their service-area assignment (e.g. a Document request).
    4. Deny by default:
       - An appointment that matches NEITHER the staff user's service area NOR the resident's
         purok is denied (PermissionDenied / False).
    """
    if not user or not user.is_authenticated:
        return False
    # Only admin and superuser bypass unconditionally:
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return True

    assignments = StaffAssignment.objects.filter(user=user)
    if not assignments.exists():
        return False

    category = appointment.category
    # Check service area assignments
    service_assignments = assignments.filter(scope_type=StaffAssignment.SCOPE_SERVICE_AREA)
    for sa in service_assignments:
        val = sa.scope_value.strip().lower()
        if val in ['all', 'general', 'punong barangay']:
            return True
        if category == 'document' and val in ['documents', 'document', 'clearance']:
            return True
        if category == 'healthcare' and val in ['health', 'healthcare', 'health center', 'health_center', 'health services']:
            return True

    # Check purok assignments
    purok_name = ''
    if appointment.resident:
        if hasattr(appointment.resident, 'resident_profile') and appointment.resident.resident_profile and appointment.resident.resident_profile.purok:
            purok_name = appointment.resident.resident_profile.purok.name
        elif hasattr(appointment.resident, 'purok') and appointment.resident.purok:
            purok_name = appointment.resident.purok.name if hasattr(appointment.resident.purok, 'name') else str(appointment.resident.purok)

    if purok_name:
        purok_assignments = assignments.filter(scope_type=StaffAssignment.SCOPE_PUROK)
        for pa in purok_assignments:
            if pa.scope_value.strip().lower() in [purok_name.strip().lower(), 'all']:
                return True

    return False


# Backward-compatible decorators:
def resident_forbidden(view_func):
    return require_perm('accounts', 'view')(view_func)

def admin_only(view_func):
    return require_perm('system', 'edit')(view_func)

def root_only(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_superuser:
            raise PermissionDenied("Root superuser privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped
