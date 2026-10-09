"""Blotter HTML pages: filters, pagination, per-role buttons, IDOR, forms, print, sidebar."""
import re
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import StaffAssignment
from apps.accounts.permissions import seed_default_permissions
from apps.blotter.models import BlotterCase
from tests.base import BaseTestCase, make_admin, make_blotter_case, make_purok, make_resident_user, make_staff
from tests.blotter.common import form_post, seeded_user

FULL = ['view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential']


class ListPageTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.login(make_staff({'blotter': ['view']}))

    def listed(self, **params):
        response = self.client.get(reverse('blotter:case_list'), params)
        self.assertEqual(response.status_code, 200)
        return [c.pk for c in response.context['page_obj'].object_list]

    def test_filters(self):
        purok = make_purok('View Filter Purok')
        old = make_blotter_case(incident_date=date(2026, 1, 10), incident_type='theft', status='settled', purok=purok)
        new = make_blotter_case(incident_date=date(2026, 3, 5),
                                parties=[('complainant', 'Rosario Quimpo'), ('respondent', 'Benito Tan')])
        self.assertEqual(self.listed(status='settled'), [old.pk])
        self.assertEqual(self.listed(incident_type='theft'), [old.pk])
        self.assertEqual(self.listed(purok=purok.pk), [old.pk])
        self.assertEqual(self.listed(date_from='2026-03-01'), [new.pk])
        self.assertEqual(self.listed(date_from='2026-01-01', date_to='2026-01-31'), [old.pk])
        self.assertEqual(self.listed(q='quimpo'), [new.pk])
        self.assertEqual(self.listed(q=old.case_no), [old.pk])
        self.assertEqual(set(self.listed()), {old.pk, new.pk})

    def test_pagination(self):
        for _ in range(21):
            make_blotter_case()
        self.assertEqual(len(self.listed()), 20)
        response = self.client.get(reverse('blotter:case_list'), {'page': 2, 'status': 'filed'})
        self.assertEqual(len(response.context['page_obj'].object_list), 1)
        self.assertContains(response, 'Page 2 of 2')
        self.assertContains(response, 'href="?status=filed&amp;page=1"')

    def test_bad_filter_shows_message(self):
        response = self.client.get(reverse('blotter:case_list'), {'status': 'nope'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'status is not a valid case status.')

    def test_empty_state(self):
        self.assertContains(self.client.get(reverse('blotter:case_list')), 'id="blotter-empty"')

    def test_create_button_needs_create(self):
        self.assertNotContains(self.client.get(reverse('blotter:case_list')), 'id="blotter-new-case"')


class AccessTests(BaseTestCase):
    def test_anonymous_redirects_and_resident_403(self):
        case = make_blotter_case()
        urls = [reverse('blotter:case_list'), reverse('blotter:case_create'),
                reverse('blotter:case_detail', args=[case.pk]), reverse('blotter:case_print', args=[case.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.login(make_resident_user())
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_idor_out_of_scope_and_confidential_give_404(self):
        make_purok('Idor Mine')
        theirs = make_blotter_case(purok=make_purok('Idor Theirs'))
        secret = make_blotter_case(is_confidential=True, purok=make_purok('Idor Mine'))
        user = make_staff({'blotter': FULL[:-1]}, scope_type=StaffAssignment.SCOPE_PUROK, scope_value='Idor Mine')
        self.login(user)
        for case in (theirs, secret):
            for name in ('case_detail', 'case_print', 'case_edit'):
                self.assertEqual(self.client.get(reverse(f'blotter:{name}', args=[case.pk])).status_code, 404, name)
            for name, data in (('case_transition', {'to_status': 'dismissed'}),
                               ('hearing_add', {'scheduled_at': '2026-01-01T10:00'}),
                               ('case_delete', {})):
                self.assertEqual(self.client.post(reverse(f'blotter:{name}', args=[case.pk]), data).status_code, 404)
            case.refresh_from_db()
            self.assertEqual(case.status, 'filed')

    def test_sidebar_link_follows_permission(self):
        link = f'href="{reverse("blotter:case_list")}"'
        self.login(make_staff({'blotter': ['view']}))
        self.assertContains(self.client.get(reverse('appointments:list')), link)
        self.client.logout()
        self.login(make_staff({'residents': ['view']}))
        self.assertNotContains(self.client.get(reverse('appointments:list')), link)
        self.client.logout()
        self.login(make_resident_user())
        self.assertNotContains(self.client.get(reverse('appointments:list')), link)


class DetailButtonTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        seed_default_permissions()
        self.case = make_blotter_case()

    def detail(self, user):
        self.client.logout()
        self.login(user)
        response = self.client.get(reverse('blotter:case_detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        return re.findall(r'data-transition="(\w+)"', response.content.decode()), response

    def test_buttons_per_role(self):
        self.assertEqual(self.detail(seeded_user('Kagawad', 'Peace and Order'))[0],
                         ['under_mediation', 'dismissed', 'withdrawn'])
        self.assertEqual(self.detail(seeded_user('Secretary'))[0], ['dismissed', 'withdrawn'])
        buttons, response = self.detail(seeded_user('Tanod'))
        self.assertEqual(buttons, [])
        self.assertNotContains(response, 'id="blotter-transitions"')
        self.assertNotContains(response, 'id="blotter-edit-link"')
        self.assertNotContains(response, 'id="blotter-hearing-form"')

    def test_delete_and_hearing_controls(self):
        _buttons, response = self.detail(seeded_user('Punong Barangay'))
        self.assertContains(response, 'id="blotter-delete"')
        self.assertContains(response, 'id="blotter-hearing-form"')
        _buttons, response = self.detail(seeded_user('Kagawad', 'Peace and Order'))
        self.assertNotContains(response, 'id="blotter-delete"')
        self.assertContains(response, 'id="blotter-hearing-form"')

    def test_closed_case_has_no_actions(self):
        self.case.status = 'settled'
        self.case.save()
        buttons, response = self.detail(seeded_user('Punong Barangay'))
        self.assertEqual(buttons, [])
        self.assertNotContains(response, 'id="blotter-hearing-form"')
        self.assertNotContains(response, 'id="blotter-edit-link"')


class FormTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = make_staff({'blotter': ['view', 'create', 'edit', 'mediate']})
        self.login(self.user)

    def test_form_renders_party_rows_and_template(self):
        response = self.client.get(reverse('blotter:case_create'))
        self.assertContains(response, 'id="party-row-template"')
        self.assertContains(response, 'name="parties-TOTAL_FORMS" value="3"')
        self.assertContains(response, 'data-phone')
        self.assertContains(response, '/static/js/blotter.js')
        self.assertNotContains(response, 'name="is_confidential"')

    def test_create_via_form(self):
        response = self.client.post(reverse('blotter:case_create'), form_post())
        case = BlotterCase.objects.get()
        self.assertRedirects(response, reverse('blotter:case_detail', args=[case.pk]))
        self.assertEqual(sorted(case.parties.values_list('full_name', flat=True)), ['Lorna Diaz', 'Ramon Uy'])

    def test_phone_error_is_shown(self):
        response = self.client.post(reverse('blotter:case_create'), form_post(**{'parties-0-contact_no': '0917 123 4567'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter an 11-digit mobile number starting with 09')
        self.assertFalse(BlotterCase.objects.exists())

    def test_missing_respondent_is_shown(self):
        response = self.client.post(reverse('blotter:case_create'), form_post(**{'parties-1-full_name': ''}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add at least one respondent.')

    def test_edit_and_transition_and_hearing(self):
        case = make_blotter_case()
        page = self.client.get(reverse('blotter:case_edit', args=[case.pk]))
        self.assertContains(page, f'Edit case {case.case_no}')
        self.assertNotContains(page, 'party-row-template')
        data = form_post(location='Edited location')
        response = self.client.post(reverse('blotter:case_edit', args=[case.pk]), data)
        self.assertRedirects(response, reverse('blotter:case_detail', args=[case.pk]))
        case.refresh_from_db()
        self.assertEqual(case.location, 'Edited location')

        response = self.client.post(reverse('blotter:case_transition', args=[case.pk]), {'to_status': 'under_mediation'})
        self.assertRedirects(response, reverse('blotter:case_detail', args=[case.pk]))
        case.refresh_from_db()
        self.assertEqual(case.status, 'under_mediation')

        when = (timezone.localdate() + timedelta(days=1)).isoformat() + 'T09:30'
        self.client.post(reverse('blotter:hearing_add', args=[case.pk]),
                         {'scheduled_at': when, 'outcome_notes': 'Set for mediation.', 'complainant_attended': 'on'})
        self.assertEqual(case.hearings.count(), 1)
        page = self.client.get(reverse('blotter:case_detail', args=[case.pk]))
        self.assertContains(page, 'Status: Filed -&gt; Under mediation')
        self.assertContains(page, 'Set for mediation.')

    def test_illegal_transition_shows_message(self):
        case = make_blotter_case()
        response = self.client.post(reverse('blotter:case_transition', args=[case.pk]),
                                    {'to_status': 'withdrawn'}, follow=True)
        self.assertEqual(response.status_code, 200)
        case.refresh_from_db()
        self.assertEqual(case.status, 'withdrawn')
        response = self.client.post(reverse('blotter:case_transition', args=[case.pk]),
                                    {'to_status': 'dismissed'}, follow=True)
        self.assertContains(response, 'cannot be moved to dismissed')


class PrintAndTemplateTests(BaseTestCase):
    def test_print_page(self):
        case = make_blotter_case(narrative='Printed narrative text.')
        self.login(make_admin())
        response = self.client.get(reverse('blotter:case_print', args=[case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, case.case_no)
        self.assertContains(response, 'Printed narrative text.')
        self.assertContains(response, '/static/css/blotter_print.css')
        self.assertContains(response, 'data-action="print"')

    def test_templates_have_no_inline_js(self):
        folder = Path(settings.BASE_DIR) / 'templates' / 'blotter'
        for path in folder.glob('*.html'):
            source = path.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'<script(?![^>]*\bsrc=)[^>]*>', source), path.name)
            self.assertIsNone(re.search(r'\son[a-z]+\s*=', source), path.name)

    def test_print_css_has_print_media(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'blotter_print.css').read_text(encoding='utf-8')
        self.assertIn('@media print', css)
