"""
Stage 4: System Settings UI.

Every tab and sub-tab renders its data, the forms post to the real routes and come back
to the same tab/sub-tab, unchecked boxes really switch things off, system categories can
not be deleted from the UI, output is escaped, and the page is wired to the external JS.
"""
import io
import os
import re
import shutil
import tempfile
from decimal import Decimal
from unittest import mock
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import BarangayInfo, User
from apps.appointments.models import DocumentType, HealthCareService, Requirement
from apps.chat.models import ConcernCategory
from apps.communications.models import PostCategory
from tests.base import BaseTestCase, make_admin, make_staff, make_resident_user

EMPTY_TEXT = 'This section is currently empty'


def _target(response):
    parsed = urlparse(response['Location'])
    return parsed.path, {k: v[0] for k, v in parse_qs(parsed.query).items()}


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class SystemUITestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.login(self.admin)
        self.url = reverse('accounts:system_dashboard')

    def page(self, tab, subtab=None, **extra):
        query = f'?tab={tab}' + (f'&subtab={subtab}' if subtab else '')
        return self.client.get(self.url + query, **extra)


class TabRenderingTests(SystemUITestCase):

    def assertRenders(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, EMPTY_TEXT)

    def test_barangay_info_shows_saved_values(self):
        info = BarangayInfo.get_solo()
        info.name = 'Barangay Sampaguita'
        info.city = 'Iloilo City'
        info.province = 'Iloilo'
        info.contact_no = '09171234567'
        info.office_hours = 'Mon-Sat 7AM-4PM'
        info.venue = 'Covered Court'
        info.save()
        response = self.page('barangay_info')
        self.assertRenders(response)
        for text in ('Barangay Sampaguita', 'Iloilo City', 'Iloilo', '09171234567', 'Mon-Sat 7AM-4PM', 'Covered Court'):
            self.assertContains(response, text)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="logo"')
        self.assertContains(response, 'accept="image/*"')
        self.assertContains(response, 'Last updated')

    def test_barangay_info_logo_preview_only_when_set(self):
        response = self.page('barangay_info')
        self.assertNotContains(response, 'Current barangay logo')
        self.assertNotContains(response, 'name="clear_logo"')
        self.assertNotContains(response, 'src=""')
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with override_settings(MEDIA_ROOT=media):
            from PIL import Image
            buf = io.BytesIO()
            Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
            self.client.post(
                reverse('accounts:system_barangay_info_update'),
                {'name': 'Logo Barangay', 'logo': SimpleUploadedFile('l.png', buf.getvalue(), content_type='image/png')},
            )
            response = self.page('barangay_info')
        self.assertContains(response, 'Current barangay logo')
        self.assertContains(response, 'name="clear_logo"')

    def test_post_categories_table(self):
        PostCategory.objects.create(name='Fiesta News', order=7, expires=False, notify_on_post=True)
        PostCategory.objects.create(name='Hidden Topic', is_active=False)
        PostCategory.objects.create(name='Core Topic', is_system=True)
        response = self.page('post_categories')
        self.assertRenders(response)
        for text in ('Fiesta News', 'Hidden Topic', 'Core Topic', 'Inactive', 'System', 'fiesta_news'):
            self.assertContains(response, text)
        self.assertContains(response, 'data-action="new-post-category"')

    def test_documents_subtab_shows_price_table(self):
        doc = DocumentType.objects.create(name='Fishing Permit', code='fishing', fee=Decimal('75.50'), order=3)
        Requirement.objects.create(document_type=doc, name='Boat registration', order=1)
        DocumentType.objects.create(name='Free Certificate', code='freecert', fee=Decimal('0.00'), is_active=False)
        response = self.page('document_health', 'documents')
        self.assertRenders(response)
        self.assertContains(response, 'Fishing Permit')
        self.assertContains(response, '₱75.50')
        self.assertContains(response, 'Boat registration')
        self.assertContains(response, 'Free Certificate')
        self.assertContains(response, 'Free</td>')
        self.assertContains(response, 'Inactive')
        self.assertNotContains(response, 'Health Center Services')

    def test_health_subtab_shows_services_and_schedule_link(self):
        HealthCareService.objects.create(
            name='Dental Mission', available_date='Tue', available_time='8 AM - 12 PM', is_free=False,
        )
        HealthCareService.objects.create(name='Old Clinic', is_active=False)
        response = self.page('document_health', 'health')
        self.assertRenders(response)
        self.assertContains(response, 'Dental Mission')
        self.assertContains(response, 'Tue')
        self.assertContains(response, 'Paid')
        self.assertContains(response, 'Old Clinic')
        self.assertContains(response, 'Inactive')
        self.assertContains(response, reverse('appointments:schedule_manage'))
        self.assertNotContains(response, 'Document Price List')

    def test_document_health_defaults_to_documents_subtab(self):
        response = self.page('document_health')
        self.assertContains(response, 'Document Price List')
        self.assertEqual(response.context['active_subtab'], 'documents')

    def test_staff_subtab(self):
        staff = make_staff(first_name='Maria', last_name='Santos', position='Secretary')
        from datetime import date, timedelta
        soon = make_staff(first_name='Pedro', last_name='Reyes', term_end=date.today() + timedelta(days=10))
        response = self.page('user_management', 'staff')
        self.assertRenders(response)
        self.assertContains(response, 'Maria Santos')
        self.assertContains(response, 'Pedro Reyes')
        self.assertContains(response, 'Secretary')
        self.assertContains(response, 'Ending soon')
        self.assertContains(response, 'ending within 30 days')
        self.assertContains(response, reverse('accounts:officers_permissions'))
        self.assertContains(response, reverse('accounts:system_staff_account_disable', args=[staff.id]))
        self.assertContains(response, 'data-action="new-staff"')
        # own account can not be disabled from the UI
        self.assertNotContains(response, reverse('accounts:system_staff_account_disable', args=[self.admin.id]))

    def test_concerns_subtab(self):
        ConcernCategory.objects.create(
            name='Stray Animals', slug='stray-animals', routing_target_type='committee',
            routing_target_value='Peace and Order',
        )
        response = self.page('user_management', 'concerns')
        self.assertRenders(response)
        self.assertContains(response, 'Stray Animals')
        self.assertContains(response, 'Committee')
        self.assertContains(response, 'Peace and Order')
        self.assertNotContains(response, 'Staff Accounts</h2>')

    def test_email_templates_tab(self):
        response = self.page('email_templates')
        self.assertRenders(response)
        self.assertContains(response, 'Appointment Approved Notice')
        self.assertContains(response, 'data-action="email-preview"')
        self.assertContains(response, 'data-action="email-edit"')
        self.assertContains(response, 'id="emailEditModal"')
        self.assertContains(response, 'aria-live="polite"')

    def test_active_tab_and_subtab_highlighted(self):
        response = self.page('user_management', 'concerns')
        html = response.content.decode()
        self.assertEqual(len(re.findall(r'aria-current="page"', html)), 2)
        self.assertEqual(response.context['active_tab'], 'user_management')
        self.assertEqual(response.context['active_subtab'], 'concerns')

    def test_legacy_tab_names_still_resolve(self):
        response = self.client.get(self.url + '?tab=staff_accounts')
        self.assertEqual(response.context['active_tab'], 'user_management')
        self.assertEqual(response.context['active_subtab'], 'staff')


