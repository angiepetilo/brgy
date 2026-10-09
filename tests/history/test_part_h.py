import datetime
import zoneinfo
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from django.core.management import call_command

from apps.accounts.models import User, Resident, Purok, Officer, StaffAssignment, BarangayInfo
from apps.appointments.models import Appointment, HealthCareService
from apps.chat.models import Notification, ChatThread
from apps.history.models import ActivityLog, EmailLog
from apps.history.utils import send_templated_email, sanitize_audit_details, log_activity
from apps.chat.services import create_notification
from apps.accounts.services import approve_resident_service, resend_temporary_password_service
from apps.accounts.system_services import create_staff_account_service


class PartHTemplateAndDispatchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.purok, _ = Purok.objects.get_or_create(name="Purok 1")
        self.info, _ = BarangayInfo.objects.get_or_create(
            id=1,
            defaults={
                'name': 'Barangay San Antonio',
                'contact_no': '(02) 8888-1234',
                'venue': 'San Antonio Session Hall',
                'address': 'San Antonio Hall, Main St.',
                'office_hours': 'Mon-Fri 8AM-5PM',
            }
        )
        self.admin = User.objects.create_superuser(
            username="admin_h",
            email="admin_h@barangay.ph",
            password="AdminPassword123!",
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_user = User.objects.create_user(
            username="resident_h",
            email="resident_h@example.com",
            password="Password123!",
            status=User.STATUS_ACTIVE,
            role=User.ROLE_RESIDENT
        )
        self.resident_profile = Resident.objects.create(
            user=self.resident_user,
            first_name="Juan",
            last_name="Tamad",
            birthdate=datetime.date(1995, 6, 15),
            contact_no="09181112222",
            purok=self.purok,
            address="123 Mabini St."
        )

    # 1. Eight Templates Render with Line 1 Subject and BarangayInfo context
    def test_all_eight_templates_render_with_subject_and_context(self):
        templates = [
            ('appt_received', {'applicant_name': 'Juan', 'service': 'Barangay Clearance', 'reference_no': 'APT-2026-0001', 'date': '2026-10-20', 'time_window': 'Morning'}),
            ('appt_approved', {'applicant_name': 'Juan', 'service': 'Barangay Clearance', 'reference_no': 'APT-2026-0001', 'appointment_date': '2026-10-20', 'appointment_time': '09:00 AM'}),
            ('appt_rejected', {'applicant_name': 'Juan', 'service': 'Barangay Clearance', 'reference_no': 'APT-2026-0001', 'rejection_reason': 'Incomplete documentation'}),
            ('appt_reminder', {'first_name': 'Juan', 'service': 'Barangay Clearance', 'date': 'October 20, 2026', 'time_window': 'Morning', 'reference_no': 'APT-2026-0001', 'requirements_line': ' and required documents: Valid ID'}),
            ('reg_received', {'first_name': 'Juan'}),
            ('reg_approved', {'first_name': 'Juan', 'email': 'juan@example.com', 'temp_password': 'abcd1234'}),
            ('reg_rejected', {'first_name': 'Juan', 'rejection_reason': 'Unreadable ID'}),
            ('staff_created', {'first_name': 'Maria', 'email': 'maria@example.com', 'temp_password': 'efgh5678', 'position': 'Kagawad'}),
        ]

        for tmpl, ctx in templates:
            sent, msg = send_templated_email(tmpl, f'test_{tmpl}@example.com', ctx)
            self.assertTrue(sent, f"Template {tmpl} failed: {msg}")

            # Verify EmailLog was created
            log = EmailLog.objects.filter(recipient=f'test_{tmpl}@example.com').first()
            self.assertIsNotNone(log, f"Log entry missing for {tmpl}")
            self.assertTrue(log.subject.strip(), f"Subject empty for {tmpl}")
            self.assertFalse(log.subject.lower().startswith('subject:'), f"Subject prefix not stripped for {tmpl}")

            # Verify no unrendered template tags remain
            if not log.is_secret:
                self.assertNotIn('{{', log.body, f"Unrendered tags in {tmpl}: {log.body}")
                self.assertNotIn('}}', log.body, f"Unrendered tags in {tmpl}: {log.body}")
                self.assertIn(self.info.name, log.body)

    # 2. Secret emails (reg_approved, staff_created): immediate dispatch, never stored in DB
    def test_secret_emails_protection_and_resend(self):
        applicant = User.objects.create_user(
            username="secret_applicant",
            email="secret@example.com",
            status=User.STATUS_PENDING,
            role=User.ROLE_RESIDENT
        )
        Resident.objects.create(
            user=applicant,
            first_name="Clara",
            last_name="Reyes",
            birthdate=datetime.date(1990, 1, 1),
            purok=self.purok,
            contact_no="09170001111"
        )

        with self.captureOnCommitCallbacks(execute=True):
            res = approve_resident_service(applicant, self.admin)
        self.assertEqual(res['status'], 'ok')

        # Check EmailLog: body must be blank, is_secret=True
        log = EmailLog.objects.filter(recipient='secret@example.com', email_type='reg_approved').first()
        self.assertIsNotNone(log)
        self.assertTrue(log.is_secret)
        self.assertEqual(log.body, '', "Secret email body must NEVER be stored in EmailLog!")
        self.assertEqual(log.status, EmailLog.STATUS_SENT)

        # Check ActivityLog: temp_password must not be present
        activity = ActivityLog.objects.filter(target_id=str(applicant.id), action='approve').first()
        self.assertIsNotNone(activity)
        self.assertNotIn('temp_password', activity.details.lower())

        # Test Resend Temporary Password creates a new password and logs without storing body
        with self.captureOnCommitCallbacks(execute=True):
            res_resend = resend_temporary_password_service(applicant, self.admin)
        self.assertEqual(res_resend['status'], 'ok')
        resend_logs = EmailLog.objects.filter(recipient='secret@example.com', email_type='reg_approved')
        self.assertEqual(resend_logs.count(), 2)
        for r_log in resend_logs:
            self.assertEqual(r_log.body, '')
            self.assertTrue(r_log.is_secret)

    # 3. Mail failure never blocks approval or staff creation
    @patch('django.core.mail.EmailMessage.send', side_effect=Exception("SMTP Connection Refused"))
    def test_mail_failure_does_not_block_approval(self, mock_send):
        applicant = User.objects.create_user(
            username="fail_applicant",
            email="fail@example.com",
            status=User.STATUS_PENDING,
            role=User.ROLE_RESIDENT
        )
        Resident.objects.create(
            user=applicant,
            first_name="Fail",
            last_name="Test",
            birthdate=datetime.date(1990, 1, 1),
            purok=self.purok
        )

        with self.captureOnCommitCallbacks(execute=True):
            res = approve_resident_service(applicant, self.admin)

        applicant.refresh_from_db()
        self.assertEqual(applicant.status, User.STATUS_ACTIVE)
        self.assertFalse(res['email_sent'])
        self.assertIn("failed", res['message'].lower())

        # EmailLog marked failed, but body still empty
        log = EmailLog.objects.filter(recipient='fail@example.com', email_type='reg_approved').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, EmailLog.STATUS_FAILED)
        self.assertEqual(log.body, '')

    # 4. Outbox Queueing and send_queued_emails Scheduled Command
    def test_outbox_queue_and_retry_backoff(self):
        send_templated_email(
            'appt_received',
            'outbox@example.com',
            {'applicant_name': 'Outbox User', 'service': 'Clearance', 'reference_no': 'APT-999', 'date': '2026-10-20', 'time_window': 'Morning'}
        )

        log = EmailLog.objects.filter(recipient='outbox@example.com', email_type='appt_received').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, EmailLog.STATUS_QUEUED)
        self.assertEqual(log.attempts, 0)
        self.assertFalse(log.is_secret)
        self.assertTrue(len(log.body) > 10)

        # Dispatch via send_queued_emails
        call_command('send_queued_emails', force=True)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.STATUS_SENT)
        self.assertEqual(log.attempts, 1)

        # Test failure retry backoff up to 3 attempts
        fail_email = EmailLog.objects.create(
            recipient="retry@example.com",
            subject="Test Retry",
            body="Retry Body",
            email_type="appt_rejected",
            status=EmailLog.STATUS_QUEUED,
            attempts=0,
            is_secret=False
        )
        with patch('apps.history.management.commands.send_queued_emails.send_mail', side_effect=Exception("Delivery Error")):
            # Attempt 1
            call_command('send_queued_emails', force=True)
            fail_email.refresh_from_db()
            self.assertEqual(fail_email.attempts, 1)
            self.assertEqual(fail_email.status, EmailLog.STATUS_QUEUED)

            # Attempt 2
            call_command('send_queued_emails', force=True)
            fail_email.refresh_from_db()
            self.assertEqual(fail_email.attempts, 2)
            self.assertEqual(fail_email.status, EmailLog.STATUS_QUEUED)

            # Attempt 3 -> Marks failed
            call_command('send_queued_emails', force=True)
            fail_email.refresh_from_db()
            self.assertEqual(fail_email.attempts, 3)
            self.assertEqual(fail_email.status, EmailLog.STATUS_FAILED)

    # 5. Appointment Reminders Scheduled Command (Tomorrow Manila time, idempotent, approved only)
    def test_send_appointment_reminders_command(self):
        manila_tz = zoneinfo.ZoneInfo("Asia/Manila")
        now_manila = timezone.now().astimezone(manila_tz)
        tomorrow_manila = now_manila.date() + datetime.timedelta(days=1)
        two_days_later = now_manila.date() + datetime.timedelta(days=2)

        service = HealthCareService.objects.create(
            name="Medical Consultation",
            description="General checkup and consultation",
            is_active=True
        )

        # 1. Approved appointment for tomorrow (should be reminded)
        apt_approved = Appointment.objects.create(
            resident=self.resident_user,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=service,
            appt_date=tomorrow_manila,
            status=Appointment.STATUS_APPROVED
        )

        # 2. Pending appointment for tomorrow (should be skipped)
        apt_pending = Appointment.objects.create(
            resident=self.resident_user,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=service,
            appt_date=tomorrow_manila,
            status=Appointment.STATUS_PENDING
        )

        # 3. Approved appointment for 2 days later (should be skipped)
        apt_future = Appointment.objects.create(
            resident=self.resident_user,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=service,
            appt_date=two_days_later,
            status=Appointment.STATUS_APPROVED
        )

        # Run command
        call_command('send_appointment_reminders')

        apt_approved.refresh_from_db()
        apt_pending.refresh_from_db()
        apt_future.refresh_from_db()

        self.assertIsNotNone(apt_approved.reminder_sent_at)
        self.assertIsNone(apt_pending.reminder_sent_at)
        self.assertIsNone(apt_future.reminder_sent_at)

        # Verify email is queued in outbox
        reminder_log = EmailLog.objects.filter(
            recipient=self.resident_user.email,
            email_type='appt_reminder.txt',
            ref_id=str(apt_approved.id)
        ).first()
        self.assertIsNotNone(reminder_log)
        self.assertEqual(reminder_log.status, EmailLog.STATUS_QUEUED)

        # Idempotency test: Running again should NOT queue another reminder
        initial_sent_at = apt_approved.reminder_sent_at
        call_command('send_appointment_reminders')
        apt_approved.refresh_from_db()
        self.assertEqual(apt_approved.reminder_sent_at, initial_sent_at)
        self.assertEqual(
            EmailLog.objects.filter(ref_id=str(apt_approved.id), email_type='appt_reminder.txt').count(),
            1
        )

    # 6. Redaction of sensitive details (passwords, needs_notes)
    def test_audit_and_email_redaction(self):
        text = "Created account password: SuperSecretPassword123! and temp_password: temp1234. Notes: needs_notes: Private medical data."
        sanitized = sanitize_audit_details(text)
        self.assertNotIn("SuperSecretPassword123!", sanitized)
        self.assertNotIn("temp1234", sanitized)
        self.assertNotIn("Private medical data", sanitized)
        self.assertIn("[REDACTED]", sanitized)

        log = log_activity(
            actor=self.admin,
            action='update',
            action_type='Resident',
            target_id='999',
            target_name='Juan',
            details=text
        )
        self.assertNotIn("SuperSecretPassword123!", log.details)
        self.assertNotIn("Private medical data", log.details)

    # 7. Notification System: Creation, Triggers, Unread Count, and Access Guard
    def test_notification_system_and_access_guard(self):
        # Create notification for resident
        notif_resident = create_notification(
            recipient=self.resident_user,
            title="Appointment Confirmed",
            message="Your appointment is set for tomorrow.",
            url="/appointments/my/",
            action_type="appointment"
        )
        self.assertFalse(notif_resident.is_read)
        self.assertEqual(notif_resident.notification_type, Notification.TYPE_APPOINTMENT)

        # Notification for staff
        notif_staff = create_notification(
            recipient=self.admin,
            title="New Pending Registration",
            message="A new resident registered.",
            url="/accounts/residents/?tab=pending",
            action_type="registration"
        )

        # Unread count
        self.client.login(username="resident_h", password="Password123!")
        res = self.client.get(reverse('chat:unread_notifications_count'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['unread_count'], 1)

        # Mark read on open
        open_res = self.client.get(reverse('chat:open_notification', kwargs={'notif_id': notif_resident.id}))
        self.assertEqual(open_res.status_code, 302)
        self.assertEqual(open_res.url, '/appointments/my/')
        notif_resident.refresh_from_db()
        self.assertTrue(notif_resident.is_read)

        # Access guard: Resident tries to open notification targeting staff area
        malicious_notif = Notification.objects.create(
            recipient=self.resident_user,
            title="Sneak Peak",
            message="Admin portal",
            url="/system/logs/",
            action_type="system"
        )
        guard_res = self.client.get(reverse('chat:open_notification', kwargs={'notif_id': malicious_notif.id}))
        self.assertEqual(guard_res.status_code, 302)
        self.assertEqual(guard_res.url, '/home/')  # Redirected safely to /home/

        # Resident tries to open someone else's notification
        other_res = self.client.get(reverse('chat:open_notification', kwargs={'notif_id': notif_staff.id}))
        self.assertEqual(other_res.status_code, 404)

        # Mark all as read
        notif_extra = create_notification(
            recipient=self.resident_user,
            title="Announcement",
            message="General meeting tonight",
            url="/feed/",
            action_type="announcement"
        )
        self.assertFalse(notif_extra.is_read)
        mark_res = self.client.post(reverse('chat:mark_all_read'))
        self.assertEqual(mark_res.status_code, 302)
        notif_extra.refresh_from_db()
        self.assertTrue(notif_extra.is_read)

    # 8. cleanup_read_notifications scheduled command
    def test_cleanup_read_notifications_command(self):
        past_95_days = timezone.now() - datetime.timedelta(days=95)
        past_10_days = timezone.now() - datetime.timedelta(days=10)

        # Old read notification (> 90 days) -> should be deleted
        n_old_read = Notification.objects.create(
            recipient=self.resident_user,
            title="Old Read",
            message="Deleted",
            is_read=True
        )
        Notification.objects.filter(id=n_old_read.id).update(created_at=past_95_days)

        # Old unread notification (> 90 days) -> should be KEPT (never delete unread)
        n_old_unread = Notification.objects.create(
            recipient=self.resident_user,
            title="Old Unread",
            message="Keep",
            is_read=False
        )
        Notification.objects.filter(id=n_old_unread.id).update(created_at=past_95_days)

        # Recent read notification (< 90 days) -> should be KEPT
        n_recent_read = Notification.objects.create(
            recipient=self.resident_user,
            title="Recent Read",
            message="Keep",
            is_read=True
        )
        Notification.objects.filter(id=n_recent_read.id).update(created_at=past_10_days)

        call_command('cleanup_read_notifications', days=90)

        self.assertFalse(Notification.objects.filter(id=n_old_read.id).exists())
        self.assertTrue(Notification.objects.filter(id=n_old_unread.id).exists())
        self.assertTrue(Notification.objects.filter(id=n_recent_read.id).exists())

    # 9. History Overview Screen (Admin-only, Read-only, Filters, and Outbox Resend)
    def test_history_screen_access_and_resend_endpoint(self):
        # Anonymous -> redirect to login
        res = self.client.get(reverse('history:overview'))
        self.assertEqual(res.status_code, 302)

        # Resident -> 403 Forbidden
        self.client.login(username="resident_h", password="Password123!")
        res = self.client.get(reverse('history:overview'))
        self.assertEqual(res.status_code, 403)

        # Admin -> 200 OK
        self.client.login(username="admin_h", password="AdminPassword123!")
        res = self.client.get(reverse('history:overview'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Audit Trail & History Records")

        # Test filtering by module and search query
        log_activity(
            actor=self.admin,
            action='create',
            action_type='Appointment',
            target_id='101',
            target_name='Medical Clearance',
            details='Scheduled appointment for medical clearance'
        )
        res_filter = self.client.get(reverse('history:overview'), {'module': 'Appointment'})
        self.assertEqual(res_filter.status_code, 200)
        self.assertContains(res_filter, "Medical Clearance")

        # Test resending failed non-secret email via admin POST
        failed_email = EmailLog.objects.create(
            recipient="failed@example.com",
            subject="Failed Document Notice",
            body="Your document is ready.",
            status=EmailLog.STATUS_FAILED,
            attempts=3,
            is_secret=False
        )
        res_resend = self.client.post(reverse('history:resend_failed_email', kwargs={'email_id': failed_email.id}))
        self.assertEqual(res_resend.status_code, 302)
        failed_email.refresh_from_db()
        self.assertEqual(failed_email.status, EmailLog.STATUS_QUEUED)
        self.assertEqual(failed_email.attempts, 0)

        # Test attempting to resend secret email via endpoint is rejected
        secret_email = EmailLog.objects.create(
            recipient="secret_fail@example.com",
            subject="Temporary Credentials",
            body="",
            status=EmailLog.STATUS_FAILED,
            is_secret=True
        )
        res_secret_resend = self.client.post(reverse('history:resend_failed_email', kwargs={'email_id': secret_email.id}))
        self.assertEqual(res_secret_resend.status_code, 302)
        secret_email.refresh_from_db()
        self.assertEqual(secret_email.status, EmailLog.STATUS_FAILED, "Secret email must never be re-queued from outbox!")
