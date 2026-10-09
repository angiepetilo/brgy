"""
Shared field validators.

Philippine mobile numbers are stored in one canonical form: 11 digits,
starting with 09 (09XXXXXXXXX). No dashes, spaces, letters or +63 prefix.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible

# \Z, not $: $ would also accept a trailing newline.
PH_MOBILE_RE = r'^09\d{9}\Z'
PH_MOBILE_MESSAGE = 'Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567).'
# HTML pattern attribute for phone inputs (the browser anchors it itself).
PH_MOBILE_HTML_PATTERN = '09[0-9]{9}'

_PH_MOBILE = re.compile(PH_MOBILE_RE)


@deconstructible
class PhMobileValidator(RegexValidator):
    regex = PH_MOBILE_RE
    message = PH_MOBILE_MESSAGE
    code = 'invalid_ph_mobile'

    def __call__(self, value):
        # RegexValidator would str() non-strings; refuse them outright.
        if not isinstance(value, str) or not value.isascii():
            raise ValidationError(self.message, code=self.code)
        super().__call__(value)


validate_ph_mobile = PhMobileValidator()


def is_valid_ph_mobile(value):
    return isinstance(value, str) and value.isascii() and bool(_PH_MOBILE.match(value))


def normalize_ph_mobile(raw):
    """
    Best-effort cleanup of a stored number, used by the data migration.

    Strips every non-digit, turns 63XXXXXXXXXX (12 digits, from +63 or 63)
    into 0XXXXXXXXXX, and returns the result only when it is a valid
    09XXXXXXXXX number. Returns None when it cannot be normalized.
    Form and API input is NOT normalized: it must already be 11 digits.
    """
    if raw is None:
        return None
    digits = re.sub(r'\D', '', str(raw))
    if len(digits) == 12 and digits.startswith('63'):
        digits = '0' + digits[2:]
    return digits if is_valid_ph_mobile(digits) else None


def ph_mobile_widget_attrs(**extra):
    """HTML attributes for a mobile-number <input> (see static/js/phone_input.js)."""
    attrs = {
        'inputmode': 'numeric',
        'pattern': PH_MOBILE_HTML_PATTERN,
        'maxlength': '11',
        'minlength': '11',
        'autocomplete': 'tel',
        'placeholder': '09XXXXXXXXX',
        'title': PH_MOBILE_MESSAGE,
        'data-phone': '',
    }
    attrs.update(extra)
    return attrs