class WiringTests(SystemUITestCase):
    TABS = [
        ('barangay_info', None), ('post_categories', None), ('document_health', 'documents'),
        ('document_health', 'health'), ('user_management', 'staff'), ('user_management', 'concerns'),
        ('email_templates', None),
    ]

    def test_script_is_external_and_exists_on_disk(self):
        response = self.page('barangay_info')
        self.assertContains(response, 'js/system_settings.js')
        self.assertRegex(response.content.decode(), r'<script src="[^"]*system_settings\.js[^"]*" defer></script>')
        self.assertTrue(os.path.isfile(os.path.join(settings.BASE_DIR, 'static', 'js', 'system_settings.js')))

    def test_no_inline_handlers_or_inline_script_bodies(self):
        for tab, subtab in self.TABS:
            with self.subTest(tab=tab, subtab=subtab):
                html = self.page(tab, subtab).content.decode()
                self.assertNotRegex(html, r'\sonclick=')
                self.assertNotRegex(html, r'\sonsubmit=')
                page_scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
                for body in page_scripts:
                    self.assertNotIn('previewEmailTemplate', body)
                    self.assertNotIn('openPostCategoryModal', body)

    def test_config_element_has_resolved_endpoints(self):
        html = self.page('barangay_info').content.decode()
        self.assertIn('id="system-settings-config"', html)
        self.assertIn(reverse('accounts:system_post_category_create'), html)
        self.assertIn(reverse('accounts:system_email_preview', kwargs={'template_name': '__name__'}), html)
        self.assertIn(reverse('accounts:system_document_type_edit', kwargs={'doc_id': 0}), html)

    def test_forms_post_to_real_routes_with_csrf(self):
        PostCategory.objects.create(name='Plain Topic')
        DocumentType.objects.create(name='Plain Doc', code='plain')
        HealthCareService.objects.create(name='Plain Svc')
        ConcernCategory.objects.create(name='Plain Concern', slug='plain-concern')
        staff = make_staff()
        cat = PostCategory.objects.get(name='Plain Topic')
        doc = DocumentType.objects.get(name='Plain Doc')
        svc = HealthCareService.objects.get(name='Plain Svc')
        concern = ConcernCategory.objects.get(name='Plain Concern')
        expected = {
            ('barangay_info', None): [reverse('accounts:system_barangay_info_update')],
            ('post_categories', None): [
                reverse('accounts:system_post_category_create'),
                reverse('accounts:system_post_category_delete', args=[cat.id]),
            ],
            ('document_health', 'documents'): [
                reverse('accounts:system_document_type_create'),
                reverse('accounts:system_document_type_delete', args=[doc.id]),
            ],
            ('document_health', 'health'): [
                reverse('accounts:system_health_service_create'),
                reverse('accounts:system_health_service_delete', args=[svc.id]),
            ],
            ('user_management', 'staff'): [
                reverse('accounts:system_staff_account_create'),
                reverse('accounts:system_staff_account_disable', args=[staff.id]),
            ],
            ('user_management', 'concerns'): [
                reverse('accounts:system_concern_category_create'),
                reverse('accounts:system_concern_category_delete', args=[concern.id]),
            ],
        }
        for (tab, subtab), actions in expected.items():
            html = self.page(tab, subtab).content.decode()
            forms = re.findall(r'<form\b[^>]*>.*?</form>', html, re.S)
            self.assertTrue(forms)
            for form in forms:
                if 'method="post"' in form:
                    self.assertIn('csrfmiddlewaretoken', form, (tab, subtab))
            for action in actions:
                self.assertIn(f'action="{action}"', html, (tab, subtab, action))

    def test_every_input_has_a_label(self):
        for tab, subtab in self.TABS:
            html = self.page(tab, subtab).content.decode()
            ids = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', html))
            html = html[html.index('id="system-settings-config"'):]  # page content only, not the site chrome
            for match in re.finditer(r'<(input|select|textarea)\b([^>]*)>', html):
                attrs = match.group(2)
                kind = re.search(r'type="([^"]+)"', attrs)
                if kind and kind.group(1) in ('hidden', 'checkbox', 'submit'):
                    continue
                if 'name="csrfmiddlewaretoken"' in attrs or 'hidden' in attrs.split():
                    continue
                field_id = re.search(r'\bid="([^"]+)"', attrs)
                self.assertTrue(field_id and field_id.group(1) in ids, (tab, subtab, attrs))

    def test_no_safe_filter_in_template(self):
        path = os.path.join(settings.BASE_DIR, 'templates', 'accounts', 'system', 'system_dashboard.html')
        with open(path, encoding='utf-8') as fh:
            self.assertNotIn('|safe', fh.read())


