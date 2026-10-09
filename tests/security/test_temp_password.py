"""B8: temporary passwords are 12+ random characters from a mixed alphabet."""
import re

from django.contrib.auth.password_validation import validate_password
from django.test import TestCase

from apps.accounts.services import generate_temp_password

AMBIGUOUS = set('O0lI1')


class TempPasswordTests(TestCase):

    def test_length_and_character_classes(self):
        for _ in range(200):
            pw = generate_temp_password()
            self.assertEqual(len(pw), 12)
            self.assertRegex(pw, r'[a-z]')
            self.assertRegex(pw, r'[A-Z]')
            self.assertRegex(pw, r'\d')
            self.assertRegex(pw, r'[!@#$%^*\-_=+]')
            self.assertFalse(AMBIGUOUS & set(pw), pw)

    def test_no_html_special_characters(self):
        # Email templates are rendered with autoescape; these would be mangled.
        for _ in range(200):
            self.assertIsNone(re.search(r'[&<>"\']', generate_temp_password()))

    def test_unique(self):
        self.assertEqual(len({generate_temp_password() for _ in range(200)}), 200)

    def test_passes_project_password_validators(self):
        validate_password(generate_temp_password())

    def test_shorter_length_is_not_allowed(self):
        self.assertEqual(len(generate_temp_password(length=6)), 12)
        self.assertEqual(len(generate_temp_password(length=16)), 16)

    def test_approval_email_carries_the_password_unescaped(self):
        from django.core import mail
        from apps.accounts.services import approve_resident_service
        from tests.base import make_admin, make_resident_user
        from apps.accounts.models import User
        applicant = make_resident_user(status=User.STATUS_PENDING, email='new.applicant@example.com')
        with self.captureOnCommitCallbacks(execute=True):
            approve_resident_service(applicant, make_admin())
        body = '\n'.join(m.body for m in mail.outbox if 'new.applicant@example.com' in m.to)
        match = re.search(r'Temporary password: (\S+)', body)
        self.assertIsNotNone(match, body)
        applicant.refresh_from_db()
        self.assertEqual(len(match.group(1)), 12)
        self.assertTrue(applicant.check_password(match.group(1)))
