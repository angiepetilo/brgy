"""
A1: canonical appointment statuses in the UI.

The stepper and action buttons come from apps.appointments.selectors, so each of
the five statuses shows the right steps and exactly the actions the services
accept (pending: approve/reject; approved: complete/no_show; others: none).
"""
import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import reverse

from apps.appointments import selectors
from apps.appointments.models import Appointment
from tests.base import BaseTestCase, make_admin, make_appointment, make_resident_user, make_staff
from tests.statistics.data import TEMP_MEDIA

ALL_ACTIONS = {
    'approve': 'appointments:approve',
    'reject': 'appointments:reject',
    'complete': 'appointments:complete',
    'no_show': 'appointments:noshow',
}

EXPECTED_STEPS = {
    Appointment.STATUS_PENDING: [('pending', 'current'), ('approved', 'upcoming'), ('completed', 'upcoming')],
    Appointment.STATUS_APPROVED: [('pending', 'done'), ('approved', 'current'), ('completed', 'upcoming')],
    Appointment.STATUS_COMPLETED: [('pending', 'done'), ('approved', 'done'), ('completed', 'done')],
    Appointment.STATUS_NO_SHOW: [('pending', 'done'), ('approved', 'done'), ('no_show', 'current')],
    Appointment.STATUS_REJECTED: [],
}

EXPECTED_ACTIONS = {
    Appointment.STATUS_PENDING: {'approve', 'reject'},
    Appointment.STATUS_APPROVED: {'complete', 'no_show'},
    Appointment.STATUS_COMPLETED: set(),
    Appointment.STATUS_REJECTED: set(),
    Appointment.STATUS_NO_SHOW: set(),
}

