"""B6: accounts 0019 / appointments 0018 normalize stored phone numbers (data only)."""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('accounts', '0018_phone_validators'), ('appointments', '0017_applicant_phone_validator')]
AFTER = [('accounts', '0019_normalize_phone_numbers'), ('appointments', '0018_normalize_applicant_phone')]

CASES = {
    'dash': ('0917-111-2222', '09171112222'),
    'plus63': ('+63 917 111 2222', '09171112222'),
    'sixty3': ('639171112222', '09171112222'),
    'valid': ('09472750431', '09472750431'),
    'blank': ('', ''),
    'garbage': ('call the hall', 'call the hall'),
    'short': ('0917-111', '0917-111'),
}


class PhoneNormalizeMigrationTests(TransactionTestCase):

    def setUp(self):
        super().setUp()
        self.old_apps = self._migrate(BEFORE)
        User = self.old_apps.get_model('accounts', 'User')
        Resident = self.old_apps.get_model('accounts', 'Resident')
        Appointment = self.old_apps.get_model('appointments', 'Appointment')
        self.users, self.residents, self.appts = {}, {}, {}
        for i, (key, (raw, _)) in enumerate(CASES.items()):
            self.users[key] = User.objects.create(username=f'ph{i}', email=f'ph{i}@example.com', phone_number=raw)
            self.residents[key] = Resident.objects.create(
                first_name=key, last_name='Phone', birthdate=date(1990, 1, 1), contact_no=raw)
            self.appts[key] = Appointment.objects.create(
                reference_no=f'APT-PH-{i}', category='healthcare', purpose='x', appt_date=date(2026, 1, 5),
                time_window='morning', status='pending', applicant_phone=raw)

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

    def test_forward_normalizes_and_keeps_invalid_values(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertLogs('apps.migrations', level='WARNING') as logs:
            apps = self._migrate(AFTER)
        User = apps.get_model('accounts', 'User')
        Resident = apps.get_model('accounts', 'Resident')
        Appointment = apps.get_model('appointments', 'Appointment')
        for key, (_raw, expected) in CASES.items():
            with self.subTest(key=key):
                self.assertEqual(User.objects.get(pk=self.users[key].pk).phone_number, expected)
                self.assertEqual(Resident.objects.get(pk=self.residents[key].pk).contact_no, expected)
                self.assertEqual(Appointment.objects.get(pk=self.appts[key].pk).applicant_phone, expected)
        # Rows are never deleted.
        self.assertEqual(Resident.objects.filter(last_name='Phone').count(), len(CASES))
        # Invalid ids are reported (printed and logged) for every table.
        report = out.getvalue() + '\n'.join(logs.output)
        for table, rows in (('User', self.users), ('Resident', self.residents), ('Appointment', self.appts)):
            self.assertIn(f'.{table}.', report)
            self.assertIn(str(rows['garbage'].pk), report)
            self.assertIn(str(rows['short'].pk), report)

    def test_reverse_is_a_noop(self):
        self._migrate(AFTER)
        apps = self._migrate(BEFORE)
        User = apps.get_model('accounts', 'User')
        self.assertEqual(User.objects.get(pk=self.users['dash'].pk).phone_number, '09171112222')
