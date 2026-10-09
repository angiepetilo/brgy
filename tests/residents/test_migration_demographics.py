"""
accounts 0013 (schema) + 0014 (data) + 0015 (schema): User demographics move to Resident.
Applied forward and backward on legacy-shaped rows.
"""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

BEFORE = [('accounts', '0012_barangayinfo_resident_no_consent_reason_and_more')]
SCHEMA_ADDED = [('accounts', '0013_resident_demographics')]
AFTER = [('accounts', '0015_drop_user_demographics')]


class DemographicsMigrationTests(TransactionTestCase):

    def setUp(self):
        super().setUp()
        self.old_apps = self._migrate(BEFORE)
        self._build_legacy_rows()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def _user(self, n, **extra):
        User = self.old_apps.get_model('accounts', 'User')
        return User.objects.create(username=f'legacy{n}', email=f'legacy{n}@example.com', password='x', **extra)

    def _resident(self, name, user=None, birthdate=date(1990, 1, 1), **extra):
        Resident = self.old_apps.get_model('accounts', 'Resident')
        return Resident.objects.create(first_name=name, last_name='Legacy', birthdate=birthdate, user=user, **extra)

    def _build_legacy_rows(self):
        senior_birthdate = date(timezone.localdate().year - 70, 6, 15)
        self.married = self._resident(
            'Married', self._user(1, is_pwd=True, is_4ps=True, civil_status='Married'))
        self.widow = self._resident(
            'Widow', self._user(2, civil_status='widowed'),
            needs_categories='senior, PWD', birthdate=senior_birthdate)
        self.junk = self._resident('Junk', self._user(3, civil_status='Complicated'))
        self.blank = self._resident('Blank', self._user(4, civil_status=''))
        self.separated = self._resident('Sep', self._user(5, civil_status=' SEPARATED '))
        self.stub_pwd = self._resident('StubPwd', None, needs_categories='low_income, pwd')
        self.stub_plain = self._resident('StubPlain', None, needs_categories='low_income, nopwd')
        self.stub_empty = self._resident('StubEmpty', None)
        self.orphan_user = self._user(6, is_pwd=True, is_4ps=True, civil_status='Married')  # no Resident

    def _read(self, apps, resident):
        Resident = apps.get_model('accounts', 'Resident')
        return Resident.objects.get(pk=resident.pk)

    def test_schema_only_step_adds_columns_with_safe_defaults(self):
        apps = self._migrate(SCHEMA_ADDED)
        row = self._read(apps, self.married)
        self.assertEqual((row.gender, row.civil_status), ('', 'single'))
        self.assertFalse(row.is_pwd or row.is_4ps or row.is_solo_parent)

    def test_forward_copies_flags_and_normalises_civil_status(self):
        apps = self._migrate(AFTER)

        married = self._read(apps, self.married)
        self.assertEqual(married.civil_status, 'married')
        self.assertTrue(married.is_pwd)
        self.assertTrue(married.is_4ps)

        widow = self._read(apps, self.widow)
        self.assertEqual(widow.civil_status, 'widowed')
        self.assertTrue(widow.is_pwd, "'PWD' in needs_categories maps to is_pwd (case-insensitive)")
        self.assertFalse(widow.is_4ps)

        self.assertEqual(self._read(apps, self.junk).civil_status, 'single')
        self.assertEqual(self._read(apps, self.blank).civil_status, 'single')
        self.assertEqual(self._read(apps, self.separated).civil_status, 'separated')

    def test_pwd_mapping_also_applies_to_residents_without_a_user(self):
        apps = self._migrate(AFTER)
        self.assertTrue(self._read(apps, self.stub_pwd).is_pwd)
        self.assertFalse(self._read(apps, self.stub_plain).is_pwd, "'nopwd' is not the 'pwd' token")
        empty = self._read(apps, self.stub_empty)
        self.assertEqual((empty.is_pwd, empty.is_4ps, empty.civil_status), (False, False, 'single'))

    def test_seniors_are_not_stored_and_user_columns_are_dropped(self):
        apps = self._migrate(AFTER)
        Resident = apps.get_model('accounts', 'Resident')
        User = apps.get_model('accounts', 'User')
        self.assertNotIn('is_senior', {f.name for f in Resident._meta.get_fields()})
        user_fields = {f.name for f in User._meta.get_fields()}
        for gone in ('is_senior', 'is_pwd', 'is_4ps', 'civil_status'):
            self.assertNotIn(gone, user_fields)

    def test_user_without_a_resident_does_not_break_the_migration(self):
        apps = self._migrate(AFTER)
        User = apps.get_model('accounts', 'User')
        self.assertTrue(User.objects.filter(pk=self.orphan_user.pk).exists())

    def test_backward_refills_the_user_columns(self):
        self._migrate(AFTER)
        apps = self._migrate(BEFORE)
        User = apps.get_model('accounts', 'User')

        married = User.objects.get(pk=self.married.user_id)
        self.assertEqual((married.is_pwd, married.is_4ps, married.civil_status), (True, True, 'Married'))

        widow = User.objects.get(pk=self.widow.user_id)
        self.assertTrue(widow.is_pwd)  # came from needs_categories on the way forward
        self.assertEqual(widow.civil_status, 'Widowed')
        self.assertTrue(widow.is_senior, 'senior flag is recomputed from the birthdate')

        self.assertEqual(User.objects.get(pk=self.junk.user_id).civil_status, 'Single')
        self.assertFalse(User.objects.get(pk=self.junk.user_id).is_senior)
        self.assertEqual(User.objects.get(pk=self.separated.user_id).civil_status, 'Separated')

    def test_backward_leaves_resident_schema_step_reversible_too(self):
        self._migrate(AFTER)
        self._migrate(BEFORE)
        Resident = self._migrate(BEFORE).get_model('accounts', 'Resident')
        self.assertNotIn('gender', {f.name for f in Resident._meta.get_fields()})

    def test_round_trip_is_stable(self):
        self._migrate(AFTER)
        self._migrate(BEFORE)
        apps = self._migrate(AFTER)
        self.assertEqual(self._read(apps, self.married).civil_status, 'married')
        self.assertTrue(self._read(apps, self.married).is_4ps)
        self.assertTrue(self._read(apps, self.widow).is_pwd)
