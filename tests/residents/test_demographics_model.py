"""Resident demographics: derived senior flag, local-date age, choices."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts import selectors
from apps.accounts.models import Resident, User
from tests.base import BaseTestCase, make_resident_profile


class SeniorDerivationTests(BaseTestCase):
    def test_turning_60_today_is_senior_and_one_day_short_is_not(self):
        today = timezone.localdate()
        sixty = make_resident_profile(birthdate=selectors.years_ago(today, 60))
        almost = make_resident_profile(birthdate=selectors.years_ago(today, 60) + timedelta(days=1))
        self.assertEqual(sixty.age, 60)
        self.assertTrue(sixty.is_senior)
        self.assertEqual(almost.age, 59)
        self.assertFalse(almost.is_senior)

    def test_59_and_61_year_olds(self):
        today = timezone.localdate()
        self.assertFalse(make_resident_profile(birthdate=selectors.years_ago(today, 59)).is_senior)
        self.assertTrue(make_resident_profile(birthdate=selectors.years_ago(today, 61)).is_senior)

    def test_queryset_helper_matches_the_property_at_the_boundary(self):
        today = timezone.localdate()
        sixty = make_resident_profile(birthdate=selectors.years_ago(today, 60))
        almost = make_resident_profile(birthdate=selectors.years_ago(today, 60) + timedelta(days=1))
        found = set(selectors.seniors())
        self.assertIn(sixty, found)
        self.assertNotIn(almost, found)
        for resident in (sixty, almost):
            self.assertEqual(resident in found, resident.is_senior)

    def test_feb_29_birthday_boundary_for_property_and_queryset(self):
        born = date(1964, 2, 29)
        resident = make_resident_profile(birthdate=born)
        for today, expected in [
            (date(2024, 2, 28), False),  # day before the 60th birthday
            (date(2024, 2, 29), True),   # 60th birthday (leap year)
            (date(2025, 2, 28), True),   # 61 already
        ]:
            with patch('django.utils.timezone.localdate', return_value=today):
                self.assertEqual(resident.is_senior, expected, today)
                self.assertEqual(resident in set(selectors.seniors(today=today)), expected, today)

    def test_feb_29_cutoff_does_not_raise_when_target_year_is_not_a_leap_year(self):
        self.assertEqual(selectors.years_ago(date(2024, 2, 29), 1), date(2023, 2, 28))
        self.assertEqual(selectors.senior_cutoff(date(2028, 2, 29)), date(1968, 2, 29))


class AgeUsesLocalDateTests(BaseTestCase):
    def test_age_follows_the_local_date_not_the_utc_date(self):
        # 2026-01-01 20:00 UTC is already 2026-01-02 04:00 in Asia/Manila.
        resident = make_resident_profile(birthdate=date(2000, 1, 2))
        utc_evening = datetime(2026, 1, 1, 20, 0, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=utc_evening):
            self.assertEqual(timezone.localdate(), date(2026, 1, 2))
            self.assertEqual(resident.age, 26)


class ChoicesTests(BaseTestCase):
    def _resident(self, **overrides):
        data = dict(first_name='A', last_name='B', birthdate=date(1990, 1, 1))
        data.update(overrides)
        return Resident(**data)

    def test_defaults(self):
        resident = self._resident()
        self.assertEqual(resident.civil_status, 'single')
        self.assertEqual(resident.gender, '')
        self.assertFalse(resident.is_solo_parent or resident.is_pwd or resident.is_4ps)
        resident.full_clean()  # blank gender is allowed for legacy rows

    def test_invalid_gender_and_civil_status_are_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self._resident(gender='x', civil_status='complicated').full_clean()
        self.assertEqual(set(ctx.exception.message_dict), {'gender', 'civil_status'})

    def test_every_declared_choice_is_valid(self):
        for code, _label in Resident.GENDER_CHOICES:
            self._resident(gender=code).full_clean()
        for code, _label in Resident.CIVIL_STATUS_CHOICES:
            self._resident(civil_status=code).full_clean()

    def test_sector_labels_combine_derived_and_stored_flags(self):
        today = timezone.localdate()
        resident = make_resident_profile(
            birthdate=selectors.years_ago(today, 70), is_pwd=True, is_solo_parent=True, is_4ps=True,
        )
        self.assertEqual(resident.sector_labels, ['Senior', 'PWD', 'Solo Parent', '4Ps'])
        self.assertEqual(make_resident_profile().sector_labels, [])


class UserNoLongerHoldsDemographicsTests(BaseTestCase):
    def test_removed_user_fields_are_gone(self):
        names = {f.name for f in User._meta.get_fields()}
        for removed in ('is_senior', 'is_pwd', 'is_4ps', 'civil_status'):
            self.assertNotIn(removed, names)
