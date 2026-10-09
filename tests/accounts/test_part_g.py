import os
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.core.management import call_command

from apps.accounts.models import (
    User, Resident, Purok, Officer, StaffAssignment, PermissionRule, BarangayInfo
)
from apps.accounts.services import (
    approve_resident_service,
    update_resident_needs_service,
    get_dashboard_metrics,
    staff_register_resident_service,
    register_resident_service,
)
from apps.accounts.permissions import PermissionRegistry
from apps.accounts import system_services
from apps.appointments.models import DocumentType, Requirement, HealthCareService, Appointment
from apps.appointments.services import book_appointment_service
from tests.base import get_document_type
from apps.chat.models import ConcernCategory
from apps.chat.services import create_direct_thread_service
from apps.communications.models import PostCategory, Post
from apps.history.models import ActivityLog
from apps.history.utils import send_templated_email
from tests.base import JPEG_BYTES, PNG_BYTES


class PartGTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_boss',
            email='admin@barangay.ph',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_superuser=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Admin',
            last_name='Barangay'
        )

        # Standard staff user with permissions
        self.staff_user = User.objects.create_user(
            username='staff_officer',
            email='staff@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Kagawad',
            last_name='Santos'
        )
        self.officer_role = Officer.objects.create(
            position='Kagawad on Health',
            committee='Health'
        )
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=self.officer_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='all'
        )
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='view', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='create', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='view_needs', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='edit_needs', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='chat', action='message_residents', allowed=True)

        # Restricted staff without view_needs
        self.restricted_staff = User.objects.create_user(
            username='tanod_juan',
            email='tanod@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Tanod',
            last_name='Juan'
        )
        self.tanod_role = Officer.objects.create(
            position='Barangay Tanod',
            committee='Security'
        )
        StaffAssignment.objects.create(
            user=self.restricted_staff,
            officer=self.tanod_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='security'
        )
        PermissionRule.objects.create(officer=self.tanod_role, module='residents', action='view', allowed=True)

        # Standard resident
        self.resident_user = User.objects.create_user(
            username='resident_pedro',
            email='pedro@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Pedro',
            last_name='Penduko',
            date_of_birth=datetime.date(1985, 3, 15)
        )
        self.purok_1, _ = Purok.objects.get_or_create(name='Purok 1')
        self.resident_profile = Resident.objects.create(
            user=self.resident_user,
            first_name='Pedro',
            last_name='Penduko',
            birthdate=datetime.date(1985, 3, 15),
            purok=self.purok_1
        )

    # 1. Link-on-approval: do NOT auto-merge. Explicit link confirmation; two people with same name & bday can stay separate.
    def test_link_on_approval_does_not_auto_merge_and_allows_separate(self):
        # Create an existing resident profile in DB (e.g. registered offline)
        existing_resident = Resident.objects.create(
            first_name='Maria',
            last_name='Clara',
            birthdate=datetime.date(1995, 8, 20),
            purok=self.purok_1,
            address='123 Old St',
            contact_no='09111111111',
            needs_attention=True,
            needs_category='pwd',
            consent_recorded=True
        )

        # New self-signup user with same name and birthdate awaiting approval
        new_applicant = User.objects.create_user(
            username='maria_new',
            email='maria.new@example.com',
            password='temppassword123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            status=User.STATUS_PENDING,
            first_name='Maria',
            last_name='Clara',
            date_of_birth=datetime.date(1995, 8, 20),
            address='456 New Blvd',
            phone_number='09222222222'
        )
        # Create applicant's initial registration stub profile
        Resident.objects.create(
            user=new_applicant,
            first_name='Maria',
            last_name='Clara',
            birthdate=datetime.date(1995, 8, 20),
            purok=self.purok_1,
            address='456 New Blvd',
            contact_no='09222222222'
        )

        # Scenario A: Admin approves WITHOUT providing link_resident_id
        # Must NOT auto-merge! Should keep the separate resident profile.
        approve_resident_service(
            user=new_applicant,
            admin_user=self.admin,
            link_resident_id=None
        )
        new_applicant.refresh_from_db()
        self.assertTrue(new_applicant.is_approved)
        self.assertEqual(new_applicant.status, User.STATUS_ACTIVE)

        new_profile = Resident.objects.get(user=new_applicant)
        self.assertNotEqual(new_profile.id, existing_resident.id)
        # Verify both residents exist separately
        self.assertEqual(Resident.objects.filter(first_name='Maria', last_name='Clara').count(), 2)

        # Scenario B: Explicit link on another applicant
        applicant_b = User.objects.create_user(
            username='maria_to_link',
            email='maria.link@example.com',
            password='temppassword123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            status=User.STATUS_PENDING,
            first_name='Maria',
            last_name='Clara',
            date_of_birth=datetime.date(1995, 8, 20),
            address='789 Winning Street',
            phone_number='09333333333'
        )
        Resident.objects.create(
            user=applicant_b,
            first_name='Maria',
            last_name='Clara',
            birthdate=datetime.date(1995, 8, 20),
            purok=self.purok_1,
            address='789 Winning Street',
            contact_no='09333333333'
        )

        approve_resident_service(
            user=applicant_b,
            admin_user=self.admin,
            link_resident_id=existing_resident.id
        )
        applicant_b.refresh_from_db()
        existing_resident.refresh_from_db()

        # Check winning fields: user account wins for address/phone, resident wins for needs/consent
        self.assertEqual(existing_resident.user, applicant_b)
        self.assertEqual(existing_resident.address, '789 Winning Street')
        self.assertEqual(existing_resident.contact_no, '09333333333')
        self.assertTrue(existing_resident.needs_attention)
        self.assertTrue(existing_resident.consent_recorded)

        # Check merge audit log
        merge_log = ActivityLog.objects.filter(action='merge', target_id=str(existing_resident.id)).first()
        self.assertIsNotNone(merge_log)

    # 2. Refuse to set needs_attention unless consent_recorded is true or reason entered
    def test_needs_attention_consent_validation(self):
        resident = Resident.objects.create(
            first_name='Jose',
            last_name='Rizal',
            birthdate=datetime.date(1980, 6, 19),
            purok=self.purok_1
        )

        # Attempt 1: needs_attention=True without consent and without reason -> ValueError
        with self.assertRaises(ValueError):
            update_resident_needs_service(
                resident=resident,
                actor=self.staff_user,
                data={
                    'needs_attention': True,
                    'needs_category': 'senior',
                    'needs_notes': 'Needs medicine delivery',
                    'consent_recorded': False,
                    'no_consent_reason': ''
                }
            )

        # Attempt 2: needs_attention=True with consent_recorded=True -> Success
        res = update_resident_needs_service(
            resident=resident,
            actor=self.staff_user,
            data={
                'needs_attention': True,
                'needs_category': 'senior',
                'needs_notes': 'Needs medicine delivery',
                'consent_recorded': True,
                'no_consent_reason': ''
            }
        )
        self.assertTrue(res.needs_attention)
        self.assertTrue(res.consent_recorded)

        # Attempt 3: needs_attention=True without consent but WITH valid reason -> Success
        res2 = update_resident_needs_service(
            resident=resident,
            actor=self.staff_user,
            data={
                'needs_attention': True,
                'needs_category': 'senior',
                'needs_notes': 'Emergency medical assistance',
                'consent_recorded': False,
                'no_consent_reason': 'Resident unconscious during rescue'
            }
        )
        self.assertTrue(res2.needs_attention)
        self.assertFalse(res2.consent_recorded)
        self.assertEqual(res2.no_consent_reason, 'Resident unconscious during rescue')

    # 3. Hide needs-attention count from anyone without residents.view_needs. No zero placeholder.
    def test_hide_needs_attention_count_without_permission(self):
        # Restricted staff lacks residents.view_needs
        metrics = get_dashboard_metrics(user=self.restricted_staff)
        self.assertIsNone(metrics['needs_attention_count'])

        # Staff with permission gets the actual count
        staff_metrics = get_dashboard_metrics(user=self.staff_user)
        self.assertIsNotNone(staff_metrics['needs_attention_count'])
        self.assertIsInstance(staff_metrics['needs_attention_count'], int)

        # Check Home / Dashboard view HTML does not render the needs attention card for restricted staff
        self.client.login(username='tanod_juan', password='password123')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Needs Attention")

        # Admin sees it
        self.client.login(username='admin_boss', password='password123')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Needs Attention")

    # 4. Staff-registered minors cannot be messaged, cannot be linked to a self-signup, and are not portal-eligible
    def test_staff_registered_minors_restrictions(self):
        # Register a minor (10 years old)
        today = timezone.localdate()
        minor_birthdate = today - datetime.timedelta(days=10 * 365)

        minor = staff_register_resident_service(
            staff_user=self.staff_user,
            data={
                'first_name': 'Batang',
                'last_name': 'Bata',
                'birthdate': minor_birthdate.strftime('%Y-%m-%d'),
                'gender': 'M',
                'purok': self.purok_1,
                'address': 'Street 10',
                'civil_status': 'single'
            }
        )
        self.assertTrue(minor.is_minor)

        # 4a. Minor cannot be messaged
        # Create an account representing minor
        minor_user = User.objects.create_user(
            username='minor_account',
            email='minor@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            date_of_birth=minor_birthdate
        )
        minor.user = minor_user
        minor.save()

        with self.assertRaises(PermissionDenied):
            create_direct_thread_service(
                sender=self.staff_user,
                recipient=minor_user,
                raw_content='Hello minor'
            )

        # 4b. Minor cannot be linked to a self-signup
        applicant = User.objects.create_user(
            username='applicant_adult',
            email='adult@example.com',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            status=User.STATUS_PENDING,
            first_name='Batang',
            last_name='Bata',
            date_of_birth=datetime.date(1990, 1, 1)
        )
        with self.assertRaises(ValueError):
            approve_resident_service(
                user=applicant,
                admin_user=self.admin,
                link_resident_id=minor.id
            )

        # 4c. Minor not counted as portal-eligible
        metrics = get_dashboard_metrics(user=self.admin)
        # Minor has age < 18, so must be excluded from portal_eligible_count
        eligible_profiles = Resident.objects.filter(is_archived=False, birthdate__lte=today.replace(year=today.year - 18))
        self.assertEqual(metrics['portal_eligible_count'], eligible_profiles.count())

    # 5. Scheduled command deletes ID photo and personal details of rejected registrations after N days
    def test_cleanup_rejected_registrations_command(self):
        old_time = timezone.now() - datetime.timedelta(days=100)

        # Create rejected user
        rejected_user = User.objects.create_user(
            username='rejected_reg',
            email='rejected@example.com',
            password='password123',
            role=User.ROLE_RESIDENT,
            status=User.STATUS_REJECTED,
            is_approved=False,
            address='Private Rejected Home 123',
            phone_number='09998887766',
            reviewed_at=old_time
        )
        # Create resident profile with id_photo
        dummy_photo = SimpleUploadedFile("id_test.jpg", JPEG_BYTES, content_type="image/jpeg")
        rejected_resident = Resident.objects.create(
            user=rejected_user,
            first_name='SecretPerson',
            last_name='SecretFamily',
            birthdate=datetime.date(1990, 1, 1),
            address='Private Address',
            contact_no='09998887766',
            id_photo=dummy_photo
        )

        photo_path = rejected_resident.id_photo.path
        self.assertTrue(os.path.exists(photo_path))

        # Call cleanup command with 90 days threshold
        call_command('cleanup_rejected_registrations', '--days', 90)

        rejected_user.refresh_from_db()
        rejected_resident.refresh_from_db()

        # ID photo should be empty, deleted from disk, and sensitive fields cleared
        self.assertFalse(bool(rejected_resident.id_photo))
        self.assertFalse(os.path.exists(photo_path))
        self.assertEqual(rejected_resident.address, '')
        self.assertEqual(rejected_resident.contact_no, '')
        self.assertEqual(rejected_user.address, '')
        self.assertEqual(rejected_user.phone_number, '')

        # Audit log must contain no personal names
        log_entry = ActivityLog.objects.filter(target_id=str(rejected_user.id), action_type='RetentionPolicy').first()
        self.assertIsNotNone(log_entry)
        self.assertNotIn('SecretPerson', log_entry.target_name)
        self.assertNotIn('SecretFamily', log_entry.target_name)
        self.assertNotIn('SecretPerson', log_entry.details)
        self.assertNotIn('SecretFamily', log_entry.details)

        # Verify person can register again with the same email
        new_photo = SimpleUploadedFile("id_new.jpg", JPEG_BYTES, content_type="image/jpeg")
        re_user, re_res = register_resident_service({
            'first_name': 'Reapplied',
            'last_name': 'Applicant',
            'email': 'rejected@example.com',
            'birthdate': datetime.date(1990, 1, 1),
            'contact_no': '09112223344',
            'address': 'New Address 456',
            'purok': self.purok_1,
        }, id_photo_file=new_photo)
        self.assertEqual(re_user.id, rejected_user.id)
        self.assertEqual(re_user.status, User.STATUS_PENDING)
        self.assertEqual(re_user.email, 'rejected@example.com')
        self.assertEqual(re_res.address, 'New Address 456')

    # 6. Paginate and search residents list
    def test_residents_list_pagination_and_search(self):
        # Create 25 approved resident users
        for i in range(25):
            u = User.objects.create_user(
                username=f'approved_user_{i:02d}',
                email=f'user{i:02d}@example.com',
                password='password123',
                role=User.ROLE_RESIDENT,
                status=User.STATUS_ACTIVE,
                is_approved=True,
                first_name=f'Resident{i:02d}',
                last_name='PaginationTest',
                date_of_birth=datetime.date(1990, 1, 1) + datetime.timedelta(days=i)
            )
            Resident.objects.create(
                user=u,
                first_name=f'Resident{i:02d}',
                last_name='PaginationTest',
                birthdate=datetime.date(1990, 1, 1) + datetime.timedelta(days=i),
                purok=self.purok_1
            )

        self.client.login(username='admin_boss', password='password123')

        # Test search on approved tab
        resp = self.client.get(reverse('accounts:residents_tabbed'), {'tab': 'approved', 'q': 'Resident05'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Resident05')
        self.assertNotContains(resp, 'Resident15')

        # Test pagination (page 2)
        resp_p2 = self.client.get(reverse('accounts:residents_tabbed'), {'tab': 'approved', 'page': 2})
        self.assertEqual(resp_p2.status_code, 200)
        self.assertTrue(resp_p2.context['approved_page'].has_previous())

    # 7. Generate post_<category> permission actions dynamically from active Category table
    def test_new_category_appears_as_grantable_permission(self):
        new_cat = PostCategory.objects.create(
            name='Sports & Recreation',
            slug='sports_rec',
            is_active=True
        )
        actions = PermissionRegistry.get_actions_for_module('communications')
        self.assertIn('post_sports_rec', actions)

    # 8. System category cannot be deleted
    def test_system_category_cannot_be_deleted(self):
        health_cat, _ = PostCategory.objects.get_or_create(
            slug='health',
            defaults={'name': 'Health Update', 'is_system': True}
        )
        with self.assertRaises(ValueError):
            system_services.delete_post_category_service(self.admin, health_cat.id)

    # 9. Deactivating a category hides it from post form but old posts still render
    def test_deactivating_category_hides_from_form_but_old_posts_render(self):
        cat = PostCategory.objects.create(
            name='Festival',
            slug='festival',
            is_active=True
        )
        old_post = Post.objects.create(
            title='Annual Fiesta 2026',
            content='Come and celebrate with us!',
            category_ref=cat,
            author=self.admin,
            audience_type=Post.AUDIENCE_EVERYONE,
            state=Post.STATE_ACTIVE
        )

        # Deactivate category
        cat.is_active = False
        cat.save()

        # Old post renders fine
        self.client.login(username='resident_pedro', password='password123')
        resp = self.client.get(reverse('communications:feed'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Annual Fiesta 2026')

        # Post creation view does not show deactivated category
        self.client.login(username='admin_boss', password='password123')
        resp_create = self.client.get(reverse('communications:create_announcement'))
        self.assertEqual(resp_create.status_code, 200)
        self.assertNotContains(resp_create, 'Festival')

    # 10. Price change on DocumentType leaves old appointments unchanged (stores fee_at_booking)
    def test_price_change_leaves_old_appointments_unchanged(self):
        doc_type = DocumentType.objects.create(
            name='Barangay Clearance Certificate',
            fee=Decimal('150.00'),
            is_active=True
        )

        # Book an appointment
        booking_date = timezone.localdate() + datetime.timedelta(days=5)
        while booking_date.weekday() >= 5:
            booking_date += datetime.timedelta(days=1)

        appt = book_appointment_service(
            user=self.resident_user,
            data={
                'category': Appointment.CATEGORY_DOCUMENT,
                'document_type_id': doc_type.id,
                'appt_date': booking_date,
                'time_window': Appointment.TIME_SLOT_MORNING,
                'purpose': 'Employment clearance'
            }
        )
        self.assertEqual(appt.fee_at_booking, Decimal('150.00'))

        # Now admin updates document fee to 300.00
        system_services.create_or_update_document_type_service(
            actor=self.admin,
            data={
                'name': 'Barangay Clearance Certificate',
                'fee': '300.00',
                'order': 1,
                'is_active': 'on'
            },
            doc_id=doc_type.id
        )

        # Old appointment fee remains 150.00
        appt.refresh_from_db()
        self.assertEqual(appt.fee_at_booking, Decimal('150.00'))

    # 11. Deleting referenced document type or health service is refused
    def test_deleting_referenced_document_or_health_service_refused(self):
        doc_type = get_document_type('residency', 'Certificate of Residency', fee=Decimal('50.00'))
        booking_date = timezone.localdate() + datetime.timedelta(days=3)
        while booking_date.weekday() >= 5:
            booking_date += datetime.timedelta(days=1)

        book_appointment_service(
            user=self.resident_user,
            data={
                'category': Appointment.CATEGORY_DOCUMENT,
                'document_type_id': doc_type.id,
                'appt_date': booking_date,
                'time_window': Appointment.TIME_SLOT_MORNING,
                'purpose': 'Bank requirement'
            }
        )

        # Deleting doc_type should be refused
        with self.assertRaises(ValueError):
            system_services.delete_document_type_service(self.admin, doc_type.id)

        # Health care service deletion protection
        health_svc = HealthCareService.objects.create(
            name='Dental Extraction',
            is_free=True
        )
        Appointment.objects.create(
            resident=self.resident_user,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=health_svc,            appt_date=booking_date,
            time_window=Appointment.TIME_SLOT_MORNING,
            purpose='Checkup',
            status=Appointment.STATUS_PENDING
        )
        with self.assertRaises(ValueError):
            system_services.delete_health_service_service(self.admin, health_svc.id)

    # 12. Emails use BarangayInfo metadata
    def test_emails_use_barangay_info(self):
        info = BarangayInfo.get_solo()
        info.name = 'Barangay San Lorenzo Ruiz'
        info.venue = 'Multi-Purpose Activity Center'
        info.contact_no = '0922-333-4444'
        info.save()

        # Send test template email (queued in outbox per Part H)
        send_templated_email(
            template_name='appt_approved',
            to_email='pedro@barangay.ph',
            context={'applicant_name': 'Pedro Penduko', 'appointment_date': '2026-10-15', 'appointment_time': '09:00'}
        )
        from django.core.management import call_command
        call_command('send_queued_emails', force=True)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('Barangay San Lorenzo Ruiz', sent_email.body)
        self.assertIn('Multi-Purpose Activity Center', sent_email.body)

    # 13. Audit row on every System change with before/after values
    def test_audit_row_on_every_system_change(self):
        # Update BarangayInfo
        system_services.update_barangay_info_service(
            actor=self.admin,
            data={
                'name': 'Barangay Moderno',
                'address': '777 Tech City',
                'contact_no': '09000000000',
                'office_hours': '8am - 5pm'
            }
        )

        log = ActivityLog.objects.filter(action_type='SystemConfig', action='update').last()
        self.assertIsNotNone(log)
        self.assertIn('before', log.details.lower())
        self.assertIn('after', log.details.lower())
        self.assertIn('Barangay Moderno', log.details)

        # Create PostCategory
        cat = system_services.create_or_update_post_category_service(
            actor=self.admin,
            data={
                'name': 'Infrastructure',
                'expires': 'on',
                'default_end': 'end_of_month',
                'notify_on_post': 'on'
            }
        )
        log_cat = ActivityLog.objects.filter(action_type='PostCategory', action='create').last()
        self.assertIsNotNone(log_cat)
        self.assertIn('Infrastructure', log_cat.target_name)

        # Create Staff Account
        staff = system_services.create_staff_account_service(
            actor=self.admin,
            data={
                'username': 'new_staff_guy',
                'email': 'guy@barangay.ph',
                'first_name': 'New',
                'last_name': 'Guy',
                'role': User.ROLE_STAFF,
                'term_end': (timezone.localdate() + datetime.timedelta(days=20)).strftime('%Y-%m-%d'),
                'officer_id': self.officer_role.id,
                'scope_type': 'all',
                'scope_value': 'all'
            }
        )
        log_staff = ActivityLog.objects.filter(action_type='StaffAccount', action='create').last()
        self.assertIsNotNone(log_staff)
        self.assertIn('New Guy', log_staff.target_name)
