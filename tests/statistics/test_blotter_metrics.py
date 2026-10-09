"""
Blotter block of the Statistics module, with exact expected numbers.

Fixture (Asia/Manila times, range 2026-01-01 .. 2026-04-30):

    case  status            filed        settled/closed           purok  type
    c1    settled           Jan 05 10:00 Jan 15 10:00 (10 days)   Alpha  dispute
    c2    settled           Jan 10 08:00 Feb 01 00:30 (21.6875 d) Alpha  noise      (UTC: Jan 31)
    c3    settled           Feb 01 09:00 Feb 03 21:00 (2.5 days)  Beta   theft      confidential
    c4    escalated         Feb 05 09:00 closed Mar 01 10:00      Beta   physical_injury
    c5    dismissed         Mar 02 09:00 closed Mar 04 09:00      -      dispute
    c6    filed             Mar 10 09:00                          Alpha  dispute
    c7    under_mediation   Mar 20 09:00                          Alpha  noise
    c8    settled           Dec 20 2025  Jan 02 10:00             Alpha  other      (filed before range)

Filed in range: c1..c7 -> settled 3, closed 5 -> rate 60.0; avg days (10 + 21.6875 + 2.5) / 3 = 11.4.
Months: Jan filed 2 settled 2 (c1, c8) closed 2 -> 100.0; Feb filed 2 settled 2 (c2, c3) closed 2 -> 100.0;
        Mar filed 3 settled 0 closed 2 (c4, c5) -> 0.0; Apr all 0 -> None.
"""
import csv
import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.urls import reverse

from apps.statistics import selectors
from tests.base import BaseTestCase, make_blotter_case, make_purok, make_resident_user, make_staff
from tests.statistics.data import TEMP_MEDIA

MNL = ZoneInfo('Asia/Manila')
RANGE = {'date_from': '2026-01-01', 'date_to': '2026-04-30'}


def at(month, day, hour=9, minute=0, year=2026):
    return datetime(year, month, day, hour, minute, tzinfo=MNL)


def seed_blotter():
    alpha, beta = make_purok('Blotter Alpha'), make_purok('Blotter Beta')
    c = {}
    c[1] = make_blotter_case(status='settled', incident_type='dispute', purok=alpha, filed_at=at(1, 5, 10),
                             settled_at=at(1, 15, 10), closed_at=at(1, 15, 10))
    c[2] = make_blotter_case(status='settled', incident_type='noise', purok=alpha, filed_at=at(1, 10, 8),
                             settled_at=at(2, 1, 0, 30), closed_at=at(2, 1, 0, 30))
    c[3] = make_blotter_case(status='settled', incident_type='theft', purok=beta, filed_at=at(2, 1, 9),
                             settled_at=at(2, 3, 21), closed_at=at(2, 3, 21), is_confidential=True,
                             narrative='Very private narrative', parties=[('complainant', 'Secret Person'),
                                                                          ('respondent', 'Hidden Person')])
    c[4] = make_blotter_case(status='escalated', incident_type='physical_injury', purok=beta, filed_at=at(2, 5),
                             escalated_at=at(3, 1, 10), closed_at=at(3, 1, 10))
    c[5] = make_blotter_case(status='dismissed', incident_type='dispute', purok=None, filed_at=at(3, 2),
                             closed_at=at(3, 4))
    c[6] = make_blotter_case(status='filed', incident_type='dispute', purok=alpha, filed_at=at(3, 10))
    c[7] = make_blotter_case(status='under_mediation', incident_type='noise', purok=alpha, filed_at=at(3, 20))
    c[8] = make_blotter_case(status='settled', incident_type='other', purok=alpha, filed_at=at(12, 20, year=2025),
                             settled_at=at(1, 2, 10), closed_at=at(1, 2, 10))
    return {'alpha': alpha, 'beta': beta, 'cases': c}


