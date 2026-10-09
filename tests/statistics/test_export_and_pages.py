import csv
import io

from django.template import Context, Template
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import Officer, PermissionRule, StaffAssignment, User
from apps.accounts.permissions import check_user_perm, seed_default_permissions
from apps.statistics import selectors
from apps.statistics.views import _safe_cell
from tests.base import (
    BaseTestCase, DEFAULT_PASSWORD, make_admin, make_document_type, make_resident_user, make_staff,
)
from tests.statistics.data import TEMP_MEDIA, seed


def parse_sections(response):
    """CSV body -> {TITLE: (header, rows)}."""
    text = response.content.decode('utf-8-sig')
    sections, current = {}, None
    for row in csv.reader(io.StringIO(text)):
        if not row:
            current = None
        elif current is None:
            current = sections.setdefault(row[0], {'header': None, 'rows': []})
        elif current['header'] is None:
            current['header'] = row
        else:
            current['rows'].append(row)
    return sections


def exporter():
    return make_staff({'statistics': ['view', 'export']})


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ExportTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = seed()

    def csv(self, **params):
        return self.client.get(reverse('statistics:export_excel'), params)

    def test_csv_requires_export_permission(self):
        self.login(make_staff({'statistics': ['view']}))
        self.assertEqual(self.csv().status_code, 403)
        self.assertEqual(self.client.get(reverse('statistics:export_pdf')).status_code, 403)

    def test_csv_denied_for_resident_and_anonymous(self):
        self.assertEqual(self.csv().status_code, 302)
        self.login(make_resident_user())
        self.assertEqual(self.csv().status_code, 403)

    def test_csv_download_headers(self):
        self.login(exporter())
        response = self.csv(**self.d['range'])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        disposition = response['Content-Disposition']
        self.assertIn('attachment', disposition)
        self.assertIn(self.d['range']['date_from'].replace('-', ''), disposition)
        self.assertIn(self.d['range']['date_to'].replace('-', ''), disposition)

    def test_csv_numbers_equal_the_api_numbers(self):
        self.login(exporter())
        sections = parse_sections(self.csv(**self.d['range']))
        report = selectors.build_report(selectors.parse_filters(self.d['range']))

        summary = {row[0]: row[1] for row in sections['SUMMARY']['rows']}
        s = report['summary']
        self.assertEqual(summary['Population'], str(s['population']))
        self.assertEqual(summary['Households'], str(s['households']))
        self.assertEqual(summary['Seniors (60+)'], str(s['seniors']))
        self.assertEqual(summary['Solo parents'], str(s['solo_parents']))
        self.assertEqual(summary['Revenue (PHP)'], s['revenue_total'])

        gender = {row[0]: row[1] for row in sections['GENDER']['rows']}
        self.assertEqual(gender, {r['label']: str(r['count']) for r in report['demographics']['gender']})

        civil = {row[0]: row[1] for row in sections['CIVIL STATUS']['rows']}
        self.assertEqual(civil, {r['label']: str(r['count']) for r in report['demographics']['civil_status']})

        density = sections['PUROK DENSITY']['rows']
        self.assertEqual(
            [(r[1], r[2], r[4]) for r in density],
            [(r['name'], str(r['households']), str(r['residents'])) for r in report['purok_density']['rows']])

        status = {row[0]: row[1] for row in sections['APPOINTMENTS BY STATUS']['rows']}
        self.assertEqual(status, {r['label']: str(r['count']) for r in report['appointments']['by_status']})

        months = sections['REVENUE BY MONTH']['rows']
        self.assertEqual(
            [(r[0], r[1], r[2]) for r in months[:-1]],
            [(m['label'], m['revenue'], str(m['count'])) for m in report['revenue']['months']])
        self.assertEqual(months[-1], ['TOTAL', report['revenue']['total'], str(report['revenue']['count'])])

    def test_csv_numbers_equal_the_json_api(self):
        self.login(make_admin())
        api = self.client.get(reverse('statistics:api_revenue'), self.d['range']).json()['data']
        sections = parse_sections(self.csv(**self.d['range']))
        self.assertEqual(sections['REVENUE BY MONTH']['rows'][-1][1], api['total'])
        api_pop = self.client.get(reverse('statistics:api_demographics'), self.d['range']).json()['data']
        summary = {row[0]: row[1] for row in sections['SUMMARY']['rows']}
        self.assertEqual(summary['Population'], str(api_pop['population']))

    def test_csv_respects_purok_filter(self):
        self.login(exporter())
        sections = parse_sections(self.csv(purok=self.d['alpha'].pk, **self.d['range']))
        summary = {row[0]: row[1] for row in sections['SUMMARY']['rows']}
        self.assertEqual((summary['Population'], summary['Revenue (PHP)']), ('3', '220.00'))

    def test_csv_invalid_filter_is_400(self):
        self.login(exporter())
        self.assertEqual(self.csv(date_from='bad').status_code, 400)
        self.assertEqual(self.client.get(reverse('statistics:export_pdf'), {'purok': 'x'}).status_code, 400)

    def test_formula_injection_is_neutralised(self):
        make_document_type('=HYPERLINK("http://evil","x")', fee='1.00')
        self.login(exporter())
        text = self.csv(**self.d['range']).content.decode('utf-8-sig')
        self.assertIn("'=HYPERLINK", text)
        for line in text.splitlines():
            self.assertFalse(line.startswith('=') or line.startswith('@'), line)

    def test_safe_cell(self):
        for raw in ('=1+1', '+1', '-1', '@x', '\tcmd'):
            self.assertEqual(_safe_cell(raw), "'" + raw)
        self.assertEqual(_safe_cell('Alpha'), 'Alpha')
        self.assertEqual(_safe_cell(5), 5)

    def test_print_report_renders_the_same_numbers(self):
        self.login(exporter())
        response = self.client.get(reverse('statistics:export_pdf'), self.d['range'])
        self.assertEqual(response.status_code, 200)
        report = selectors.build_report(selectors.parse_filters(self.d['range']))
        self.assertEqual(response.context['report']['summary'], report['summary'])
        self.assertContains(response, '255.00')
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'data-action="print"')
        self.assertNotContains(response, 'onclick=')

    def test_print_report_empty_database_renders(self):
        from apps.accounts.models import Resident
        Resident.objects.all().delete()
        self.login(exporter())
        self.assertEqual(self.client.get(reverse('statistics:export_pdf')).status_code, 200)


