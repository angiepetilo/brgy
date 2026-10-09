"""Stage D: Font Awesome and external font/icon CDNs are gone; Lucide replaces them."""
import re

from django.test import SimpleTestCase

from tests.ui.scan import STATIC, scan, static_sources, template_files

FA_CLASS = re.compile(r'\bfa-[a-z]')
FA_PREFIX = re.compile(r'''class=["'][^"']*\bfa[srb]?\s''')
CDN = re.compile(r'cdnjs|font-?awesome|fonts\.googleapis|fonts\.gstatic', re.I)


class NoFontAwesomeTests(SimpleTestCase):

    def test_templates_have_no_fa_classes_or_cdns(self):
        hits = scan(template_files(), [('fa- class', FA_CLASS), ('fa prefix', FA_PREFIX), ('CDN', CDN)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_static_js_and_css_have_no_fa_classes_or_cdns(self):
        hits = scan(static_sources(), [('fa- class', FA_CLASS), ('CDN', CDN)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_font_awesome_vendor_copy_removed(self):
        self.assertFalse((STATIC / 'vendor' / 'fontawesome').exists())

    def test_scanner_detects_violations(self):
        self.assertTrue(FA_CLASS.search('<i class="fa-solid fa-house"></i>'))
        self.assertTrue(FA_PREFIX.search('<i class="fas fa-house"></i>'))
        self.assertTrue(CDN.search('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'))
        self.assertFalse(FA_CLASS.search('<div class="sofa-bed">'))