def counts(rows, key='code'):
    return {row[key]: row['count'] for row in rows}


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BlotterMetricsTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = seed_blotter()

    def block(self, **extra):
        return selectors.blotter(selectors.parse_filters({**RANGE, **extra}))

    def test_headline_numbers(self):
        b = self.block()
        self.assertEqual((b['total'], b['open'], b['settled'], b['closed']), (7, 2, 3, 5))
        self.assertEqual(b['settlement_rate'], 60.0)
        self.assertEqual(b['avg_days_to_settle'], 11.4)

    def test_by_status_type_purok(self):
        b = self.block()
        self.assertEqual(counts(b['by_status']), {
            'filed': 1, 'under_mediation': 1, 'settled': 3, 'escalated': 1, 'dismissed': 1, 'withdrawn': 0})
        self.assertEqual(counts(b['by_type']), {
            'dispute': 3, 'noise': 2, 'theft': 1, 'physical_injury': 1, 'property_damage': 0, 'domestic': 0,
            'threat': 0, 'trespassing': 0, 'other': 0})
        purok = counts(b['by_purok'], 'name')
        self.assertEqual(purok['Blotter Alpha'], 4)
        self.assertEqual(purok['Blotter Beta'], 2)
        self.assertEqual(purok['Unassigned'], 1)

    def test_monthly_series(self):
        months = [(m['month'], m['filed'], m['settled'], m['closed'], m['settlement_rate']) for m in self.block()['months']]
        self.assertEqual(months, [
            ('2026-01', 2, 2, 2, 100.0),
            ('2026-02', 2, 2, 2, 100.0),
            ('2026-03', 3, 0, 2, 0.0),
            ('2026-04', 0, 0, 0, None),
        ])
        self.assertEqual(self.block()['months'][0]['label'], 'Jan 2026')

    def test_purok_filter(self):
        b = self.block(purok=self.d['alpha'].pk)
        self.assertEqual((b['total'], b['settled'], b['closed'], b['settlement_rate']), (4, 2, 2, 100.0))
        self.assertEqual(b['avg_days_to_settle'], round((10 + 21.6875) / 2, 1))
        self.assertEqual([r['name'] for r in b['by_purok']], ['Blotter Alpha'])
        # c8 (Alpha, filed 2025) still counts as settled in January.
        self.assertEqual(b['months'][0]['settled'], 2)

    def test_summary_includes_blotter(self):
        summary = selectors.summary_block(selectors.parse_filters(RANGE))
        self.assertEqual(summary['blotter_cases'], 7)
        self.assertEqual(summary['settlement_rate'], 60.0)

    def test_api(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:api_blotter'), RANGE)
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['settlement_rate'], 60.0)
        self.assertEqual(data['total'], 7)
        self.assertEqual(self.client.get(reverse('statistics:api_blotter'), {'date_from': 'x'}).status_code, 400)

    def test_api_leaks_no_case_details(self):
        self.login(make_staff({'statistics': ['view']}))
        text = json.dumps(self.client.get(reverse('statistics:api_blotter'), RANGE).json())
        for secret in ('BLT-', 'Very private', 'Secret Person', 'Hidden Person', 'Sample narrative', 'Complainant'):
            self.assertNotIn(secret, text)

    def test_api_auth(self):
        url = reverse('statistics:api_blotter')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.login(make_resident_user())
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.login(make_staff({'blotter': ['view']}))  # blotter rights do not open statistics
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_csv_sections(self):
        self.login(make_staff({'statistics': ['view', 'export']}))
        text = self.client.get(reverse('statistics:export_excel'), RANGE).content.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text)))
        titles = [r[0] for r in rows if len(r) == 1]
        for title in ('BLOTTER BY STATUS', 'BLOTTER BY TYPE', 'BLOTTER BY PUROK', 'BLOTTER MONTHLY'):
            self.assertIn(title, titles)
        self.assertIn(['Blotter settlement rate (%)', '60.0'], rows)
        self.assertIn(['Average days to settle', '11.4'], rows)
        self.assertIn(['Settled', '3'], rows)
        self.assertIn(['Jan 2026', '2', '2', '2', '100.0'], rows)
        self.assertIn(['Apr 2026', '0', '0', '0', ''], rows)
        self.assertNotIn('Secret Person', text)
        self.assertNotIn('BLT-', text)

    def test_print_report(self):
        self.login(make_staff({'statistics': ['view', 'export']}))
        response = self.client.get(reverse('statistics:export_pdf'), RANGE)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td class="num" id="print-settlement-rate">60.0%</td>', html=False)
        self.assertContains(response, 'Blotter (Katarungang Pambarangay)')
        self.assertNotContains(response, 'Secret Person')

    def test_overview_has_blotter_card(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'))
        self.assertContains(response, f'data-api-blotter="{reverse("statistics:api_blotter")}"')
        self.assertContains(response, 'data-kpi="settlement_rate"')
        self.assertContains(response, 'data-chart="blotter"')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BlotterEmptyStateTests(BaseTestCase):
    def test_empty(self):
        b = selectors.blotter(selectors.parse_filters(RANGE))
        self.assertEqual((b['total'], b['open'], b['settled'], b['closed']), (0, 0, 0, 0))
        self.assertIsNone(b['settlement_rate'])
        self.assertIsNone(b['avg_days_to_settle'])
        self.assertTrue(all(r['count'] == 0 for r in b['by_status'] + b['by_type'] + b['by_purok']))
        self.assertEqual(len(b['months']), 4)
        self.assertTrue(all(m['filed'] == m['settled'] == m['closed'] == 0 and m['settlement_rate'] is None
                            for m in b['months']))

    def test_empty_exports_render(self):
        self.login(make_staff({'statistics': ['view', 'export']}))
        self.assertEqual(self.client.get(reverse('statistics:export_excel'), RANGE).status_code, 200)
        response = self.client.get(reverse('statistics:export_pdf'), RANGE)
        self.assertContains(response, '<td class="num" id="print-settlement-rate">-</td>', html=False)

    def test_statistics_js_renders_blotter(self):
        from pathlib import Path
        from django.conf import settings
        source = (Path(settings.BASE_DIR) / 'static' / 'js' / 'statistics.js').read_text(encoding='utf-8')
        self.assertIn('function renderBlotter', source)
        self.assertIn("['blotter', renderBlotter]", source)
        self.assertNotIn('.innerHTML', source)
