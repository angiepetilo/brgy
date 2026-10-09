"""
Appointment canonical data layer (Stage 1).

* Migration 0014 (data) and 0015 (schema), forward and backward, on legacy-shaped rows.
* The removed legacy names no longer appear anywhere in apps/, templates/ or static/js.
* End-to-end booking through the public endpoint, fee snapshot, and the contact
  number coming from BarangayInfo instead of a literal in code.
"""
import datetime
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import BarangayInfo
from apps.accounts.selectors import get_contact_number
from apps.appointments.models import Appointment, DocumentType, HealthCareService
from tests.base import BaseTestCase, get_document_type, make_admin, make_health_service, make_resident_user

BEFORE_A = [('appointments', '0013_alter_documenttype_options_alter_requirement_options_and_more')]
AFTER_B = [('appointments', '0015_canonical_appointment_schema')]

REMOVED_PATTERNS = {
    'preferred_date': r'preferred_date',
    'preferred_time_slot': r'preferred_time_slot',
    'purpose_notes': r'purpose_notes',
    'document_type_fk': r'document_type_fk',
    'get_document_type_display': r'get_document_type_display',
    'get_preferred_time_slot_display': r'get_preferred_time_slot_display',
    'DOCUMENT_CHOICES': r'DOCUMENT_CHOICES',
    'DOC_* constants': r'\bDOC_(CLEARANCE|RESIDENCY|INDIGENCY|NOA)\b',
    'Appointment status aliases': r'\bSTATUS_(UNDER_REVIEW|APPROVED_SCHEDULED|READY_FOR_PICKUP)\b',
    'Appointment.STATUS_SUBMITTED': r'Appointment\.STATUS_SUBMITTED',
    'HealthService alias': r'\bHealthService\b',
    'legacy related names': r'health_service_appointments|appointments_fk',
    'hard-coded admin phone': r'0917-111-2222',
}


def next_weekday(days_ahead=3):
    day = timezone.localdate() + datetime.timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += datetime.timedelta(days=1)
    return day