class OverviewPageTests(BaseTestCase):
    def test_overview_references_api_urls_and_local_assets(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'))
        self.assertEqual(response.status_code, 200)
        for name in ENDPOINT_NAMES:
            self.assertContains(response, f'"{reverse("statistics:" + name)}"')
        self.assertContains(response, '/static/vendor/chartjs/chart.umd.js')
        self.assertContains(response, '/static/js/statistics.js')
        self.assertContains(response, '/static/css/statistics.css')
        self.assertNotContains(response, 'cdn.jsdelivr')
        html = response.content.decode()
        self.assertNotIn('chart.js@', html)

    def test_overview_has_no_inline_script_from_this_module(self):
        self.login(make_staff({'statistics': ['view']}))
        html = self.client.get(reverse('statistics:overview')).content.decode()
        statistics_part = html[html.index('id="stats-root"'):]
        self.assertNotIn('onclick=', statistics_part)

    def test_view_only_user_sees_no_export_buttons(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'))
        self.assertNotContains(response, 'id="stats-export-csv"')
        self.assertNotContains(response, 'id="stats-export-print"')

    def test_exporter_sees_export_buttons(self):
        self.login(exporter())
        response = self.client.get(reverse('statistics:overview'))
        self.assertContains(response, 'id="stats-export-csv"')
        self.assertContains(response, 'id="stats-export-print"')

    def test_filter_bar_is_labelled_and_lists_puroks(self):
        from tests.base import make_purok
        purok = make_purok('Label Purok')
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'), {
            'date_from': '2026-01-01', 'date_to': '2026-02-01', 'purok': purok.pk})
        for field in ('stats-date-from', 'stats-date-to', 'stats-purok'):
            self.assertContains(response, f'<label for="{field}">')
        self.assertContains(response, 'value="2026-01-01"')
        self.assertContains(response, f'<option value="{purok.pk}" selected>Label Purok</option>')

    def test_invalid_filter_shows_message_not_an_error_page(self):
        self.login(make_staff({'statistics': ['view']}))
        response = self.client.get(reverse('statistics:overview'), {'date_from': 'junk'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'date_from must be an ISO date')

    def test_overview_denied(self):
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 302)
        self.login(make_resident_user())
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 403)
        self.client.logout()
        self.login(make_staff({'residents': ['view']}))
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 403)

    def test_old_system_edit_permission_no_longer_opens_statistics(self):
        self.login(make_staff({'system': ['edit']}))
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 403)

    def test_sidebar_link_follows_the_permission(self):
        link = f'href="{reverse("statistics:overview")}"'
        self.login(make_staff({'statistics': ['view']}))
        self.assertContains(self.client.get(reverse('appointments:list')), link)
        self.client.logout()
        self.login(make_staff({'residents': ['view']}))
        self.assertNotContains(self.client.get(reverse('appointments:list')), link)

    def test_user_can_tag(self):
        template = Template("{% load perm_tags %}{% user_can u 'statistics' 'view' as ok %}{{ ok }}")
        self.assertEqual(template.render(Context({'u': make_staff({'statistics': ['view']})})), 'True')
        self.assertEqual(template.render(Context({'u': make_staff({})})), 'False')


