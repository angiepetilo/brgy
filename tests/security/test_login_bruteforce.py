"""B2: login brute-force protection counted from the user_login_failed signal."""
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts import login_security
from tests.base import DEFAULT_PASSWORD, make_resident_user

GENERIC = 'Invalid email/username or password.'
LOCKED = 'Too many failed sign-in attempts.'


@override_settings(LOGIN_FAILURE_LIMIT=5, LOGIN_USER_FAILURE_LIMIT=10, LOGIN_IP_FAILURE_LIMIT=20,
                   LOGIN_LOCKOUT_SECONDS=900, TRUSTED_PROXY_COUNT=0)
class LoginBruteForceTests(TestCase):

    def setUp(self):
        cache.clear()
        self.user = make_resident_user(username='juan', email='juan@barangay.test')
        self.url = reverse('accounts:login')

    def _post(self, username, password='WrongPass!1', ip='192.0.2.10', **extra):
        client = Client(REMOTE_ADDR=ip, **extra)
        return client.post(self.url, {'username': username, 'password': password})

    def test_five_failures_lock_username_and_ip(self):
        for _ in range(5):
            self.assertEqual(self._post('juan').status_code, 200)
        locked = self._post('juan', password=DEFAULT_PASSWORD)  # even the right password
        self.assertEqual(locked.status_code, 429)
        self.assertTrue(int(locked['Retry-After']) > 0)
        self.assertContains(locked, LOCKED, status_code=429)

    def test_same_message_for_unknown_and_known_users(self):
        unknown = self._post('nobody-here')
        known = self._post('juan')
        self.assertContains(unknown, GENERIC)
        self.assertContains(known, GENERIC)
        for _ in range(5):
            self._post('nobody-here', ip='192.0.2.20')
            self._post('juan', ip='192.0.2.21')
        a = self._post('nobody-here', ip='192.0.2.20')
        b = self._post('juan', ip='192.0.2.21')
        self.assertEqual((a.status_code, b.status_code), (429, 429))
        self.assertContains(a, LOCKED, status_code=429)
        self.assertContains(b, LOCKED, status_code=429)

    def test_other_ip_allowed_until_per_user_limit(self):
        for _ in range(5):
            self._post('juan', ip='192.0.2.10')
        self.assertEqual(self._post('juan', ip='192.0.2.10').status_code, 429)
        # A different IP still works (failures 6..10 for this username).
        for i in range(5):
            self.assertEqual(self._post('juan', ip=f'198.51.100.{i + 1}').status_code, 200)
        # 10 failures across IPs -> the username is locked everywhere.
        self.assertEqual(self._post('juan', ip='198.51.100.99').status_code, 429)

    def test_twenty_failures_across_usernames_lock_the_ip(self):
        for i in range(20):
            self.assertEqual(self._post(f'user{i}', ip='203.0.113.7').status_code, 200)
        response = self._post('someone-new', ip='203.0.113.7')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        # Another IP is not affected.
        self.assertEqual(self._post('someone-new', ip='203.0.113.8').status_code, 200)

    def test_successful_login_clears_username_ip_counter(self):
        for _ in range(4):
            self._post('juan')
        ok = self._post('juan', password=DEFAULT_PASSWORD)
        self.assertEqual(ok.status_code, 302)
        # Counter reset: 4 more failures do not lock yet.
        for _ in range(4):
            self.assertEqual(self._post('juan').status_code, 200)
        self.assertEqual(login_security.lock_remaining('juan', '192.0.2.10'), 0)

    def test_login_by_email_is_counted_under_the_typed_identifier(self):
        for _ in range(5):
            self._post('JUAN@barangay.test')
        self.assertEqual(self._post('juan@barangay.test').status_code, 429)

    def test_spoofed_forwarded_for_does_not_bypass_lock(self):
        for i in range(5):
            self._post('juan', HTTP_X_FORWARDED_FOR=f'10.9.9.{i}')
        response = self._post('juan', HTTP_X_FORWARDED_FOR='10.9.9.200')
        self.assertEqual(response.status_code, 429)

    def test_lockout_is_logged_without_password(self):
        with self.assertLogs('apps.security.login', level='WARNING') as logs:
            for _ in range(5):
                self._post('juan', password='S3cret-typed!')
        output = '\n'.join(logs.output)
        self.assertIn('Login lockout', output)
        self.assertNotIn('S3cret-typed!', output)
        self.assertNotIn('juan', output)  # identifier is hashed