class CanonicalMigrationTests(TransactionTestCase):
    """0014 (data) + 0015 (schema) applied forward and backward on legacy-shaped rows."""

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(BEFORE_A)
        self.old_apps = self.executor.loader.project_state(BEFORE_A).apps
        self._build_legacy_rows()

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

    def _build_legacy_rows(self):
        DocumentTypeOld = self.old_apps.get_model('appointments', 'DocumentType')
        HealthOld = self.old_apps.get_model('appointments', 'HealthCareService')
        AppointmentOld = self.old_apps.get_model('appointments', 'Appointment')

        DocumentTypeOld.objects.all().delete()
        # Matches by code; its fee must survive.
        self.dt_clearance = DocumentTypeOld.objects.create(name='Barangay Clearance', code='clearance', fee=Decimal('50.00'))
        # Matches by case-insensitive NAME only (no code yet); its fee must survive.
        self.dt_residency = DocumentTypeOld.objects.create(name='certificate of residency', code='', fee=Decimal('20.00'))
        self.health = HealthOld.objects.create(name='Legacy Consult')

        d1, d2, d3 = next_weekday(3), next_weekday(5), next_weekday(7)
        self.d1, self.d2, self.d3 = d1, d2, d3
        base = dict(category='document', status='pending', time_window='morning', preferred_time_slot='morning')

        def make(**kw):
            data = {**base, **kw}
            return AppointmentOld.objects.create(**data)

        # 1. Never synced: appt_date empty, only preferred_* / purpose_notes filled, dup notes.
        self.a1 = make(document_type='clearance', purpose='', purpose_notes='Need for job',
                       preferred_date=d1, appt_date=None, preferred_time_slot='afternoon',
                       admin_notes='Bring ID', rejection_reason='Bring ID')
        # 2. CharField-only name in UPPER case, rejected, canonical and legacy dates differ.
        self.a2 = make(document_type='CERTIFICATE OF RESIDENCY', status='rejected',
                       purpose='Canonical purpose', purpose_notes='Other notes',
                       preferred_date=d3, appt_date=d2, admin_notes='Note only', rejection_reason='')
        # 3. Rejected with both texts already different: both must be kept.
        self.a3 = make(document_type='clearance', status='rejected', purpose='p3', preferred_date=d1,
                       appt_date=d1, admin_notes='General remark', rejection_reason='Incomplete')
        # 4. Approved with a stray rejection_reason only (admin_notes empty): nothing may be lost.
        self.a4 = make(document_type='clearance', status='approved', purpose='p4', preferred_date=d1,
                       appt_date=d1, admin_notes='', rejection_reason='stray text')
        # 5. Custom document name that matches nothing in the catalog.
        self.a5 = make(document_type='Fire Safety Cert', purpose='p5', preferred_date=d1, appt_date=d1)
        # 6. Health request: legacy health_service only, spurious clearance CharField and FK.
        self.a6 = make(category='healthcare', document_type='clearance',
                       document_type_fk_id=self.dt_clearance.id, health_service_id=self.health.id,
                       healthcare_service_id=None, purpose='checkup', preferred_date=d2, appt_date=d2)
        # 7. FK already set and canonical: must not be re-mapped from the CharField.
        self.a7 = make(document_type='residency', document_type_fk_id=self.dt_clearance.id,
                       purpose='p7', preferred_date=d1, appt_date=d1, status='completed')

    def test_forward_backfills_canonical_values_without_data_loss(self):
        total_before = self.old_apps.get_model('appointments', 'Appointment').objects.count()
        new_apps = self._migrate(AFTER_B)
        Appointment_ = new_apps.get_model('appointments', 'Appointment')
        DocumentType_ = new_apps.get_model('appointments', 'DocumentType')

        self.assertEqual(Appointment_.objects.count(), total_before)
        field_names = {f.name for f in Appointment_._meta.get_fields()}
        for gone in ('preferred_date', 'preferred_time_slot', 'purpose_notes', 'health_service', 'document_type_fk'):
            self.assertNotIn(gone, field_names)

        a1 = Appointment_.objects.get(pk=self.a1.pk)
        self.assertEqual(a1.appt_date, self.d1)
        self.assertEqual(a1.time_window, 'afternoon')  # the deliberate (non-default) value wins
        self.assertEqual(a1.purpose, 'Need for job')
        self.assertEqual(a1.document_type.code, 'clearance')
        self.assertEqual(a1.admin_notes, 'Bring ID')
        self.assertEqual(a1.rejection_reason, '')  # not rejected: no mirrored reason

        a2 = Appointment_.objects.get(pk=self.a2.pk)
        self.assertEqual(a2.appt_date, self.d2)  # canonical wins over legacy
        self.assertEqual(a2.purpose, 'Canonical purpose')
        self.assertEqual(a2.document_type_id, self.dt_residency.id)  # case-insensitive name match
        self.assertEqual(a2.rejection_reason, 'Note only')  # fallback to admin_notes
        self.assertEqual(a2.admin_notes, 'Note only')

        a3 = Appointment_.objects.get(pk=self.a3.pk)
        self.assertEqual((a3.admin_notes, a3.rejection_reason), ('General remark', 'Incomplete'))

        a4 = Appointment_.objects.get(pk=self.a4.pk)
        self.assertEqual(a4.rejection_reason, '')
        self.assertEqual(a4.admin_notes, 'stray text')  # moved, not lost

        a5 = Appointment_.objects.get(pk=self.a5.pk)
        self.assertEqual(a5.document_type.name, 'Fire Safety Cert')
        self.assertFalse(a5.document_type.is_active)
        self.assertEqual(a5.document_type.fee, Decimal('0.00'))

        a6 = Appointment_.objects.get(pk=self.a6.pk)
        self.assertIsNone(a6.document_type_id)
        self.assertEqual(a6.healthcare_service_id, self.health.id)

        a7 = Appointment_.objects.get(pk=self.a7.pk)
        self.assertEqual(a7.document_type_id, self.dt_clearance.id)

        # Fees untouched, no duplicate catalog rows, missing standard types created.
        self.assertEqual(DocumentType_.objects.get(pk=self.dt_clearance.pk).fee, Decimal('50.00'))
        self.assertEqual(DocumentType_.objects.get(pk=self.dt_residency.pk).fee, Decimal('20.00'))
        self.assertEqual(DocumentType_.objects.filter(code__iexact='clearance').count(), 1)
        self.assertEqual(DocumentType_.objects.filter(name__iexact='Certificate of Residency').count(), 1)
        for code in ('indigency', 'noa'):
            created = DocumentType_.objects.get(code=code)
            self.assertEqual(created.fee, Decimal('0.00'))
            self.assertTrue(created.is_active)

    def test_backward_repopulates_legacy_columns(self):
        self._migrate(AFTER_B)
        back_apps = self._migrate(BEFORE_A)
        Appointment_ = back_apps.get_model('appointments', 'Appointment')

        a1 = Appointment_.objects.get(pk=self.a1.pk)
        self.assertEqual(a1.preferred_date, self.d1)
        self.assertEqual(a1.preferred_time_slot, 'afternoon')
        self.assertEqual(a1.purpose_notes, 'Need for job')
        self.assertEqual(a1.document_type, 'clearance')
        self.assertEqual(a1.document_type_fk_id, self.dt_clearance.id)

        a2 = Appointment_.objects.get(pk=self.a2.pk)
        self.assertEqual(a2.preferred_date, self.d2)
        self.assertEqual(a2.document_type, 'residency')  # code was filled in on the name-matched row

        a6 = Appointment_.objects.get(pk=self.a6.pk)
        self.assertEqual(a6.health_service_id, self.health.id)
        self.assertEqual(a6.document_type, '')

        self.assertEqual(Appointment_.objects.count(), 7)


