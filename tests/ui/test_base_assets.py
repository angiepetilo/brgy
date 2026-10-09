"""Stage D: every page shell loads the local theme and Lucide assets, no external hosts."""
import re

from django.test import TestCase
from django.urls import reverse

from tests.base import make_resident_user
from tests.ui.scan import STATIC, TEMPLATES, static_sources, template_files

STYLESHEET = re.compile(r'<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"')
SCRIPT_SRC = re.compile(r'<script[^>]+src="([^"]+)"')

# Palette from barangay_agent_prompt.md plus the neutral grays in theme.css.
PALETTE = {'#F9FAFB', '#FFFFFF', '#1E3A8A', '#0F4C81', '#DC2626', '#16A34A',
           '#111827', '#1F2937', '#374151', '#4B5563', '#6B7280', '#9CA3AF',
           '#D1D5DB', '#E5E7EB', '#F3F4F6', '#172F70', '#B42020'}
# Same palette as RGB triples for rgb()/rgba() tints; black is allowed for overlays.
PALETTE_RGB = {tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in PALETTE} | {(0, 0, 0)}
RGBA = re.compile(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')
# An element with an inline style and its contents up to the first closing tag of the same name.
STYLED_ELEMENT = re.compile(r'<(span|div|td|p|strong|small|a|label)\b[^>]*?style="([^"]*)"[^>]*>(.*?)</\1>', re.S)
SMALL_GREEN_TEXT = re.compile(r'(?<![-\w])color:\s*#16A34A', re.I)
SMALL_FONT = re.compile(r'font-size:\s*(0\.\d+rem|1[0-5]px)')


class BaseAssetTests(TestCase):

    def assert_local_shell(self, html):
        sheets = STYLESHEET.findall(html)
        self.assertTrue(any('css/theme' in s for s in sheets), sheets)
        self.assertIn('vendor/lucide/sprite', html)
        for url in sheets + SCRIPT_SRC.findall(html):
            self.assertTrue(url.startswith('/static/'), url)
        theme = [i for i, s in enumerate(sheets) if 'css/theme' in s][0]
        main = [i for i, s in enumerate(sheets) if 'css/main' in s]
        if main:
            self.assertGreater(theme, main[0], 'theme.css must load after main.css')

    def test_base_template_for_logged_in_page(self):
        self.client.force_login(make_resident_user())
        html = self.client.get(reverse('communications:feed')).content.decode()
        self.assert_local_shell(html)
        self.assertIn('js/icons.js', html)
        self.assertIn('class="skip-link"', html)

    def test_standalone_landing_and_login(self):
        for url in ('/', reverse('accounts:login')):
            with self.subTest(url=url):
                self.assert_local_shell(self.client.get(url).content.decode())

    def test_standalone_500_template(self):
        from django.template.loader import render_to_string
        self.assert_local_shell(render_to_string('500.html'))

    def test_theme_tokens(self):
        css = (STATIC / 'css' / 'theme.css').read_text(encoding='utf-8')
        for token in ('--color-canvas: #F9FAFB', '--color-card: #FFFFFF', '--color-primary: #1E3A8A',
                      '--color-danger: #DC2626', '--color-success: #16A34A', '--font-size-base: 1rem',
                      'prefers-reduced-motion', ':focus-visible'):
            self.assertIn(token, css)
        self.assertNotIn('gradient(', css)

    def test_first_party_css_uses_only_the_palette(self):
        hits = []
        for name in ('theme.css', 'main.css', 'statistics.css', 'blotter.css'):
            css = (STATIC / 'css' / name).read_text(encoding='utf-8')
            self.assertNotIn('gradient(', css, name)
            for color in set(re.findall(r'#[0-9A-Fa-f]{6}\b', css)):
                if color.upper() not in PALETTE:
                    hits.append(f'{name}: {color}')
        self.assertEqual(hits, [])

    def test_rgb_and_rgba_colours_use_the_palette(self):
        """rgb()/rgba() tints (any alpha) in templates and first-party CSS/JS must be palette colours."""
        hits = []
        for path in list(template_files()) + list(static_sources()):
            text = path.read_text(encoding='utf-8')
            for number, line in enumerate(text.splitlines(), 1):
                for match in RGBA.finditer(line):
                    if tuple(int(v) for v in match.groups()) not in PALETTE_RGB:
                        hits.append(f'{path.name}:{number}: {match.group(0)}')
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_rgba_checker_flags_off_palette_tints(self):
        self.assertNotIn((37, 99, 235), PALETTE_RGB)
        self.assertIn((30, 58, 138), PALETTE_RGB)
        self.assertEqual(RGBA.findall('fill: rgba(37, 99, 235, 0.15)'), [('37', '99', '235')])

    def test_green_is_not_used_for_small_text(self):
        """#16A34A on white is about 3.3:1, below AA for normal text: small text uses dark gray."""
        hits = []
        for path in list(template_files()) + list(static_sources()):
            text = path.read_text(encoding='utf-8')
            for match in STYLED_ELEMENT.finditer(text):
                style, inner = match.group(2), match.group(3)
                # Icon-only boxes (non-text UI, 3:1 is enough) may stay green.
                label = re.sub(r'{%\s*icon[^%]*%}|<[^>]+>|\s+', '', inner)
                if label and SMALL_GREEN_TEXT.search(style) and SMALL_FONT.search(style):
                    hits.append(f'{path.name}:{text.count(chr(10), 0, match.start()) + 1}')
            if "style.color = '#16A34A'" in text:
                hits.append(f'{path.name}: style.color green')
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_green_text_checker_self_test(self):
        bad = '<span style="font-size: 0.875rem; color: #16A34A;">Delivered</span>'
        icon_only = '<span style="color: #16A34A; font-size: 0.95rem;">{% icon \'check\' %}</span>'
        m = STYLED_ELEMENT.search(bad)
        self.assertTrue(SMALL_GREEN_TEXT.search(m.group(2)) and SMALL_FONT.search(m.group(2)))
        self.assertEqual(re.sub(r'{%\s*icon[^%]*%}|<[^>]+>|\s+', '', STYLED_ELEMENT.search(icon_only).group(3)), '')

    def test_narrow_screen_layout_rules(self):
        css = (STATIC / 'css' / 'theme.css').read_text(encoding='utf-8')
        self.assertIn('.fb-center-content > div[style*=" auto"]', css)
        self.assertIn('.grid-stack-sm { grid-template-columns: 1fr !important; }', css)
        signup = (TEMPLATES / 'accounts' / 'signup.html').read_text(encoding='utf-8')
        self.assertIn('class="grid-stack-sm"', signup)
        inbox = (TEMPLATES / 'chat' / 'inbox.html').read_text(encoding='utf-8')
        self.assertIn('messenger-shell{% if other_user %} has-conversation{% endif %}', inbox)

    def test_statistics_chart_palette(self):
        js = (STATIC / 'js' / 'statistics.js').read_text(encoding='utf-8')
        palette = re.search(r'var PALETTE = \[([^\]]+)\]', js).group(1)
        colors = re.findall(r"'(#[0-9A-Fa-f]{6})'", palette)
        self.assertEqual(colors[0], '#1E3A8A')
        self.assertTrue(set(c.upper() for c in colors) <= PALETTE, colors)
        self.assertIn("var HIGHLIGHT = '#DC2626'", js)
