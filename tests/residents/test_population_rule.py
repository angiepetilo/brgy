"""
A3: population rule. A Resident counts when it is not archived AND it has no
linked user or its linked user is active. Pending, rejected and disabled
sign-ups are excluded everywhere (selectors, Records RBI table, Statistics API,
purok and household counts).
"""
from django.test import override_settings
from django.urls import reverse

from apps.accounts import selectors
from apps.accounts.models import Household, User
from tests.base import BaseTestCase, make_admin, make_purok, make_resident_profile, make_resident_user
from tests.statistics.data import TEMP_MEDIA


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PopulationRuleTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.purok = make_purok('Rule Purok')
        self.households = {}

        def resident(label, user=None, **extra):
            hh = Household.objects.create(household_name=f'HH {label}', purok=self.purok)
            self.households[label] = hh
            return make_resident_profile(user=user, purok=self.purok, household=hh,
                                         first_name=label, last_name='Rule', **extra)

        self.no_user = resident('NoUser')
        self.active = resident('Active', user=make_resident_user())
        self.pending = resident('Pending', user=make_resident_user(status=User.STATUS_PENDING, is_approved=False))
        self.rejected = resident('Rejected', user=make_resident_user(status=User.STATUS_REJECTED, is_approved=False))
        self.disabled = resident('Disabled', user=make_resident_user(status=User.STATUS_DISABLED, is_active=False))
        self.archived = resident('Archived', is_archived=True)
        self.counted = {self.no_user.pk, self.active.pk}

    def test_selector_population_counts_only_no_user_and_active(self):
        self.assertEqual(set(selectors.active_residents().values_list('pk', flat=True)), self.counted)
        self.assertEqual(selectors.population(), 2)
        self.assertEqual(selectors.population(self.purok.id), 2)

    def test_purok_and_household_counts_follow_the_rule(self):
        row = next(r for r in selectors.population_per_purok() if r['purok_id'] == self.purok.id)
        self.assertEqual(row['count'], 2)
        hh_row = next(r for r in selectors.households_per_purok() if r['purok_id'] == self.purok.id)
        # Only the households of NoUser and Active still have a counted member.
        self.assertEqual(hh_row['households'], 2)

    def test_records_rbi_table_lists_only_counted_residents(self):
        self.login(make_admin())
        resp = self.client.get(reverse('records:hub'), {'tab': 'inhabitants'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({r.pk for r in resp.context['rbi_page']}, self.counted)
        self.assertEqual(resp.context['total_inhabitants'], 2)

    def test_statistics_demographics_population_matches(self):
        self.login(make_admin())
        resp = self.client.get(reverse('statistics:api_demographics'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['population'], 2)