class RemovedNamesGoneTests(SimpleTestCase):
    """No reference to a removed field, alias or hard-coded phone remains (migrations excluded)."""

    def test_removed_names_absent_from_source_and_templates(self):
        root = Path(settings.BASE_DIR)
        roots = [root / 'apps', root / 'templates', root / 'static' / 'js']
        offenders = []
        for base in roots:
            if not base.exists():
                continue
            for path in base.rglob('*'):
                if (not path.is_file() or path.suffix not in {'.py', '.html', '.js', '.txt'}
                        or 'migrations' in path.parts or '__pycache__' in path.parts
                        or path.name.endswith('.min.js')):
                    continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                for label, pattern in REMOVED_PATTERNS.items():
                    for match in re.finditer(pattern, text):
                        line_no = text.count('\n', 0, match.start()) + 1
                        offenders.append(f'{path.relative_to(root)}:{line_no} -> {label}')
        self.assertEqual(offenders, [], 'Removed names still referenced:\n' + '\n'.join(offenders))


class CanonicalBookingFlowTests(BaseTestCase):
    """End-to-end booking: public endpoint -> service -> canonical columns -> pages render."""

    def setUp(self):
        super().setUp()
        self.resident = make_resident_user(first_name='Ana', last_name='Reyes', email='ana@example.com')
        self.doc = get_document_type('clearance', 'Barangay Clearance', fee=Decimal('75.00'))
        DocumentType.objects.filter(pk=self.doc.pk).update(fee=Decimal('75.00'), is_active=True)
        self.doc.refresh_from_db()
        self.url = reverse('appointments:api_public_book')

    def _payload(self, when, **extra):
        data = {
            'first_name': 'Ana', 'last_name': 'Reyes', 'middle_name': '', 'age': '30',
            'address': 'Purok 1', 'email': 'ana@example.com', 'phone_number': '09171234567',
            'category': 'document', 'document_type': str(self.doc.id),
            'appt_date': when.isoformat(), 'time_window': 'afternoon',
            'purpose': 'Employment',
        }
        data.update(extra)
        return data

    def test_public_booking_creates_canonical_appointment(self):
        self.login(self.resident)
        when = next_weekday(3)
        resp = self.client.post(self.url, self._payload(when))
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body['status'], 'ok')

        appt = Appointment.objects.get(pk=body['appointment_id'])
        self.assertEqual(appt.document_type, self.doc)
        self.assertEqual(appt.appt_date, when)
        self.assertEqual(appt.time_window, 'afternoon')
        self.assertEqual(appt.purpose, 'Employment')
        self.assertEqual(appt.rejection_reason, '')
        self.assertEqual(body['service_title'], self.doc.name)
        self.assertEqual(body['time_slot'], appt.get_time_window_display())

    def test_unknown_or_inactive_document_type_is_rejected(self):
        self.login(self.resident)
        when = next_weekday(3)
        resp = self.client.post(self.url, self._payload(when, document_type='999999'))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('document_type', resp.json()['errors'])

        DocumentType.objects.filter(pk=self.doc.pk).update(is_active=False)
        resp = self.client.post(self.url, self._payload(when))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_fee_is_snapshotted_at_booking_and_price_change_only_affects_new_bookings(self):
        self.login(self.resident)
        first_day, second_day = next_weekday(3), next_weekday(6)
        resp = self.client.post(self.url, self._payload(first_day))
        first = Appointment.objects.get(pk=resp.json()['appointment_id'])
        self.assertEqual(first.fee_at_booking, Decimal('75.00'))

        DocumentType.objects.filter(pk=self.doc.pk).update(fee=Decimal('120.00'))
        resp = self.client.post(self.url, self._payload(second_day))
        second = Appointment.objects.get(pk=resp.json()['appointment_id'])

        first.refresh_from_db()
        self.assertEqual(first.fee_at_booking, Decimal('75.00'))
        self.assertEqual(second.fee_at_booking, Decimal('120.00'))

    def test_health_booking_has_no_document_type_and_zero_fee(self):
        self.login(self.resident)
        service = make_health_service(name='Dental Cleaning')
        when = next_weekday(4)
        resp = self.client.post(self.url, self._payload(
            when, category='healthcare', healthcare_service=str(service.id), document_type='',
        ))
        self.assertEqual(resp.status_code, 200, resp.content)
        appt = Appointment.objects.get(pk=resp.json()['appointment_id'])
        self.assertIsNone(appt.document_type)
        self.assertEqual(appt.healthcare_service, service)
        self.assertEqual(appt.fee_at_booking, 0)

    def test_api_services_lists_catalog_with_real_fee(self):
        self.login(self.resident)
        resp = self.client.get(reverse('appointments:api_services'))
        docs = {d['id']: d for d in resp.json()['documents']}
        self.assertEqual(docs[self.doc.id]['price'], 75.0)
        self.assertEqual(docs[self.doc.id]['name'], self.doc.name)

    def test_save_does_not_mirror_notes_and_still_generates_reference(self):
        appt = Appointment.objects.create(
            resident=self.resident, category='document', document_type=self.doc,
            purpose='No mirror', appt_date=next_weekday(3), admin_notes='Bring a photo',
        )
        appt.refresh_from_db()
        self.assertEqual(appt.rejection_reason, '')
        self.assertEqual(appt.admin_notes, 'Bring a photo')
        self.assertRegex(appt.reference_no, r'^APT-\d{4}-\d{4}$')

    def test_reject_service_writes_rejection_reason_only(self):
        from apps.appointments.services import reject_appointment_service
        appt = Appointment.objects.create(
            resident=self.resident, category='document', document_type=self.doc,
            purpose='Reject me', appt_date=next_weekday(3), admin_notes='Internal remark',
        )
        reject_appointment_service(appt, make_admin(), 'Blurry ID')
        appt.refresh_from_db()
        self.assertEqual(appt.rejection_reason, 'Blurry ID')
        self.assertEqual(appt.admin_notes, 'Internal remark')

    def test_pages_render_with_canonical_fields(self):
        appt = Appointment.objects.create(
            resident=self.resident, category='document', document_type=self.doc,
            purpose='Render check', appt_date=next_weekday(3), time_window='morning',
            status=Appointment.STATUS_REJECTED, rejection_reason='Blurry ID', admin_notes='See me',
        )
        admin = make_admin()
        self.login(admin)
        self.assertEqual(self.client.get(reverse('appointments:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('appointments:list') + f'?service=doc_{self.doc.id}').status_code, 200)
        detail = self.client.get(reverse('appointments:detail', kwargs={'pk': appt.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.doc.name)
        self.assertContains(detail, 'Blurry ID')
        self.assertContains(detail, 'See me')


class ContactNumberFromBarangayInfoTests(BaseTestCase):
    """The public contact number is data (BarangayInfo), never a literal in code."""

    def setUp(self):
        super().setUp()
        self.info = BarangayInfo.get_solo()

    def test_barangay_info_wins_and_appears_in_landing_and_booking_json(self):
        self.info.contact_no = '(02) 5555-0100'
        self.info.save()
        self.assertEqual(get_contact_number(), '(02) 5555-0100')

        landing = self.client.get(reverse('landing'))
        self.assertContains(landing, '(02) 5555-0100')
        self.assertNotContains(landing, '0917-111-2222')

        resident = make_resident_user(email='c@example.com')
        doc = get_document_type('clearance', 'Barangay Clearance')
        self.login(resident)
        resp = self.client.post(reverse('appointments:api_public_book'), {
            'first_name': 'A', 'last_name': 'B', 'age': '30', 'address': 'Purok 1',
            'email': 'c@example.com', 'phone_number': '09171234567', 'category': 'document',
            'document_type': str(doc.id), 'appt_date': next_weekday(3).isoformat(),
            'time_window': 'morning', 'purpose': 'x',
        })
        self.assertEqual(resp.json()['admin_phone'], '(02) 5555-0100')
        self.assertIn('(02) 5555-0100', resp.json()['message'])

    @override_settings(BARANGAY_CONTACT='09990001111')
    def test_falls_back_to_settings_when_barangay_info_is_blank(self):
        self.info.contact_no = ''
        self.info.save()
        self.assertEqual(get_contact_number(), '09990001111')

    @override_settings(BARANGAY_CONTACT='')
    def test_blank_everywhere_returns_empty_string(self):
        self.info.contact_no = ''
        self.info.save()
        self.assertEqual(get_contact_number(), '')
