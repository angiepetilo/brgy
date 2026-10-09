"""apps.blotter.services: numbering, transitions, timestamps, validation, scope and audit."""
from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.accounts.models import StaffAssignment
from apps.blotter import services
from apps.blotter.models import BlotterCase, BlotterParty
from apps.history.models import ActivityLog
from tests.base import BaseTestCase, make_admin, make_blotter_case, make_purok, make_staff
from tests.blotter.common import case_data, two_parties

ALL = ['view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential']


class CaseNumberTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.year = timezone.localdate().year

    def create(self, **data):
        return services.create_case(self.admin, case_data(**data), two_parties())

    def test_sequential_numbers(self):
        self.assertEqual(self.create().case_no, f'BLT-{self.year}-0001')
        self.assertEqual(self.create().case_no, f'BLT-{self.year}-0002')

    def test_numbering_resets_per_year(self):
        make_blotter_case(case_no='BLT-2025-0007')
        with mock.patch('apps.blotter.services._today', return_value=date(2025, 6, 1)):
            self.assertEqual(self.create(incident_date=date(2025, 5, 30)).case_no, 'BLT-2025-0008')
        self.assertEqual(self.create().case_no, f'BLT-{self.year}-0001')

    def test_numbers_past_9999_sort_numerically(self):
        make_blotter_case(case_no=f'BLT-{self.year}-9999')
        make_blotter_case(case_no=f'BLT-{self.year}-10000')
        self.assertEqual(self.create().case_no, f'BLT-{self.year}-10001')

    def test_collision_is_retried_with_the_next_number(self):
        # Simulate a concurrent insert: the read says 0 is the last number, but 0001 exists.
        make_blotter_case(case_no=f'BLT-{self.year}-0001')
        with mock.patch('apps.blotter.services._last_number', return_value=0):
            case = self.create()
        self.assertEqual(case.case_no, f'BLT-{self.year}-0002')
        self.assertEqual(BlotterCase.objects.filter(case_no__startswith=f'BLT-{self.year}-').count(), 2)
        self.assertEqual(case.parties.count(), 2)

    def test_gives_up_after_max_attempts(self):
        for n in range(1, services.MAX_CASE_NO_ATTEMPTS + 1):
            make_blotter_case(case_no=f'BLT-{self.year}-{n:04d}')
        with mock.patch('apps.blotter.services._last_number', return_value=0):
            with self.assertRaises(ValueError):
                self.create()
        self.assertEqual(BlotterCase.objects.count(), services.MAX_CASE_NO_ATTEMPTS)

    def test_case_numbers_are_unique(self):
        numbers = [self.create().case_no for _ in range(5)]
        self.assertEqual(len(set(numbers)), 5)


class CreateValidationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()

    def test_requires_complainant_and_respondent(self):
        with self.assertRaises(ValidationError) as ctx:
            services.create_case(self.admin, case_data(), [{'role': 'complainant', 'full_name': 'A'}])
        self.assertIn('Add at least one respondent.', ctx.exception.message_dict['parties'])
        with self.assertRaises(ValidationError) as ctx:
            services.create_case(self.admin, case_data(), [{'role': 'witness', 'full_name': 'W'}])
        self.assertEqual(len(ctx.exception.message_dict['parties']), 2)
        self.assertFalse(BlotterCase.objects.exists())

    def test_party_phone_must_be_ph_mobile(self):
        for bad in ('0917-123-4567', '+639171234567', '9171234567', '0917123456a', '091712345678'):
            with self.assertRaises(ValidationError) as ctx:
                services.create_case(self.admin, case_data(), two_parties(contact_no=bad))
            self.assertIn('contact_no', ctx.exception.message_dict, bad)
        self.assertFalse(BlotterCase.objects.exists())

    def test_valid_and_blank_phone_saved(self):
        case = services.create_case(self.admin, case_data(), two_parties(contact_no='09171234567'))
        numbers = sorted(case.parties.values_list('contact_no', flat=True))
        self.assertEqual(numbers, ['', '09171234567'])

    def test_future_incident_date_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            services.create_case(self.admin, case_data(incident_date=timezone.localdate() + timedelta(days=2)),
                                 two_parties())
        self.assertIn('incident_date', ctx.exception.message_dict)

    def test_bad_incident_type_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_case(self.admin, case_data(incident_type='murder'), two_parties())

    def test_create_sets_recorder_status_and_audit(self):
        case = services.create_case(self.admin, case_data(), two_parties())
        self.assertEqual(case.status, BlotterCase.STATUS_FILED)
        self.assertEqual(case.recorded_by, self.admin)
        self.assertIsNotNone(case.filed_at)
        log = ActivityLog.objects.get(action_type='Blotter Case', target_id=str(case.pk))
        self.assertEqual(log.action, ActivityLog.ACTION_CREATE)
        self.assertEqual(log.target_name, case.case_no)
        self.assertEqual(log.actor, self.admin)
        self.assertNotIn('fence', log.details)        # no narrative in the audit log
        self.assertNotIn('Maria', log.details)        # no party names either

    def test_create_requires_permission(self):
        with self.assertRaises(PermissionDenied):
            services.create_case(make_staff({'blotter': ['view']}), case_data(), two_parties())

    def test_purok_scoped_staff_can_only_file_for_their_purok(self):
        own, other = make_purok('Scope Own'), make_purok('Scope Other')
        tanod = make_staff({'blotter': ['view', 'create']}, scope_type=StaffAssignment.SCOPE_PUROK,
                           scope_value='Scope Own', position='Tanod')
        services.create_case(tanod, case_data(purok=own), two_parties())
        with self.assertRaises(PermissionDenied):
            services.create_case(tanod, case_data(purok=other), two_parties())
        with self.assertRaises(PermissionDenied):
            services.create_case(tanod, case_data(purok=None), two_parties())

    def test_confidential_needs_view_confidential(self):
        clerk = make_staff({'blotter': ['view', 'create']})
        with self.assertRaises(PermissionDenied):
            services.create_case(clerk, case_data(is_confidential=True), two_parties())
        case = services.create_case(self.admin, case_data(is_confidential=True), two_parties())
        self.assertTrue(case.is_confidential)


class TransitionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()

    def test_every_legal_and_illegal_transition(self):
        statuses = [code for code, _ in BlotterCase.STATUS_CHOICES]
        for start in statuses:
            for target in statuses:
                case = make_blotter_case(status=start)
                legal = target in BlotterCase.TRANSITIONS[start]
                with self.subTest(start=start, target=target):
                    if legal:
                        updated = services.transition_case(self.admin, case, target)
                        self.assertEqual(updated.status, target)
                    else:
                        with self.assertRaises(ValueError):
                            services.transition_case(self.admin, case, target)
                        case.refresh_from_db()
                        self.assertEqual(case.status, start)

    def test_unknown_status(self):
        with self.assertRaises(ValueError):
            services.transition_case(self.admin, make_blotter_case(), 'archived')

    def test_terminal_statuses_are_final(self):
        for terminal in BlotterCase.TERMINAL:
            case = make_blotter_case(status=terminal)
            for target in ('filed', 'under_mediation', 'settled'):
                with self.assertRaises(ValueError):
                    services.transition_case(self.admin, case, target)

    def test_mediation_sets_handler_and_no_closure(self):
        case = services.transition_case(self.admin, make_blotter_case(), 'under_mediation')
        self.assertEqual(case.handled_by, self.admin)
        self.assertIsNone(case.closed_at)
        self.assertIsNone(case.settled_at)

    def test_settled_timestamps_and_notes(self):
        case = make_blotter_case(status='under_mediation')
        case = services.transition_case(self.admin, case, 'settled', notes='Amicable settlement signed.')
        self.assertIsNotNone(case.settled_at)
        self.assertEqual(case.closed_at, case.settled_at)
        self.assertIsNone(case.escalated_at)
        self.assertEqual(case.resolution_notes, 'Amicable settlement signed.')

    def test_escalated_timestamps(self):
        case = services.transition_case(self.admin, make_blotter_case(status='under_mediation'), 'escalated')
        self.assertIsNotNone(case.escalated_at)
        self.assertEqual(case.closed_at, case.escalated_at)
        self.assertIsNone(case.settled_at)

    def test_dismissed_and_withdrawn_only_close(self):
        for target in ('dismissed', 'withdrawn'):
            case = services.transition_case(self.admin, make_blotter_case(), target)
            self.assertIsNotNone(case.closed_at)
            self.assertIsNone(case.settled_at)
            self.assertIsNone(case.escalated_at)

    def test_transition_audit_row(self):
        case = make_blotter_case()
        services.transition_case(self.admin, case, 'under_mediation', notes='First summons served.')
        log = ActivityLog.objects.filter(target_id=str(case.pk), action=ActivityLog.ACTION_UPDATE).get()
        self.assertEqual(log.action_type, 'Blotter Case')
        self.assertTrue(log.details.startswith('Status: Filed -> Under mediation'))
        self.assertIn('First summons served.', log.details)

    def test_confidential_notes_stay_out_of_the_audit_log(self):
        case = make_blotter_case(is_confidential=True)
        services.transition_case(self.admin, case, 'dismissed', notes='Sensitive family matter.')
        log = ActivityLog.objects.get(target_id=str(case.pk))
        self.assertNotIn('Sensitive', log.details)
        case.refresh_from_db()
        self.assertEqual(case.resolution_notes, 'Sensitive family matter.')

    def test_permission_per_target_status(self):
        secretary = make_staff({'blotter': ['view', 'create', 'edit']})
        with self.assertRaises(PermissionDenied):
            services.transition_case(secretary, make_blotter_case(), 'under_mediation')
        self.assertEqual(services.transition_case(secretary, make_blotter_case(), 'dismissed').status, 'dismissed')
        mediator = make_staff({'blotter': ['view', 'mediate']})
        with self.assertRaises(PermissionDenied):
            services.transition_case(mediator, make_blotter_case(status='under_mediation'), 'settled')

    def test_out_of_scope_case_denied(self):
        make_purok('Far Purok')
        near = make_purok('Near Purok')
        kagawad = make_staff({'blotter': ALL}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Near Purok')
        far_case = make_blotter_case(purok=make_purok('Far Purok'))
        with self.assertRaises(PermissionDenied):
            services.transition_case(kagawad, far_case, 'under_mediation')
        self.assertEqual(services.transition_case(kagawad, make_blotter_case(purok=near), 'dismissed').status,
                         'dismissed')


class HearingUpdateDeleteTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()

    def test_add_hearing(self):
        case = make_blotter_case(status='under_mediation')
        when = timezone.now() + timedelta(days=3)
        hearing = services.add_hearing(self.admin, case, {
            'scheduled_at': when, 'outcome_notes': 'Both appeared.', 'complainant_attended': True,
            'respondent_attended': False,
        })
        self.assertEqual(hearing.recorded_by, self.admin)
        self.assertEqual(case.hearings.count(), 1)
        log = ActivityLog.objects.get(target_id=str(case.pk))
        self.assertTrue(log.details.startswith('Hearing:'))

    def test_no_hearing_on_closed_case(self):
        with self.assertRaises(ValueError):
            services.add_hearing(self.admin, make_blotter_case(status='settled'), {'scheduled_at': timezone.now()})

    def test_hearing_requires_mediate(self):
        with self.assertRaises(PermissionDenied):
            services.add_hearing(make_staff({'blotter': ['view', 'edit']}), make_blotter_case(),
                                 {'scheduled_at': timezone.now()})

    def test_hearing_requires_date(self):
        with self.assertRaises(ValidationError):
            services.add_hearing(self.admin, make_blotter_case(), {'outcome_notes': 'x'})

    def test_update_case(self):
        case = make_blotter_case()
        updated = services.update_case(self.admin, case, {'location': 'New place', 'incident_type': 'noise'})
        self.assertEqual((updated.location, updated.incident_type), ('New place', 'noise'))
        log = ActivityLog.objects.get(target_id=str(case.pk))
        self.assertIn('incident_type, location', log.details)

    def test_closed_case_cannot_be_edited(self):
        with self.assertRaises(ValueError):
            services.update_case(self.admin, make_blotter_case(status='withdrawn'), {'location': 'x'})

    def test_delete_needs_permission_and_is_audited(self):
        case = make_blotter_case()
        with self.assertRaises(PermissionDenied):
            services.delete_case(make_staff({'blotter': ['view', 'edit']}), case)
        services.delete_case(self.admin, case)
        self.assertFalse(BlotterCase.objects.filter(pk=case.pk).exists())
        self.assertFalse(BlotterParty.objects.filter(case_id=case.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(action=ActivityLog.ACTION_DELETE, target_name=case.case_no).exists())
