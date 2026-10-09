"""Exact numbers from the seeded dataset in tests/statistics/data.py."""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.statistics import selectors
from tests.statistics.data import TEMP_MEDIA, seed


def by_code(rows):
    return {r['code']: r['count'] for r in rows}


def by_name(rows, key='name'):
    return {r[key]: r for r in rows}


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SeededStatisticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = seed()

    def filters(self, **params):
        return selectors.parse_filters({**self.d['range'], **params})

    # ---- demographics ----
    def test_population_excludes_archived(self):
        self.assertEqual(selectors.demographics(self.filters())['population'], 6)

    def test_gender_distribution(self):
        gender = by_code(selectors.demographics(self.filters())['gender'])
        self.assertEqual(gender, {'male': 2, 'female': 2, 'other': 1, 'unspecified': 1})

    def test_sectors(self):
        sectors = by_code(selectors.demographics(self.filters())['sectors'])
        self.assertEqual(sectors, {'senior': 2, 'pwd': 1, 'solo_parent': 1, '4ps': 2})

    def test_civil_status_uses_fixed_labels(self):
        rows = selectors.demographics(self.filters())['civil_status']
        self.assertEqual(by_code(rows), {
            'single': 2, 'married': 2, 'widowed': 1, 'separated': 1, 'divorced': 0})
        self.assertEqual({r['label'] for r in rows},
                         {'Single', 'Married', 'Widowed', 'Separated', 'Divorced'})

    def test_age_bands_and_minors(self):
        data = selectors.demographics(self.filters())
        self.assertEqual(by_code(data['age_bands']), {
            '0_17': 1, '18_29': 1, '30_44': 2, '45_59': 0, '60_plus': 2})
        self.assertEqual([r['label'] for r in data['age_bands']], ['0-17', '18-29', '30-44', '45-59', '60+'])
        self.assertEqual(data['minors'], 1)
        self.assertEqual(sum(r['count'] for r in data['age_bands']), data['population'])

    def test_purok_filter_limits_demographics(self):
        data = selectors.demographics(self.filters(purok=self.d['alpha'].pk))
        self.assertEqual(data['population'], 3)
        self.assertEqual(by_code(data['gender']), {'male': 1, 'female': 2, 'other': 0, 'unspecified': 0})
        self.assertEqual(by_code(data['sectors']), {'senior': 1, 'pwd': 1, 'solo_parent': 1, '4ps': 1})

    def test_dates_do_not_change_demographics(self):
        narrow = selectors.parse_filters({'date_from': '2001-01-01', 'date_to': '2001-02-01'})
        self.assertEqual(selectors.demographics(narrow)['population'], 6)

    # ---- purok density ----
    def test_purok_density_ranking_and_highest_flag(self):
        density = selectors.purok_density(self.filters())
        rows = by_name(density['rows'])
        self.assertEqual((density['total_residents'], density['total_households']), (6, 4))
        self.assertEqual((rows['Alpha']['households'], rows['Alpha']['residents']), (2, 3))
        self.assertEqual((rows['Beta']['households'], rows['Beta']['residents']), (1, 2))
        self.assertEqual((rows['Alpha']['rank'], rows['Beta']['rank']), (1, 2))
        self.assertTrue(rows['Alpha']['is_highest'])
        self.assertFalse(rows['Beta']['is_highest'])
        self.assertEqual(density['highest']['name'], 'Alpha')
        self.assertEqual(sum(1 for r in density['rows'] if r['is_highest']), 1)

    def test_purok_density_percentages(self):
        rows = by_name(selectors.purok_density(self.filters())['rows'])
        self.assertEqual((rows['Alpha']['pct_population'], rows['Alpha']['pct_households']), (50.0, 50.0))
        self.assertEqual((rows['Beta']['pct_population'], rows['Beta']['pct_households']), (33.3, 25.0))
        self.assertEqual((rows['Unassigned']['pct_population'], rows['Unassigned']['pct_households']), (16.7, 25.0))

    def test_unassigned_bucket_is_last_and_unranked(self):
        rows = selectors.purok_density(self.filters())['rows']
        last = rows[-1]
        self.assertEqual((last['name'], last['purok_id'], last['rank']), ('Unassigned', None, None))
        self.assertEqual((last['residents'], last['households']), (1, 1))
        self.assertFalse(last['is_highest'])

    def test_rows_are_sorted_descending_by_households(self):
        ranked = [r for r in selectors.purok_density(self.filters())['rows'] if r['rank']]
        keys = [(-r['households'], -r['residents']) for r in ranked]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual([r['rank'] for r in ranked], list(range(1, len(ranked) + 1)))

    def test_dead_household_is_not_counted(self):
        rows = by_name(selectors.purok_density(self.filters())['rows'])
        self.assertEqual(rows['Alpha']['households'], 2)

    def test_purok_filter_trims_rows_but_keeps_global_rank(self):
        density = selectors.purok_density(self.filters(purok=self.d['beta'].pk))
        self.assertEqual([r['name'] for r in density['rows']], ['Beta'])
        self.assertEqual(density['rows'][0]['rank'], 2)
        self.assertEqual(density['highest']['name'], 'Alpha')

    # ---- appointments ----
    def test_appointment_status_counts(self):
        appts = selectors.appointments(self.filters())
        self.assertEqual(appts['total'], 9)
        self.assertEqual(by_code(appts['by_status']), {
            'pending': 1, 'approved': 0, 'completed': 6, 'rejected': 1, 'no_show': 1})

    def test_category_document_type_and_service_counts(self):
        appts = selectors.appointments(self.filters())
        self.assertEqual(by_code(appts['by_category']), {'document': 8, 'healthcare': 1})
        docs = {r['name']: r['count'] for r in appts['by_document_type']}
        self.assertEqual((docs['Test Certificate'], docs['Test Permit']), (5, 3))
        services = {r['name']: r['count'] for r in appts['by_health_service']}
        self.assertEqual(services['Test Checkup'], 1)

    def test_catalog_is_zero_filled(self):
        from apps.appointments.models import DocumentType
        appts = selectors.appointments(self.filters())
        names = {r['name'] for r in appts['by_document_type']}
        self.assertTrue(set(DocumentType.objects.filter(is_active=True).values_list('name', flat=True)) <= names)

    def test_issued_documents_follow_the_date_range(self):
        self.assertEqual(selectors.appointments(self.filters())['issued_documents'], 5)
        default = selectors.appointments(selectors.parse_filters({}))
        self.assertEqual(default['issued_documents'], 5)  # a9 is 14 months back: outside both

    def test_purok_filter_limits_appointments(self):
        appts = selectors.appointments(self.filters(purok=self.d['alpha'].pk))
        self.assertEqual(appts['total'], 4)
        self.assertEqual(by_code(appts['by_status'])['completed'], 3)
        self.assertEqual(appts['issued_documents'], 2)
        beta = selectors.appointments(self.filters(purok=self.d['beta'].pk))
        self.assertEqual((beta['total'], beta['issued_documents']), (4, 2))

    def test_date_range_excludes_outside_appointments(self):
        narrow = selectors.parse_filters({
            'date_from': self.d['M'][0].isoformat(), 'date_to': date(
                self.d['today'].year, self.d['today'].month, 28).isoformat()})
        self.assertEqual(selectors.appointments(narrow)['total'], 4)  # a1 a5 a7 a10

    # ---- revenue ----
    def test_revenue_months_zero_filled_and_exact(self):
        rev = selectors.revenue(self.filters())
        M = self.d['M']
        months = {m['month']: m for m in rev['months']}
        self.assertEqual(len(rev['months']), 4)
        self.assertEqual(rev['months'][0]['month'], M[3].strftime('%Y-%m'))
        self.assertEqual((months[M[3].strftime('%Y-%m')]['revenue'], months[M[3].strftime('%Y-%m')]['count']), ('0.00', 0))
        self.assertEqual((months[M[2].strftime('%Y-%m')]['revenue'], months[M[2].strftime('%Y-%m')]['count']), ('25.00', 1))
        self.assertEqual((months[M[1].strftime('%Y-%m')]['revenue'], months[M[1].strftime('%Y-%m')]['count']), ('100.00', 2))
        self.assertEqual((months[M[0].strftime('%Y-%m')]['revenue'], months[M[0].strftime('%Y-%m')]['count']), ('130.00', 2))
        self.assertEqual((rev['total'], rev['count'], rev['currency']), ('255.00', 5, 'PHP'))

    def test_revenue_uses_snapshot_then_falls_back_to_document_fee(self):
        rev = selectors.revenue(self.filters())
        months = {m['month']: m['revenue'] for m in rev['months']}
        M = self.d['M']
        # a1: snapshot 120 beats the current fee 100; a3: free snapshot 0 beats the fee 25.
        self.assertEqual(months[M[0].strftime('%Y-%m')], '130.00')
        # a2 and a4 have no snapshot and use the document type fee.
        self.assertEqual(months[M[2].strftime('%Y-%m')], '25.00')

    def test_revenue_ignores_unfinished_and_health_appointments(self):
        rev = selectors.revenue(self.filters())
        self.assertEqual(rev['count'], 5)  # a5 pending, a6 rejected, a7 health, a8 no_show excluded

    def test_revenue_per_document_type(self):
        rows = {r['name']: r for r in selectors.revenue(self.filters())['by_document_type']}
        self.assertEqual((rows['Test Certificate']['revenue'], rows['Test Certificate']['count']), ('230.00', 3))
        self.assertEqual((rows['Test Permit']['revenue'], rows['Test Permit']['count']), ('25.00', 2))

    def test_revenue_purok_filter(self):
        rev = selectors.revenue(self.filters(purok=self.d['alpha'].pk))
        self.assertEqual((rev['total'], rev['count']), ('220.00', 2))

    def test_default_range_is_twelve_months_ending_this_month(self):
        rev = selectors.revenue(selectors.parse_filters({}))
        self.assertEqual(len(rev['months']), 12)
        self.assertEqual(rev['months'][-1]['month'], self.d['today'].strftime('%Y-%m'))
        self.assertEqual(rev['total'], '255.00')  # a9 (14 months back) is outside

    def test_month_labels(self):
        rev = selectors.revenue(self.filters())
        last = rev['months'][-1]
        self.assertEqual(last['label'], f"{self.d['today']:%b %Y}")

    # ---- summary ----
    def test_summary_is_derived_from_the_same_numbers(self):
        s = selectors.summary_block(self.filters())
        self.assertEqual(s['population'], 6)
        self.assertEqual(s['households'], 4)
        self.assertEqual((s['seniors'], s['pwd'], s['solo_parents'], s['four_ps'], s['minors']), (2, 1, 1, 2, 1))
        self.assertEqual((s['appointments_total'], s['appointments_pending'], s['appointments_completed']), (9, 1, 6))
        self.assertEqual((s['documents_issued'], s['revenue_total']), (5, '255.00'))

    def test_summary_households_follow_purok_filter(self):
        s = selectors.summary_block(self.filters(purok=self.d['alpha'].pk))
        self.assertEqual((s['population'], s['households']), (3, 2))

    def test_report_has_every_block(self):
        report = selectors.build_report(self.filters())
        self.assertEqual(
            set(report), {'filters', 'generated_at', 'summary', 'demographics', 'purok_density',
                          'appointments', 'revenue', 'blotter'})


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class RevenueDecimalTests(TestCase):
    def test_sum_is_exact_decimal(self):
        from tests.base import make_document_type, make_appointment
        from django.utils import timezone
        doc = make_document_type('Cents', fee='0.10')
        today = timezone.localdate()
        for _ in range(3):
            make_appointment(document_type=doc, appt_date=today, status='completed')
        rev = selectors.revenue(selectors.parse_filters({}))
        self.assertEqual(rev['total'], '0.30')


