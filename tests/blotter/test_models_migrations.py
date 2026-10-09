"""Blotter models (choices, TRANSITIONS) and the 0006 permission data migration."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from apps.accounts.permissions import registry
from apps.blotter.models import BlotterCase, BlotterParty
from tests.blotter.common import ALL_ACTIONS

BEFORE = [('blotter', '0005_blotter_schema')]
AFTER = [('blotter', '0006_seed_blotter_permissions')]


class ModelConstantsTests(SimpleTestCase):
    def test_incident_type_choices(self):
        self.assertEqual(
            [code for code, _ in BlotterCase.INCIDENT_TYPE_CHOICES],
            ['dispute', 'noise', 'theft', 'physical_injury', 'property_damage', 'domestic', 'threat',
             'trespassing', 'other'])

    def test_status_choices_and_default(self):
        self.assertEqual(
            [code for code, _ in BlotterCase.STATUS_CHOICES],
            ['filed', 'under_mediation', 'settled', 'escalated', 'dismissed', 'withdrawn'])
        self.assertEqual(BlotterCase._meta.get_field('status').default, 'filed')

    def test_transitions_map(self):
        self.assertEqual(BlotterCase.TRANSITIONS, {
            'filed': ('under_mediation', 'dismissed', 'withdrawn'),
            'under_mediation': ('settled', 'escalated', 'withdrawn'),
            'settled': (), 'escalated': (), 'dismissed': (), 'withdrawn': (),
        })
        self.assertEqual(BlotterCase.TERMINAL, {'settled', 'escalated', 'dismissed', 'withdrawn'})

    def test_party_roles(self):
        self.assertEqual([c for c, _ in BlotterParty.ROLE_CHOICES], ['complainant', 'respondent', 'witness'])

    def test_case_no_is_unique_and_not_editable(self):
        field = BlotterCase._meta.get_field('case_no')
        self.assertTrue(field.unique)
        self.assertFalse(field.editable)
        self.assertEqual(field.max_length, 20)

    def test_party_contact_uses_ph_mobile_validator(self):
        from apps.core.validators import validate_ph_mobile
        self.assertIn(validate_ph_mobile, BlotterParty._meta.get_field('contact_no').validators)

    def test_registry_lists_blotter_actions(self):
        self.assertEqual(registry.get_modules()['blotter'], sorted(ALL_ACTIONS))


class BlotterPermissionMigrationTests(TransactionTestCase):
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

    @staticmethod
    def _rules(apps, **officer):
        PermissionRule = apps.get_model('accounts', 'PermissionRule')
        return set(
            PermissionRule.objects.filter(module='blotter', allowed=True, **{f'officer__{k}': v for k, v in officer.items()})
            .values_list('action', flat=True)
        )

    def test_forwards_and_backwards(self):
        old = self._migrate(BEFORE)
        Officer = old.get_model('accounts', 'Officer')
        PermissionRule = old.get_model('accounts', 'PermissionRule')
        Officer.objects.all().delete()
        Officer.objects.create(position='Punong Barangay')
        sec = Officer.objects.create(position='Secretary')
        Officer.objects.create(position='Kagawad', committee='Peace and Order')
        Officer.objects.create(position='Kagawad', committee='Health')
        Officer.objects.create(position='Tanod')
        Officer.objects.create(position='Treasurer')
        PermissionRule.objects.create(officer=sec, module='residents', action='view', allowed=True)
        # A rule an administrator switched off before the migration keeps that choice.
        PermissionRule.objects.create(officer=sec, module='blotter', action='edit', allowed=False)

        new = self._migrate(AFTER)
        self.assertEqual(self._rules(new, position='Punong Barangay'), set(ALL_ACTIONS))
        self.assertEqual(self._rules(new, position='Secretary'), {'view', 'create'})
        self.assertEqual(self._rules(new, position='Kagawad', committee='Peace and Order'),
                         {'view', 'create', 'edit', 'mediate', 'settle', 'escalate'})
        self.assertEqual(self._rules(new, position='Tanod'), {'view', 'create'})
        self.assertEqual(self._rules(new, position='Kagawad', committee='Health'), set())
        self.assertEqual(self._rules(new, position='Treasurer'), set())
        NewRule = new.get_model('accounts', 'PermissionRule')
        self.assertFalse(NewRule.objects.get(officer__position='Secretary', module='blotter', action='edit').allowed)
        self.assertEqual(NewRule.objects.filter(module='blotter').count(), 8 + 3 + 6 + 2)

        old = self._migrate(BEFORE)
        OldRule = old.get_model('accounts', 'PermissionRule')
        self.assertFalse(OldRule.objects.filter(module='blotter').exists())
        self.assertTrue(OldRule.objects.filter(module='residents', action='view').exists())

    def test_no_officers_is_a_noop(self):
        old = self._migrate(BEFORE)
        old.get_model('accounts', 'Officer').objects.all().delete()
        new = self._migrate(AFTER)
        self.assertEqual(new.get_model('accounts', 'PermissionRule').objects.filter(module='blotter').count(), 0)
        self._migrate(BEFORE)

    def test_schema_migration_reverses(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([('blotter', None)])
        self.assertNotIn('blotter_blottercase', connection.introspection.table_names())
        self._migrate(AFTER)
        tables = connection.introspection.table_names()
        for table in ('blotter_blottercase', 'blotter_blotterparty', 'blotter_blotterhearing'):
            self.assertIn(table, tables)
