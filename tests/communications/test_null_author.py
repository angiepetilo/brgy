"""A2: posts whose author was deleted (author=NULL via SET_NULL) render on every list page."""
from django.urls import reverse

from apps.communications.models import Announcement
from tests.base import BaseTestCase, make_admin, make_resident_user


class NullAuthorPostTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        author = make_admin()
        self.announcement = Announcement.objects.create(
            title='Orphan Announcement', content='Author was deleted.',
            category=Announcement.CATEGORY_ANNOUNCEMENT, author=author,
        )
        self.emergency = Announcement.objects.create(
            title='Orphan Emergency', content='Author was deleted.',
            category=Announcement.CATEGORY_EMERGENCY, author=author,
        )
        # Deleting the author sets author=NULL on both posts.
        author.delete()
        self.announcement.refresh_from_db()
        self.assertIsNone(self.announcement.author)
        self.login(make_resident_user())

    def _assert_renders(self, url_name, title):
        resp = self.client.get(reverse(url_name))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, title)
        self.assertContains(resp, '[BARANGAY OFFICIAL]')

    def test_feed_renders_null_author(self):
        self._assert_renders('communications:feed', 'Orphan Announcement')

    def test_announcements_list_renders_null_author(self):
        self._assert_renders('communications:announcements_list', 'Orphan Announcement')

    def test_emergency_list_renders_null_author(self):
        self._assert_renders('communications:emergency_list', 'Orphan Emergency')
