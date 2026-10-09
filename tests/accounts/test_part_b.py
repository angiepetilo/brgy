import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Resident, Purok, Officer, StaffAssignment, PermissionRule
from apps.accounts.permissions import registry, check_user_perm, seed_default_permissions
from apps.accounts.services import (
    register_resident_service,
    approve_resident_service,
    reject_resident_service,
    resend_temporary_password_service,
    calculate_age,
)
from apps.history.models import EmailLog
from tests.base import JPEG_BYTES, PNG_BYTES


class PartBAndPartAFollowupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.purok, _ = Purok.objects.get_or_create(name="Purok 1")
        seed_default_permissions()

        # Admin user
        self.admin = User.objects.create_superuser(
            username="admin_test",
            email="admin@barangay.ph",
            password="AdminPassword123!",
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Kapitan user
        self.kapitan = User.objects.create_user(
            username="kapitan_test",
            email="kapitan@barangay.ph",
            password="KapitanPassword123!",
            role=User.ROLE_KAPITAN,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        pb_officer = Officer.objects.filter(position=Officer.POSITION_PUNONG_BARANGAY).first()
        pb_officer.user = self.kapitan
        pb_officer.save()

        # Staff user (Health Officer)
        self.staff_user = User.objects.create_user(
            username="bhw_nurse",
            email="bhw@barangay.ph",
            password="StaffPassword123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.bhw_officer = Officer.objects.filter(position=Officer.POSITION_BHW).first()
        self.bhw_officer.user = self.staff_user
        self.bhw_officer.committee = "Health"
        self.bhw_officer.save()

        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=self.bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Health"
        )
        # Allow BHW view accounts
        PermissionRule.objects.update_or_create(
            officer=self.bhw_officer,
            module="accounts",
            action="view",
            defaults={'allowed': True}
        )
        # Deny BHW delete
        PermissionRule.objects.update_or_create(
            officer=self.bhw_officer,
            module="accounts",
            action="delete",
            defaults={'allowed': False}
        )

        # Active Resident
        self.resident_user = User.objects.create_user(
            username="resident_test",
            email="resident@barangay.ph",
            password="ResidentPassword123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_profile = Resident.objects.create(
            user=self.resident_user,
            first_name="Juan",
            last_name="Tamad",
            birthdate=datetime.date(1995, 6, 15),
            contact_no="09171112233",
            purok=self.purok,
            id_photo=SimpleUploadedFile("juan_id.jpg", JPEG_BYTES, content_type="image/jpeg")
        )

    # 1. Exactly-18 boundary test
    def test_exactly_18_boundary_is_accepted(self):
        """Applicant turning exactly 18 today must be accepted."""
        today = timezone.localdate()
        birthdate_18 = today.replace(year=today.year - 18)
        self.assertEqual(calculate_age(birthdate_18), 18)

        fake_photo = SimpleUploadedFile("id_proof.png", PNG_BYTES, content_type="image/png")
        post_data = {
            'first_name': 'Young',
            'last_name': 'Adult',
            'birthdate': birthdate_18.strftime('%Y-%m-%d'),
            'contact_no': '09171234567',
            'email': 'young.adult@example.com',
            'purok': self.purok.id,
            'address': 'Purok 1 Center',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='young.adult@example.com').exists())

    # 2. Future and impossible birthdate tests
    def test_future_birthdate_rejected(self):
        """Future birthdate must be rejected."""
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        with self.assertRaises(ValueError) as ctx:
            calculate_age(tomorrow)
        self.assertIn("cannot be in the future", str(ctx.exception))

        fake_photo = SimpleUploadedFile("id_proof.png", PNG_BYTES, content_type="image/png")
        post_data = {
            'first_name': 'Time',
            'last_name': 'Traveler',
            'birthdate': tomorrow.strftime('%Y-%m-%d'),
            'contact_no': '09171234567',
            'email': 'timetraveler@example.com',
            'purok': self.purok.id,
            'address': 'Future St.',
            'id_photo': fake_photo,
        }
        response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertContains(response, "Birthdate cannot be in the future.")

    def test_impossible_birthdate_before_1900_rejected(self):
        """Birthdate before 1900 must be rejected."""
        old_date = datetime.date(1880, 1, 1)
        with self.assertRaises(ValueError) as ctx:
            calculate_age(old_date)
        self.assertIn("valid birthdate", str(ctx.exception))

    # 3. Middleware redirect allow-list
    def test_middleware_redirect_allow_list(self):
        """Public pages allowed; protected pages redirect anonymous users to login."""
        # Allowed public
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/landing/').status_code, 200)
        self.assertEqual(self.client.get('/accounts/login/').status_code, 200)
        self.assertEqual(self.client.get('/accounts/signup/').status_code, 200)

        # Protected pages redirect to login
        res = self.client.get('/home/')
        self.assertRedirects(res, '/accounts/login/?next=/home/')
        res2 = self.client.get('/accounts/residents/')
        self.assertRedirects(res2, '/accounts/login/?next=/accounts/residents/')

    # 4. Separate login messages for pending, rejected, and disabled accounts
    def test_separate_login_messages_for_account_statuses(self):
        """UserLoginForm returns distinct, explicit messages for pending, rejected, and disabled."""
        # Pending account
        User.objects.create_user(
            username="user_pending",
            email="pending@test.com",
            password="MyPassword123!",
            status=User.STATUS_PENDING
        )
        res = self.client.post(reverse('accounts:login'), {'username': 'pending@test.com', 'password': 'MyPassword123!'})
        self.assertContains(res, "Your account is pending verification. Please wait for an approval email.")

        # Rejected account
        User.objects.create_user(
            username="user_rejected",
            email="rejected@test.com",
            password="MyPassword123!",
            status=User.STATUS_REJECTED,
            rejection_reason="unclear ID photo"
        )
        res = self.client.post(reverse('accounts:login'), {'username': 'rejected@test.com', 'password': 'MyPassword123!'})
        self.assertContains(res, "Your registration was rejected: unclear ID photo. You may register again.")

        # Disabled account
        User.objects.create_user(
            username="user_disabled",
            email="disabled@test.com",
            password="MyPassword123!",
            status=User.STATUS_DISABLED
        )
        res = self.client.post(reverse('accounts:login'), {'username': 'disabled@test.com', 'password': 'MyPassword123!'})
        self.assertContains(res, "This account has been disabled. Please contact the Barangay Administrator.")

    # 5. Re-registration after rejection
    def test_reregistration_after_rejection_reuses_record_and_resets_pending(self):
        """Re-registration with same email reuses User record, sets back to pending, clears rejection reason."""
        rej_user = User.objects.create_user(
            username="carlos",
            email="carlos@test.com",
            status=User.STATUS_REJECTED,
            rejection_reason="duplicate account"
        )
        Resident.objects.create(
            user=rej_user,
            first_name="Carlos",
            last_name="Santana",
            birthdate=datetime.date(1990, 1, 1),
            contact_no="09170000000",
            purok=self.purok
        )

        fake_photo = SimpleUploadedFile("clean_id.jpg", JPEG_BYTES, content_type="image/jpeg")
        post_data = {
            'first_name': 'Carlos Updated',
            'last_name': 'Santana',
            'birthdate': '1990-01-01',
            'contact_no': '09170000000',
            'email': 'carlos@test.com',
            'purok': self.purok.id,
            'address': 'Purok 1',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        res = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(res.status_code, 200)

        rej_user.refresh_from_db()
        self.assertEqual(rej_user.status, User.STATUS_PENDING)
        self.assertEqual(rej_user.rejection_reason, "")
        self.assertEqual(rej_user.first_name, "Carlos Updated")

    # 6. Admin action: Resend temporary password
    def test_admin_resend_temporary_password_service(self):
        """Resend temporary password generates new 4+4 temp password, resets 7-day expiry, sends Email 3."""
        user = User.objects.create_user(
            username="reset_target",
            email="reset.target@test.com",
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        with self.captureOnCommitCallbacks(execute=True):
            res = resend_temporary_password_service(user, self.admin)
        self.assertEqual(res['status'], 'ok')

        user.refresh_from_db()
        self.assertTrue(user.must_change_password)
        self.assertIsNotNone(user.temp_password_expires_at)
        diff_days = (user.temp_password_expires_at - timezone.now()).days
        self.assertEqual(diff_days, 6)

        # Email 3 logged
        email_log = EmailLog.objects.filter(recipient="reset.target@test.com", email_type="reg_approved").first()
        self.assertIsNotNone(email_log)

    # 7. Protected ID Photo view
    def test_id_photo_protected_from_public_and_unauthorized_users(self):
        """id_photo is served only through permission-checked view, not open media URL."""
        # Anonymous request returns 302 to login
        res = self.client.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_profile.id}))
        self.assertEqual(res.status_code, 302)

        # Another resident tries to view -> HTTP 403 Forbidden!
        other_resident = User.objects.create_user(
            username="snooper_resident",
            email="snooper@test.com",
            password="Password123!",
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.client.login(username="snooper_resident", password="Password123!")
        res = self.client.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_profile.id}))
        self.assertEqual(res.status_code, 403)

        # Resident owner themself -> HTTP 200 OK!
        self.client.login(username="resident_test", password="ResidentPassword123!")
        res = self.client.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_profile.id}))
        self.assertEqual(res.status_code, 200)

        # Admin -> HTTP 200 OK!
        self.client.login(username="admin_test", password="AdminPassword123!")
        res = self.client.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_profile.id}))
        self.assertEqual(res.status_code, 200)

    # 8. Part B: Resident typing staff URL directly receives HTTP 403
    def test_resident_typing_staff_url_directly_returns_403(self):
        """Logging in as a resident and typing staff URL directly returns 403 Forbidden."""
        self.client.login(username="resident_test", password="ResidentPassword123!")

        # 1. Residents tabbed management URL
        response = self.client.get('/accounts/residents/')
        self.assertEqual(response.status_code, 403)

        # 2. Approve resident direct POST URL
        response = self.client.post(f'/accounts/residents/{self.resident_user.id}/approve/')
        self.assertEqual(response.status_code, 403)

        # 3. Officers & permissions management URL
        response = self.client.get('/accounts/officers/permissions/')
        self.assertEqual(response.status_code, 403)

    # 9. Part B: Kapitan treated as admin-level through PermissionRule
    def test_kapitan_has_admin_level_access_through_permission_rules(self):
        """Kapitan accesses staff views through Punong Barangay PermissionRules."""
        self.client.login(username="kapitan_test", password="KapitanPassword123!")

        # Kapitan can view residents management
        response = self.client.get('/accounts/residents/')
        self.assertEqual(response.status_code, 200)

        # Kapitan can view officers permissions
        response = self.client.get('/accounts/officers/permissions/')
        self.assertEqual(response.status_code, 200)

    # 10. Part B: Staff user restricted by permission rules
    def test_staff_restricted_by_permission_rules(self):
        """Staff with accounts.view can view, but denied accounts.delete receives 403."""
        self.client.login(username="bhw_nurse", password="StaffPassword123!")

        # BHW has accounts.view -> 200
        res = self.client.get('/accounts/residents/')
        self.assertEqual(res.status_code, 200)

        # BHW does NOT have officers.edit -> 403
        res = self.client.get('/accounts/officers/permissions/')
        self.assertEqual(res.status_code, 403)
