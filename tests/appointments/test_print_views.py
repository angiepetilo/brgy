"""Tests for print_document and print_health_record views."""
from django.test import override_settings
from django.urls import reverse

from apps.appointments.models import Appointment, IssuedDocumentLog
from tests.base import (
    BaseTestCase, make_admin, make_appointment, make_health_service, make_resident_user,
)
from tests.statistics.data import TEMP_MEDIA


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PrintViewsNullStaffTests(BaseTestCase):

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

    def test_print_health_record_renders_fallback(self):
        resp = self.client.get(reverse('appointments:print_health', args=[self.health.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Attending Health Worker')

    def test_issued_document_with_null_users_renders(self):
        doc_apt = make_appointment(resident=None, status=Appointment.STATUS_COMPLETED,
                                   applicant_first_name='Walk', applicant_last_name='In')
        log = IssuedDocumentLog.objects.get(appointment=doc_apt)
        resp = self.client.get(reverse('appointments:print_document', args=[log.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Barangay Staff')
