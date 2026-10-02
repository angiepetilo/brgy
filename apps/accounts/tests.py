from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, date
from apps.accounts.models import User, Household
from apps.appointments.models import Appointment, IssuedDocumentLog
from apps.communications.models import KapitanStatus, Announcement, LegislativeRecord
from apps.blotter.models import BlotterRecord, KPCase
from apps.finance.models import AssetInventory


class BarangaySystemIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            role=User.ROLE_ADMIN,
        )

        # Kapitan user
        self.kapitan_user = User.objects.create_user(
            username='kapitan_test',
            email='kapitan@test.com',
            password='password123',
            role=User.ROLE_KAPITAN,
            is_approved=True,
        )

        # Approved resident
        self.approved_resident = User.objects.create_user(
            username='maria_test',
            email='maria@test.com',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            purok='Purok 2',
            civil_status='Single',
            occupation='Accountant',
            is_senior=False,
            is_pwd=False,
            is_4ps=False,
        )

        # Unapproved resident
        self.unapproved_resident = User.objects.create_user(
            username='juan_test',
            email='juan@test.com',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            purok='Purok 4',
        )

    def test_custom_user_roles_and_properties(self):
        """Verify role flags and helper properties"""
        self.assertTrue(self.admin_user.is_admin_user)
        self.assertTrue(self.admin_user.is_staff)
        self.assertTrue(self.kapitan_user.is_kapitan_user)
        self.assertTrue(self.approved_resident.is_resident_user)
        self.assertFalse(self.unapproved_resident.is_approved)

    def test_approval_gate_blocks_unapproved_resident(self):
        """Unapproved resident must be redirected away from core views to pending verification page"""
        self.client.login(username='juan_test', password='password123')

        # Attempt to access dashboard
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(response, reverse('accounts:pending_approval'))

        # Attempt to access document requests
        response = self.client.get(reverse('appointments:list'))
        self.assertRedirects(response, reverse('accounts:pending_approval'))

        # Attempt to access chat inbox
        response = self.client.get(reverse('chat:inbox'))
        self.assertRedirects(response, reverse('accounts:pending_approval'))

        # Must be able to view pending page
        response = self.client.get(reverse('accounts:pending_approval'))
        self.assertEqual(response.status_code, 200)

    def test_approved_resident_can_access_core_views(self):
        """Approved resident can freely view dashboard and document appointments"""
        self.client.login(username='maria_test', password='password123')

        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mabuhay")

        response = self.client.get(reverse('appointments:list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_approves_resident(self):
        """Admin can approve unverified resident"""
        self.client.login(username='admin_test', password='password123')

        # Check approval list
        response = self.client.get(reverse('accounts:approval_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'juan_test')

        # Approve resident
        approve_url = reverse('accounts:approve_resident', kwargs={'user_id': self.unapproved_resident.id})
        response = self.client.post(approve_url)
        self.assertRedirects(response, reverse('accounts:approval_list'))

        # Reload user
        self.unapproved_resident.refresh_from_db()
        self.assertTrue(self.unapproved_resident.is_approved)
        self.assertEqual(self.unapproved_resident.verified_by, self.admin_user)

    def test_appointment_lifecycle_and_status_update(self):
        """Resident submits request and admin transitions status"""
        self.client.login(username='maria_test', password='password123')

        create_url = reverse('appointments:create')
        post_data = {
            'document_type': Appointment.DOC_CLEARANCE,
            'purpose': 'Passport Application Requirement',
            'preferred_date': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
            'preferred_time_slot': Appointment.TIME_SLOT_MORNING,
        }
        response = self.client.post(create_url, post_data)
        apt = Appointment.objects.filter(resident=self.approved_resident).first()
        self.assertIsNotNone(apt)
        self.assertEqual(apt.status, Appointment.STATUS_SUBMITTED)

        # Admin updates status to approved_scheduled
        self.client.login(username='admin_test', password='password123')
        detail_url = reverse('appointments:detail', kwargs={'pk': apt.id})
        update_data = {
            'update_status': '1',
            'status': Appointment.STATUS_APPROVED_SCHEDULED,
            'admin_notes': 'Confirmed for Friday morning processing.',
        }
        response = self.client.post(detail_url, update_data)
        self.assertRedirects(response, detail_url)

        apt.refresh_from_db()
        self.assertEqual(apt.status, Appointment.STATUS_APPROVED_SCHEDULED)
        self.assertEqual(apt.processed_by, self.admin_user)

    def test_kapitan_duty_tracker(self):
        """Kapitan can toggle status to on_leave with mandatory reason and return date"""
        self.client.login(username='kapitan_test', password='password123')
        url = reverse('communications:kapitan_tracker')

        # Toggle to on_leave
        post_data = {
            'status': KapitanStatus.STATUS_ON_LEAVE,
            'leave_reason': 'Official League of Municipalities Convention',
            'return_date': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
        }
        response = self.client.post(url, post_data)
        self.assertRedirects(response, url)

        status_obj = KapitanStatus.objects.order_by('-updated_at').first()
        self.assertEqual(status_obj.status, KapitanStatus.STATUS_ON_LEAVE)
        self.assertEqual(status_obj.leave_reason, 'Official League of Municipalities Convention')

    def test_rbi_directory_and_demographics(self):
        """Admin can access RBI directory and filter by Household and Senior/PWD flags"""
        hh = Household.objects.create(
            household_number='HH-TEST-001',
            head=self.approved_resident,
            address='123 Sunflower St',
            purok='Purok 2'
        )
        self.approved_resident.household = hh
        self.approved_resident.is_senior = True
        self.approved_resident.save()

        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('accounts:rbi_directory'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registry of Barangay Inhabitants')
        self.assertContains(response, 'HH-TEST-001')

        # Filter by senior
        response = self.client.get(reverse('accounts:rbi_directory') + '?is_senior=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maria_test')

    def test_blotter_and_kp_mediation(self):
        """Admin can log blotter case and manage KP mediation hearings"""
        self.client.login(username='admin_test', password='password123')

        # Log new incident
        post_data = {
            'case_number': 'BLOT-TEST-001',
            'complainant_name': 'Juan Complainant',
            'respondent_name': 'Pedro Respondent',
            'incident_type': 'Noise Disturbance',
            'incident_location': 'Purok 1 Hall',
            'incident_date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'narrative': 'Loud music played during curfew hours.',
            'status': BlotterRecord.STATUS_OPEN,
        }
        response = self.client.post(reverse('blotter:create'), post_data)
        record = BlotterRecord.objects.filter(case_number='BLOT-TEST-001').first()
        self.assertIsNotNone(record)
        self.assertRedirects(response, reverse('blotter:detail', kwargs={'pk': record.id}))

        # Update KP mediation hearing
        hearing_time = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        kp_data = {
            'update_kp': '1',
            'hearing_date': hearing_time,
            'mediator_notes': 'Hearing scheduled before Punong Barangay.',
            'certificate_to_file_action': False,
        }
        detail_url = reverse('blotter:detail', kwargs={'pk': record.id})
        response = self.client.post(detail_url, kp_data)
        self.assertRedirects(response, detail_url)

        kp_case = KPCase.objects.get(blotter=record)
        self.assertIsNotNone(kp_case.hearing_date)
        self.assertEqual(kp_case.mediator_notes, 'Hearing scheduled before Punong Barangay.')

    def test_transparency_portal_and_legislative_records(self):
        """Verify public access to ordinances and resolutions"""
        leg = LegislativeRecord.objects.create(
            title='Curfew and Youth Safety Ordinance',
            category=LegislativeRecord.CATEGORY_ORDINANCE,
            document_number='Ord. 2026-99',
            date_approved=date(2026, 1, 1),
            summary='Curfew hours for minors between 10PM and 4AM.',
            is_public=True,
        )

        self.client.login(username='maria_test', password='password123')
        response = self.client.get(reverse('communications:transparency'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ord. 2026-99')
        self.assertContains(response, 'Curfew and Youth Safety Ordinance')

    def test_automated_qr_code_signal_on_completed_appointment(self):
        """Signal must automatically create IssuedDocumentLog with QR code when appointment is completed"""
        apt = Appointment.objects.create(
            resident=self.approved_resident,
            document_type=Appointment.DOC_CLEARANCE,
            purpose='Employment Verification Requirement',
            preferred_date=timezone.now().date() + timedelta(days=1),
            preferred_time_slot=Appointment.TIME_SLOT_MORNING,
            status=Appointment.STATUS_UNDER_REVIEW,
            processed_by=self.admin_user,
        )
        self.assertFalse(IssuedDocumentLog.objects.filter(appointment=apt).exists())

        # Transition status to completed
        apt.status = Appointment.STATUS_COMPLETED
        apt.save()

        # Check that IssuedDocumentLog was automatically generated by post_save signal
        log = IssuedDocumentLog.objects.filter(appointment=apt).first()
        self.assertIsNotNone(log)
        self.assertTrue(log.control_number.startswith('BRGY-'))
        self.assertTrue(bool(log.qr_code))
        self.assertEqual(log.issued_to, self.approved_resident)

        # Verify public authenticity verification endpoint
        verify_url = reverse('appointments:verify', kwargs={'control_number': log.control_number})
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, log.control_number)
        self.assertContains(response, 'Official Document Verified Authentic')

    def test_finance_and_asset_inventory(self):
        """Admin can access Finance & Assets overview and register equipment"""
        asset = AssetInventory.objects.create(
            item_name='Disaster Relief Generator',
            category=AssetInventory.CATEGORY_EQUIPMENT,
            quantity=2,
            condition=AssetInventory.CONDITION_GOOD,
            date_acquired=date(2025, 5, 20),
        )

        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('finance:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finance, Clearance Logs & Asset Inventory')
        self.assertContains(response, 'Disaster Relief Generator')

    def test_residents_tabbed_module(self):
        """Verify tri-tab interface: PENDING, APPROVED, REJECTED and re-evaluation"""
        self.client.login(username='admin_test', password='password123')

        # Test Pending tab
        response = self.client.get(reverse('accounts:residents_tabbed') + '?tab=pending')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UNAPPROVED RESIDENT REGISTRATIONS')
        self.assertContains(response, self.unapproved_resident.username)

        # Test Approved tab
        response = self.client.get(reverse('accounts:residents_tabbed') + '?tab=approved')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VERIFIED RESIDENTS DIRECTORY (RBI)')
        self.assertContains(response, self.approved_resident.username)

        # Reject a resident with reason
        reject_url = reverse('accounts:reject_resident', kwargs={'user_id': self.unapproved_resident.id})
        response = self.client.post(reject_url, {'rejection_reason': 'Invalid ID proof image provided'})
        self.unapproved_resident.refresh_from_db()
        self.assertEqual(self.unapproved_resident.rejection_reason, 'Invalid ID proof image provided')

        # Test Rejected tab
        response = self.client.get(reverse('accounts:residents_tabbed') + '?tab=rejected')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid ID proof image provided')

        # Re-evaluate rejected resident to approved
        reevaluate_url = reverse('accounts:reevaluate_resident', kwargs={'user_id': self.unapproved_resident.id})
        response = self.client.post(reevaluate_url, {'action': 'approve'})
        self.unapproved_resident.refresh_from_db()
        self.assertTrue(self.unapproved_resident.is_approved)
        self.assertEqual(self.unapproved_resident.rejection_reason, '')

    def test_feed_module_publishing_reactions_and_comments(self):
        """Verify Facebook-style feed with post creation, reactions, and comment threads"""
        self.client.login(username='admin_test', password='password123')

        # 1. Publish official post via feed
        feed_url = reverse('communications:feed')
        post_data = {
            'create_post': '1',
            'title': 'Emergency Dengue Fumigation Schedule',
            'category': 'emergency',
            'content': 'Fumigation will be conducted in **Purok 1 through 7** tomorrow morning.',
        }
        response = self.client.post(feed_url, post_data)
        self.assertRedirects(response, feed_url)

        post = Announcement.objects.filter(title='Emergency Dengue Fumigation Schedule').first()
        self.assertIsNotNone(post)
        self.assertEqual(post.category, 'emergency')

        # 2. Approved resident views feed and reacts [LIKE], [SUPPORT], [IMPORTANT]
        self.client.login(username='maria_test', password='password123')
        react_url = reverse('communications:react_post', kwargs={'post_id': post.id})

        # Toggle LIKE
        response = self.client.post(react_url, {'reaction_type': 'like'})
        self.assertEqual(post.likes_count, 1)

        # Switch to SUPPORT
        response = self.client.post(react_url, {'reaction_type': 'support'})
        self.assertEqual(post.likes_count, 0)
        self.assertEqual(post.supports_count, 1)

        # 3. Add comment to post
        comment_url = reverse('communications:comment_post', kwargs={'post_id': post.id})
        response = self.client.post(comment_url, {'content': 'Thank you for this notice, our family is prepared.'})
        self.assertEqual(post.comments.count(), 1)
        comment = post.comments.first()
        self.assertEqual(comment.author, self.approved_resident)
        self.assertEqual(comment.content, 'Thank you for this notice, our family is prepared.')

    def test_appointments_dual_tab_and_schedule(self):
        """Verify appointment tabs and document request stepper"""
        self.client.login(username='maria_test', password='password123')

        # Test documents tab
        response = self.client.get(reverse('appointments:list') + '?tab=documents')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DOCUMENT APPLICATION PROCESSING STEPPER')
        self.assertContains(response, 'Add New Document')

        # Test appointments tab
        response = self.client.get(reverse('appointments:list') + '?tab=appointments')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book Appointment')

    def test_messages_live_staff_status_roster(self):
        """Verify chat inbox displays active barangay officers with clear duty status badges"""
        self.kapitan_user.duty_status = 'on_duty'
        self.kapitan_user.status_message = 'Available at Mayor Office / Brgy Hall'
        self.kapitan_user.save()

        self.client.login(username='maria_test', password='password123')
        response = self.client.get(reverse('chat:inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ACTIVE BARANGAY OFFICERS & STAFF DUTY ROSTER')
        self.assertContains(response, '[ON-DUTY]')
        self.assertContains(response, '[MESSAGE STAFF]')

    def test_records_hub_tri_tab_interface(self):
        """Verify /records/ tri-tab architecture for Peace & Order, Finance, and RBI with Coming Soon design"""
        self.client.login(username='admin_test', password='password123')

        # Tab 1: Peace & Order
        response = self.client.get(reverse('records_hub') + '?tab=peace_order')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Coming Soon')

        # Tab 2: Finance & Assets
        response = self.client.get(reverse('records_hub') + '?tab=finance_assets')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Coming Soon')

        # Tab 3: RBI Directory
        response = self.client.get(reverse('records_hub') + '?tab=rbi')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Coming Soon')

    def test_profile_and_settings_functionality(self):
        """Verify profile updates, avatar removal fallback to initials, and guarded Django admin access"""
        self.client.login(username='maria_test', password='password123')

        # Profile view
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OFFICIAL AVATAR BADGE')
        self.assertContains(response, f'[{self.approved_resident.initials}]')

        # Update status message
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'Maria',
            'last_name': 'Santos-Dela Cruz',
            'email': 'maria.updated@test.com',
            'phone_number': '0912-888-9999',
            'status_message': 'Available for Purok meeting after 5 PM',
        })
        self.approved_resident.refresh_from_db()
        self.assertEqual(self.approved_resident.status_message, 'Available for Purok meeting after 5 PM')
        self.assertEqual(self.approved_resident.last_name, 'Santos-Dela Cruz')

        # Settings view - non-superuser should NOT see Django Admin card
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'DJANGO SYSTEM ADMINISTRATION')

        # Superuser visits settings - should see guarded Django Admin card
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DJANGO SYSTEM ADMINISTRATION')
        self.assertContains(response, '[ENTER DJANGO ADMIN]')

