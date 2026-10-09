"""
B5: Content-Security-Policy and the removal of inline JavaScript.

script-src 'self' blocks inline <script> bodies, on*= handler attributes and
javascript: URLs, so the templates must not contain any of them. Server data
reaches scripts through data-* attributes or <script type="application/json">.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.middleware import SecurityHeadersMiddleware
from tests.base import make_resident_user

TEMPLATES = Path(settings.BASE_DIR) / 'templates'
STATIC_JS = Path(settings.BASE_DIR) / 'static' / 'js'

SCRIPT_TAG = re.compile(r'<script\b([^>]*)>', re.I)
HANDLER_ATTR = re.compile(r'\son[a-z]+\s*=', re.I)
JS_URL = re.compile(r'javascript:', re.I)
CDN = re.compile(r'fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|cdnjs\.cloudflare|unpkg\.com', re.I)
# String literals in JS that would create inline handlers / javascript: URLs.
JS_STRING_HANDLER = re.compile(r'''["'`][^"'`\n]*\son[a-z]+\s*=\s*\\?["'][^"'`\n]*["'`]''', re.I)
JS_STRING_URL = re.compile(r'''["'`]\s*javascript:''', re.I)


def _template_files():
    for path in sorted(TEMPLATES.rglob('*.html')):
        if 'emails' in path.relative_to(TEMPLATES).parts:
            continue
        yield path


def _scan(path, patterns):
    hits = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        for label, pattern in patterns:
            if pattern.search(line):
                hits.append(f'{path.relative_to(settings.BASE_DIR)}:{number}: {label}: {line.strip()[:120]}')
    return hits


class TemplateInlineJsScanTests(TestCase):

    def test_no_inline_script_bodies(self):
        hits = []
        for path in _template_files():
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                for match in SCRIPT_TAG.finditer(line):
                    attrs = match.group(1)
                    if 'src=' in attrs or re.search(r'type=["\']application/json["\']', attrs):
                        continue
                    hits.append(f'{path.relative_to(settings.BASE_DIR)}:{number}: {line.strip()[:120]}')
        self.assertEqual(hits, [], 'Inline <script> blocks found:\n' + '\n'.join(hits))

    def test_no_inline_event_handlers_or_javascript_urls(self):
        hits = []
        for path in _template_files():
            hits += _scan(path, [('on*= handler', HANDLER_ATTR), ('javascript: URL', JS_URL)])
        self.assertEqual(hits, [], 'Inline handlers found:\n' + '\n'.join(hits))

    def test_no_external_cdns(self):
        hits = []
        for path in _template_files():
            hits += _scan(path, [('external CDN', CDN)])
        for path in sorted(STATIC_JS.glob('*.js')):
            hits += _scan(path, [('external CDN', CDN)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_static_js_does_not_build_inline_handlers(self):
        hits = []
        for path in sorted(STATIC_JS.glob('*.js')):
            hits += _scan(path, [('handler in string', JS_STRING_HANDLER), ('javascript: in string', JS_STRING_URL)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_scanner_detects_violations(self):
        # Guard against a scanner that silently matches nothing.
        self.assertTrue(HANDLER_ATTR.search('<button onclick="x()">'))
        self.assertTrue(JS_STRING_HANDLER.search("el.innerHTML = '<a onclick=\"go()\">x</a>';"))
        self.assertTrue(SCRIPT_TAG.search('<script>alert(1)</script>'))
        self.assertFalse(HANDLER_ATTR.search('<button data-confirm="ok">'))

    def test_vendored_assets_exist(self):
        # Stage D replaced Font Awesome with the local Lucide sprite.
        for rel in ('vendor/lucide/sprite.svg', 'vendor/lucide/LICENSE', 'css/theme.css', 'js/icons.js',
                    'vendor/fullcalendar/index.global.min.js', 'js/phone_input.js', 'js/landing.js'):
            with self.subTest(rel=rel):
                self.assertTrue((Path(settings.BASE_DIR) / 'static' / rel).is_file())


class CspHeaderTests(TestCase):

    def assert_csp(self, response):
        policy = response['Content-Security-Policy']
        for directive in ("default-src 'self'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
                          "img-src 'self' data: blob:", "font-src 'self'", "connect-src 'self' ws: wss:",
                          "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'", "object-src 'none'"):
            self.assertIn(directive, policy)
        self.assertNotIn('unsafe-eval', policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertEqual(response['Permissions-Policy'], 'camera=(), microphone=(), geolocation=()')
        self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin')

    def test_public_pages_send_csp(self):
        for url in ('/', reverse('accounts:login')):
            with self.subTest(url=url):
                self.assert_csp(self.client.get(url))

    def test_logged_in_page_sends_csp(self):
        self.client.force_login(make_resident_user())
        response = self.client.get('/home/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assert_csp(response)

    def test_json_and_error_responses_send_csp(self):
        self.assert_csp(self.client.get('/appointments/api/services/'))  # 401 JSON
        self.assert_csp(self.client.get('/static-does-not-exist-404/'))

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode(self):
        from django.http import HttpResponse
        response = SecurityHeadersMiddleware(lambda request: HttpResponse('ok'))(None)
        self.assertIn('Content-Security-Policy-Report-Only', response)
        self.assertNotIn('Content-Security-Policy', response)
        self.assertIn("script-src 'self'", response['Content-Security-Policy-Report-Only'])
