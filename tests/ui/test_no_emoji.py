"""Stage D: no raw emoji in the interface (icons are Lucide SVGs with text labels)."""
import re

from django.test import SimpleTestCase

from tests.ui.scan import scan, static_sources, template_files

# Includes Miscellaneous Technical (U+2300-23FF: ⏩ ⏪ ⌛ ⏰ ⌚) and
# Miscellaneous Symbols and Arrows (U+2B00-2BFF: ⭐ ⬆ ⬛).
EMOJI = re.compile(
    '[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF'
    '\U00002300-\U000023FF\U00002B00-\U00002BFF\uFE0F]'
)


class NoEmojiTests(SimpleTestCase):

    def test_templates_have_no_emoji(self):
        hits = scan(template_files(), [('emoji', EMOJI)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_static_js_and_css_have_no_emoji(self):
        hits = scan(static_sources(), [('emoji', EMOJI)])
        self.assertEqual(hits, [], '\n'.join(hits))

    def test_scanner_detects_emoji(self):
        for sample in ('\U0001F6A8 Alert', 'Done \u2705', '\u26A0\uFE0F',
                       '\u23EA Yesterday', '\u23E9 Tomorrow', '\u231B', '\u2B50 Star', '\u2B06 Up'):
            self.assertTrue(EMOJI.search(sample), sample)
        self.assertFalse(EMOJI.search('Barangay Clearance - PHP 50.00'))
