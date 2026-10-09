"""A2: completed health records and issued documents with NULL staff FKs render safely."""
from django.test import override_settings
from django.urls import reverse

from apps.appointments.models import Appointment, IssuedDocumentLog
from tests.base import (
    BaseTestCase, make_admin, make_appointment, make_health_service, make_resident_user,
)
from tests.statistics.data import TEMP_MEDIA


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class NullStaffRecordsTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.login(make_admin())
        self.health = make_appointment(
            resident=make_resident_user(),
            category=Appointment.CATEGORY_HEALTHCARE,
            document_type=None,
            healthcare_service=make_health_service(),
            status=Appointment.STATUS_COMPLETED,
            processed_by=None,
        )

    def test_health_subtab_renders_fallback(self):
        resp = self.client.get(reverse('records:hub'), {'tab': 'document_health', 'subtab': 'health'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Health Officer')

    def test_print_health_record_renders_fallback(self):
        resp = self.client.get(reverse('records:print_health', args=[self.health.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Barangay Health Nurse')

    def test_issued_document_with_null_users_renders(self):
        doc_apt = make_appointment(resident=None, status=Appointment.STATUS_COMPLETED,
                                   applicant_first_name='Walk', applicant_last_name='In')
        # post_save signal creates the log with issued_to/issued_by NULL here.
        log = IssuedDocumentLog.objects.get(appointment=doc_apt)
        self.assertIsNone(log.issued_to)
        self.assertIsNone(log.issued_by)
        resp = self.client.get(reverse('records:hub'), {'tab': 'document_health', 'subtab': 'documents'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Barangay Staff')
        resp = self.client.get(reverse('records:print_document', args=[log.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Barangay Staff')
