"""Demographic selectors: Resident is the source, archived residents never count."""
from datetime import timedelta

from django.utils import timezone

from apps.accounts import selectors
from apps.accounts.models import Household, Resident
from tests.base import BaseTestCase, make_purok, make_resident_profile, make_resident_user


def born(age, extra_days=0):
    """Birthdate of someone who turned `age` today (extra_days older)."""
    return selectors.years_ago(timezone.localdate(), age) - timedelta(days=extra_days)


def counts(rows):
    return {row['code']: row['count'] for row in rows}


class SelectorTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(Resident.objects.count(), 0)
        self.p1 = make_purok('Sel Purok 1')
        self.p2 = make_purok('Sel Purok 2')

    def test_archived_residents_are_excluded_everywhere(self):
        make_resident_profile(purok=self.p1, gender='male', is_pwd=True, is_4ps=True, birthdate=born(70))
        make_resident_profile(
            purok=self.p1, gender='male', is_pwd=True, is_4ps=True, birthdate=born(70),
            is_archived=True,
        )
        self.assertEqual(selectors.population(), 1)
        self.assertEqual(counts(selectors.by_gender())['male'], 1)
        sectors = counts(selectors.by_sector())
        self.assertEqual((sectors['senior'], sectors['pwd'], sectors['4ps']), (1, 1, 1))
        self.assertEqual(sum(r['count'] for r in selectors.by_civil_status()), 1)
        self.assertEqual(sum(b['count'] for b in selectors.age_bands()['bands']), 1)
        self.assertEqual(selectors.seniors().count(), 1)
        self.assertEqual(sum(r['count'] for r in selectors.population_per_purok()), 1)

    def test_staff_registered_resident_without_a_user_is_counted(self):
        make_resident_profile(user=None, purok=self.p1, gender='female')
        linked = make_resident_profile(user=make_resident_user(), purok=self.p1, gender='male')
        self.assertIsNone(Resident.objects.exclude(pk=linked.pk).get().user)
        self.assertEqual(selectors.population(), 2)

    def test_by_gender_is_zero_filled_and_reports_legacy_blank(self):
        make_resident_profile(gender='female')
        make_resident_profile(gender='female')
        make_resident_profile(gender='')
        got = counts(selectors.by_gender())
        self.assertEqual(got, {'male': 0, 'female': 2, 'other': 0, '': 1})

    def test_by_civil_status_uses_lowercase_codes_and_lists_every_choice(self):
        make_resident_profile(civil_status='married')
        make_resident_profile(civil_status='widowed')
        make_resident_profile(civil_status='widowed')
        rows = selectors.by_civil_status()
        self.assertEqual([r['code'] for r in rows], [c for c, _ in Resident.CIVIL_STATUS_CHOICES])
        self.assertEqual(
            counts(rows),
            {'single': 0, 'married': 1, 'widowed': 2, 'separated': 0, 'divorced': 0},
        )

    def test_by_sector_counts_overlap_and_derives_seniors(self):
        make_resident_profile(birthdate=born(60), is_pwd=True)
        make_resident_profile(birthdate=born(60, -1))  # one day short of 60
        make_resident_profile(is_solo_parent=True, is_4ps=True)
        make_resident_profile()
        got = counts(selectors.by_sector())
        self.assertEqual(got, {'senior': 1, 'pwd': 1, 'solo_parent': 1, '4ps': 1})

    def test_age_bands_cover_every_resident_once_with_correct_edges(self):
        for age in (0, 17, 18, 29, 30, 44, 45, 59, 60, 90):
            make_resident_profile(birthdate=born(age))
        result = selectors.age_bands()
        self.assertEqual(
            counts(result['bands']),
            {'0_17': 2, '18_29': 2, '30_44': 2, '45_59': 2, '60_plus': 2},
        )
        self.assertEqual(result['minors'], 2)
        self.assertEqual(sum(b['count'] for b in result['bands']), selectors.population())

    def test_households_per_purok_has_unassigned_bucket_and_zero_fill(self):
        Household.objects.create(household_name='A', purok=self.p1)
        Household.objects.create(household_name='B', purok=self.p1)
        Household.objects.create(household_name='C', purok=None)
        rows = {r['name']: r['households'] for r in selectors.households_per_purok()}
        self.assertEqual(rows['Sel Purok 1'], 2)
        self.assertEqual(rows['Sel Purok 2'], 0)
        self.assertEqual(rows['Unassigned'], 1)
        self.assertEqual(selectors.households_per_purok()[-1]['name'], 'Unassigned')

    def test_household_whose_members_are_all_archived_is_not_counted(self):
        live = Household.objects.create(household_name='Live', purok=self.p1)
        gone = Household.objects.create(household_name='Gone', purok=self.p1)
        make_resident_profile(purok=self.p1, household=live)
        make_resident_profile(purok=self.p1, household=gone, is_archived=True)
        rows = {r['name']: r['households'] for r in selectors.households_per_purok()}
        self.assertEqual(rows['Sel Purok 1'], 1)

    def test_purok_filter_limits_every_selector(self):
        make_resident_profile(purok=self.p1, gender='male', civil_status='married', is_pwd=True, birthdate=born(20))
        make_resident_profile(purok=self.p2, gender='female', birthdate=born(70))
        make_resident_profile(purok=None, gender='female')
        Household.objects.create(household_name='A', purok=self.p1)
        Household.objects.create(household_name='B', purok=self.p2)

        pid = self.p1.id
        self.assertEqual(selectors.population(pid), 1)
        self.assertEqual(counts(selectors.by_gender(pid))['male'], 1)
        self.assertEqual(counts(selectors.by_gender(pid))['female'], 0)
        self.assertEqual(counts(selectors.by_civil_status(pid))['married'], 1)
        self.assertEqual(counts(selectors.by_sector(pid))['pwd'], 1)
        self.assertEqual(counts(selectors.by_sector(pid))['senior'], 0)
        self.assertEqual(counts(selectors.age_bands(pid)['bands'])['18_29'], 1)
        self.assertEqual(
            [(r['name'], r['households']) for r in selectors.households_per_purok(pid)],
            [('Sel Purok 1', 1)],
        )
        self.assertEqual(
            [(r['name'], r['count']) for r in selectors.population_per_purok(pid)],
            [('Sel Purok 1', 1)],
        )

    def test_every_breakdown_reconciles_with_population(self):
        make_resident_profile(purok=self.p1, gender='male', civil_status='married', birthdate=born(33))
        make_resident_profile(purok=self.p2, gender='female', civil_status='single', birthdate=born(61))
        make_resident_profile(purok=None, gender='', civil_status='divorced', birthdate=born(5))
        make_resident_profile(purok=self.p1, gender='other', civil_status='widowed', birthdate=born(80), is_archived=True)
        total = selectors.population()
        self.assertEqual(total, 3)
        self.assertEqual(sum(r['count'] for r in selectors.by_gender()), total)
        self.assertEqual(sum(r['count'] for r in selectors.by_civil_status()), total)
        self.assertEqual(sum(b['count'] for b in selectors.age_bands()['bands']), total)
        self.assertEqual(sum(r['count'] for r in selectors.population_per_purok()), total)
