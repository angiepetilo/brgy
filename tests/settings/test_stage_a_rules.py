"""
Stage A5/A6: disable_staff_account_service target rules and requirement sync.
"""
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.accounts import system_services
from apps.accounts.models import User
from apps.appointments.models import Requirement
from apps.history.models import ActivityLog
from tests.base import BaseTestCase, make_admin, make_staff, make_resident_user, make_document_type


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class DisableStaffRulesTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        # Non-superuser admin with the RBAC grant via role (admin role bypasses perms).
        self.admin = make_admin(is_superuser=False)
        self.superuser = make_admin()

    def test_resident_target_rejected(self):
        resident = make_resident_user()
        with self.assertRaisesMessage(ValueError, 'Only staff accounts can be disabled here.'):
            system_services.disable_staff_account_service(self.admin, resident.id)
        resident.refresh_from_db()
        self.assertEqual(resident.status, User.STATUS_ACTIVE)
        self.assertTrue(resident.is_active)

    def test_resident_target_rejected_even_for_superuser(self):
        resident = make_resident_user()
        with self.assertRaisesMessage(ValueError, 'Only staff accounts'):
            system_services.disable_staff_account_service(self.superuser, resident.id)

    def test_superuser_target_needs_superuser_actor(self):
        target = make_admin()  # superuser
        with self.assertRaisesMessage(ValueError, 'Only a superuser can disable a superuser'):
            system_services.disable_staff_account_service(self.admin, target.id)
        target.refresh_from_db()
        self.assertEqual(target.status, User.STATUS_ACTIVE)

        system_services.disable_staff_account_service(self.superuser, target.id)
        target.refresh_from_db()
        self.assertEqual(target.status, User.STATUS_DISABLED)

    def test_staff_target_disabled_and_audited(self):
        staff = make_staff()
        system_services.disable_staff_account_service(self.admin, staff.id)
        staff.refresh_from_db()
        self.assertEqual(staff.status, User.STATUS_DISABLED)
        self.assertFalse(staff.is_active)
        self.assertTrue(ActivityLog.objects.filter(
            action_type='StaffAccount', action='disable', target_id=str(staff.id),
        ).exists())

    def test_kapitan_target_allowed(self):
        kap = make_staff(role=User.ROLE_KAPITAN)
        system_services.disable_staff_account_service(self.admin, kap.id)
        kap.refresh_from_db()
        self.assertEqual(kap.status, User.STATUS_DISABLED)

    def test_self_rejected(self):
        with self.assertRaisesMessage(ValueError, 'cannot disable your own'):
            system_services.disable_staff_account_service(self.superuser, self.superuser.id)

    def test_view_shows_error_for_resident_target(self):
        resident = make_resident_user()
        self.login(self.admin)
        response = self.client.post(reverse('accounts:system_staff_account_disable', args=[resident.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('Only staff accounts can be disabled here.', _messages(response))
        resident.refresh_from_db()
        self.assertEqual(resident.status, User.STATUS_ACTIVE)


class RequirementSyncTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.doc = make_document_type(requirements_needed='Valid ID\nCedula')
        Requirement.objects.create(document_type=self.doc, name='Valid ID', order=1)
        Requirement.objects.create(document_type=self.doc, name='Cedula', order=2)

    def _save(self, requirements):
        return system_services.create_or_update_document_type_service(
            self.admin,
            {'name': self.doc.name, 'fee': '50.00', 'requirements_needed': requirements, 'is_active': '1'},
            doc_id=self.doc.id,
        )

    def test_empty_textarea_clears_rows(self):
        doc = self._save('')
        self.assertEqual(Requirement.objects.filter(document_type=doc).count(), 0)
        doc.refresh_from_db()
        self.assertEqual(doc.requirements_needed, '')

    def test_three_lines_give_three_rows_in_order(self):
        doc = self._save('A\nB\n\nC')
        names = list(Requirement.objects.filter(document_type=doc).order_by('order').values_list('name', flat=True))
        self.assertEqual(names, ['A', 'B', 'C'])

    def test_empty_textarea_through_view(self):
        self.login(self.admin)
        self.client.post(
            reverse('accounts:system_document_type_edit', args=[self.doc.id]),
            {'name': self.doc.name, 'fee': '50.00', 'requirements_needed': '', 'is_active': '1'},
        )
        self.assertEqual(Requirement.objects.filter(document_type=self.doc).count(), 0)
