"""
A8: API callers get JSON auth errors (401/403), never a login redirect, and the
statistics page explains filter scope and session expiry.
"""
from pathlib import Path

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from tests.base import BaseTestCase, make_resident_user, make_staff
from tests.statistics.data import TEMP_MEDIA

API_NAMES = ('api_summary', 'api_demographics', 'api_purok_density', 'api_appointments', 'api_revenue', 'api_blotter')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class StatisticsApiAuthTests(BaseTestCase):

    def test_anonymous_gets_401_json_not_redirect(self):
        for name in API_NAMES:
            url = reverse(f'statistics:{name}')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401, name)
            self.assertEqual(response['Content-Type'], 'application/json', name)
            body = response.json()
            self.assertTrue(body['requires_login'], name)
            self.assertEqual(body['login_url'], f'/accounts/login/?next={url}', name)
            self.assertIn('log in', body['error'].lower())

    def test_resident_gets_403_json(self):
        self.login(make_resident_user())
        for name in API_NAMES:
            response = self.client.get(reverse(f'statistics:{name}'))
            self.assertEqual(response.status_code, 403, name)
            self.assertEqual(response['Content-Type'], 'application/json', name)
            self.assertIn('error', response.json())

    def test_inactive_session_gets_401_json(self):
        user = make_staff({'statistics': ['view']})
        self.login(user)
        User.objects.filter(pk=user.pk).update(status=User.STATUS_DISABLED)
        response = self.client.get(reverse('statistics:api_summary'))
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()['requires_login'])

    def test_json_accept_header_on_html_route_gets_401_json(self):
        response = self.client.get(reverse('statistics:overview'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()['requires_login'])

    def test_html_routes_still_redirect_to_login(self):
        response = self.client.get(reverse('statistics:overview'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_html_route_forbidden_stays_html(self):
        self.login(make_resident_user())
        response = self.client.get(reverse('statistics:overview'))
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(response.get('Content-Type'), 'application/json')

    def test_overview_page_shows_filter_scope_note(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'))
        self.assertContains(
            response,
            'Date filters apply to appointments, revenue and blotter cases only. '
            'Resident and household figures are a current snapshot.',
        )

    def test_statistics_js_handles_session_expiry(self):
        source = (Path(settings.BASE_DIR) / 'static' / 'js' / 'statistics.js').read_text(encoding='utf-8')
        self.assertIn('Your session expired, please log in again.', source)
        self.assertIn('response.status === 401', source)
        self.assertIn('response.redirected', source)
        self.assertNotIn('.innerHTML', source)

    def test_session_expired_link_returns_to_current_page(self):
        # The server's login_url points at the API path; the link must use the page path.
        source = (Path(settings.BASE_DIR) / 'static' / 'js' / 'statistics.js').read_text(encoding='utf-8')
        self.assertIn("'/accounts/login/?next=' + encodeURIComponent(window.location.pathname", source)
        self.assertIn('link.href = defaultLoginUrl();', source)
        self.assertNotIn('body.login_url', source)


class JsonPermissionDeniedMiddlewareTests(BaseTestCase):

    def _process(self, path, **headers):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        from apps.core.middleware import JsonExceptionMiddleware

        request = RequestFactory().get(path, **headers)
        middleware = JsonExceptionMiddleware(lambda r: None)
        return middleware.process_exception(request, PermissionDenied('Out of scope.'))

    def test_permission_denied_in_api_view_becomes_403_json(self):
        import json
        response = self._process('/appointments/api/services/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(json.loads(response.content)['error'], 'Out of scope.')

    def test_permission_denied_with_json_accept_becomes_403_json(self):
        response = self._process('/appointments/1/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_on_html_request_is_left_to_django(self):
        self.assertIsNone(self._process('/appointments/1/'))
