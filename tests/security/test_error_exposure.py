"""B9: unexpected exceptions are logged and replaced by a generic message; user errors still show."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from django.urls import reverse

from apps.core.http import GENERIC_ERROR_MESSAGE, public_error_message
from tests.base import BaseTestCase, get_clearance_type, make_admin, make_appointment, make_resident_user


class PublicErrorMessageTests(TestCase):
    def test_only_user_facing_exceptions_pass_through(self):
        self.assertEqual(public_error_message(ValueError('Pick a weekday.')), 'Pick a weekday.')
        self.assertEqual(public_error_message(ValidationError('Bad file.')), 'Bad file.')
        self.assertEqual(public_error_message(PermissionDenied('Not yours.')), 'Not yours.')
        self.assertIsNone(public_error_message(RuntimeError('db secret')))
        self.assertIsNone(public_error_message(KeyError('password')))


class ViewErrorExposureTests(BaseTestCase):

    def _messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_edit_view_hides_internal_error(self):
        self.login(make_admin())
        apt = make_appointment(resident=make_resident_user())
        url = reverse('appointments:edit', args=[apt.pk])
        with mock.patch('apps.appointments.views.update_appointment_service',
                        side_effect=RuntimeError('db secret: password=hunter2')), \
                self.assertLogs('apps.appointments.views', level='ERROR') as logs:
            response = self.client.post(url, {'purpose': 'x'})
        shown = self._messages(response)
        self.assertIn(GENERIC_ERROR_MESSAGE, shown)
        self.assertFalse(any('db secret' in m for m in shown))
        self.assertIn('db secret', '\n'.join(logs.output))  # traceback kept for admins

    def test_edit_view_still_shows_value_error(self):
        self.login(make_admin())
        apt = make_appointment(resident=make_resident_user())
        with mock.patch('apps.appointments.views.update_appointment_service',
                        side_effect=ValueError('Status changes use the action buttons.')):
            response = self.client.post(reverse('appointments:edit', args=[apt.pk]), {'purpose': 'x'})
        self.assertIn('Status changes use the action buttons.', self._messages(response))

    def test_create_view_ajax_hides_internal_error(self):
        self.login(make_resident_user())
        when = date.today() + timedelta(days=1)
        while when.weekday() >= 5:
            when += timedelta(days=1)
        data = {'category': 'document', 'document_type': get_clearance_type().pk,
                'appt_date': when.isoformat(), 'time_window': 'morning', 'purpose': 'Work'}
        with mock.patch('apps.appointments.views.book_appointment_service',
                        side_effect=RuntimeError('SELECT * FROM secret')), \
                self.assertLogs('apps.appointments.views', level='ERROR'):
            response = self.client.post(reverse('appointments:create'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], GENERIC_ERROR_MESSAGE)
        self.assertNotIn('secret', response.content.decode())

    def test_create_view_shows_value_error(self):
        self.login(make_resident_user())
        when = date.today() + timedelta(days=1)
        while when.weekday() >= 5:
            when += timedelta(days=1)
        data = {'category': 'document', 'document_type': get_clearance_type().pk,
                'appt_date': when.isoformat(), 'time_window': 'morning', 'purpose': 'Work'}
        with mock.patch('apps.appointments.views.book_appointment_service',
                        side_effect=ValueError('You already have an active appointment request.')):
            response = self.client.post(reverse('appointments:create'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['message'], 'You already have an active appointment request.')

    def test_no_view_echoes_broad_exceptions(self):
        """Static guard: `except Exception` handlers in views never pass str(exc) to the user."""
        import re
        from pathlib import Path
        from django.conf import settings
        offenders = []
        for path in (Path(settings.BASE_DIR) / 'apps').rglob('*views*.py'):
            lines = path.read_text(encoding='utf-8').splitlines()
            for i, line in enumerate(lines):
                if re.search(r'except\s*\(?[^)]*\bException\b', line):
                    block = '\n'.join(lines[i + 1:i + 4])
                    if re.search(r'messages\.error\(request,\s*str\(|JsonResponse\(.*str\(', block):
                        offenders.append(f'{path.name}:{i + 1}')
        self.assertEqual(offenders, [])