class PermissionTests(SystemUITestCase):

    def test_resident_forbidden(self):
        self.logout()
        self.login(make_resident_user())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_without_system_view_forbidden(self):
        self.logout()
        self.login(make_staff(permissions={'appointments': ['view']}))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_view_only_staff_sees_data_but_no_edit_controls(self):
        PostCategory.objects.create(name='Visible Topic')
        self.logout()
        self.login(make_staff(permissions={'system': ['view']}))
        for tab, subtab in WiringTests.TABS:
            response = self.page(tab, subtab)
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertNotIn('data-action="new-', html)
            self.assertNotIn('data-action="edit-', html)
            self.assertNotIn('data-confirm=', html)
        response = self.page('post_categories')
        self.assertContains(response, 'Visible Topic')
        response = self.page('barangay_info')
        self.assertNotContains(response, 'Save Barangay Information')
        self.assertContains(response, '<fieldset disabled')

    def test_view_only_staff_post_endpoints_forbidden(self):
        self.logout()
        self.login(make_staff(permissions={'system': ['view']}))
        for name in ('system_barangay_info_update', 'system_post_category_create', 'system_document_type_create',
                     'system_health_service_create', 'system_concern_category_create', 'system_staff_account_create'):
            with self.subTest(route=name):
                self.assertEqual(self.client.post(reverse(f'accounts:{name}'), {'name': 'X'}).status_code, 403)
        self.assertFalse(PostCategory.objects.filter(name='X').exists())

    def test_staff_with_manage_permission_sees_only_that_control(self):
        self.logout()
        self.login(make_staff(permissions={'system': ['view', 'manage_categories']}))
        self.assertContains(self.page('post_categories'), 'data-action="new-post-category"')
        self.assertNotContains(self.page('document_health', 'documents'), 'data-action="new-document-type"')

    def test_csrf_enforced_on_settings_forms(self):
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        strict.login(username=self.admin.username, password='Str0ng-Test-Pass!')
        response = strict.post(reverse('accounts:system_post_category_create'), {'name': 'No Token'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PostCategory.objects.filter(name='No Token').exists())


class FormFlowTests(SystemUITestCase):
    """Posting each form through the client, exactly as the browser would."""

    def follow(self, response):
        return self.client.get(response['Location'])

    # --- Barangay info ------------------------------------------------------
    def test_barangay_info_update_redirects_and_shows_message(self):
        response = self.client.post(reverse('accounts:system_barangay_info_update'), {
            'name': 'Barangay Luntian', 'city': 'Cebu City', 'province': 'Cebu', 'address': 'Hall Road',
            'contact_no': '09181112222', 'office_hours': '8-5', 'venue': 'Plaza',
        })
        self.assertEqual(_target(response), (self.url, {'tab': 'barangay_info'}))
        page = self.follow(response)
        self.assertContains(page, 'Barangay Information updated successfully.')
        self.assertContains(page, 'Barangay Luntian')
        self.assertEqual(BarangayInfo.get_solo().city, 'Cebu City')

    def test_barangay_info_invalid_shows_error_and_keeps_data(self):
        before = BarangayInfo.get_solo().name
        response = self.client.post(reverse('accounts:system_barangay_info_update'), {'name': '  '})
        self.assertEqual(_target(response)[1], {'tab': 'barangay_info'})
        self.assertIn('Barangay name is required.', _messages(response))
        self.assertEqual(BarangayInfo.get_solo().name, before)

    def test_logo_upload_writes_to_media_root(self):
        from PIL import Image
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        buf = io.BytesIO()
        Image.new('RGB', (6, 6), 'blue').save(buf, 'PNG')
        with override_settings(MEDIA_ROOT=media):
            response = self.client.post(reverse('accounts:system_barangay_info_update'), {
                'name': 'With Logo',
                'logo': SimpleUploadedFile('seal.png', buf.getvalue(), content_type='image/png'),
            })
            self.assertEqual(response.status_code, 302)
            info = BarangayInfo.get_solo()
            self.assertTrue(info.logo)
            self.assertTrue(os.path.isfile(os.path.join(media, info.logo.name)))
            # remove logo checkbox
            self.client.post(reverse('accounts:system_barangay_info_update'), {'name': 'With Logo', 'clear_logo': '1'})
            self.assertFalse(BarangayInfo.get_solo().logo)

    # --- Post categories ----------------------------------------------------
    def test_post_category_create_update_delete(self):
        response = self.client.post(reverse('accounts:system_post_category_create'), {
            'name': 'Sports Fest', 'order': '4', 'default_end': 'end_of_month',
            'expires': ['0', '1'], 'notify_on_post': ['0', '1'], 'is_active': ['0', '1'],
        })
        self.assertEqual(_target(response), (self.url, {'tab': 'post_categories'}))
        cat = PostCategory.objects.get(name='Sports Fest')
        self.assertTrue(cat.expires and cat.notify_on_post and cat.is_active)
        self.assertEqual((cat.order, cat.default_end), (4, 'end_of_month'))
        self.assertContains(self.follow(response), 'Sports Fest')

        response = self.client.post(reverse('accounts:system_post_category_edit', args=[cat.id]), {
            'name': 'Sports Festival', 'order': '5', 'default_end': 'none',
            'expires': '0', 'notify_on_post': '0', 'is_active': '0',
        })
        self.assertEqual(_target(response)[1], {'tab': 'post_categories'})
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Sports Festival')
        self.assertFalse(cat.expires or cat.notify_on_post or cat.is_active)

        response = self.client.post(reverse('accounts:system_post_category_delete', args=[cat.id]))
        self.assertEqual(_target(response)[1], {'tab': 'post_categories'})
        self.assertFalse(PostCategory.objects.filter(id=cat.id).exists())

    def test_unchecked_checkbox_really_deactivates_and_page_shows_inactive(self):
        cat = PostCategory.objects.create(name='Toggle Me', is_active=True, expires=True, notify_on_post=True)
        # A browser posts only the hidden "0" when the box is unchecked.
        response = self.client.post(reverse('accounts:system_post_category_edit', args=[cat.id]), {
            'name': 'Toggle Me', 'order': '0', 'default_end': 'none',
            'expires': '0', 'notify_on_post': '0', 'is_active': '0',
        })
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)
        page = self.follow(response)
        row = re.search(r'<tr[^>]*>(?:(?!</tr>).)*Toggle Me(?:(?!</tr>).)*</tr>', page.content.decode(), re.S).group(0)
        self.assertIn('Inactive', row)

    def test_inactive_toggle_for_document_health_and_concern(self):
        doc = DocumentType.objects.create(name='Toggle Doc', code='tdoc', fee=Decimal('10.00'))
        svc = HealthCareService.objects.create(name='Toggle Svc')
        concern = ConcernCategory.objects.create(name='Toggle Concern', slug='toggle-concern')
        self.client.post(reverse('accounts:system_document_type_edit', args=[doc.id]),
                         {'name': 'Toggle Doc', 'fee': '10.00', 'is_active': '0'})
        self.client.post(reverse('accounts:system_health_service_edit', args=[svc.id]),
                         {'name': 'Toggle Svc', 'is_active': '0', 'is_free': '0'})
        self.client.post(reverse('accounts:system_concern_category_edit', args=[concern.id]),
                         {'name': 'Toggle Concern', 'is_active': '0'})
        doc.refresh_from_db(); svc.refresh_from_db(); concern.refresh_from_db()
        self.assertFalse(doc.is_active)
        self.assertFalse(svc.is_active)
        self.assertFalse(svc.is_free)
        self.assertFalse(concern.is_active)

    def test_system_category_cannot_be_deleted_from_ui(self):
        cat = PostCategory.objects.create(name='Protected Topic', is_system=True)
        html = self.page('post_categories').content.decode()
        self.assertNotIn(reverse('accounts:system_post_category_delete', args=[cat.id]), html)
        self.assertIn('System categories cannot be deleted', html)
        response = self.client.post(reverse('accounts:system_post_category_delete', args=[cat.id]))
        self.assertTrue(PostCategory.objects.filter(id=cat.id).exists())
        self.assertTrue(any('cannot be deleted' in m for m in _messages(response)))
        self.assertContains(self.follow(response), 'cannot be deleted')

    # --- Documents ----------------------------------------------------------
    def test_document_type_create_update_delete_returns_to_documents_subtab(self):
        response = self.client.post(reverse('accounts:system_document_type_create'), {
            'name': 'Business Permit', 'code': 'bizpermit', 'fee': '250.00', 'order': '2',
            'description': 'For shops', 'requirements_needed': 'DTI Registration\nLease contract',
            'is_active': ['0', '1'],
        })
        self.assertEqual(_target(response), (self.url, {'tab': 'document_health', 'subtab': 'documents'}))
        doc = DocumentType.objects.get(name='Business Permit')
        self.assertEqual(doc.fee, Decimal('250.00'))
        self.assertEqual(list(doc.requirements.values_list('name', flat=True)), ['DTI Registration', 'Lease contract'])
        page = self.follow(response)
        self.assertContains(page, '₱250.00')
        self.assertContains(page, 'DTI Registration')
        self.assertContains(page, 'aria-current="page"')
        self.assertEqual(page.context['active_subtab'], 'documents')

        response = self.client.post(reverse('accounts:system_document_type_edit', args=[doc.id]), {
            'name': 'Business Permit', 'code': 'bizpermit', 'fee': '0.00', 'order': '2',
            'requirements_needed': 'DTI Registration', 'is_active': '0',
        })
        doc.refresh_from_db()
        self.assertEqual(doc.fee, Decimal('0.00'))
        self.assertFalse(doc.is_active)
        self.assertEqual(_target(response)[1]['subtab'], 'documents')

        response = self.client.post(reverse('accounts:system_document_type_delete', args=[doc.id]))
        self.assertEqual(_target(response)[1], {'tab': 'document_health', 'subtab': 'documents'})
        self.assertFalse(DocumentType.objects.filter(id=doc.id).exists())

    def test_document_edit_modal_data_is_in_page(self):
        doc = DocumentType.objects.create(name='Edit Me', code='editme', fee=Decimal('12.00'), description='Desc text')
        Requirement.objects.create(document_type=doc, name='First req', order=1)
        Requirement.objects.create(document_type=doc, name='Second req', order=2)
        html = self.page('document_health', 'documents').content.decode()
        self.assertIn(f'id="doc-req-source-{doc.id}"', html)
        self.assertRegex(html, r'First req\s+Second req')
        self.assertIn('data-fee="12.00"', html)
        self.assertIn('Desc text', html)

    def test_invalid_fee_shows_error_message(self):
        response = self.client.post(reverse('accounts:system_document_type_create'), {'name': 'Bad Fee', 'fee': '-5'})
        self.assertEqual(_target(response)[1]['subtab'], 'documents')
        self.assertFalse(DocumentType.objects.filter(name='Bad Fee').exists())
        self.assertTrue(_messages(response))

    # --- Health -------------------------------------------------------------
    def test_health_service_create_update_delete_returns_to_health_subtab(self):
        response = self.client.post(reverse('accounts:system_health_service_create'), {
            'name': 'Blood Pressure Check', 'description': 'Walk in', 'available_date': 'Mon, Wed',
            'available_time': '9 AM - 11 AM', 'is_free': ['0', '1'], 'is_active': ['0', '1'],
        })
        self.assertEqual(_target(response), (self.url, {'tab': 'document_health', 'subtab': 'health'}))
        svc = HealthCareService.objects.get(name='Blood Pressure Check')
        self.assertTrue(svc.is_free and svc.is_active)
        page = self.follow(response)
        self.assertContains(page, 'Blood Pressure Check')
        self.assertContains(page, 'Mon, Wed')
        self.assertEqual(page.context['active_subtab'], 'health')

        response = self.client.post(reverse('accounts:system_health_service_edit', args=[svc.id]), {
            'name': 'Blood Pressure Check', 'available_date': 'Fri', 'is_free': '0', 'is_active': '0',
        })
        svc.refresh_from_db()
        self.assertEqual(svc.available_date, 'Fri')
        self.assertFalse(svc.is_free or svc.is_active)
        self.assertEqual(_target(response)[1]['subtab'], 'health')

        response = self.client.post(reverse('accounts:system_health_service_delete', args=[svc.id]))
        self.assertEqual(_target(response)[1], {'tab': 'document_health', 'subtab': 'health'})
        self.assertFalse(HealthCareService.objects.filter(id=svc.id).exists())

    # --- User management ----------------------------------------------------
    def test_concern_category_create_update_delete_returns_to_concerns_subtab(self):
        response = self.client.post(reverse('accounts:system_concern_category_create'), {
            'name': 'Noise Complaint', 'routing_target_type': 'committee',
            'routing_target_value': 'Peace and Order', 'is_active': ['0', '1'],
        })
        self.assertEqual(_target(response), (self.url, {'tab': 'user_management', 'subtab': 'concerns'}))
        cat = ConcernCategory.objects.get(name='Noise Complaint')
        self.assertEqual(cat.routing_target_type, 'committee')
        page = self.follow(response)
        self.assertContains(page, 'Noise Complaint')
        self.assertEqual(page.context['active_subtab'], 'concerns')

        self.client.post(reverse('accounts:system_concern_category_edit', args=[cat.id]), {
            'name': 'Noise Complaints', 'routing_target_type': 'service_area',
            'routing_target_value': 'Security', 'is_active': '0',
        })
        cat.refresh_from_db()
        self.assertEqual((cat.name, cat.routing_target_value, cat.is_active), ('Noise Complaints', 'Security', False))

        response = self.client.post(reverse('accounts:system_concern_category_delete', args=[cat.id]))
        self.assertEqual(_target(response)[1], {'tab': 'user_management', 'subtab': 'concerns'})
        self.assertFalse(ConcernCategory.objects.filter(id=cat.id).exists())

    def test_staff_create_and_disable_return_to_staff_subtab(self):
        from apps.accounts.models import Officer
        officer = Officer.objects.create(position='Treasurer')
        with mock.patch('apps.accounts.system_services.send_templated_email'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('accounts:system_staff_account_create'), {
                    'first_name': 'Lito', 'last_name': 'Garcia', 'email': 'lito@barangay.test',
                    'officer_id': officer.id, 'term_end': '2030-06-30',
                    'scope_type': 'service_area', 'scope_value': 'general',
                })
        self.assertEqual(_target(response), (self.url, {'tab': 'user_management', 'subtab': 'staff'}))
        user = User.objects.get(email='lito@barangay.test')
        self.assertEqual(user.role, User.ROLE_STAFF)
        page = self.follow(response)
        self.assertContains(page, 'Lito Garcia')
        self.assertContains(page, 'Treasurer')

        response = self.client.post(reverse('accounts:system_staff_account_disable', args=[user.id]))
        self.assertEqual(_target(response)[1], {'tab': 'user_management', 'subtab': 'staff'})
        user.refresh_from_db()
        self.assertEqual(user.status, User.STATUS_DISABLED)
        page = self.follow(response)
        self.assertNotContains(page, reverse('accounts:system_staff_account_disable', args=[user.id]))

    def test_disable_own_account_rejected(self):
        response = self.client.post(reverse('accounts:system_staff_account_disable', args=[self.admin.id]))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.status, User.STATUS_ACTIVE)
        self.assertTrue(_messages(response))