class EmptyDatabaseTests(TestCase):
    def test_everything_is_zero_without_errors(self):
        report = selectors.build_report(selectors.parse_filters({}))
        s = report['summary']
        for key, value in s.items():
            if key == 'currency':
                continue
            if key == 'settlement_rate':
                self.assertIsNone(value)  # no closed cases: no rate (not 0%)
                continue
            self.assertIn(value, (0, '0.00'), key)
        self.assertEqual(report['demographics']['population'], 0)
        self.assertEqual(sum(r['count'] for r in report['demographics']['gender']), 0)
        self.assertEqual(sum(r['count'] for r in report['demographics']['age_bands']), 0)

    def test_no_division_by_zero_in_density(self):
        density = selectors.purok_density(selectors.parse_filters({}))
        self.assertIsNone(density['highest'])
        for row in density['rows']:
            self.assertEqual((row['pct_population'], row['pct_households']), (0.0, 0.0))
            self.assertFalse(row['is_highest'])

    def test_revenue_series_is_still_twelve_zero_months(self):
        rev = selectors.revenue(selectors.parse_filters({}))
        self.assertEqual(len(rev['months']), 12)
        self.assertTrue(all(m['revenue'] == '0.00' and m['count'] == 0 for m in rev['months']))
        self.assertEqual((rev['total'], rev['count']), ('0.00', 0))


