import json

from django.test import override_settings
from django.urls import reverse

from tests.base import BaseTestCase, make_admin, make_resident_user, make_staff
from tests.statistics.data import TEMP_MEDIA, seed

ENDPOINTS = {
    'api_summary': {'population', 'households', 'seniors', 'pwd', 'solo_parents', 'four_ps',
                    'appointments_pending', 'revenue_total', 'currency'},
    'api_demographics': {'population', 'minors', 'gender', 'sectors', 'civil_status', 'age_bands'},
    'api_purok_density': {'total_residents', 'total_households', 'highest', 'rows'},
    'api_appointments': {'total', 'by_status', 'by_category', 'by_document_type',
                         'by_health_service', 'issued_documents'},
    'api_revenue': {'currency', 'total', 'count', 'months', 'by_document_type'},
}


def viewer():
    return make_staff({'statistics': ['view']})


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class StatisticsApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = seed()

    def get(self, name, **params):
        return self.client.get(reverse(f'statistics:{name}'), params)

    def test_route_paths(self):
        self.assertEqual(reverse('statistics:api_summary'), '/statistics/api/summary/')
        self.assertEqual(reverse('statistics:api_purok_density'), '/statistics/api/purok-density/')

    def test_each_endpoint_returns_documented_shape(self):
        self.login(viewer())
        for name, keys in ENDPOINTS.items():
            response = self.get(name)
            self.assertEqual(response.status_code, 200, name)
            self.assertEqual(response['Content-Type'], 'application/json')
            self.assertEqual(response['Cache-Control'], 'no-store')
            body = response.json()
            self.assertEqual(set(body), {'filters', 'generated_at', 'data'}, name)
            self.assertTrue(keys <= set(body['data']), f'{name}: {keys - set(body["data"])}')
            self.assertEqual(set(body['filters']), {'date_from', 'date_to', 'purok', 'purok_name', 'default_range'})

    def test_admin_is_allowed(self):
        self.login(make_admin())
        self.assertEqual(self.get('api_summary').status_code, 200)

    def test_default_filters_are_echoed(self):
        self.login(viewer())
        filters = self.get('api_summary').json()['filters']
        self.assertTrue(filters['default_range'])
        self.assertIsNone(filters['purok'])

    def test_values_match_the_seeded_dataset(self):
        self.login(viewer())
        data = self.get('api_summary', **self.d['range']).json()['data']
        self.assertEqual((data['population'], data['households'], data['revenue_total']), (6, 4, '255.00'))

    def test_purok_filter_changes_results(self):
        self.login(viewer())
        everyone = self.get('api_demographics', **self.d['range']).json()['data']['population']
        alpha = self.get('api_demographics', purok=self.d['alpha'].pk, **self.d['range'])
        self.assertEqual(alpha.json()['filters']['purok_name'], 'Alpha')
        self.assertEqual((everyone, alpha.json()['data']['population']), (6, 3))
        revenue = self.get('api_revenue', purok=self.d['alpha'].pk, **self.d['range']).json()['data']
        self.assertEqual(revenue['total'], '220.00')

    def test_date_filter_changes_results(self):
        self.login(viewer())
        data = self.get('api_appointments', date_from=self.d['M'][0].isoformat(),
                        date_to=self.d['range']['date_to']).json()['data']
        self.assertEqual(data['total'], 4)

    def test_invalid_filters_return_400_json(self):
        self.login(viewer())
        bad = [
            {'date_from': 'nope'}, {'date_to': '2026-02-30'},
            {'date_from': '2026-05-02', 'date_to': '2026-05-01'},
            {'purok': 'x'}, {'purok': '424242'},
        ]
        for name in ENDPOINTS:
            for params in bad:
                response = self.get(name, **params)
                self.assertEqual(response.status_code, 400, (name, params))
                self.assertEqual(response['Content-Type'], 'application/json')
                self.assertIn('error', response.json())
                self.assertEqual(response['Cache-Control'], 'no-store')

    def test_denied_without_statistics_view(self):
        for user in (make_staff({'statistics': ['export']}), make_staff({'residents': ['view']}),
                     make_resident_user()):
            self.client.logout()
            self.login(user)
            for name in ENDPOINTS:
                self.assertEqual(self.get(name).status_code, 403, (user.role, name))

    def test_anonymous_gets_401_json_with_login_url(self):
        # Stage A8: API callers get 401 JSON (not a login redirect) so the page can
        # show "session expired" instead of a JSON parse error.
        for name in ENDPOINTS:
            response = self.get(name)
            self.assertEqual(response.status_code, 401)
            self.assertTrue(response.json()['requires_login'])
            self.assertIn('/accounts/login/', response.json()['login_url'])

    def test_non_get_methods_are_rejected(self):
        self.login(viewer())
        url = reverse('statistics:api_summary')
        for method in ('post', 'put', 'delete'):
            self.assertEqual(getattr(self.client, method)(url).status_code, 405, method)

    def test_response_is_valid_json_without_html(self):
        self.login(viewer())
        text = self.get('api_demographics').content.decode()
        json.loads(text)