class EscapingTests(SystemUITestCase):

    PAYLOAD = '<script>alert(1)</script>'

    def test_post_category_name_is_escaped(self):
        PostCategory.objects.create(name=self.PAYLOAD)
        html = self.page('post_categories').content.decode()
        self.assertNotIn(self.PAYLOAD, html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)

    def test_other_user_data_is_escaped(self):
        DocumentType.objects.create(name=self.PAYLOAD, code='xss')
        HealthCareService.objects.create(name=self.PAYLOAD, description=self.PAYLOAD)
        ConcernCategory.objects.create(name=self.PAYLOAD, slug='xss', routing_target_value=self.PAYLOAD)
        make_staff(first_name=self.PAYLOAD, last_name='Tester')
        info = BarangayInfo.get_solo()
        info.name = self.PAYLOAD
        info.save()
        for tab, subtab in WiringTests.TABS:
            html = self.page(tab, subtab).content.decode()
            self.assertNotIn(self.PAYLOAD, html, (tab, subtab))

    def test_attribute_breakout_is_escaped(self):
        PostCategory.objects.create(name='x" onmouseover="alert(1)')
        html = self.page('post_categories').content.decode()
        self.assertNotIn('data-name="x" onmouseover', html)
        self.assertIn('&quot; onmouseover=&quot;', html)


