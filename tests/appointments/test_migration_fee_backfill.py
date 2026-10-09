"""A4: appointments 0016 backfills fee_at_booking from DocumentType.fee (data only)."""
from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('appointments', '0015_canonical_appointment_schema')]
AFTER = [('appointments', '0016_backfill_fee_at_booking')]


class FeeBackfillMigrationTests(TransactionTestCase):

    def setUp(self):
        super().setUp()
        self.old_apps = self._migrate(BEFORE)
        Appointment = self.old_apps.get_model('appointments', 'Appointment')
        DocumentType = self.old_apps.get_model('appointments', 'DocumentType')
        HealthCareService = self.old_apps.get_model('appointments', 'HealthCareService')

        self.doc = DocumentType.objects.create(name='Backfill Clearance', code='bf_clearance', fee=Decimal('50.00'))
        svc = HealthCareService.objects.create(name='Backfill Checkup')
        common = dict(purpose='x', appt_date=date(2026, 1, 5), time_window='morning', status='pending')
        self.null_doc = Appointment.objects.create(
            reference_no='APT-BF-1', category='document', document_type=self.doc, fee_at_booking=None, **common)
        self.kept_doc = Appointment.objects.create(
            reference_no='APT-BF-2', category='document', document_type=self.doc,
            fee_at_booking=Decimal('20.00'), **common)
        self.health = Appointment.objects.create(
            reference_no='APT-BF-3', category='healthcare', healthcare_service=svc, fee_at_booking=None, **common)
        self.no_type = Appointment.objects.create(
            reference_no='APT-BF-4', category='document', document_type=None, fee_at_booking=None, **common)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def _fee(self, apps, apt):
        return apps.get_model('appointments', 'Appointment').objects.get(pk=apt.pk).fee_at_booking

    def test_forward_backfills_only_null_document_rows(self):
        apps = self._migrate(AFTER)
        self.assertEqual(self._fee(apps, self.null_doc), Decimal('50.00'))
        self.assertEqual(self._fee(apps, self.kept_doc), Decimal('20.00'))
        self.assertIsNone(self._fee(apps, self.health))
        self.assertIsNone(self._fee(apps, self.no_type))

    def test_reverse_runs_and_keeps_values(self):
        self._migrate(AFTER)
        apps = self._migrate(BEFORE)
        self.assertEqual(self._fee(apps, self.null_doc), Decimal('50.00'))
        self.assertEqual(self._fee(apps, self.kept_doc), Decimal('20.00'))
