"""A7: resident edit reports clearly when the user has no Resident (RBI) profile."""
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.accounts.models import Resident
from apps.history.models import ActivityLog
from tests.base import BaseTestCase, make_admin, make_resident_profile, make_resident_user


def _messages(response):
    return [(m.level_tag, str(m)) for m in get_messages(response.wsgi_request)]


class ResidentEditTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.login(make_admin())

    def _post(self, user, referer=None, **data):
        payload = {
            'first_name': 'Edited', 'last_name': 'Person', 'email': user.email,
            'phone_number': '09171112222', 'street_address': '1 Rizal St',
            'gender': 'female', 'civil_status': 'married', 'is_pwd': 'on',
        }
        payload.update(data)
        extra = {'HTTP_REFERER': referer} if referer else {}
        return self.client.post(reverse('accounts:resident_edit', args=[user.id]), payload, **extra)

    def test_with_profile_saves_fields_and_shows_success(self):
        user = make_resident_user()
        res = make_resident_profile(user=user)
        response = self._post(user)
        res.refresh_from_db()
        self.assertEqual((res.first_name, res.gender, res.civil_status, res.is_pwd),
                         ('Edited', 'female', 'married', True))
        self.assertEqual(res.contact_no, '09171112222')
        msgs = _messages(response)
        self.assertTrue(any(level == 'success' and 'updated' in text for level, text in msgs), msgs)
        self.assertTrue(ActivityLog.objects.filter(action_type='ResidentAccount', target_id=str(user.id)).exists())

    def test_without_profile_updates_user_and_warns(self):
        user = make_resident_user()
        self.assertFalse(Resident.objects.filter(user=user).exists())
        response = self._post(user)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Edited')
        msgs = _messages(response)
        self.assertIn(
            ('warning', f"Account details for Edited Person were updated, but this user has no resident "
                        "(RBI) profile, so demographics were not saved."),
            msgs,
        )
        self.assertFalse(any(level == 'success' for level, _ in msgs))

    def test_bad_demographics_save_nothing(self):
        user = make_resident_user(first_name='Orig')
        res = make_resident_profile(user=user, first_name='Orig')
        response = self._post(user, gender='nonsense')
        user.refresh_from_db()
        res.refresh_from_db()
        self.assertEqual(user.first_name, 'Orig')
        self.assertEqual(res.first_name, 'Orig')
        self.assertIn(('error', 'Select a valid gender.'), _messages(response))

    def test_offsite_referer_redirects_to_residents_page(self):
        user = make_resident_user()
        response = self._post(user, referer='https://evil.example.com/phish')
        self.assertEqual(response['Location'], reverse('accounts:residents_tabbed'))

    def test_same_site_referer_is_kept(self):
        user = make_resident_user()
        back = 'http://testserver' + reverse('accounts:residents_tabbed') + '?tab=approved'
        response = self._post(user, referer=back)
        self.assertEqual(response['Location'], back)
