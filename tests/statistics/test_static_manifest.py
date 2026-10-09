"""
The statistics page under WhiteNoise's manifest storage (the production backend).

Django 5.1+ ignores the old STATICFILES_STORAGE setting, so tests and `runserver` use plain
StaticFilesStorage and would never notice a missing manifest entry. This test switches the
real backend on with STORAGES, runs collectstatic into a temp folder and renders the page.
"""
import re
import shutil
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from tests.base import DEFAULT_PASSWORD, make_staff

MANIFEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}


@pytest.mark.slow
class ManifestStaticTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_root = tempfile.mkdtemp(prefix='brgy-static-')
        cls.addClassCleanup(shutil.rmtree, cls.static_root, ignore_errors=True)

    def test_overview_resolves_hashed_static_files(self):
        with override_settings(STATIC_ROOT=self.static_root, STORAGES=MANIFEST_STORAGES):
            call_command('collectstatic', interactive=False, verbosity=0)
            manifest = Path(self.static_root) / 'staticfiles.json'
            self.assertTrue(manifest.exists(), 'collectstatic did not write a manifest')

            user = make_staff({'statistics': ['view']})
            self.client.login(username=user.username, password=DEFAULT_PASSWORD)
            response = self.client.get(reverse('statistics:overview'))
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()

            for logical in ('vendor/chartjs/chart.umd.js', 'js/statistics.js', 'css/statistics.css'):
                stem, dot, ext = logical.rpartition('.')
                pattern = rf'/static/{re.escape(stem)}\.[0-9a-f]{{12}}\.{ext}'
                match = re.search(pattern, html)
                self.assertIsNotNone(match, f'{logical} was not served with a hashed name')
                self.assertTrue((Path(self.static_root) / match.group(0)[len('/static/'):]).exists())
