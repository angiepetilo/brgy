"""B3: cache-based rate limits return 429 + Retry-After (JSON for API/AJAX callers)."""
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.chat.models import ChatThread
from apps.core.ratelimit import parse_rate
from tests.base import make_admin, make_resident_user

LOW = {
    'password_reset': '2/15m',
    'signup': '2/h',
    'public_booking': '2/h',
    'email_validation': '2/h',
    'chat_send': '2/m',
    'statistics_export': '2/h',
    'blotter_create': '2/h',
}


class ParseRateTests(TestCase):
    def test_formats(self):
        self.assertEqual(parse_rate('5/15m'), (5, 900))
        self.assertEqual(parse_rate('20/h'), (20, 3600))
        self.assertEqual(parse_rate('30/m'), (30, 60))
        self.assertEqual(parse_rate('1/d'), (1, 86400))
        for bad in ('', 'five/m', '5/x', '5'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_rate(bad)


@override_settings(RATE_LIMITS=LOW)
class RateLimitTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = Client(REMOTE_ADDR='192.0.2.50')

    def assert_429(self, response, json_body):
        self.assertEqual(response.status_code, 429)
        self.assertTrue(int(response['Retry-After']) > 0)
        if json_body:
            self.assertEqual(response['Content-Type'], 'application/json')
            self.assertIn('error', response.json())
        else:
            self.assertContains(response, 'Too Many Requests', status_code=429)

    def test_password_reset_per_ip(self):
        url = reverse('accounts:password_reset')
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'email': 'x@example.com'}).status_code, 302)
        self.assert_429(self.client.post(url, {'email': 'x@example.com'}), json_body=False)
        # GET (showing the form) is not limited.
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_signup_per_ip(self):
        url = reverse('accounts:signup')
        for _ in range(2):
            self.assertEqual(self.client.post(url, {}).status_code, 200)
        self.assert_429(self.client.post(url, {}), json_body=False)

    @mock.patch('apps.appointments.views.validate_email_address', return_value=(True, 'ok', {}))
    def test_public_booking_per_user_json(self, validator):
        self.client.force_login(make_resident_user())
        url = reverse('appointments:api_public_book')
        for _ in range(2):
            self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assert_429(self.client.post(url, {}), json_body=True)

    @mock.patch('apps.appointments.views.validate_email_address', return_value=(True, 'ok', {}))
    def test_email_validation_per_user_json(self, validator):
        self.client.force_login(make_resident_user())
        url = reverse('appointments:api_validate_email') + '?email=a@example.com'
        for _ in range(2):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assert_429(self.client.get(url), json_body=True)
        self.assertEqual(validator.call_count, 2)

    @mock.patch('apps.appointments.views.validate_email_address')
    def test_external_email_api_never_called_for_anonymous(self, validator):
        r1 = self.client.get(reverse('appointments:api_validate_email') + '?email=a@example.com')
        r2 = self.client.post(reverse('appointments:api_public_book'), {'email': 'a@example.com'})
        self.assertEqual((r1.status_code, r2.status_code), (401, 401))
        validator.assert_not_called()

    @mock.patch('apps.appointments.views.validate_email_address')
    def test_view_rejects_anonymous_before_email_api_even_without_middleware(self, validator):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from apps.appointments import views
        rf = RequestFactory()
        for view, request in (
            (views.api_validate_email_view, rf.get('/appointments/api/validate-email/?email=a@example.com')),
            (views.public_appointment_book_view, rf.post('/appointments/api/public-book/', {'email': 'a@example.com'})),
        ):
            request.user = AnonymousUser()
            request.META['REMOTE_ADDR'] = '192.0.2.77'
            self.assertEqual(view(request).status_code, 401)
        validator.assert_not_called()

    def test_chat_room_send_per_user(self):
        sender, other = make_resident_user(), make_admin()
        self.client.force_login(sender)
        url = reverse('chat:room', args=[other.id])
        for _ in range(2):
            self.assertNotEqual(self.client.post(url, {'message': 'hello'}).status_code, 429)
        self.assert_429(self.client.post(url, {'message': 'hello'}), json_body=False)
        # Reading the room is not limited.
        self.assertNotEqual(self.client.get(url).status_code, 429)

    def test_concern_reply_shares_chat_limit(self):
        resident = make_resident_user()
        thread = ChatThread.objects.create(
            thread_type=ChatThread.THREAD_CONCERN, initiator=resident, title='Streetlight',
            status=ChatThread.STATUS_SUBMITTED,
        )
        self.client.force_login(resident)
        url = reverse('chat:concern_detail', args=[thread.id])
        for _ in range(2):
            self.assertNotEqual(self.client.post(url, {'message': 'any update?'}).status_code, 429)
        self.assert_429(self.client.post(url, {'message': 'any update?'}), json_body=False)

    def test_statistics_exports_per_user(self):
        self.client.force_login(make_admin())
        for name in ('statistics:export_excel', 'statistics:export_pdf'):
            cache.clear()
            url = reverse(name)
            with self.subTest(name=name):
                for _ in range(2):
                    self.assertEqual(self.client.get(url).status_code, 200)
                self.assert_429(self.client.get(url), json_body=False)

    def test_ajax_caller_gets_json(self):
        url = reverse('accounts:signup')
        for _ in range(2):
            self.client.post(url, {})
        response = self.client.post(url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assert_429(response, json_body=True)

    def test_limits_are_per_ip(self):
        url = reverse('accounts:signup')
        for _ in range(3):
            self.client.post(url, {})
        other = Client(REMOTE_ADDR='192.0.2.51')
        self.assertEqual(other.post(url, {}).status_code, 200)

    def test_every_limit_has_a_default(self):
        from config import settings as project_settings
        self.assertEqual(set(project_settings._RATE_LIMIT_DEFAULTS), set(LOW))
        self.assertEqual(project_settings._RATE_LIMIT_DEFAULTS['password_reset'], '5/15m')
