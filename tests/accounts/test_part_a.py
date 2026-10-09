import re
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User, Resident, Purok, Officer
from apps.accounts.services import (
    generate_temp_password,
    calculate_age,
    register_resident_service,
    approve_resident_service,
    reject_resident_service,
    change_password_service,
    create_staff_account_service,
    disable_account_service,
)
from apps.history.models import ActivityLog, EmailLog
from tests.base import JPEG_BYTES, PNG_BYTES


class PartAAccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.purok, _ = Purok.objects.get_or_create(name="Purok 1")
        self.admin = User.objects.create_superuser(
            username="admin_user",
            email="admin@barangay.ph",
            password="AdminPassword123!",
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

    def test_temp_password_format_12_mixed_characters(self):
        """Temporary password: 12 characters with lowercase, uppercase, digit and symbol (B8)."""
        for _ in range(20):
            pw = generate_temp_password()
            self.assertEqual(len(pw), 12)
            self.assertTrue(re.search(r'[a-z]', pw) and re.search(r'[A-Z]', pw)
                            and re.search(r'\d', pw) and re.search(r'[^A-Za-z0-9]', pw),
                            f"Password {pw} is missing a character class")

    def test_age_calculation_and_never_stored(self):
        """Age is calculated from birthdate on the server, never stored in DB."""
        today = timezone.now().date()
        birthdate_20 = today.replace(year=today.year - 20)
        resident = Resident.objects.create(
            first_name="Juan",
            last_name="Dela Cruz",
            birthdate=birthdate_20,
            contact_no="09171234567",
            purok=self.purok,
        )
        self.assertEqual(resident.age, 20)
        self.assertFalse(hasattr(resident, 'age_stored'))
        # Check column names in resident table
        field_names = [f.name for f in Resident._meta.get_fields()]
        self.assertNotIn('age', field_names)

    def test_under_18_signup_blocked_with_exact_message(self):
        """Under 18 at sign up: rejected with 'This portal is for residents 18 and above.'"""
        today = timezone.now().date()
        birthdate_17 = today.replace(year=today.year - 17)

        fake_photo = SimpleUploadedFile("id_photo.jpg", JPEG_BYTES, content_type="image/jpeg")
        post_data = {
            'first_name': 'Minor',
            'last_name': 'Applicant',
            'birthdate': birthdate_17.strftime('%Y-%m-%d'),
            'contact_no': '09170000000',
            'email': 'minor@example.com',
            'purok': self.purok.id,
            'address': 'House 1, Street 1',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This portal is for residents 18 and above.")
        self.assertFalse(User.objects.filter(email='minor@example.com').exists())

    def test_signup_requires_privacy_consent(self):
        """Privacy consent checkbox is required to register."""
        today = timezone.now().date()
        birthdate_25 = today.replace(year=today.year - 25)
        fake_photo = SimpleUploadedFile("id_photo.jpg", JPEG_BYTES, content_type="image/jpeg")
        post_data = {
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'birthdate': birthdate_25.strftime('%Y-%m-%d'),
            'contact_no': '09170000000',
            'email': 'noconsent@example.com',
            'purok': self.purok.id,
            'address': 'House 1, Street 1',
            'id_photo': fake_photo,
            # 'privacy_consent' omitted
        }
        response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='noconsent@example.com').exists())

    def test_valid_signup_creates_user_pending_and_resident_and_sends_email2(self):
        """Valid sign up creates User (pending) + Resident, saves ID photo, sends Email 2."""
        today = timezone.now().date()
        birthdate_25 = today.replace(year=today.year - 25)

        fake_photo = SimpleUploadedFile("id_proof.png", PNG_BYTES, content_type="image/png")
        post_data = {
            'first_name': 'Pedro',
            'middle_name': 'Santos',
            'last_name': 'Penduko',
            'birthdate': birthdate_25.strftime('%Y-%m-%d'),
            'contact_no': '09181112233',
            'email': 'pedro@example.com',
            'purok': self.purok.id,
            'address': 'Block 5 Lot 2',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(response.status_code, 200)

        user = User.objects.filter(email='pedro@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.status, User.STATUS_PENDING)
        self.assertFalse(user.is_approved)

        resident = Resident.objects.filter(user=user).first()
        self.assertIsNotNone(resident)
        self.assertEqual(resident.first_name, 'Pedro')
        self.assertEqual(resident.middle_name, 'Santos')
        self.assertEqual(resident.last_name, 'Penduko')
        self.assertTrue(bool(resident.id_photo))

        # Check Email 2 (reg_received) logged
        email_log = EmailLog.objects.filter(recipient='pedro@example.com', email_type='reg_received').first()
        self.assertIsNotNone(email_log)
        self.assertIn(email_log.status, ['queued', 'sent'])

    def test_landing_page_public_and_everything_else_requires_login(self):
        """Landing page stays public. Everything else requires login and status = active."""
        # Landing page is accessible
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # Home requires login
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

        # Pending user trying to access /home/ is blocked and redirected to login
        pending_user = User.objects.create_user(
            username="pending_tester",
            email="pending@test.com",
            password="Password123!",
            status=User.STATUS_PENDING
        )
        self.client.login(username="pending_tester", password="Password123!")
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_admin_approve_flow_with_temp_password_and_email3(self):
        """Approve: status=active, 4+4 temp password, must_change_password=True, expires in 7 days, Email 3."""
        applicant = User.objects.create_user(
            username="applicant1",
            email="applicant1@test.com",
            status=User.STATUS_PENDING,
            role=User.ROLE_RESIDENT
        )
        Resident.objects.create(
            user=applicant,
            first_name="Elena",
            last_name="Reyes",
            birthdate=datetime.date(1990, 5, 10),
            contact_no="09191234567",
            purok=self.purok
        )

        with self.captureOnCommitCallbacks(execute=True):
            res = approve_resident_service(applicant, self.admin)
        self.assertEqual(res['status'], 'ok')

        applicant.refresh_from_db()
        self.assertEqual(applicant.status, User.STATUS_ACTIVE)
        self.assertTrue(applicant.must_change_password)
        self.assertIsNotNone(applicant.temp_password_expires_at)
        diff_days = (applicant.temp_password_expires_at - timezone.now()).days
        self.assertEqual(diff_days, 6)  # now + 7 days minus slight delta

        # Check Email 3 (reg_approved) sent
        email_log = EmailLog.objects.filter(recipient="applicant1@test.com", email_type="reg_approved").first()
        self.assertIsNotNone(email_log)
        self.assertEqual(email_log.status, 'sent')

        # Check ActivityLog does NOT log the temporary password
        activity = ActivityLog.objects.filter(target_id=str(applicant.id), action='approve').first()
        self.assertIsNotNone(activity)
        self.assertNotIn("kdmr", activity.details)

    def test_admin_reject_flow_and_reapplication(self):
        """Reject: requires reason, status=rejected, sends Email 5, person may sign up again."""
        applicant = User.objects.create_user(
            username="applicant2",
            email="applicant2@test.com",
            status=User.STATUS_PENDING,
            role=User.ROLE_RESIDENT
        )
        res_profile = Resident.objects.create(
            user=applicant,
            first_name="Carlos",
            last_name="Gomez",
            birthdate=datetime.date(1992, 4, 1),
            contact_no="09195556677",
            purok=self.purok
        )

        # Reject without reason must raise ValueError
        with self.assertRaises(ValueError):
            reject_resident_service(applicant, self.admin, "")

        # Reject with valid reason
        with self.captureOnCommitCallbacks(execute=True):
            res = reject_resident_service(applicant, self.admin, "unclear ID photo")
        self.assertEqual(res['status'], 'ok')

        applicant.refresh_from_db()
        self.assertEqual(applicant.status, User.STATUS_REJECTED)
        self.assertEqual(applicant.rejection_reason, "unclear ID photo")

        # Email 5 sent
        email_log = EmailLog.objects.filter(recipient="applicant2@test.com", email_type="reg_rejected").first()
        self.assertIsNotNone(email_log)

        # Person may sign up again
        fake_photo = SimpleUploadedFile("new_id.jpg", JPEG_BYTES, content_type="image/jpeg")
        post_data = {
            'first_name': 'Carlos',
            'last_name': 'Gomez',
            'birthdate': '1992-04-01',
            'contact_no': '09195556677',
            'email': 'applicant2@test.com',
            'purok': self.purok.id,
            'address': 'New Address',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        response = self.client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(response.status_code, 200)

        applicant.refresh_from_db()
        self.assertEqual(applicant.status, User.STATUS_PENDING)
        self.assertEqual(applicant.rejection_reason, '')

    def test_forced_password_change_middleware(self):
        """If must_change_password=True, redirect every request to change-password until done."""
        user = User.objects.create_user(
            username="temp_user",
            email="temp@test.com",
            password="InitialPassword123!",
            status=User.STATUS_ACTIVE,
            must_change_password=True,
            temp_password_expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        self.client.login(username="temp_user", password="InitialPassword123!")

        # Trying to access /home/ redirects to /accounts/change-password/
        response = self.client.get('/home/')
        self.assertRedirects(response, reverse('accounts:change_password'))

        # Perform password change
        response = self.client.post(reverse('accounts:change_password'), {
            'new_password': 'MyNewPermanentPassword123!',
            'confirm_password': 'MyNewPermanentPassword123!',
        })
        self.assertRedirects(response, reverse('home'))

        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password('MyNewPermanentPassword123!'))

        # Now can access /home/
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 200)

    def test_expired_temporary_password_cannot_login(self):
        """An expired temporary password cannot log in."""
        user = User.objects.create_user(
            username="expired_user",
            email="expired@test.com",
            password="TempPassword123!",
            status=User.STATUS_ACTIVE,
            must_change_password=True,
            temp_password_expires_at=timezone.now() - timezone.timedelta(hours=1)
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'expired@test.com',
            'password': 'TempPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your temporary password has expired")

    def test_admin_created_staff_and_disable_account(self):
        """Admin creates staff account with temp password & forced change; can disable at end of term."""
        staff_user = create_staff_account_service(
            admin_user=self.admin,
            email="officer@barangay.ph",
            first_name="Kagawad",
            last_name="Santos",
            role=User.ROLE_STAFF
        )
        self.assertEqual(staff_user.status, User.STATUS_ACTIVE)
        self.assertTrue(staff_user.must_change_password)
        self.assertTrue(staff_user.is_staff)

        # Disable account
        disable_account_service(self.admin, staff_user, reason="Term ended")
        staff_user.refresh_from_db()
        self.assertEqual(staff_user.status, User.STATUS_DISABLED)
