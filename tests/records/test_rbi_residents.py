"""Records hub RBI tab reads Resident (the single demographics source), not User."""
from django.urls import reverse
from django.utils import timezone

from apps.accounts import selectors
from tests.base import BaseTestCase, make_admin, make_purok, make_resident_profile, make_resident_user


class RbiTabTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.login(make_admin())
        self.url = reverse('records:hub')
        self.purok = make_purok('RBI Purok')
        self.staff_registered = make_resident_profile(
            user=None, first_name='Walang', last_name='Account', purok=self.purok,
            gender='female', civil_status='widowed', is_solo_parent=True,
            birthdate=selectors.years_ago(timezone.localdate(), 65), address='77 Mabini St',
        )
        self.with_account = make_resident_profile(
            user=make_resident_user(), first_name='May', last_name='Account', purok=self.purok,
            gender='male', is_pwd=True, is_4ps=True,
        )
        self.archived = make_resident_profile(first_name='Gone', last_name='Archived', is_archived=True)

    def _rows(self, **params):
        resp = self.client.get(self.url, {'tab': 'inhabitants', **params})
        self.assertEqual(resp.status_code, 200)
        return resp, list(resp.context['rbi_page'])

    def test_resident_without_a_user_appears_and_archived_does_not(self):
        resp, rows = self._rows()
        self.assertIn(self.staff_registered, rows)
        self.assertIn(self.with_account, rows)
        self.assertNotIn(self.archived, rows)
        self.assertEqual(resp.context['total_inhabitants'], 2)

    def test_rows_show_gender_civil_status_and_derived_sector_badges(self):
        resp, _rows = self._rows()
        html = resp.content.decode()
        self.assertIn('Walang Account', html)
        self.assertIn('Widowed', html)
        self.assertIn('Female', html)
        for badge in ('Senior', 'Solo Parent', 'PWD', '4Ps', 'NO ACCOUNT'):
            self.assertIn(badge, html)

    def test_search_by_name_address_and_contact(self):
        self.assertEqual([r for r in self._rows(q='walang')[1]], [self.staff_registered])
        self.assertEqual([r for r in self._rows(q='Mabini')[1]], [self.staff_registered])
        self.assertEqual([r for r in self._rows(q=self.with_account.contact_no)[1]].count(self.with_account), 1)
        self.assertEqual(self._rows(q='no-such-person')[1], [])

    def test_purok_filter(self):
        other = make_resident_profile(first_name='Elsewhere', last_name='Resident', purok=make_purok('RBI Other'))
        rows = self._rows(purok='RBI Other')[1]
        self.assertEqual(rows, [other])
