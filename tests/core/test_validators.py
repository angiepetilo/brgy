"""B6: shared Philippine mobile number validator and normalizer."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.core.validators import (
    PH_MOBILE_MESSAGE, is_valid_ph_mobile, normalize_ph_mobile, validate_ph_mobile,
)


class ValidatePhMobileTests(SimpleTestCase):

    def test_valid_number(self):
        validate_ph_mobile('09171234567')
        self.assertTrue(is_valid_ph_mobile('09171234567'))

    def test_rejected_values(self):
        bad = [
            '0917-123-4567',   # dashes
            '0917 123 4567',   # spaces
            '0917123456a',     # letters
            '+639171234567',   # +63
            '639171234567',    # 63 prefix, 12 digits
            '0917123456',      # 10 digits
            '091712345678',    # 12 digits
            '08171234567',     # does not start with 09
            '٠٩١٧١٢٣٤٥٦٧',     # non-ASCII digits
            ' 09171234567',    # leading space
            '09171234567\n',   # trailing newline
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    validate_ph_mobile(value)
                self.assertEqual(ctx.exception.messages, [PH_MOBILE_MESSAGE])
                self.assertFalse(is_valid_ph_mobile(value))

    def test_non_string_rejected(self):
        with self.assertRaises(ValidationError):
            validate_ph_mobile(9171234567)


class NormalizePhMobileTests(SimpleTestCase):

    def test_cases(self):
        cases = {
            '0917-111-2222': '09171112222',
            '0917 111 2222': '09171112222',
            '(0917) 111-2222': '09171112222',
            '+63 917 111 2222': '09171112222',
            '639171112222': '09171112222',
            '09472750431': '09472750431',
            '9171112222': None,          # 10 digits, ambiguous
            '0817-111-2222': None,       # not a mobile prefix
            'call me': None,
            '': None,
            None: None,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ph_mobile(raw), expected)