class EmailFlowTests(SystemUITestCase):
    """The preview / edit flow used by the page (JSON endpoints, Stage 3 backend)."""

    def setUp(self):
        super().setUp()
        real_dir = os.path.join(settings.BASE_DIR, 'templates', 'emails')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in os.listdir(real_dir):
            if name.endswith('.txt'):
                shutil.copy(os.path.join(real_dir, name), os.path.join(self.tmp, name))
        patcher = mock.patch('apps.accounts.system_services.email_template_dir', return_value=self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_preview_edit_roundtrip_through_page_urls(self):
        html = self.page('email_templates').content.decode()
        preview_tpl = re.search(r'data-email-preview-url="([^"]+)"', html).group(1)
        edit_tpl = re.search(r'data-email-edit-url="([^"]+)"', html).group(1)
        self.assertIn('/__name__/', preview_tpl)
        preview = self.client.get(preview_tpl.replace('__name__', 'appt_approved'))
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()['body'])

        edit_url = edit_tpl.replace('__name__', 'appt_approved')
        source = self.client.get(edit_url).json()
        self.assertIn('subject', source)
        saved = self.client.post(
            edit_url, {'subject': 'Approved for you', 'body': 'Hello {{ first_name }}, see you.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['status'], 'success')
        self.assertEqual(self.client.get(edit_url).json()['subject'], 'Approved for you')

    def test_source_payload_flags_whether_template_has_a_subject(self):
        plain = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        reset = reverse('accounts:system_email_edit', kwargs={'template_name': 'password_reset_email'})
        self.assertTrue(self.client.get(plain).json()['has_subject'])
        self.assertFalse(self.client.get(reset).json()['has_subject'])

    def test_password_reset_template_saves_without_subject_line(self):
        reset = reverse('accounts:system_email_edit', kwargs={'template_name': 'password_reset_email'})
        body = 'Open this link to reset: {{ protocol }}://{{ domain }}'
        # The modal hides the subject for this template and sends only the body.
        saved = self.client.post(reset, {'body': body}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(saved.status_code, 200)
        with open(os.path.join(self.tmp, 'password_reset_email.txt'), encoding='utf-8') as handle:
            self.assertEqual(handle.read().strip(), body)

    def test_password_reset_template_ignores_a_posted_subject(self):
        reset = reverse('accounts:system_email_edit', kwargs={'template_name': 'password_reset_email'})
        saved = self.client.post(
            reset, {'subject': 'Should not be written', 'body': 'Reset your password.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(saved.status_code, 200)
        with open(os.path.join(self.tmp, 'password_reset_email.txt'), encoding='utf-8') as handle:
            text = handle.read()
        self.assertNotIn('Subject:', text)
        self.assertNotIn('Should not be written', text)

    def test_preview_only_staff_cannot_save_and_sees_no_edit_button(self):
        edit_url = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        with open(os.path.join(self.tmp, 'appt_approved.txt'), encoding='utf-8') as handle:
            before = handle.read()
        self.logout()
        self.login(make_staff(permissions={'system': ['view', 'preview_emails']}))
        html = self.page('email_templates').content.decode()
        self.assertIn('data-action="email-preview"', html)
        self.assertNotIn('data-action="email-edit"', html)
        self.assertNotIn('id="emailEditModal"', html)
        # Preview and reading the source still work.
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        saved = self.client.post(
            edit_url, {'subject': 'Hijacked', 'body': 'Nope'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(saved.status_code, 403)
        with open(os.path.join(self.tmp, 'appt_approved.txt'), encoding='utf-8') as handle:
            self.assertEqual(handle.read(), before)

    def test_staff_with_edit_and_preview_sees_edit_button_and_can_save(self):
        edit_url = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        self.logout()
        self.login(make_staff(permissions={'system': ['view', 'edit', 'preview_emails']}))
        html = self.page('email_templates').content.decode()
        self.assertIn('data-action="email-edit"', html)
        self.assertIn('id="emailEditModal"', html)
        saved = self.client.post(
            edit_url, {'subject': 'Approved', 'body': 'Hi {{ first_name }}'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(saved.status_code, 200)

    def test_edit_modal_subject_group_can_be_toggled(self):
        html = self.page('email_templates').content.decode()
        self.assertIn('id="ee-subject-group"', html)

    def test_error_from_edit_endpoint_is_json(self):
        edit_url = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        response = self.client.post(
            edit_url, {'subject': 'Oops', 'body': '{% if %}'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