ENDPOINT_NAMES = ['api_summary', 'api_demographics', 'api_purok_density', 'api_appointments', 'api_revenue']


class DefaultRuleTests(BaseTestCase):
    """seed_default_permissions(): Punong Barangay all, Secretary view+export, others none."""

    def setUp(self):
        super().setUp()
        seed_default_permissions()

    def user_for(self, position, **officer_filter):
        officer = Officer.objects.filter(position=position, **officer_filter).first()
        user = User.objects.create_user(
            username=f'{position.replace(" ", "")}{officer.pk}', password=DEFAULT_PASSWORD,
            role=User.ROLE_STAFF, is_staff=True, is_approved=True, status=User.STATUS_ACTIVE)
        StaffAssignment.objects.create(user=user, officer=officer, scope_type='service_area', scope_value='all')
        return user

    def test_registry_lists_statistics_actions(self):
        from apps.accounts.permissions import registry
        self.assertEqual(registry.get_modules()['statistics'], ['export', 'view'])

    def test_punong_barangay_gets_all(self):
        user = self.user_for(Officer.POSITION_PUNONG_BARANGAY)
        self.assertTrue(check_user_perm(user, 'statistics', 'view'))
        self.assertTrue(check_user_perm(user, 'statistics', 'export'))

    def test_kapitan_role_uses_punong_barangay_rules(self):
        kapitan = User.objects.create_user(
            username='kap1', password=DEFAULT_PASSWORD, role=User.ROLE_KAPITAN, is_approved=True,
            status=User.STATUS_ACTIVE)
        self.assertTrue(check_user_perm(kapitan, 'statistics', 'view'))
        self.login(kapitan)
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 200)

    def test_secretary_gets_view_and_export(self):
        user = self.user_for(Officer.POSITION_SECRETARY)
        self.assertTrue(check_user_perm(user, 'statistics', 'view'))
        self.assertTrue(check_user_perm(user, 'statistics', 'export'))
        self.login(user)
        self.assertEqual(self.client.get(reverse('statistics:overview')).status_code, 200)
        self.assertEqual(self.client.get(reverse('statistics:export_excel')).status_code, 200)

    def test_nobody_else_gets_it(self):
        allowed = {Officer.POSITION_PUNONG_BARANGAY, Officer.POSITION_SECRETARY}
        rules = PermissionRule.objects.filter(module='statistics', allowed=True)
        self.assertEqual({r.officer.position for r in rules}, allowed)
        treasurer = self.user_for(Officer.POSITION_TREASURER)
        self.assertFalse(check_user_perm(treasurer, 'statistics', 'view'))