LEGACY_IDS = ('submitted', 'under_review', 'approved_scheduled', 'ready_for_pickup', 'for_pickup', 'released', 'cancelled')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class StatusStepsAndActionsTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.resident = make_resident_user()

    def _apt(self, status):
        return make_appointment(resident=self.resident, status=status, days_ahead=0)

    def test_status_steps_are_exact_for_every_status(self):
        for status, expected in EXPECTED_STEPS.items():
            steps = selectors.status_steps(self._apt(status))
            self.assertEqual([(s['code'], s['state']) for s in steps], expected, status)

    def test_allowed_actions_for_admin(self):
        for status, expected in EXPECTED_ACTIONS.items():
            self.assertEqual(selectors.allowed_actions(self._apt(status), self.admin), expected, status)

    def test_allowed_actions_respect_permissions(self):
        staff = make_staff({'appointments': ['view', 'approve']})
        self.assertEqual(selectors.allowed_actions(self._apt('pending'), staff), {'approve'})
        self.assertEqual(selectors.allowed_actions(self._apt('approved'), staff), set())
        self.assertEqual(selectors.allowed_actions(self._apt('pending'), self.resident), set())

    def _action_urls(self, html):
        return set(re.findall(r'action="(/appointments/\d+/(?:approve|reject|complete|noshow)/)"', html))

    def test_detail_page_shows_exactly_the_expected_buttons(self):
        self.login(self.admin)
        for status, expected in EXPECTED_ACTIONS.items():
            apt = self._apt(status)
            response = self.client.get(reverse('appointments:detail', args=[apt.pk]))
            self.assertEqual(response.status_code, 200, status)
            html = response.content.decode()
            expected_urls = {reverse(ALL_ACTIONS[a], args=[apt.pk]) for a in expected}
            self.assertEqual(self._action_urls(html), expected_urls, status)
            for action in ALL_ACTIONS:
                marker = f'data-action-button="{action}"'
                if action in expected:
                    self.assertIn(marker, html, f'{status}: {action}')
                else:
                    self.assertNotIn(marker, html, f'{status}: {action}')
            for code, state in EXPECTED_STEPS[status]:
                self.assertIn(f'data-step="{code}" data-step-state="{state}"', html, status)

    def test_approved_offers_complete_and_no_show_only(self):
        self.login(self.admin)
        apt = self._apt('approved')
        html = self.client.get(reverse('appointments:detail', args=[apt.pk])).content.decode()
        self.assertIn('MARK COMPLETED', html)
        self.assertIn('NO-SHOW', html)
        self.assertNotIn('APPROVE &amp; DISPATCH EMAIL', html)
        self.assertNotIn('REJECT...', html)

    def test_rejected_shows_alert_and_no_stepper(self):
        self.login(self.admin)
        apt = self._apt('rejected')
        html = self.client.get(reverse('appointments:detail', args=[apt.pk])).content.decode()
        self.assertIn('REQUEST REJECTED', html)
        self.assertNotIn('data-step=', html)

    def test_resident_sees_no_action_buttons(self):
        self.login(self.resident)
        for status in EXPECTED_ACTIONS:
            apt = self._apt(status)
            html = self.client.get(reverse('appointments:detail', args=[apt.pk])).content.decode()
            self.assertEqual(self._action_urls(html), set(), status)
            self.assertNotIn('data-action-button=', html, status)

    def test_detail_page_has_no_inline_handlers_and_loads_js(self):
        self.login(self.admin)
        apt = self._apt('pending')
        html = self.client.get(reverse('appointments:detail', args=[apt.pk])).content.decode()
        self.assertIn('js/appointment_detail.js', html)
        self.assertIn('data-action="toggle-reject"', html)
        self.assertNotIn("onclick=\"return confirm", html)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ActionRoutesTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.login(make_admin())
        self.resident = make_resident_user()

    def _post(self, route, apt, **data):
        return self.client.post(reverse(route, args=[apt.pk]), data)

    def test_approve_route(self):
        apt = make_appointment(resident=self.resident, status='pending')
        self._post('appointments:approve', apt)
        apt.refresh_from_db()
        self.assertEqual(apt.status, Appointment.STATUS_APPROVED)

    def test_reject_route(self):
        apt = make_appointment(resident=self.resident, status='pending')
        self._post('appointments:reject', apt, rejection_reason='Incomplete requirements')
        apt.refresh_from_db()
        self.assertEqual(apt.status, Appointment.STATUS_REJECTED)
        self.assertEqual(apt.rejection_reason, 'Incomplete requirements')

    def test_complete_route(self):
        apt = make_appointment(resident=self.resident, status='approved', days_ahead=0)
        self._post('appointments:complete', apt)
        apt.refresh_from_db()
        self.assertEqual(apt.status, Appointment.STATUS_COMPLETED)

    def test_noshow_route(self):
        apt = make_appointment(resident=self.resident, status='approved', days_ahead=0)
        self._post('appointments:noshow', apt)
        apt.refresh_from_db()
        self.assertEqual(apt.status, Appointment.STATUS_NO_SHOW)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class TablePillsTests(BaseTestCase):

    def test_table_renders_a_pill_per_status(self):
        resident = make_resident_user()
        apts = [make_appointment(resident=resident, status=s) for s in EXPECTED_ACTIONS]
        html = render_to_string('appointments/table.html', {'appointments': apts})
        for status in EXPECTED_ACTIONS:
            self.assertIn(f'data-status-pill="{status}"', html, status)


class LegacyStatusScanTests(BaseTestCase):
    """No legacy status id may come back as a quoted literal in templates or JS."""

    def test_no_legacy_status_literals(self):
        base = Path(settings.BASE_DIR)
        roots = [base / 'templates' / 'appointments', base / 'templates' / 'records', base / 'static' / 'js',
                 base / 'apps' / 'appointments']
        pattern = re.compile(r"""['"](%s)['"]""" % '|'.join(LEGACY_IDS))
        hits = []
        for root in roots:
            for path in root.rglob('*'):
                if path.suffix not in ('.html', '.js', '.py') or 'migrations' in path.parts or 'vendor' in path.parts:
                    continue
                for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    if pattern.search(line):
                        hits.append(f'{path.relative_to(base)}:{lineno}: {line.strip()}')
        self.assertEqual(hits, [])

    def test_list_edit_modal_has_no_status_select(self):
        source = (Path(settings.BASE_DIR) / 'templates' / 'appointments' / 'appointment_list.html').read_text(encoding='utf-8')
        self.assertNotIn('id="edit-apt-status"', source)
        for legacy in ('status-submitted', 'status-under_review', 'status-approved_scheduled', 'status-ready_for_pickup'):
            self.assertNotIn(legacy, source)