class ParseFilterTests(TestCase):
    def test_valid_filters(self):
        f = selectors.parse_filters({'date_from': '2026-01-15', 'date_to': '2026-03-31'})
        self.assertEqual((f.date_from, f.date_to, f.default_range), (date(2026, 1, 15), date(2026, 3, 31), False))

    def test_default_range_uses_the_manila_month(self):
        f = selectors.parse_filters({}, today=date(2026, 3, 10))
        self.assertEqual((f.date_from, f.date_to), (date(2025, 4, 1), date(2026, 3, 31)))
        self.assertTrue(f.default_range)

    def test_only_date_to_backs_up_twelve_months(self):
        f = selectors.parse_filters({'date_to': '2026-06-15'})
        self.assertEqual(f.date_from, date(2025, 7, 1))

    def test_invalid_values_raise_filter_error(self):
        bad = [
            {'date_from': 'yesterday'}, {'date_from': '2026-13-01'}, {'date_from': '2026-02-30'},
            {'date_from': '20260101'}, {'date_from': '2026-W01-1'}, {'date_to': '01/02/2026'},
            {'date_from': '2026-05-02', 'date_to': '2026-05-01'},
            {'date_from': '2000-01-01', 'date_to': '2026-01-01'},
            {'purok': 'abc'}, {'purok': '-1'}, {'purok': '1.5'}, {'purok': '999999'},
            {'purok': '9' * 30},
        ]
        for params in bad:
            with self.assertRaises(selectors.FilterError, msg=str(params)):
                selectors.parse_filters(params)

    def test_filter_error_is_a_value_error(self):
        self.assertTrue(issubclass(selectors.FilterError, ValueError))
