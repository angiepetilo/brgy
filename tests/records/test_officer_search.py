"""Records hub: Officer search must use real Officer fields (regression: FieldError on `title`)."""
from django.urls import reverse

from apps.accounts.models import Officer
from tests.base import BaseTestCase, get_document_type, make_admin, make_appointment, make_health_service, make_resident_user


class OfficerSearchTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.login(self.admin)
        self.kagawad_user = make_resident_user(first_name='Lorna', last_name='Mercado', username='lmercado')
        self.secretary_user = make_resident_user(first_name='Pedro', last_name='Santos', username='psantos')
        self.kagawad = Officer.objects.create(
            position=Officer.POSITION_KAGAWAD, committee='Health and Sanitation', user=self.kagawad_user,
        )
        self.secretary = Officer.objects.create(
            position=Officer.POSITION_SECRETARY, committee='Records', user=self.secretary_user,
        )
        self.url = reverse('records:hub')

    def _search(self, term):
        resp = self.client.get(self.url, {'tab': 'officers', 'q': term})
        self.assertEqual(resp.status_code, 200)
        return set(resp.context['officers'])

    def test_search_by_position(self):
        self.assertEqual(self._search('kagawad'), {self.kagawad})

    def test_search_by_committee(self):
        self.assertEqual(self._search('sanitation'), {self.kagawad})

    def test_search_by_assigned_user_first_name_last_name_and_username(self):
        self.assertEqual(self._search('Pedro'), {self.secretary})
        self.assertEqual(self._search('Mercado'), {self.kagawad})
        self.assertEqual(self._search('psantos'), {self.secretary})

    def test_search_without_match_is_empty_not_an_error(self):
        self.assertEqual(self._search('zzz-no-such-officer'), set())

    def test_document_and_health_tabs_search_and_order_by_appt_date(self):
        doc_type = get_document_type('clearance', 'Barangay Clearance')
        service = make_health_service(name='Dental Cleaning')
        resident = make_resident_user()
        make_appointment(
            resident=resident, category='healthcare', healthcare_service=service,
            status='completed', days_ahead=2, purpose='older', processed_by=self.admin,
        )
        make_appointment(
            resident=resident, category='healthcare', healthcare_service=service,
            status='completed', days_ahead=9, purpose='newer', processed_by=self.admin,
        )
        resp = self.client.get(self.url, {'tab': 'document_health', 'subtab': 'health'})
        self.assertEqual(resp.status_code, 200)
        purposes = [a.purpose for a in resp.context['health_page']]
        self.assertEqual(purposes, ['newer', 'older'])

        resp = self.client.get(self.url, {'tab': 'document_health', 'subtab': 'documents', 'q': doc_type.name})
        self.assertEqual(resp.status_code, 200)
