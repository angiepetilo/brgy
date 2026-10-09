"""Stage D: the {% icon %} tag and the vendored Lucide subset sprite."""
import re

from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase

from apps.core import icons
from tests.ui.scan import STATIC, template_files

SPRITE = STATIC / 'vendor' / 'lucide' / 'sprite.svg'
LITERAL_ICON = re.compile(r"""{%\s*icon\s+['"]([a-z0-9-]+)['"]""")
JS_ICON = re.compile(r"""BrgyUI\.icon(?:Element)?\(\s*['"]([a-z0-9-]+)['"]""")


def render(source, **context):
    return Template('{% load core_tags %}' + source).render(Context(context))


class IconTagTests(SimpleTestCase):

    def test_renders_decorative_svg_from_local_sprite(self):
        html = render("{% icon 'file-text' %}")
        self.assertIn('<svg class="icon icon-file-text"', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('focusable="false"', html)
        self.assertRegex(html, r'<use href="/static/vendor/lucide/sprite(\.[0-9a-f]+)?\.svg#lucide-file-text">')

    def test_design_guide_aliases_resolve(self):
        self.assertIn('#lucide-triangle-alert', render("{% icon 'alert-triangle' %}"))
        self.assertIn('#lucide-house', render("{% icon 'home' %}"))
        self.assertIn('#lucide-house', render("{% icon 'lucide-home' %}"))

    def test_unknown_name_raises(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% icon 'not-a-real-icon' %}")

    def test_variable_name_and_classes(self):
        html = render("{% icon name cls='icon-primary' %}", name='stethoscope')
        self.assertIn('class="icon icon-stethoscope icon-primary"', html)

    def test_class_and_style_are_escaped(self):
        html = render("{% icon 'x' cls=evil %}", evil='"><script>')
        self.assertNotIn('<script>', html)

    def test_every_registered_icon_is_in_the_sprite(self):
        sprite = SPRITE.read_text(encoding='utf-8')
        missing = [name for name in icons.ICON_NAMES if f'id="lucide-{name}"' not in sprite]
        self.assertEqual(missing, [])

    def test_every_template_and_js_icon_name_exists_in_the_sprite(self):
        sprite = SPRITE.read_text(encoding='utf-8')
        used = set()
        for path in template_files():
            used.update(LITERAL_ICON.findall(path.read_text(encoding='utf-8')))
        for path in (STATIC / 'js').glob('*.js'):
            used.update(JS_ICON.findall(path.read_text(encoding='utf-8')))
        self.assertTrue(used)
        problems = []
        for name in sorted(used):
            canonical = icons.resolve(name)
            if canonical is None or f'id="lucide-{canonical}"' not in sprite:
                problems.append(name)
        self.assertEqual(problems, [])

    def test_records_department_icons_are_lucide_names(self):
        from apps.records.views import DEPARTMENTS
        for dept in DEPARTMENTS:
            self.assertIsNotNone(icons.resolve(dept['icon']), dept['icon'])

    def test_vendor_readme_records_version_and_license(self):
        readme = (SPRITE.parent / 'README.md').read_text(encoding='utf-8')
        self.assertIn('lucide-static@1.52.0', readme)
        self.assertIn('ISC', readme)
        self.assertIn('static/js/icons.js', readme)
        self.assertTrue((SPRITE.parents[2] / 'js' / 'icons.js').exists())
        self.assertIn('ISC License', (SPRITE.parent / 'LICENSE').read_text(encoding='utf-8'))
