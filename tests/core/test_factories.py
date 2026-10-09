"""Smoke tests proving the shared factories in tests/base.py stay usable."""

from apps.accounts.permissions import check_user_perm
from apps.accounts.models import User
from tests.base import (
    BaseTestCase, make_admin, make_staff, make_resident_user, make_purok,
    make_resident_profile, make_document_type, make_health_service, make_appointment,
)


class FactoriesSmokeTests(BaseTestCase):
    def test_admin_can_log_in_and_has_all_permissions(self):
        admin = make_admin()
        self.login(admin)
        self.assertTrue(check_user_perm(admin, 'system', 'edit'))

    def test_staff_gets_only_granted_permissions(self):
        staff = make_staff(permissions={'residents': ['view']})
        self.assertTrue(check_user_perm(staff, 'residents', 'view'))
        self.assertFalse(check_user_perm(staff, 'residents', 'delete'))

    def test_resident_profile_links_to_user_and_purok(self):
        user = make_resident_user()
        purok = make_purok('Purok Test')
        profile = make_resident_profile(user=user, purok=purok)
        self.assertEqual(user.resident_profile, profile)
        self.assertEqual(profile.purok.name, 'Purok Test')
        self.assertEqual(user.role, User.ROLE_RESIDENT)

    def test_catalog_and_appointment_factories(self):
        doc = make_document_type(fee='75.00')
        svc = make_health_service()
        appt = make_appointment(resident=make_resident_user())
        self.assertEqual(str(doc.fee), '75.00')
        self.assertTrue(svc.is_active)
        self.assertTrue(appt.reference_no.startswith('APT-'))

    def test_factories_generate_unique_identities(self):
        a, b = make_resident_user(), make_resident_user()
        self.assertNotEqual(a.username, b.username)
        self.assertNotEqual(a.email, b.email)
