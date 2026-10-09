"""A0: display_name filter for nullable user FKs."""
from django.template import Context, Template

from apps.core.templatetags.core_tags import display_name
from tests.base import BaseTestCase, make_resident_user


class DisplayNameFilterTests(BaseTestCase):

    def test_full_name_wins(self):
        user = make_resident_user(first_name='Maria', last_name='Santos')
        self.assertEqual(display_name(user, 'Fallback'), 'Maria Santos')

    def test_username_when_no_full_name(self):
        user = make_resident_user(first_name='', last_name='')
        self.assertEqual(display_name(user, 'Fallback'), user.username)

    def test_none_with_fallback(self):
        self.assertEqual(display_name(None, 'Health Officer'), 'Health Officer')

    def test_none_without_fallback_is_empty(self):
        self.assertEqual(display_name(None), '')

    def test_template_with_null_fk_does_not_raise(self):
        tpl = Template('{% load core_tags %}[{{ obj.processed_by|display_name:"Health Officer" }}]')

        class Obj:
            processed_by = None

        self.assertEqual(tpl.render(Context({'obj': Obj()})), '[Health Officer]')
