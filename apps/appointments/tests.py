from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.appointments.models import Appointment, HealthCareService


class ComprehensiveSystemRefinementTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_officer',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            first_name='Rodrigo',
            last_name='Admin'
        )

        # Resident user
        self.resident = User.objects.create_user(
            username='juan_resident',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            first_name='Juan',
            last_name='Dela Cruz',
            phone_number='0919-777-6666',
            purok='Purok 1'
        )

        # Unapproved resident user
        self.unapproved = User.objects.create_user(
            username='pedro_unapproved',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            first_name='Pedro',
            last_name='Penduko'
        )

        # Health Care Service
        self.service = HealthCareService.objects.create(
            name='Dental Cleaning',
            description='Free dental prophylaxis',
            is_active=True
        )

    def test_public_landing_page_renders_cleanly(self):
        """Root / and /landing/ should render public landing page with 200 status."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BARANGAY.PH')
        self.assertContains(response, 'Book Appointment')
        self.assertContains(response, 'Dental Cleaning')
        self.assertContains(response, '4-Step Appointment & Request Process')

    def test_api_services_endpoint(self):
        """API returning active healthcare services and documents for modal selector."""
        response = self.client.get(reverse('appointments:api_services'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(len(data['health_services']) >= 1)
        self.assertTrue(len(data['documents']) >= 4)

    def test_admin_healthcare_service_crud(self):
        """Admin can list, add, edit, and delete healthcare services; Resident is denied."""
        # Resident cannot access
        self.client.login(username='juan_resident', password='password123')
        response = self.client.get(reverse('appointments:service_list'))
        self.assertRedirects(response, reverse('accounts:dashboard'))

        # Admin can access list
        self.client.login(username='admin_officer', password='password123')
        response = self.client.get(reverse('appointments:service_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dental Cleaning')

        # Admin can create new service
        create_data = {
            'create_service': '1',
            'name': 'Tooth Extraction',
            'description': 'Simple and surgical extractions',
            'is_active': 'on'
        }
        response = self.client.post(reverse('appointments:service_list'), create_data)
        self.assertRedirects(response, reverse('appointments:service_list'))
        self.assertTrue(HealthCareService.objects.filter(name='Tooth Extraction').exists())

        # Admin can edit service
        svc = HealthCareService.objects.get(name='Tooth Extraction')
        edit_data = {
            'name': 'Tooth Extraction & Oral Surgery',
            'description': 'Updated description',
            'is_active': 'on'
        }
        response = self.client.post(reverse('appointments:service_update', kwargs={'pk': svc.id}), edit_data)
        self.assertRedirects(response, reverse('appointments:service_list'))
        svc.refresh_from_db()
        self.assertEqual(svc.name, 'Tooth Extraction & Oral Surgery')

        # Admin can delete service
        response = self.client.post(reverse('appointments:service_delete', kwargs={'pk': svc.id}))
        self.assertRedirects(response, reverse('appointments:service_list'))
        self.assertFalse(HealthCareService.objects.filter(name='Tooth Extraction & Oral Surgery').exists())

    def test_appointment_booking_healthcare_category(self):
        """Resident can book appointment with category healthcare."""
        self.client.login(username='juan_resident', password='password123')
        post_data = {
            'category': Appointment.CATEGORY_HEALTHCARE,
            'healthcare_service': self.service.id,
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'purpose': 'Routine dental cleaning and tartar removal',
            'preferred_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'preferred_time_slot': Appointment.TIME_SLOT_MORNING,
        }
        response = self.client.post(reverse('appointments:create'), post_data)
        apt = Appointment.objects.filter(resident=self.resident, category=Appointment.CATEGORY_HEALTHCARE).first()
        self.assertIsNotNone(apt)
        self.assertEqual(apt.healthcare_service, self.service)
        self.assertEqual(apt.get_service_title(), 'Dental Cleaning')

    def test_residents_management_view_and_filter(self):
        """Admin residents table contains 5-column structure and filter dropdown."""
        self.client.login(username='admin_officer', password='password123')
        
        # Test pending tab
        response = self.client.get(reverse('accounts:residents_tabbed') + '?tab=pending')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'APPLICANT NAME')
        self.assertNotContains(response, 'CONTACT NO.')
        self.assertContains(response, 'PUROK')
        self.assertContains(response, 'REGISTERED ON')
        self.assertContains(response, 'ACTION')
        self.assertNotContains(response, '[APPROVE]')
        self.assertNotContains(response, '[REJECT]')
        self.assertContains(response, 'Pedro Penduko')

        # Test approved tab
        response = self.client.get(reverse('accounts:residents_tabbed') + '?tab=approved')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Juan Dela Cruz')

    def test_appointment_schedule_calendar_json(self):
        """Appointment schedule view passes serialized JSON events for FullCalendar."""
        self.client.login(username='admin_officer', password='password123')
        response = self.client.get(reverse('appointments:list') + '?tab=schedule')
        self.assertEqual(response.status_code, 200)
        self.assertIn('calendar_events_json', response.context)
        self.assertContains(response, 'fullcalendar-view')

    def test_landing_page_updates(self):
        """Verify hero button removal, QR verification removal, and modal trigger."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        # Register Resident Account in hero is removed
        self.assertNotContains(response, 'Register Resident Account')
        # QR Verification in hero card is removed
        self.assertNotContains(response, 'QR Verification')
        # Book Appointment opens modern popup modal
        self.assertContains(response, 'openBookAppointmentModal')
        self.assertContains(response, 'bookAppointmentModal')

    def test_email_validation_api(self):
        """Validate email endpoint detects disposable and invalid email formats."""
        # Disposable email
        res_disp = self.client.get(reverse('appointments:api_validate_email') + '?email=user@mailinator.com')
        self.assertEqual(res_disp.status_code, 200)
        self.assertFalse(res_disp.json()['valid'])

        # Valid format
        res_valid = self.client.get(reverse('appointments:api_validate_email') + '?email=maria.santos@gmail.com')
        self.assertEqual(res_valid.status_code, 200)
        self.assertTrue(res_valid.json()['valid'])

    def test_public_booking_api_success_and_validation(self):
        """Test public appointment booking with required fields, 11-digit phone, and success response."""
        tomorrow = (timezone.now() + timedelta(days=2)).date().isoformat()
        
        # Missing required middle name or invalid phone
        bad_data = {
            'first_name': 'Carlos',
            'last_name': 'Santos',
            'middle_name': '',  # missing
            'age': '32',
            'address': '12 Mabini St, Purok 3',
            'email': 'carlos.santos@gmail.com',
            'phone_number': '0912345',  # only 7 digits
            'category': 'document',
            'document_type': 'clearance',
            'preferred_date': tomorrow,
            'preferred_time_slot': 'morning',
            'purpose': 'Job Application Requirement',
        }
        res_bad = self.client.post(reverse('appointments:api_public_book'), bad_data)
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn('middle_name', res_bad.json()['errors'])
        self.assertIn('phone_number', res_bad.json()['errors'])

        # Complete valid submission with 11-digit phone
        good_data = {
            'first_name': 'Carlos',
            'middle_name': 'Bautista',
            'last_name': 'Santos',
            'age': '32',
            'address': '12 Mabini St, Purok 3',
            'email': 'carlos.santos@gmail.com',
            'phone_number': '09171234567',  # strictly 11 digits
            'category': 'document',
            'document_type': 'clearance',
            'preferred_date': tomorrow,
            'preferred_time_slot': 'morning',
            'purpose': 'Job Application Requirement',
        }
        res_good = self.client.post(reverse('appointments:api_public_book'), good_data)
        self.assertEqual(res_good.status_code, 200)
        json_data = res_good.json()
        self.assertEqual(json_data['status'], 'ok')
        self.assertIn('Wait for the email sent for approved your appointment date', json_data['message'])
        self.assertIn('carlos.santos@gmail.com', json_data['applicant_email'])
        self.assertEqual(json_data['applicant_phone'], '09171234567')

        # Check record in DB
        apt = Appointment.objects.get(id=json_data['appointment_id'])
        self.assertEqual(apt.applicant_first_name, 'Carlos')
        self.assertEqual(apt.applicant_middle_name, 'Bautista')
        self.assertEqual(apt.applicant_last_name, 'Santos')
        self.assertEqual(apt.applicant_age, 32)
        self.assertEqual(apt.applicant_phone, '09171234567')

    def test_appointment_module_3_tabs_and_filters(self):
        """Test Appointment module 3 tabs: appointments, documents, health_services, and date filters."""
        self.client.login(username='admin_officer', password='password123')
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)

        # Create sample appointments
        Appointment.objects.create(
            resident=self.resident,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type='clearance',
            preferred_date=today,
            preferred_time_slot='morning',
            purpose='Employment'
        )
        Appointment.objects.create(
            resident=self.resident,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.service,
            preferred_date=tomorrow,
            preferred_time_slot='afternoon',
            purpose='Dental checkup'
        )

        # Test tab=appointments with date_filter=today
        res_today = self.client.get(reverse('appointments:list') + '?tab=appointments&date_filter=today')
        self.assertEqual(res_today.status_code, 200)
        self.assertContains(res_today, 'Employment')
        self.assertNotContains(res_today, 'Dental checkup')

        # Test tab=appointments with date_filter=tomorrow
        res_tomorrow = self.client.get(reverse('appointments:list') + '?tab=appointments&date_filter=tomorrow')
        self.assertEqual(res_tomorrow.status_code, 200)
        self.assertContains(res_tomorrow, 'Dental checkup')
        self.assertNotContains(res_tomorrow, 'Employment')

        # Test tab=documents
        res_docs = self.client.get(reverse('appointments:list') + '?tab=documents')
        self.assertEqual(res_docs.status_code, 200)
        self.assertContains(res_docs, 'Barangay Clearance')

        # Test tab=health_services
        res_health = self.client.get(reverse('appointments:list') + '?tab=health_services')
        self.assertEqual(res_health.status_code, 200)
        self.assertContains(res_health, 'Dental Cleaning')
