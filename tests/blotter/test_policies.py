"""apps.blotter.policies: RBAC per seeded role, purok scope and confidentiality."""
from apps.accounts.models import StaffAssignment, User
from apps.accounts.permissions import seed_default_permissions
from apps.blotter import policies
from tests.base import (
    DEFAULT_PASSWORD, BaseTestCase, make_admin, make_blotter_case, make_purok, make_resident_user, make_staff,
)
from tests.blotter.common import ALL_ACTIONS, seeded_user


class SeededRoleTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        seed_default_permissions()

    def allowed(self, user):
        return {action for action in ALL_ACTIONS if policies.can(user, action)}

    def test_punong_barangay_has_everything(self):
        self.assertEqual(self.allowed(seeded_user('Punong Barangay')), set(ALL_ACTIONS))

    def test_kapitan_role_uses_punong_barangay_rules(self):
        kapitan = User.objects.create_user(
            username='kap_blotter', password=DEFAULT_PASSWORD, role=User.ROLE_KAPITAN,
            is_approved=True, status=User.STATUS_ACTIVE)
        self.assertEqual(self.allowed(kapitan), set(ALL_ACTIONS))

    def test_secretary(self):
        self.assertEqual(self.allowed(seeded_user('Secretary')), {'view', 'create', 'edit'})

    def test_kagawad_peace_and_order(self):
        self.assertEqual(self.allowed(seeded_user('Kagawad', 'Peace and Order')),
                         {'view', 'create', 'edit', 'mediate', 'settle', 'escalate'})

    def test_tanod(self):
        self.assertEqual(self.allowed(seeded_user('Tanod')), {'view', 'create'})

    def test_other_positions_get_nothing(self):
        for position, committee in (('Treasurer', ''), ('Kagawad', 'Health'), ('BHW', ''), ('Purok Leader', '')):
            self.assertEqual(self.allowed(seeded_user(position, committee)), set(), position)

    def test_residents_get_nothing(self):
        self.assertEqual(self.allowed(make_resident_user()), set())
        self.assertFalse(policies.visible_cases(make_resident_user()).exists())

    def test_allowed_transitions_per_role(self):
        filed = make_blotter_case()
        mediating = make_blotter_case(status='under_mediation')
        secretary, kagawad, tanod = seeded_user('Secretary'), seeded_user('Kagawad', 'Peace and Order'), seeded_user('Tanod')
        codes = lambda user, case: [c for c, _ in policies.allowed_transitions(user, case)]  # noqa: E731
        self.assertEqual(codes(secretary, filed), ['dismissed', 'withdrawn'])
        self.assertEqual(codes(kagawad, filed), ['under_mediation', 'dismissed', 'withdrawn'])
        self.assertEqual(codes(tanod, filed), [])
        self.assertEqual(codes(secretary, mediating), ['withdrawn'])
        self.assertEqual(codes(kagawad, mediating), ['settled', 'escalated', 'withdrawn'])
        self.assertEqual(codes(kagawad, make_blotter_case(status='settled')), [])


class ScopeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.alpha, self.beta = make_purok('Scope Alpha'), make_purok('Scope Beta')
        self.case_alpha = make_blotter_case(purok=self.alpha)
        self.case_beta = make_blotter_case(purok=self.beta)
        self.case_none = make_blotter_case(purok=None)

    def visible(self, user):
        return set(policies.visible_cases(user).values_list('pk', flat=True))

    def test_admin_sees_every_purok(self):
        self.assertEqual(self.visible(make_admin()), {self.case_alpha.pk, self.case_beta.pk, self.case_none.pk})

    def test_purok_staff_sees_only_their_purok(self):
        user = make_staff({'blotter': ['view']}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='scope alpha')
        self.assertEqual(self.visible(user), {self.case_alpha.pk})
        self.assertTrue(policies.can_see(user, self.case_alpha))
        self.assertFalse(policies.can_see(user, self.case_beta))
        self.assertTrue(policies.purok_allowed(user, self.alpha))
        self.assertFalse(policies.purok_allowed(user, self.beta))
        self.assertFalse(policies.purok_allowed(user, None))

    def test_all_service_area_overrides_purok_scope(self):
        user = make_staff({'blotter': ['view']}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Scope Alpha')
        StaffAssignment.objects.create(user=user, officer=user.test_officer,
                                       scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value='All')
        self.assertEqual(len(self.visible(user)), 3)

    def test_non_all_service_area_does_not_override(self):
        user = make_staff({'blotter': ['view']}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Scope Alpha')
        StaffAssignment.objects.create(user=user, officer=user.test_officer,
                                       scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value='Health')
        self.assertEqual(self.visible(user), {self.case_alpha.pk})

    def test_service_area_staff_sees_all(self):
        self.assertEqual(len(self.visible(make_staff({'blotter': ['view']}, scope_value='Peace and Order'))), 3)

    def test_two_purok_assignments_union(self):
        user = make_staff({'blotter': ['view']}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Scope Alpha')
        StaffAssignment.objects.create(user=user, officer=user.test_officer,
                                       scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Scope Beta')
        self.assertEqual(self.visible(user), {self.case_alpha.pk, self.case_beta.pk})

    def test_no_view_permission_sees_nothing(self):
        self.assertEqual(self.visible(make_staff({'blotter': ['create']})), set())


class ConfidentialTests(BaseTestCase):
    def test_confidential_hidden_without_view_confidential(self):
        secret = make_blotter_case(is_confidential=True)
        public = make_blotter_case()
        viewer = make_staff({'blotter': ['view']})
        self.assertEqual(set(policies.visible_cases(viewer).values_list('pk', flat=True)), {public.pk})
        cleared = make_staff({'blotter': ['view', 'view_confidential']})
        self.assertEqual(set(policies.visible_cases(cleared).values_list('pk', flat=True)), {public.pk, secret.pk})
