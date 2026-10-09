"""Stage D: key pages render for the right roles; the feed follows the civic hierarchy."""
import re

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import BarangayInfo
from apps.communications.models import Announcement
from tests.base import make_admin, make_resident_user
from tests.ui.pages import ADMIN_PAGES, ANONYMOUS_PAGES, RESIDENT_PAGES, urls

SECTION = re.compile(r'data-section="([a-z]+)"')


class KeyPagesTests(TestCase):

    def assert_ok(self, page_urls):
        for url in page_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous(self):
        self.assert_ok(urls(ANONYMOUS_PAGES))

    def test_resident(self):
        self.client.force_login(make_resident_user())
        self.assert_ok(urls(RESIDENT_PAGES))

    def test_admin(self):
        self.client.force_login(make_admin())
        self.assert_ok(urls(ADMIN_PAGES))


class FeedHierarchyTests(TestCase):

    def setUp(self):
        self.admin = make_admin()
        info = BarangayInfo.get_solo()
        info.contact_no = '09171234567'
        info.save()
        Announcement.objects.create(title='Flood warning Purok 2', content='Evacuate now.', author=self.admin,
                                    category=Announcement.CATEGORY_EMERGENCY)
        Announcement.objects.create(title='Office hours notice', content='Hall closes at 5 PM.', author=self.admin,
                                    category=Announcement.CATEGORY_GENERAL, is_pinned=True)
        Announcement.objects.create(title='Clean-up drive', content='Saturday.', author=self.admin,
                                    category=Announcement.CATEGORY_GENERAL)

    def test_sections_in_civic_order(self):
        self.client.force_login(make_resident_user())
        html = self.client.get(reverse('communications:feed')).content.decode()
        self.assertEqual(SECTION.findall(html), ['feed'])

    def test_clean_home_feed_has_no_civic_stack(self):
        self.client.force_login(make_resident_user())
        html = self.client.get(reverse('communications:feed')).content.decode()
        self.assertNotIn('civic-stack', html)
        self.assertNotIn('civic-emergency', html)
        self.assertNotIn('Documents and health services', html)

    def test_order_kept_when_feed_is_empty_or_filtered(self):
        self.client.force_login(make_resident_user())
        html = self.client.get(reverse('communications:feed') + '?cat=scholarship').content.decode()
        self.assertEqual(SECTION.findall(html), ['feed'])

    def test_landing_emergency_below_services(self):
        html = self.client.get('/').content.decode()
        self.assertIn('data-section="emergency"', html)
        self.assertGreater(html.index('data-section="emergency"'), html.index('class="services-section"'))
        self.assertIn('href="tel:09171234567"', html)

    def test_landing_footer_has_email_and_all_networks(self):
        html = self.client.get('/').content.decode()
        self.assertIn('helpdesk@barangay.gov.ph', html)
        self.assertIn('SMART', html)
        self.assertIn('TNT', html)
        self.assertIn('GLOBE', html)
        self.assertIn('TM', html)
        self.assertIn('DITO', html)

    def test_dashboard_has_no_footer(self):
        self.client.force_login(make_resident_user())
        html = self.client.get(reverse('communications:feed')).content.decode()
        self.assertNotIn('official-portal-footer', html)
        self.assertNotIn('id="portal-footer"', html)

    def test_booking_modal_screenshot_2_and_3(self):
        html = self.client.get('/').content.decode()
        # Screenshot 2: Month and Year dropdowns, Today button, Circular Nav, Services list
        self.assertIn('id="cal-month-select"', html)
        self.assertIn('id="cal-year-select"', html)
        self.assertIn('id="cal-today-btn"', html)
        self.assertIn('id="cal-prev-btn"', html)
        self.assertIn('id="cal-next-btn"', html)
        self.assertIn('id="custom-cal-grid"', html)
        self.assertIn('cal-day-num', html)
        self.assertIn('id="health-services-section"', html)
        self.assertIn('id="cal-services-list"', html)
        self.assertIn('class="cal-services-container"', html)
        self.assertIn('Health Center Services', html)

        # Health Center Services is located BELOW the calendar, and hidden by default for Document Request
        cal_idx = html.index('id="custom-cal-grid"')
        health_idx = html.index('id="health-services-section"')
        self.assertGreater(health_idx, cal_idx, "Health Center Services must be positioned below the calendar")
        self.assertIn('id="health-services-section" class="cal-services-container" style="display: none;', html)

        # Screenshot 3: Time Picker
        self.assertIn('id="time-picker-badge"', html)
        self.assertTrue('8:00 AM' in html or '8:00 PM' in html)
        self.assertIn('id="drum-col-hour"', html)
        self.assertIn('id="drum-col-min"', html)
        self.assertIn('id="drum-col-ampm"', html)
        self.assertIn('class="time-drum-highlight-bar"', html)

    def test_signup_page_file_preview_and_logo_link(self):
        html = self.client.get(reverse('accounts:signup')).content.decode()
        # Clickable logo back to home
        self.assertIn('class="fb-brand-title"', html)
        self.assertIn('href="/"', html)
        # ID file preview cards and modal
        self.assertIn('id="front_id_prompt_box"', html)
        self.assertIn('id="back_id_prompt_box"', html)
        self.assertIn('id="front_id_preview_card"', html)
        self.assertIn('id="back_id_preview_card"', html)
        self.assertIn('class="id-preview-hover-overlay"', html)
        self.assertIn('class="btn-view-uploaded"', html)
        self.assertIn('class="btn-remove-uploaded"', html)
        self.assertIn('id="fileViewerModal"', html)


class FeedQueryCountTests(TestCase):
    """The civic stacks add a fixed number of queries, not one per post."""

    def _count(self, user):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(reverse('communications:feed')).status_code, 200)
        return len(ctx.captured_queries)

    def test_query_count_does_not_grow_with_posts(self):
        admin = make_admin()
        BarangayInfo.get_solo()
        user = make_resident_user()
        self.client.force_login(user)
        # Start with every kind present (emergency, pinned, plain) so only the volume changes.
        Announcement.objects.create(title='E', content='x', author=admin, category=Announcement.CATEGORY_EMERGENCY)
        Announcement.objects.create(title='P', content='x', author=admin, category=Announcement.CATEGORY_GENERAL,
                                    is_pinned=True)
        Announcement.objects.create(title='G', content='x', author=admin, category=Announcement.CATEGORY_GENERAL)
        self._count(user)  # warm-up: the first feed request seeds the default PostCategory rows
        few = self._count(user)
        for i in range(10):
            Announcement.objects.create(title=f'Q{i}', content='x', author=admin,
                                        category=Announcement.CATEGORY_EMERGENCY if i % 2 else Announcement.CATEGORY_GENERAL,
                                        is_pinned=(i % 3 == 0))
        self.assertEqual(self._count(user), few)
