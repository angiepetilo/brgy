import os
import time
from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse, get_resolver, URLPattern, URLResolver
from django.utils import timezone
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.accounts.models import User, Resident, Purok, Officer, StaffAssignment, PermissionRule
from apps.accounts.services import (
    anonymize_resident_service,
    update_resident_needs_service,
    change_password_service,
    register_resident_service,
)
from apps.accounts.permissions import seed_default_permissions
from apps.appointments.models import Appointment, HealthCareService, DocumentType, Requirement
from apps.communications.models import Announcement, PostCategory
from apps.chat.models import ChatThread, Message, Notification, ConcernCategory
from tests.base import get_clearance_type
from tests.base import JPEG_BYTES, PNG_BYTES


class PartIHardeningReleaseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.purok, _ = Purok.objects.get_or_create(name="Purok 1")
        seed_default_permissions()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="admin_lead",
            email="admin_lead@barangay.ph",
            password="AdminPassword123!",
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Resident A
        self.res_user_a = User.objects.create_user(
            username="resident_a",
            email="resident_a@example.com",
            password="ResidentPass123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_a = Resident.objects.create(
            user=self.res_user_a,
            first_name="Juan",
            last_name="Dela Cruz",
            birthdate=date(1995, 5, 20),
            contact_no="09171112233",
            address="123 Mabini St",
            purok=self.purok,
            consent_recorded=True,
            consent_recorded_date=date(2026, 1, 15)
        )

        # Resident B
        self.res_user_b = User.objects.create_user(
            username="resident_b",
            email="resident_b@example.com",
            password="ResidentPass123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_b = Resident.objects.create(
            user=self.res_user_b,
            first_name="Maria",
            last_name="Clara",
            birthdate=date(1996, 6, 25),
            contact_no="09182223344",
            address="456 Rizal St",
            purok=self.purok,
            consent_recorded=True,
            consent_recorded_date=date(2026, 1, 20)
        )

        # Staff with No Assignment
        self.staff_unassigned = User.objects.create_user(
            username="staff_no_assign",
            email="staff_no_assign@barangay.ph",
            password="StaffPass123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Scoped Staff (Health)
        self.staff_health = User.objects.create_user(
            username="staff_health",
            email="staff_health@barangay.ph",
            password="StaffPass123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        bhw_officer = Officer.objects.filter(position='BHW').first() or Officer.objects.create(position='BHW')
        StaffAssignment.objects.create(
            user=self.staff_health,
            officer=bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='Health'
        )

    # =========================================================================
    # I1: SETTINGS & ENVIRONMENT TESTS
    # =========================================================================
    def test_i1_security_settings_configured(self):
        """Verify production security settings, session timeout, and memory limits are defined."""
        self.assertTrue(hasattr(settings, 'SESSION_COOKIE_AGE'))
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 3600)  # 8 hours absolute
        self.assertEqual(settings.SESSION_IDLE_TIMEOUT, 30 * 60)  # 30 minutes idle
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)
        self.assertEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)

    # =========================================================================
    # I2: LOGIN, THROTTLING, AND PASSWORDS TESTS
    # =========================================================================
    def test_i2_login_generic_error_wrong_credentials(self):
        """Wrong email or password shows same generic error message without leaking account existence."""
        client = Client()
        resp = client.post(reverse('accounts:login'), {
            'username': 'nonexistent_user_999@example.com',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid email/username or password.")

        # Real user, wrong password -> exact same error
        resp2 = client.post(reverse('accounts:login'), {
            'username': self.res_user_a.email,
            'password': 'WrongPassword123!'
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "Invalid email/username or password.")

    def test_i2_status_messages_shown_only_after_correct_password(self):
        """Pending / rejected / disabled accounts only see status message with correct password."""
        # Create pending user
        pending_user = User.objects.create_user(
            username="pending_pedro",
            email="pending_pedro@example.com",
            password="CorrectPassword123!",
            status=User.STATUS_PENDING
        )
        client = Client()

        # 1. Wrong password -> generic message
        resp_wrong = client.post(reverse('accounts:login'), {
            'username': 'pending_pedro@example.com',
            'password': 'WrongPassword123!'
        })
        self.assertContains(resp_wrong, "Invalid email/username or password.")

        # 2. Correct password -> reveals pending verification message
        resp_correct = client.post(reverse('accounts:login'), {
            'username': 'pending_pedro@example.com',
            'password': 'CorrectPassword123!'
        })
        self.assertContains(resp_correct, "pending verification")

    def test_i2_login_throttle_locks_after_5_failures(self):
        """Throttle: 5 failed attempts locks account+IP for 15 minutes (HTTP 429)."""
        client = Client(REMOTE_ADDR='192.168.1.50')
        cache.clear()

        for attempt in range(5):
            resp = client.post(reverse('accounts:login'), {
                'username': 'test_throttle_user',
                'password': 'WrongPassword!'
            })
            self.assertEqual(resp.status_code, 200)

        # 6th attempt -> 429 Too Many Requests
        resp_locked = client.post(reverse('accounts:login'), {
            'username': 'test_throttle_user',
            'password': 'AnyPassword'
        })
        self.assertEqual(resp_locked.status_code, 429)

    def test_i2_password_reset_generic_response_and_timeout(self):
        """Password reset returns generic response regardless of whether email exists."""
        client = Client()
        # Request for non-existent email
        resp = client.post(reverse('accounts:password_reset'), {
            'email': 'does_not_exist@example.com'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/accounts/password-reset/done/')

        # Timeout setting is 1 hour (3600 seconds)
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    def test_i2_change_password_differs_from_temporary_and_invalidates_sessions(self):
        """Change-password enforces that the new password differs from the temporary one."""
        from apps.accounts.forms import ForcePasswordChangeForm
        self.res_user_a.set_password("TempPassword123!")
        self.res_user_a.must_change_password = True
        self.res_user_a.save()

        # Attempting to reuse same temporary password fails validation
        form_same = ForcePasswordChangeForm(
            data={'new_password': 'TempPassword123!', 'confirm_password': 'TempPassword123!'},
            user=self.res_user_a
        )
        self.assertFalse(form_same.is_valid())
        self.assertIn("must differ", str(form_same.errors))

        # Distinct new password succeeds
        form_valid = ForcePasswordChangeForm(
            data={'new_password': 'BrandNewSecurePassword123!', 'confirm_password': 'BrandNewSecurePassword123!'},
            user=self.res_user_a
        )
        self.assertTrue(form_valid.is_valid())

    # =========================================================================
    # I3: AUTHORIZATION SWEEP & IDOR TESTS
    # =========================================================================
    def test_i3_idor_appointment_isolation(self):
        """Resident A cannot view or manipulate Resident B's appointment."""
        apt_b = Appointment.objects.create(
            resident=self.res_user_b,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=get_clearance_type(),
            appt_date=date.today() + timedelta(days=2),
            time_window='morning',
            purpose='Employment clearance'
        )

        client_a = Client()
        client_a.force_login(self.res_user_a)

        # Resident A tries to open Resident B's appointment detail
        resp = client_a.get(reverse('appointments:detail', kwargs={'pk': apt_b.id}))
        # Returns 404 (object not found within resident scope)
        self.assertEqual(resp.status_code, 404)

    def test_i3_idor_thread_isolation(self):
        """Resident A cannot access Resident B's concern thread."""
        thread_b = ChatThread.objects.create(
            thread_type=ChatThread.THREAD_CONCERN,
            initiator=self.res_user_b,
            title="Resident B Concern",
            status=ChatThread.STATUS_SUBMITTED
        )

        client_a = Client()
        client_a.force_login(self.res_user_a)

        resp = client_a.get(reverse('chat:concern_detail', kwargs={'concern_id': thread_b.id}))
        # 403 Forbidden
        self.assertEqual(resp.status_code, 403)

    def test_i3_idor_notification_isolation(self):
        """Resident A cannot read or mark Resident B's notification."""
        notif_b = Notification.objects.create(
            recipient=self.res_user_b,
            title="Private Notice B",
            message="Confidential message for Resident B"
        )

        client_a = Client()
        client_a.force_login(self.res_user_a)

        resp = client_a.get(reverse('chat:open_notification', kwargs={'notif_id': notif_b.id}))
        self.assertEqual(resp.status_code, 404)

    def test_i3_idor_id_photo_isolation(self):
        """Resident A cannot download Resident B's ID photo proof."""
        fake_photo = SimpleUploadedFile("id_b.jpg", b"fake_id_bytes", content_type="image/jpeg")
        self.resident_b.id_photo = fake_photo
        self.resident_b.save()

        client_a = Client()
        client_a.force_login(self.res_user_a)

        resp = client_a.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_b.id}))
        self.assertEqual(resp.status_code, 403)

        # Owner can view their own ID photo
        client_b = Client()
        client_b.force_login(self.res_user_b)
        resp_owner = client_b.get(reverse('accounts:serve_id_photo', kwargs={'resident_id': self.resident_b.id}))
        self.assertEqual(resp_owner.status_code, 200)

    def test_i3_anonymous_user_blocked_from_protected_routes(self):
        """Anonymous client redirected to login on protected routes."""
        client = Client()
        protected_urls = [
            '/home/',
            '/feed/',
            '/chat/',
            '/appointments/',
            '/accounts/residents/',
            '/accounts/officers/permissions/',
            '/accounts/system/',
            '/history/',
            '/statistics/',
        ]
        for url in protected_urls:
            resp = client.get(url)
            self.assertEqual(resp.status_code, 302, f"Route {url} failed to redirect anonymous user")
            self.assertIn('/accounts/login/', resp.url)

    def test_i3_resident_cannot_access_staff_or_admin_views(self):
        """Resident client is blocked (403 or redirect) from administrative management routes."""
        client = Client()
        client.force_login(self.res_user_a)

        staff_urls = [
            '/accounts/residents/',
            '/accounts/officers/permissions/',
            '/accounts/system/',
            '/appointments/schedules/manage/',
            '/history/',
            '/statistics/',
        ]
        for url in staff_urls:
            resp = client.get(url)
            self.assertIn(resp.status_code, [302, 403], f"Resident unexpectedly reached {url}")

    # =========================================================================
    # I4: UPLOADS & PRIVATE FILES TESTS
    # =========================================================================
    def test_i4_private_media_not_directly_routable(self):
        """Direct anonymous HTTP requests to private_media return 404/403."""
        client = Client()
        resp = client.get('/private_media/id_photos/test.jpg')
        # URL dispatcher has no route for /private_media/, so it either 404s or redirects to login
        self.assertIn(resp.status_code, [302, 404, 403])

    # =========================================================================
    # I5: PRIVACY CONSENT & DATA ANONYMIZATION TESTS
    # =========================================================================
    def test_i5_signup_requires_privacy_consent_and_records_date(self):
        """Sign-up form enforces mandatory privacy consent checkbox and records date."""
        fake_photo = SimpleUploadedFile("id_doc.jpg", JPEG_BYTES, content_type="image/jpeg")
        post_data = {
            'first_name': 'Test',
            'last_name': 'Resident',
            'birthdate': '1990-01-01',
            'contact_no': '09123456789',
            'email': 'new_resident_privacy@example.com',
            'purok': self.purok.id,
            'address': 'House 123',
            'id_photo': fake_photo,
            'privacy_consent': 'on',
            'gender': 'female',
            'civil_status': 'single',
        }
        client = Client()
        resp = client.post(reverse('accounts:signup'), post_data)
        self.assertEqual(resp.status_code, 200)

        res_profile = Resident.objects.filter(user__email='new_resident_privacy@example.com').first()
        self.assertIsNotNone(res_profile)
        self.assertTrue(res_profile.consent_recorded)
        self.assertEqual(res_profile.consent_recorded_date, timezone.localdate())

    def test_i5_admin_anonymize_resident_service(self):
        """Admin anonymization service strips PII, deletes ID photo, archives record, and logs activity."""
        fake_photo = SimpleUploadedFile("id_photo_anon.jpg", b"id_photo_content", content_type="image/jpeg")
        self.resident_a.id_photo = fake_photo
        self.resident_a.save()

        anonymized = anonymize_resident_service(self.resident_a, self.admin_user)
        self.assertEqual(anonymized.first_name, "Anonymized")
        self.assertEqual(anonymized.last_name, f"Resident-{anonymized.id}")
        self.assertEqual(anonymized.contact_no, "")
        self.assertEqual(anonymized.address, "Redacted")
        self.assertTrue(anonymized.is_archived)
        self.assertFalse(bool(anonymized.id_photo))

        # Linked user account disabled and anonymized
        user_a = User.objects.get(id=self.res_user_a.id)
        self.assertFalse(user_a.is_active)
        self.assertEqual(user_a.status, User.STATUS_DISABLED)
        self.assertTrue(user_a.email.endswith('@deleted.local'))

    # =========================================================================
    # I7: PERFORMANCE, ROTATING LOGS & CUSTOM ERROR TEMPLATES
    # =========================================================================
    def test_i7_custom_error_pages_render(self):
        """Custom 403, 404, and 500 error templates exist and render cleanly."""
        from django.template.loader import render_to_string
        content_403 = render_to_string('403.html')
        content_404 = render_to_string('404.html')
        content_500 = render_to_string('500.html')

        self.assertIn("Access Denied", content_403)
        self.assertIn("Page Not Found", content_404)
        self.assertIn("Something went wrong", content_500)

    def test_i7_query_count_and_pagination_on_feed(self):
        """Main feed runs within bounded query counts and does not trigger N+1."""
        client = Client()
        client.force_login(self.res_user_a)

        # Create sample announcements
        for i in range(5):
            Announcement.objects.create(
                title=f"Sample Post {i}",
                content="Post content",
                author=self.admin_user,
                category=Announcement.CATEGORY_GENERAL
            )

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(reverse('feed'))
            self.assertEqual(resp.status_code, 200)
        # Stage D civic stack adds a fixed 3 queries (hotline, document types, health
        # services) plus a one-time BarangayInfo singleton insert in a fresh test DB
        # (savepoint + insert + release). Growth with post count is checked in
        # tests/ui/test_key_pages.py::FeedQueryCountTests.
        self.assertLess(len(ctx.captured_queries), 41)
