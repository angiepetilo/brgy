"""accounts 0017: statistics permission rules for existing officers, forwards and backwards."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('accounts', '0016_barangayinfo_city_province')]
AFTER = [('accounts', '0017_seed_statistics_permissions')]


class StatisticsPermissionMigrationTests(TransactionTestCase):
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

    def _rules(self, apps, position):
        PermissionRule = apps.get_model('accounts', 'PermissionRule')
        return set(
            PermissionRule.objects.filter(officer__position=position, module='statistics', allowed=True)
            .values_list('action', flat=True)
        )

    def test_forwards_and_backwards(self):
        old = self._migrate(BEFORE)
        Officer = old.get_model('accounts', 'Officer')
        PermissionRule = old.get_model('accounts', 'PermissionRule')
        Officer.objects.all().delete()
        pb = Officer.objects.create(position='Punong Barangay')
        sec = Officer.objects.create(position='Secretary')
        Officer.objects.create(position='Treasurer')
        Officer.objects.create(position='Kagawad', committee='Health')
        PermissionRule.objects.create(officer=sec, module='residents', action='view', allowed=True)
        # An administrator who turned a rule off before the migration must keep that choice.
        PermissionRule.objects.create(officer=sec, module='statistics', action='export', allowed=False)

        new = self._migrate(AFTER)
        self.assertEqual(self._rules(new, 'Punong Barangay'), {'view', 'export'})
        self.assertEqual(self._rules(new, 'Secretary'), {'view'})
        NewRule = new.get_model('accounts', 'PermissionRule')
        self.assertFalse(NewRule.objects.get(officer__position='Secretary', action='export').allowed)
        self.assertFalse(NewRule.objects.filter(module='statistics', officer__position__in=['Treasurer', 'Kagawad']).exists())
        self.assertEqual(NewRule.objects.filter(officer=pb.pk, module='statistics').count(), 2)

        old = self._migrate(BEFORE)
        OldRule = old.get_model('accounts', 'PermissionRule')
        self.assertFalse(OldRule.objects.filter(module='statistics').exists())
        self.assertTrue(OldRule.objects.filter(module='residents', action='view').exists())

    def test_no_officers_is_a_noop(self):
        old = self._migrate(BEFORE)
        old.get_model('accounts', 'Officer').objects.all().delete()
        new = self._migrate(AFTER)
        self.assertEqual(new.get_model('accounts', 'PermissionRule').objects.filter(module='statistics').count(), 0)
        self._migrate(BEFORE)
