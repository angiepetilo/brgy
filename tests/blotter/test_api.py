"""Blotter JSON API: auth, validation, create, transition, list filters and rate limit."""
import json
import re

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import StaffAssignment
from apps.blotter.models import BlotterCase
from tests.base import BaseTestCase, make_admin, make_blotter_case, make_purok, make_resident_user, make_staff
from tests.blotter.common import api_payload, form_post

FULL = ['view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential']


class ApiTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')


class AuthTests(ApiTestCase):
    def test_anonymous_gets_401_json(self):
        case = make_blotter_case()
        for url, method in ((reverse('blotter:api_list'), 'get'),
                            (reverse('blotter:api_detail', args=[case.pk]), 'get'),
                            (reverse('blotter:api_create'), 'post'),
                            (reverse('blotter:api_transition', args=[case.pk]), 'post')):
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 401, url)
            self.assertTrue(response.json()['requires_login'])

    def test_resident_gets_403_json(self):
        self.login(make_resident_user())
        response = self.client.get(reverse('blotter:api_list'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(self.post_json(reverse('blotter:api_create'), api_payload()).status_code, 403)

    def test_create_needs_create_permission(self):
        self.login(make_staff({'blotter': ['view']}))
        self.assertEqual(self.post_json(reverse('blotter:api_create'), api_payload()).status_code, 403)
        self.assertFalse(BlotterCase.objects.exists())

    def test_wrong_methods(self):
        self.login(make_admin())
        self.assertEqual(self.client.get(reverse('blotter:api_create')).status_code, 405)
        self.assertEqual(self.client.post(reverse('blotter:api_list')).status_code, 405)


class CreateTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_staff({'blotter': ['view', 'create']})
        self.login(self.user)
        self.url = reverse('blotter:api_create')

    def test_create_returns_201_with_case_no(self):
        response = self.post_json(self.url, api_payload())
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertRegex(body['case_no'], r'^BLT-\d{4}-0001$')
        self.assertEqual(body['status'], 'filed')
        case = BlotterCase.objects.get(pk=body['id'])
        self.assertEqual(case.parties.count(), 2)
        self.assertEqual(case.recorded_by, self.user)

    def test_create_with_form_encoding(self):
        response = self.client.post(self.url, form_post())
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(BlotterCase.objects.get().parties.count(), 2)

    def test_missing_fields_400(self):
        response = self.post_json(self.url, {'parties': []})
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        for field in ('incident_type', 'incident_date', 'location', 'narrative'):
            self.assertIn(field, errors)

    def test_invalid_json_400(self):
        response = self.client.post(self.url, data='{not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('__all__', response.json()['errors'])
        response = self.client.post(self.url, data='[1, 2]', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_bad_choice_and_date_400(self):
        response = self.post_json(self.url, api_payload(incident_type='riot', incident_date='2026-13-40'))
        errors = response.json()['errors']
        self.assertEqual(response.status_code, 400)
        self.assertIn('incident_type', errors)
        self.assertIn('incident_date', errors)

    def test_parties_must_be_a_list(self):
        response = self.post_json(self.url, api_payload(parties={'role': 'complainant'}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('parties', response.json()['errors'])

    def test_party_phone_validation_400(self):
        payload = api_payload()
        payload['parties'][1]['contact_no'] = '0917-123-4567'
        response = self.post_json(self.url, payload)
        self.assertEqual(response.status_code, 400)
        parties = response.json()['errors']['parties']
        self.assertEqual(parties[0], {})
        self.assertIn('11-digit', parties[1]['contact_no'][0])
        self.assertFalse(BlotterCase.objects.exists())

    def test_missing_respondent_400(self):
        payload = api_payload()
        payload['parties'] = payload['parties'][:1]
        response = self.post_json(self.url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['parties'], ['Add at least one respondent.'])

    def test_confidential_field_ignored_without_view_confidential(self):
        response = self.post_json(self.url, api_payload(is_confidential=True))
        self.assertEqual(response.status_code, 201)
        self.assertFalse(BlotterCase.objects.get().is_confidential)

    def test_out_of_scope_purok_rejected(self):
        make_purok('Api Own')
        other = make_purok('Api Other')
        tanod = make_staff({'blotter': ['view', 'create']}, scope_type=StaffAssignment.SCOPE_PUROK,
                           scope_value='Api Own')
        self.client.logout()
        self.login(tanod)
        response = self.post_json(self.url, api_payload(purok=other.pk))
        # The purok select only offers the user's own puroks, so this is a field error.
        self.assertEqual(response.status_code, 400)
        self.assertIn('purok', response.json()['errors'])

    @override_settings(RATE_LIMITS={'blotter_create': '2/h'})
    def test_create_is_rate_limited(self):
        self.assertEqual(self.post_json(self.url, api_payload()).status_code, 201)
        self.assertEqual(self.post_json(self.url, api_payload()).status_code, 201)
        response = self.post_json(self.url, api_payload())
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(BlotterCase.objects.count(), 2)


class ListDetailTransitionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_staff({'blotter': FULL})
        self.login(self.user)

    def test_list_paginates_20(self):
        for _ in range(23):
            make_blotter_case()
        first = self.client.get(reverse('blotter:api_list')).json()
        self.assertEqual((first['count'], first['num_pages'], len(first['results'])), (23, 2, 20))
        second = self.client.get(reverse('blotter:api_list'), {'page': 2}).json()
        self.assertEqual(len(second['results']), 3)
        self.assertEqual(self.client.get(reverse('blotter:api_list'), {'page': 9}).status_code, 400)
        self.assertEqual(self.client.get(reverse('blotter:api_list'), {'page': 'x'}).status_code, 400)

    def test_list_filters(self):
        purok = make_purok('Api Filter Purok')
        a = make_blotter_case(status='settled', incident_type='theft', purok=purok)
        make_blotter_case(parties=[('complainant', 'Unique Zenaida'), ('respondent', 'Someone')])
        url = reverse('blotter:api_list')
        ids = lambda params: [r['id'] for r in self.client.get(url, params).json()['results']]  # noqa: E731
        self.assertEqual(ids({'status': 'settled'}), [a.pk])
        self.assertEqual(ids({'incident_type': 'theft'}), [a.pk])
        self.assertEqual(ids({'purok': purok.pk}), [a.pk])
        self.assertEqual(len(ids({'q': 'zenaida'})), 1)
        self.assertEqual(ids({'q': a.case_no}), [a.pk])

    def test_bad_filters_400(self):
        url = reverse('blotter:api_list')
        for params in ({'status': 'open'}, {'incident_type': 'x'}, {'purok': 'abc'},
                       {'date_from': '01/01/2026'}, {'date_from': '2026-02-01', 'date_to': '2026-01-01'},
                       {'q': 'x' * 101}):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn('error', response.json())

    def test_detail(self):
        case = make_blotter_case()
        body = self.client.get(reverse('blotter:api_detail', args=[case.pk])).json()
        self.assertEqual(body['case_no'], case.case_no)
        self.assertEqual(body['allowed_transitions'], ['under_mediation', 'dismissed', 'withdrawn'])
        self.assertEqual(len(body['parties']), 2)

    def test_detail_404_when_not_visible(self):
        make_purok('Api Mine')
        theirs = make_blotter_case(purok=make_purok('Api Theirs'))
        secret = make_blotter_case(is_confidential=True)
        viewer = make_staff({'blotter': ['view']}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Api Mine')
        self.client.logout()
        self.login(viewer)
        for case in (theirs, secret):
            response = self.client.get(reverse('blotter:api_detail', args=[case.pk]))
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(self.client.get(reverse('blotter:api_detail', args=[999999])).status_code, 404)

    def test_transition_ok(self):
        case = make_blotter_case()
        response = self.post_json(reverse('blotter:api_transition', args=[case.pk]), {'to_status': 'under_mediation'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'under_mediation')
        response = self.post_json(reverse('blotter:api_transition', args=[case.pk]),
                                  {'to_status': 'settled', 'notes': 'Signed.'})
        body = response.json()
        self.assertEqual(body['status'], 'settled')
        self.assertIsNotNone(body['settled_at'])
        self.assertEqual(body['closed_at'], body['settled_at'])

    def test_transition_illegal_400(self):
        case = make_blotter_case()
        response = self.post_json(reverse('blotter:api_transition', args=[case.pk]), {'to_status': 'settled'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('to_status', response.json()['errors'])

    def test_transition_validation_400(self):
        case = make_blotter_case()
        for payload in ({}, {'to_status': 'bogus'}):
            response = self.post_json(reverse('blotter:api_transition', args=[case.pk]), payload)
            self.assertEqual(response.status_code, 400, payload)

    def test_transition_without_permission_403(self):
        case = make_blotter_case()
        self.client.logout()
        self.login(make_staff({'blotter': ['view', 'create']}))
        response = self.post_json(reverse('blotter:api_transition', args=[case.pk]), {'to_status': 'dismissed'})
        self.assertEqual(response.status_code, 403)
        case.refresh_from_db()
        self.assertEqual(case.status, 'filed')

    def test_transition_out_of_scope_404(self):
        case = make_blotter_case(is_confidential=True)
        self.client.logout()
        self.login(make_staff({'blotter': ['view', 'edit']}))
        response = self.post_json(reverse('blotter:api_transition', args=[case.pk]), {'to_status': 'dismissed'})
        self.assertEqual(response.status_code, 404)

    def test_list_hides_confidential_without_permission(self):
        make_blotter_case(is_confidential=True)
        visible = make_blotter_case()
        self.client.logout()
        self.login(make_staff({'blotter': ['view']}))
        results = self.client.get(reverse('blotter:api_list')).json()['results']
        self.assertEqual([r['id'] for r in results], [visible.pk])
        self.assertFalse(any(re.search('narrative', json.dumps(r)) for r in results))
