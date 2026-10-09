"""accounts 0016: BarangayInfo city/province, forwards and backwards."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('accounts', '0015_drop_user_demographics')]
AFTER = [('accounts', '0016_barangayinfo_city_province')]


class BarangayInfoMigrationTests(TransactionTestCase):

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

    def test_forwards_and_backwards(self):
        old_apps = self._migrate(BEFORE)
        Info = old_apps.get_model('accounts', 'BarangayInfo')
        Info.objects.create(id=1, name='Legacy Brgy')
        self.assertFalse(hasattr(Info, 'city'))

        new_apps = self._migrate(AFTER)
        Info = new_apps.get_model('accounts', 'BarangayInfo')
        row = Info.objects.get(id=1)
        self.assertEqual((row.name, row.city, row.province), ('Legacy Brgy', '', ''))
        row.city, row.province = 'Cebu City', 'Cebu'
        row.save()

        old_apps = self._migrate(BEFORE)
        Info = old_apps.get_model('accounts', 'BarangayInfo')
        self.assertEqual(Info.objects.get(id=1).name, 'Legacy Brgy')
        column_names = [f.name for f in Info._meta.get_fields()]
        self.assertNotIn('city', column_names)
        self.assertNotIn('province', column_names)
