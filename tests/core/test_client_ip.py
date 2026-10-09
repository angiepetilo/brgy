"""B1: get_client_ip trusts X-Forwarded-For only behind a configured number of proxies."""
from django.test import RequestFactory, TestCase, override_settings

from apps.core.net import get_client_ip
from apps.history.models import ActivityLog
from apps.history.utils import log_activity


class ClientIpTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()

    def _req(self, xff=None, remote='10.0.0.5'):
        extra = {'REMOTE_ADDR': remote}
        if xff is not None:
            extra['HTTP_X_FORWARDED_FOR'] = xff
        return self.rf.get('/', **extra)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_default_ignores_spoofed_forwarded_for(self):
        self.assertEqual(get_client_ip(self._req(xff='1.2.3.4')), '10.0.0.5')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_one_proxy_takes_last_entry(self):
        self.assertEqual(get_client_ip(self._req(xff='6.6.6.6, 203.0.113.9')), '203.0.113.9')

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_two_proxies_take_second_from_last(self):
        self.assertEqual(get_client_ip(self._req(xff='6.6.6.6, 203.0.113.9, 10.1.1.1')), '203.0.113.9')

    @override_settings(TRUSTED_PROXY_COUNT=3)
    def test_fewer_entries_than_proxies_falls_back_to_remote_addr(self):
        self.assertEqual(get_client_ip(self._req(xff='203.0.113.9, 10.1.1.1')), '10.0.0.5')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_missing_header_uses_remote_addr(self):
        self.assertEqual(get_client_ip(self._req()), '10.0.0.5')

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_log_activity_stores_the_same_ip(self):
        request = self._req(xff='9.9.9.9')
        log_activity(None, 'view', 'IpTest', target_id='1', request=request)
        self.assertEqual(ActivityLog.objects.get(action_type='IpTest').ip_address, '10.0.0.5')

    def test_no_other_code_reads_the_raw_headers(self):
        from pathlib import Path
        from django.conf import settings
        offenders = []
        for path in (Path(settings.BASE_DIR) / 'apps').rglob('*.py'):
            if 'migrations' in path.parts or path.name == 'net.py':
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            if 'HTTP_X_FORWARDED_FOR' in text or "'REMOTE_ADDR'" in text:
                offenders.append(str(path))
        self.assertEqual(offenders, [])
