"""
B4: insecure production settings refuse to start; a production-like env passes
`manage.py check --deploy` with no warnings. Each case runs in a subprocess so
the settings module is evaluated with that environment.
"""
import os
import secrets
import string
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = str(settings.BASE_DIR)
STRONG_KEY = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#%^*-_=+') for _ in range(64))


def _env(**overrides):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DJANGO_', 'SECURE_', 'SESSION_', 'CSRF_'))}
    for key in ('DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'CSP_REPORT_ONLY', 'TRUSTED_PROXY_COUNT'):
        env.pop(key, None)
    env.update({'DJANGO_SETTINGS_MODULE': 'config.settings', 'PYTHONUTF8': '1'})
    env.update({k: v for k, v in overrides.items() if v is not None})
    for k, v in overrides.items():
        if v is None:
            env.pop(k, None)
    return env


def _run(args, **env):
    return subprocess.run(
        [sys.executable, *args], cwd=BASE_DIR, env=_env(**env),
        capture_output=True, text=True, timeout=120,
    )


SETUP = ['-c', 'import django; django.setup()']


class UnsafeProductionConfigTests(SimpleTestCase):

    def assert_refuses(self, **env):
        result = _run(SETUP, DEBUG='False', **env)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('ImproperlyConfigured', result.stderr)
        return result.stderr

    def test_missing_secret_key(self):
        self.assert_refuses(SECRET_KEY=None, ALLOWED_HOSTS='example.com')

    def test_dev_default_secret_key(self):
        self.assert_refuses(SECRET_KEY=settings.DEV_SECRET_KEY, ALLOWED_HOSTS='example.com')

    def test_short_secret_key(self):
        self.assert_refuses(SECRET_KEY='short-test-key-x', ALLOWED_HOSTS='example.com')

    def test_wildcard_allowed_hosts(self):
        self.assert_refuses(SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS='*')

    def test_wildcard_among_hosts(self):
        self.assert_refuses(SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS='example.com,*')

    def test_empty_allowed_hosts(self):
        self.assert_refuses(SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS=None)

    def test_error_does_not_print_the_key(self):
        stderr = self.assert_refuses(SECRET_KEY='short-secret-key', ALLOWED_HOSTS='example.com')
        self.assertNotIn('short-secret-key', stderr)

    def test_local_dev_defaults_still_start(self):
        result = _run(SETUP, DEBUG=None, SECRET_KEY=None, ALLOWED_HOSTS=None)
        self.assertEqual(result.returncode, 0, result.stderr)


class DeployCheckTests(SimpleTestCase):

    def test_check_deploy_has_no_warnings(self):
        result = _run(
            ['manage.py', 'check', '--deploy'],
            DEBUG='False', SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS='example.com',
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('System check identified no issues', output)
        self.assertNotIn('WARNINGS', output)

    def test_production_defaults_are_secure(self):
        code = (
            'import django; django.setup(); from django.conf import settings as s; '
            'print(s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, '
            's.SECURE_HSTS_SECONDS, s.SECURE_HSTS_INCLUDE_SUBDOMAINS)'
        )
        result = _run(['-c', code], DEBUG='False', SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS='example.com')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ['True', 'True', 'True', '31536000', 'True'])

    def test_env_can_override_secure_defaults(self):
        code = 'import django; django.setup(); from django.conf import settings as s; print(s.SECURE_SSL_REDIRECT)'
        result = _run(['-c', code], DEBUG='False', SECRET_KEY=STRONG_KEY, ALLOWED_HOSTS='example.com',
                      SECURE_SSL_REDIRECT='False')
        self.assertEqual(result.stdout.strip(), 'False', result.stderr)


class InProcessSettingsTests(SimpleTestCase):

    def test_cookie_samesite_lax(self):
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')

    def test_dead_xss_filter_setting_removed(self):
        source = (settings.BASE_DIR / 'config' / 'settings.py').read_text(encoding='utf-8')
        self.assertNotIn('SECURE_BROWSER_XSS_FILTER', source)

    def test_env_example_documents_the_new_variables(self):
        text = (settings.BASE_DIR / '.env.example').read_text(encoding='utf-8')
        for name in ('SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'TRUSTED_PROXY_COUNT', 'CSP_REPORT_ONLY',
                     'LOGIN_IP_FAILURE_LIMIT', 'LOGIN_USER_FAILURE_LIMIT', 'RATE_LIMIT_PASSWORD_RESET',
                     'REDIS_URL', 'SECURE_SSL_REDIRECT', 'SECURE_HSTS_SECONDS'):
            with self.subTest(name=name):
                self.assertIn(name, text)
