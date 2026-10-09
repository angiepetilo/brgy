"""
Stage 3: System Settings backend.

Covers checkbox parsing through the real views, canonical redirect targets, error
handling (no leaked exception text), BarangayInfo city/province and clearing, email
template validation/whitelist/audit, delete-missing-object handling, RBAC per action
and audit rows for every write.
"""
import io
import os
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

from apps.accounts import system_services
from apps.accounts.models import BarangayInfo, User
from apps.accounts.system_utils import parse_bool, safe_int, with_unchecked_checkboxes
from apps.appointments.models import DocumentType, HealthCareService
from apps.chat.models import ConcernCategory
from apps.communications.models import PostCategory
from apps.history.models import ActivityLog
from tests.base import (
    BaseTestCase, make_admin, make_staff, make_resident_user, make_document_type,
    make_health_service, make_appointment, make_resident_profile, _n,
)


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def _redirect_target(response):
    parsed = urlparse(response['Location'])
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return parsed.path, query


class ParseBoolTests(BaseTestCase):

    def test_true_values(self):
        for raw in ('on', 'ON', 'true', 'True', '1', 'yes', ' Yes ', True):
            self.assertTrue(parse_bool({'k': raw}, 'k', False), raw)

    def test_false_values(self):
        for raw in ('off', 'false', 'False', '0', 'no', 'NO', '', False):
            self.assertFalse(parse_bool({'k': raw}, 'k', True), raw)

    def test_missing_key_and_unknown_values_use_default(self):
        self.assertTrue(parse_bool({}, 'k', True))
        self.assertFalse(parse_bool({}, 'k', False))
        self.assertTrue(parse_bool({'k': None}, 'k', True))
        self.assertTrue(parse_bool({'k': 'maybe'}, 'k', True))
        self.assertFalse(parse_bool({'k': 'maybe'}, 'k', False))

    def test_hidden_input_pattern_last_value_wins(self):
        from django.http import QueryDict
        unchecked = QueryDict('is_active=0')
        checked = QueryDict('is_active=0&is_active=1')
        self.assertFalse(parse_bool(unchecked, 'is_active', True))
        self.assertTrue(parse_bool(checked, 'is_active', False))

    def test_with_unchecked_checkboxes_fills_only_missing(self):
        from django.http import QueryDict
        data = with_unchecked_checkboxes(QueryDict('is_active=1'), ('is_active', 'is_free'))
        self.assertEqual(data.get('is_active'), '1')
        self.assertEqual(data.get('is_free'), '0')

    def test_safe_int(self):
        self.assertEqual(safe_int('5', 0), 5)
        self.assertEqual(safe_int('x', 3), 3)
        self.assertEqual(safe_int('-4', 0), 0)
        self.assertEqual(safe_int(None, 2), 2)


class SettingsTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.login(self.admin)

    def audit(self, action_type, action=None):
        qs = ActivityLog.objects.filter(action_type=action_type)
        return qs.filter(action=action) if action else qs


class CheckboxViewTests(SettingsTestCase):
    """Real view POSTs: unchecked boxes switch flags off, checked ones on."""

    def test_post_category_flags_off_and_on(self):
        url = reverse('accounts:system_post_category_create')
        self.client.post(url, {'name': 'Sports', 'expires': '1', 'notify_on_post': '1', 'is_active': '1'})
        cat = PostCategory.objects.get(name='Sports')
        self.assertTrue(cat.expires and cat.notify_on_post and cat.is_active)

        edit = reverse('accounts:system_post_category_edit', kwargs={'category_id': cat.id})
        # hidden-input pattern: unchecked posts only the hidden 0
        self.client.post(edit, {'name': 'Sports', 'expires': '0', 'notify_on_post': '0', 'is_active': '0'})
        cat.refresh_from_db()
        self.assertFalse(cat.expires or cat.notify_on_post or cat.is_active)

        # browser without hidden inputs: missing keys mean unchecked
        self.client.post(edit, {'name': 'Sports', 'expires': 'on', 'notify_on_post': 'on', 'is_active': 'on'})
        cat.refresh_from_db()
        self.assertTrue(cat.expires and cat.notify_on_post and cat.is_active)
        self.client.post(edit, {'name': 'Sports'})
        cat.refresh_from_db()
        self.assertFalse(cat.expires or cat.notify_on_post or cat.is_active)

        # hidden 0 followed by the checked 1: last value wins
        self.client.post(edit, {'name': 'Sports', 'is_active': ['0', '1'], 'expires': ['0', '1']})
        cat.refresh_from_db()
        self.assertTrue(cat.is_active and cat.expires)
        self.assertFalse(cat.notify_on_post)

    def test_document_type_is_active_off_and_on(self):
        self.client.post(reverse('accounts:system_document_type_create'),
                         {'name': 'Cedula', 'fee': '10', 'is_active': '1'})
        doc = DocumentType.objects.get(name='Cedula')
        self.assertTrue(doc.is_active)
        edit = reverse('accounts:system_document_type_edit', kwargs={'doc_id': doc.id})
        self.client.post(edit, {'name': 'Cedula', 'fee': '10', 'is_active': '0'})
        doc.refresh_from_db()
        self.assertFalse(doc.is_active)
        self.client.post(edit, {'name': 'Cedula', 'fee': '10'})  # missing on an edit form
        doc.refresh_from_db()
        self.assertFalse(doc.is_active)
        self.client.post(edit, {'name': 'Cedula', 'fee': '10', 'is_active': 'on'})
        doc.refresh_from_db()
        self.assertTrue(doc.is_active)

    def test_health_service_is_active_and_is_free(self):
        self.client.post(reverse('accounts:system_health_service_create'),
                         {'name': 'Dental', 'is_active': '1', 'is_free': '1'})
        svc = HealthCareService.objects.get(name='Dental')
        self.assertTrue(svc.is_active and svc.is_free)
        edit = reverse('accounts:system_health_service_edit', kwargs={'svc_id': svc.id})
        self.client.post(edit, {'name': 'Dental', 'is_active': '0', 'is_free': '0'})
        svc.refresh_from_db()
        self.assertFalse(svc.is_active or svc.is_free)
        self.client.post(edit, {'name': 'Dental', 'is_active': 'on', 'is_free': 'on'})
        svc.refresh_from_db()
        self.assertTrue(svc.is_active and svc.is_free)
        self.client.post(edit, {'name': 'Dental'})
        svc.refresh_from_db()
        self.assertFalse(svc.is_active or svc.is_free)

    def test_concern_category_is_active_off_and_on(self):
        self.client.post(reverse('accounts:system_concern_category_create'),
                         {'name': 'Noise', 'is_active': '1'})
        cat = ConcernCategory.objects.get(name='Noise')
        self.assertTrue(cat.is_active)
        edit = reverse('accounts:system_concern_category_edit', kwargs={'cat_id': cat.id})
        self.client.post(edit, {'name': 'Noise', 'is_active': '0'})
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)
        self.client.post(edit, {'name': 'Noise', 'is_active': 'true'})
        cat.refresh_from_db()
        self.assertTrue(cat.is_active)
        self.client.post(edit, {'name': 'Noise'})
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)

    def test_service_level_create_defaults_and_partial_update_keeps_flags(self):
        cat = system_services.create_or_update_post_category_service(self.admin, {'name': 'Plain'})
        self.assertTrue(cat.expires)
        self.assertTrue(cat.is_active)
        self.assertFalse(cat.notify_on_post)
        self.assertFalse(cat.is_system)
        system_services.create_or_update_post_category_service(
            self.admin, {'name': 'Plain', 'is_active': '0'}, category_id=cat.id)
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)
        # partial payload on update keeps what it does not mention
        system_services.create_or_update_post_category_service(
            self.admin, {'name': 'Plain renamed'}, category_id=cat.id)
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)
        self.assertTrue(cat.expires)

        svc = system_services.create_or_update_health_service_service(self.admin, {'name': 'Checkup'})
        self.assertTrue(svc.is_active and svc.is_free)
        doc = system_services.create_or_update_document_type_service(self.admin, {'name': 'Permit', 'fee': '5'})
        self.assertTrue(doc.is_active)
        concern = system_services.create_or_update_concern_category_service(self.admin, {'name': 'Roads'})
        self.assertTrue(concern.is_active)

    def test_is_system_only_applies_on_create(self):
        cat = system_services.create_or_update_post_category_service(
            self.admin, {'name': 'Core', 'is_system': 'on'})
        self.assertTrue(cat.is_system)
        system_services.create_or_update_post_category_service(
            self.admin, {'name': 'Core', 'is_system': '0'}, category_id=cat.id)
        cat.refresh_from_db()
        self.assertTrue(cat.is_system)
        with self.assertRaises(ValueError):
            system_services.delete_post_category_service(self.admin, cat.id)


class ValidationAndGuardTests(SettingsTestCase):

    def test_duplicate_names_rejected_case_insensitively(self):
        system_services.create_or_update_post_category_service(self.admin, {'name': 'Events'})
        with self.assertRaisesMessage(ValueError, 'already exists'):
            system_services.create_or_update_post_category_service(self.admin, {'name': 'EVENTS'})
        make_document_type(name='Unique Doc')
        with self.assertRaisesMessage(ValueError, 'already exists'):
            system_services.create_or_update_document_type_service(self.admin, {'name': 'unique doc', 'fee': '1'})
        make_health_service(name='Vaccines')
        with self.assertRaisesMessage(ValueError, 'already exists'):
            system_services.create_or_update_health_service_service(self.admin, {'name': 'vaccines'})
        system_services.create_or_update_concern_category_service(self.admin, {'name': 'Garbage'})
        with self.assertRaisesMessage(ValueError, 'already exists'):
            system_services.create_or_update_concern_category_service(self.admin, {'name': 'garbage'})

    def test_duplicate_name_via_view_shows_message_and_creates_nothing(self):
        make_document_type(name='Dup Doc')
        before = DocumentType.objects.count()
        response = self.client.post(reverse('accounts:system_document_type_create'),
                                    {'name': 'dup doc', 'fee': '1'})
        self.assertEqual(DocumentType.objects.count(), before)
        self.assertTrue(any('already exists' in m for m in _messages(response)))

    def test_negative_and_invalid_fee_rejected(self):
        for bad in ('-5', '-0.01', 'abc', 'NaN', 'Infinity', '1e20'):
            with self.subTest(fee=bad):
                with self.assertRaises(ValueError):
                    system_services.create_or_update_document_type_service(
                        self.admin, {'name': f'Fee {bad}', 'fee': bad})
        self.assertFalse(DocumentType.objects.filter(name__startswith='Fee ').exists())

    def test_negative_fee_message_is_specific(self):
        response = self.client.post(reverse('accounts:system_document_type_create'),
                                    {'name': 'Negative', 'fee': '-5'})
        self.assertTrue(any('negative' in m.lower() for m in _messages(response)))
        self.assertFalse(DocumentType.objects.filter(name='Negative').exists())

    def test_valid_fee_is_quantized_and_free_is_allowed(self):
        doc = system_services.create_or_update_document_type_service(self.admin, {'name': 'Half', 'fee': '12.5'})
        self.assertEqual(doc.fee, Decimal('12.50'))
        free = system_services.create_or_update_document_type_service(self.admin, {'name': 'Indigent', 'fee': '0'})
        self.assertEqual(free.fee, Decimal('0.00'))

    def test_overlong_names_rejected(self):
        with self.assertRaises(ValueError):
            system_services.create_or_update_post_category_service(self.admin, {'name': 'x' * 51})

    def test_delete_referenced_document_type_refused_with_clean_message(self):
        doc = make_document_type()
        make_appointment(resident=make_resident_user(), document_type=doc)
        response = self.client.post(reverse('accounts:system_document_type_delete', kwargs={'doc_id': doc.id}))
        self.assertTrue(DocumentType.objects.filter(id=doc.id).exists())
        self.assertTrue(any('referenced' in m for m in _messages(response)))

    def test_delete_referenced_health_service_refused(self):
        svc = make_health_service()
        from apps.appointments.models import Appointment
        Appointment.objects.create(
            resident=make_resident_user(), category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=svc, purpose='Checkup',
            appt_date=make_appointment(resident=make_resident_user()).appt_date,
            time_window=Appointment.TIME_SLOT_MORNING, status=Appointment.STATUS_PENDING,
        )
        response = self.client.post(reverse('accounts:system_health_service_delete', kwargs={'svc_id': svc.id}))
        self.assertTrue(HealthCareService.objects.filter(id=svc.id).exists())
        self.assertTrue(any('referenced' in m for m in _messages(response)))

    def test_system_category_cannot_be_deleted_via_view(self):
        cat = PostCategory.objects.create(name='Locked', is_system=True)
        response = self.client.post(reverse('accounts:system_post_category_delete', kwargs={'category_id': cat.id}))
        self.assertTrue(PostCategory.objects.filter(id=cat.id).exists())
        self.assertTrue(any('cannot be deleted' in m for m in _messages(response)))

    def test_delete_and_edit_of_missing_objects_give_clean_errors(self):
        missing = 999999
        cases = [
            ('accounts:system_post_category_delete', {'category_id': missing}),
            ('accounts:system_document_type_delete', {'doc_id': missing}),
            ('accounts:system_health_service_delete', {'svc_id': missing}),
            ('accounts:system_concern_category_delete', {'cat_id': missing}),
            ('accounts:system_staff_account_disable', {'user_id': missing}),
            ('accounts:system_post_category_edit', {'category_id': missing}),
            ('accounts:system_document_type_edit', {'doc_id': missing}),
            ('accounts:system_health_service_edit', {'svc_id': missing}),
            ('accounts:system_concern_category_edit', {'cat_id': missing}),
        ]
        for name, kwargs in cases:
            with self.subTest(url=name):
                response = self.client.post(reverse(name, kwargs=kwargs), {'name': 'Ghost', 'fee': '1'})
                self.assertEqual(response.status_code, 302)
                msgs = _messages(response)
                self.assertTrue(any('no longer exists' in m for m in msgs), msgs)
                self.assertFalse(any('DoesNotExist' in m or 'matching query' in m for m in msgs), msgs)

    def test_service_level_missing_object_is_valueerror(self):
        with self.assertRaisesMessage(ValueError, 'no longer exists'):
            system_services.delete_post_category_service(self.admin, 424242)
        with self.assertRaisesMessage(ValueError, 'no longer exists'):
            system_services.delete_concern_category_service(self.admin, 424242)

    def test_staff_cannot_disable_self_and_bad_term_end_is_clean(self):
        response = self.client.post(reverse('accounts:system_staff_account_disable', kwargs={'user_id': self.admin.id}))
        self.assertTrue(any('cannot disable your own' in m for m in _messages(response)))
        with self.assertRaisesMessage(ValueError, 'valid date'):
            system_services.create_staff_account_service(
                self.admin, {'email': 'x@barangay.test', 'username': 'xstaff', 'term_end': '31-31-2020'})


class RedirectTargetTests(SettingsTestCase):
    """Every view redirects to the canonical tab/subtab the dashboard understands."""

    def expect(self, response, tab, subtab=None):
        self.assertEqual(response.status_code, 302)
        path, query = _redirect_target(response)
        self.assertEqual(path, reverse('accounts:system_dashboard'))
        self.assertEqual(query.get('tab'), tab)
        self.assertEqual(query.get('subtab'), subtab)

    def test_redirects(self):
        doc = make_document_type()
        svc = make_health_service()
        cat = PostCategory.objects.create(name='Redirect cat')
        concern = ConcernCategory.objects.create(name='Redirect concern', slug='redirect_concern')
        staff = make_staff()
        post = self.client.post

        self.expect(post(reverse('accounts:system_barangay_info_update'), {'name': 'Brgy X'}), 'barangay_info')
        self.expect(post(reverse('accounts:system_post_category_create'), {'name': 'New P'}), 'post_categories')
        self.expect(post(reverse('accounts:system_post_category_edit', kwargs={'category_id': cat.id}), {'name': 'Redirect cat'}), 'post_categories')
        self.expect(post(reverse('accounts:system_post_category_delete', kwargs={'category_id': cat.id})), 'post_categories')
        self.expect(post(reverse('accounts:system_document_type_create'), {'name': 'New D', 'fee': '1'}), 'document_health', 'documents')
        self.expect(post(reverse('accounts:system_document_type_edit', kwargs={'doc_id': doc.id}), {'name': doc.name, 'fee': '1'}), 'document_health', 'documents')
        self.expect(post(reverse('accounts:system_document_type_delete', kwargs={'doc_id': doc.id})), 'document_health', 'documents')
        self.expect(post(reverse('accounts:system_health_service_create'), {'name': 'New H'}), 'document_health', 'health')
        self.expect(post(reverse('accounts:system_health_service_edit', kwargs={'svc_id': svc.id}), {'name': svc.name}), 'document_health', 'health')
        self.expect(post(reverse('accounts:system_health_service_delete', kwargs={'svc_id': svc.id})), 'document_health', 'health')
        self.expect(post(reverse('accounts:system_concern_category_create'), {'name': 'New C'}), 'user_management', 'concerns')
        self.expect(post(reverse('accounts:system_concern_category_edit', kwargs={'cat_id': concern.id}), {'name': 'Redirect concern'}), 'user_management', 'concerns')
        self.expect(post(reverse('accounts:system_concern_category_delete', kwargs={'cat_id': concern.id})), 'user_management', 'concerns')
        self.expect(post(reverse('accounts:system_staff_account_create'), {'email': 'r@barangay.test'}), 'user_management', 'staff')
        self.expect(post(reverse('accounts:system_staff_account_disable', kwargs={'user_id': staff.id})), 'user_management', 'staff')
        self.expect(post(reverse('accounts:system_email_edit', kwargs={'template_name': 'nope'}), {'content': 'x'}), 'email_templates')

    def test_redirect_failure_paths_use_same_targets(self):
        response = self.client.post(reverse('accounts:system_document_type_create'), {'name': '', 'fee': '1'})
        self.expect(response, 'document_health', 'documents')
        response = self.client.post(reverse('accounts:system_concern_category_create'), {'name': ''})
        self.expect(response, 'user_management', 'concerns')

    def test_redirect_targets_render_the_matching_tab(self):
        for url, tab, subtab in [
            (reverse('accounts:system_dashboard') + '?tab=document_health&subtab=health', 'document_health', 'health'),
            (reverse('accounts:system_dashboard') + '?tab=user_management&subtab=concerns', 'user_management', 'concerns'),
            (reverse('accounts:system_dashboard') + '?tab=email_templates', 'email_templates', ''),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['active_tab'], tab)
            self.assertEqual(response.context['active_subtab'], subtab)

    def test_legacy_and_invalid_tabs_are_normalised(self):
        base = reverse('accounts:system_dashboard')
        cases = {
            '?tab=documents': ('document_health', 'documents'),
            '?tab=health_services': ('document_health', 'health'),
            '?tab=staff_accounts': ('user_management', 'staff'),
            '?tab=concern_categories': ('user_management', 'concerns'),
            '?tab=bogus': ('barangay_info', ''),
            '?tab=document_health&subtab=bogus': ('document_health', 'documents'),
            '': ('barangay_info', ''),
        }
        for query, (tab, subtab) in cases.items():
            with self.subTest(query=query):
                ctx = self.client.get(base + query).context
                self.assertEqual((ctx['active_tab'], ctx['active_subtab']), (tab, subtab))

    def test_views_module_uses_no_legacy_tab_names(self):
        import inspect
        from apps.accounts import system_views
        source = inspect.getsource(system_views)
        for legacy in ('tab=documents', 'tab=health_services', 'tab=concern_categories', 'tab=staff_accounts'):
            self.assertNotIn(legacy, source)


class ErrorHandlingTests(SettingsTestCase):

    SECRET = 'secret detail /etc/passwd'

    def test_unexpected_error_shows_generic_message_and_is_logged(self):
        with mock.patch('apps.accounts.system_services.create_or_update_post_category_service',
                        side_effect=RuntimeError(self.SECRET)):
            with self.assertLogs('apps.accounts.system_views', level='ERROR') as logs:
                response = self.client.post(reverse('accounts:system_post_category_create'), {'name': 'Boom'})
        msgs = _messages(response)
        self.assertTrue(any('Something went wrong' in m for m in msgs), msgs)
        self.assertFalse(any('secret' in m for m in msgs))
        self.assertIn('RuntimeError', '\n'.join(logs.output))

    def test_every_write_view_hides_internal_errors(self):
        targets = [
            ('update_barangay_info_service', 'accounts:system_barangay_info_update', {}, {'name': 'X'}),
            ('delete_post_category_service', 'accounts:system_post_category_delete', {'category_id': 1}, {}),
            ('create_or_update_document_type_service', 'accounts:system_document_type_create', {}, {'name': 'X'}),
            ('delete_document_type_service', 'accounts:system_document_type_delete', {'doc_id': 1}, {}),
            ('create_or_update_health_service_service', 'accounts:system_health_service_create', {}, {'name': 'X'}),
            ('delete_health_service_service', 'accounts:system_health_service_delete', {'svc_id': 1}, {}),
            ('create_or_update_concern_category_service', 'accounts:system_concern_category_create', {}, {'name': 'X'}),
            ('delete_concern_category_service', 'accounts:system_concern_category_delete', {'cat_id': 1}, {}),
            ('create_staff_account_service', 'accounts:system_staff_account_create', {}, {'email': 'a@b.co'}),
            ('disable_staff_account_service', 'accounts:system_staff_account_disable', {'user_id': 1}, {}),
        ]
        for func, url_name, kwargs, data in targets:
            with self.subTest(service=func):
                with mock.patch(f'apps.accounts.system_services.{func}', side_effect=RuntimeError(self.SECRET)):
                    with self.assertLogs('apps.accounts.system_views', level='ERROR'):
                        response = self.client.post(reverse(url_name, kwargs=kwargs), data)
                msgs = _messages(response)
                self.assertTrue(any('Something went wrong' in m for m in msgs), msgs)
                self.assertFalse(any('secret' in m or 'passwd' in m for m in msgs), msgs)

    def test_value_error_message_is_shown(self):
        with mock.patch('apps.accounts.system_services.create_or_update_post_category_service',
                        side_effect=ValueError('Pick another name.')):
            response = self.client.post(reverse('accounts:system_post_category_create'), {'name': 'Boom'})
        self.assertIn('Pick another name.', _messages(response))

    def test_email_json_endpoints_do_not_leak_internal_errors(self):
        url_edit = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        url_prev = reverse('accounts:system_email_preview', kwargs={'template_name': 'appt_approved'})
        for func, call in [
            ('get_email_template_source', lambda: self.client.get(url_edit)),
            ('render_email_template_preview', lambda: self.client.get(url_prev)),
            ('update_email_template_service', lambda: self.client.post(
                url_edit, {'content': 'Subject: x\n\nbody'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')),
        ]:
            with self.subTest(service=func):
                with mock.patch(f'apps.accounts.system_services.{func}', side_effect=RuntimeError(self.SECRET)):
                    with self.assertLogs('apps.accounts.system_views', level='ERROR'):
                        response = call()
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('secret', response.content.decode())
                self.assertIn('Something went wrong', response.json()['error'])

    def test_email_json_value_error_is_shown(self):
        response = self.client.get(reverse('accounts:system_email_preview', kwargs={'template_name': '..%2Fsettings'}))
        self.assertIn(response.status_code, (400, 404))
        response = self.client.get(reverse('accounts:system_email_preview', kwargs={'template_name': 'unknown_one'}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid template name specified.')


class BarangayInfoTests(SettingsTestCase):

    def post(self, **fields):
        data = {'name': 'Barangay Poblacion'}
        data.update(fields)
        return self.client.post(reverse('accounts:system_barangay_info_update'), data)

    def test_city_and_province_saved_and_cleared(self):
        self.post(city='Cebu City', province='Cebu', address='Hall', venue='Gym', office_hours='8-5', contact_no='09171234567')
        info = BarangayInfo.get_solo()
        self.assertEqual((info.city, info.province), ('Cebu City', 'Cebu'))
        self.post(city='', province='', address='', venue='', office_hours='', contact_no='')
        info.refresh_from_db()
        self.assertEqual(info.city, '')
        self.assertEqual(info.province, '')
        self.assertEqual(info.address, '')
        self.assertEqual(info.venue, '')
        self.assertEqual(info.office_hours, '')
        self.assertEqual(info.contact_no, '')

    def test_new_fields_have_blank_defaults(self):
        info = BarangayInfo.objects.create(id=99)
        self.assertEqual((info.city, info.province), ('', ''))

    def test_missing_keys_are_left_unchanged(self):
        self.post(city='Davao', province='Davao del Sur')
        system_services.update_barangay_info_service(self.admin, {'name': 'Renamed'})
        info = BarangayInfo.get_solo()
        self.assertEqual(info.name, 'Renamed')
        self.assertEqual(info.city, 'Davao')
        self.assertEqual(info.province, 'Davao del Sur')

    def test_name_required(self):
        before = BarangayInfo.get_solo().name
        response = self.post(name='   ')
        self.assertTrue(any('name is required' in m for m in _messages(response)))
        self.assertEqual(BarangayInfo.get_solo().name, before)

    def test_contact_number_accepts_mobile_and_landline(self):
        for good in ('09171234567', '(02) 8123-4567', '0917-111-2222', '123 4567', ''):
            with self.subTest(contact=good):
                system_services.update_barangay_info_service(self.admin, {'name': 'B', 'contact_no': good})
                self.assertEqual(BarangayInfo.get_solo().contact_no, good)

    def test_contact_number_rejects_bad_values(self):
        system_services.update_barangay_info_service(self.admin, {'name': 'B', 'contact_no': '09171234567'})
        for bad in ('abc', '12345', '1' * 20, '0917+111+2222', '09171234567 ext 5', '((((((((', '+639171234567'):
            with self.subTest(contact=bad):
                with self.assertRaises(ValueError):
                    system_services.update_barangay_info_service(self.admin, {'name': 'B', 'contact_no': bad})
        self.assertEqual(BarangayInfo.get_solo().contact_no, '09171234567')

    def test_logo_validation_and_clear(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with override_settings(MEDIA_ROOT=media):
            bad = SimpleUploadedFile('logo.png', b'not an image', content_type='image/png')
            with self.assertRaises(ValueError):
                system_services.update_barangay_info_service(self.admin, {'name': 'B'}, bad)
            self.assertFalse(BarangayInfo.get_solo().logo)

            from PIL import Image
            buf = io.BytesIO()
            Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
            good = SimpleUploadedFile('logo.png', buf.getvalue(), content_type='image/png')
            system_services.update_barangay_info_service(self.admin, {'name': 'B'}, good)
            self.assertTrue(BarangayInfo.get_solo().logo)

            # not replaced when no file is uploaded
            system_services.update_barangay_info_service(self.admin, {'name': 'B2'})
            self.assertTrue(BarangayInfo.get_solo().logo)

            system_services.update_barangay_info_service(self.admin, {'name': 'B2', 'clear_logo': 'on'})
            self.assertFalse(BarangayInfo.get_solo().logo)

    def test_audit_row_has_before_and_after(self):
        self.post(city='Iloilo', province='Iloilo')
        log = self.audit('SystemConfig', 'update').last()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor_id, self.admin.id)
        self.assertIn('Before', log.details)
        self.assertIn('After', log.details)
        self.assertIn('Iloilo', log.details)


class EmailTemplateTests(SettingsTestCase):

    def setUp(self):
        super().setUp()
        self.real_dir = os.path.join(settings.BASE_DIR, 'templates', 'emails')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in os.listdir(self.real_dir):
            if name.endswith('.txt'):
                shutil.copy(os.path.join(self.real_dir, name), os.path.join(self.tmp, name))
        patcher = mock.patch('apps.accounts.system_services.email_template_dir', return_value=self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, name):
        with open(os.path.join(self.tmp, f'{name}.txt'), encoding='utf-8') as f:
            return f.read()

    def test_catalog_includes_new_templates_and_files_exist(self):
        names = [item['name'] for item in system_services.EMAIL_TEMPLATE_CATALOG]
        self.assertIn('staff_created', names)
        self.assertIn('password_reset_email', names)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(self.real_dir, f'{name}.txt')), name)
        ctx = self.client.get(reverse('accounts:system_dashboard') + '?tab=email_templates').context
        self.assertEqual([t['name'] for t in ctx['email_templates_list']], names)

    def test_every_catalog_template_previews_and_loads(self):
        for item in system_services.EMAIL_TEMPLATE_CATALOG:
            with self.subTest(template=item['name']):
                preview = system_services.render_email_template_preview(item['name'])
                self.assertTrue(preview['body'])
                src = system_services.get_email_template_source(item['name'])
                self.assertTrue(src['raw_source'])

    def test_broken_syntax_rejected_and_file_untouched(self):
        original = self.read('appt_approved')
        for bad in ('Subject: Hi\n\n{% if %}oops{% endif %}', 'Subject: Hi\n\n{% if x %}never closed',
                    'Subject: Hi\n\n{{ first_name|nosuchfilter }}', 'Subject: Hi\n\n{% nosuchtag %}'):
            with self.subTest(content=bad):
                with self.assertRaisesMessage(ValueError, 'syntax error'):
                    system_services.update_email_template_service(self.admin, 'appt_approved', bad)
                self.assertEqual(self.read('appt_approved'), original)
        self.assertFalse(self.audit('EmailTemplate').exists())

    def test_broken_template_via_view_shows_clear_message(self):
        url = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        original = self.read('appt_approved')
        response = self.client.post(url, {'content': 'Subject: Hi\n\n{% if %}'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertIn('syntax error', response.json()['error'])
        self.assertEqual(self.read('appt_approved'), original)
        response = self.client.post(url, {'content': 'Subject: Hi\n\n{% if %}'})
        self.assertTrue(any('syntax error' in m for m in _messages(response)))

    def test_subject_line_required_except_password_reset(self):
        original = self.read('appt_approved')
        for bad in ('No subject here\n\nbody', 'Subject:\n\nbody', 'Subject: Only a subject'):
            with self.subTest(content=bad):
                with self.assertRaises(ValueError):
                    system_services.update_email_template_service(self.admin, 'appt_approved', bad)
        self.assertEqual(self.read('appt_approved'), original)
        self.assertFalse(self.read('password_reset_email').lower().startswith('subject:'))
        system_services.update_email_template_service(
            self.admin, 'password_reset_email', 'Reset here: https://{{ domain }}/r/{{ uid }}/{{ token }}/')
        self.assertIn('{{ domain }}', self.read('password_reset_email'))

    def test_empty_and_oversized_rejected(self):
        for bad in ('', '   \n  '):
            with self.assertRaises(ValueError):
                system_services.update_email_template_service(self.admin, 'appt_approved', bad)
        with self.assertRaisesMessage(ValueError, 'too large'):
            system_services.update_email_template_service(
                self.admin, 'appt_approved', 'Subject: Big\n\n' + 'x' * (21 * 1024))

    def test_whitelist_applies_to_read_preview_and_write(self):
        for bad in ('../settings', '..\\settings', 'not_in_catalog', 'appt_approved/../x', 'password_reset_subject',
                    '../x.txt', '', 'appt_approved.html'):
            with self.subTest(name=bad):
                with self.assertRaisesMessage(ValueError, 'Invalid template name'):
                    system_services.get_email_template_source(bad)
                with self.assertRaisesMessage(ValueError, 'Invalid template name'):
                    system_services.render_email_template_preview(bad)
                with self.assertRaisesMessage(ValueError, 'Invalid template name'):
                    system_services.update_email_template_service(self.admin, bad, 'Subject: x\n\nbody')
        self.assertFalse(os.path.exists(os.path.join(self.tmp, '..', 'x.txt')))

    def test_valid_save_round_trips_and_is_audited_without_content(self):
        content = 'Subject: Approved for {{ first_name }}\n\nHello {{ first_name }}, see you on {{ appointment_date }}.\n'
        self.assertTrue(system_services.update_email_template_service(self.admin, 'appt_approved', content))
        self.assertEqual(self.read('appt_approved'), content)
        source = system_services.get_email_template_source('appt_approved')
        self.assertEqual(source['subject'], 'Approved for {{ first_name }}')
        self.assertIn('Hello {{ first_name }}', source['body'])
        preview = system_services.render_email_template_preview('appt_approved.txt')
        self.assertEqual(preview['subject'], 'Approved for Juan')
        log = self.audit('EmailTemplate', 'update').get()
        self.assertEqual(log.actor_id, self.admin.id)
        self.assertEqual(log.target_name, 'appt_approved.txt')
        self.assertNotIn('Hello', log.details)
        self.assertEqual([f for f in os.listdir(self.tmp) if f.endswith('.tmp')], [])

    def test_edit_view_passes_actor_and_builds_content_from_subject_and_body(self):
        url = reverse('accounts:system_email_edit', kwargs={'template_name': 'reg_received'})
        response = self.client.post(url, {'subject': 'Got it', 'body': 'Thanks {{ first_name }}'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['status'], 'success')
        self.assertTrue(self.read('reg_received').startswith('Subject: Got it'))
        self.assertEqual(self.audit('EmailTemplate', 'update').get().actor_id, self.admin.id)

    def test_write_normalises_crlf(self):
        system_services.update_email_template_service(
            self.admin, 'appt_approved', 'Subject: A\r\n\r\nBody line\r\nSecond')
        with open(os.path.join(self.tmp, 'appt_approved.txt'), 'rb') as f:
            self.assertNotIn(b'\r', f.read())

    def test_real_repo_templates_untouched(self):
        with open(os.path.join(self.real_dir, 'appt_approved.txt'), encoding='utf-8') as before:
            snapshot = before.read()
        system_services.update_email_template_service(self.admin, 'appt_approved', 'Subject: Z\n\nChanged body')
        with open(os.path.join(self.real_dir, 'appt_approved.txt'), encoding='utf-8') as after:
            self.assertEqual(after.read(), snapshot)


class RBACTests(BaseTestCase):
    """admin, permitted staff, unpermitted staff and resident, per action."""

    ACTIONS = [
        # (module action, url name, kwargs, post data)
        ('edit', 'accounts:system_barangay_info_update', {}, {'name': 'RBAC Brgy'}),
        ('manage_categories', 'accounts:system_post_category_create', {}, {'name': 'RBAC cat'}),
        ('manage_documents', 'accounts:system_document_type_create', {}, {'name': 'RBAC doc', 'fee': '1'}),
        ('manage_health_services', 'accounts:system_health_service_create', {}, {'name': 'RBAC svc'}),
        ('manage_concerns', 'accounts:system_concern_category_create', {}, {'name': 'RBAC concern'}),
        ('manage_staff', 'accounts:system_staff_account_create', {}, {'email': 'rbac@barangay.test', 'username': 'rbacuser'}),
    ]

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.resident = make_resident_user()
        self.unpermitted = make_staff(permissions={'residents': ['view']})

    def test_each_action_honours_its_own_permission(self):
        for action, url_name, kwargs, data in self.ACTIONS:
            with self.subTest(action=action):
                url = reverse(url_name, kwargs=kwargs)
                permitted = make_staff(permissions={'system': [action]})
                other = make_staff(permissions={'system': [a for a, *_ in self.ACTIONS if a != action] + ['view']})

                self.login(permitted)
                self.assertEqual(self.client.post(url, data).status_code, 302, 'permitted staff')
                self.login(other)
                self.assertEqual(self.client.post(url, data).status_code, 403, 'staff with only other system permissions')
                self.login(self.unpermitted)
                self.assertEqual(self.client.post(url, data).status_code, 403, 'unpermitted staff')
                self.login(self.resident)
                self.assertEqual(self.client.post(url, data).status_code, 403, 'resident')
                self.login(self.admin)
                self.assertEqual(self.client.post(url, data).status_code, 302, 'admin')

    def test_delete_and_edit_routes_use_same_permission_as_create(self):
        doc = make_document_type()
        svc = make_health_service()
        cat = PostCategory.objects.create(name='RBAC del')
        concern = ConcernCategory.objects.create(name='RBAC concern del', slug='rbac_concern_del')
        routes = [
            ('manage_documents', reverse('accounts:system_document_type_delete', kwargs={'doc_id': doc.id})),
            ('manage_health_services', reverse('accounts:system_health_service_delete', kwargs={'svc_id': svc.id})),
            ('manage_categories', reverse('accounts:system_post_category_delete', kwargs={'category_id': cat.id})),
            ('manage_concerns', reverse('accounts:system_concern_category_delete', kwargs={'cat_id': concern.id})),
            ('manage_staff', reverse('accounts:system_staff_account_disable', kwargs={'user_id': self.unpermitted.id})),
        ]
        for action, url in routes:
            with self.subTest(url=url):
                self.login(self.unpermitted)
                self.assertEqual(self.client.post(url).status_code, 403)
                self.login(self.resident)
                self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(DocumentType.objects.filter(id=doc.id).exists())
        self.assertTrue(HealthCareService.objects.filter(id=svc.id).exists())
        self.assertTrue(PostCategory.objects.filter(id=cat.id).exists())
        self.assertTrue(ConcernCategory.objects.filter(id=concern.id).exists())
        self.assertEqual(User.objects.get(id=self.unpermitted.id).status, User.STATUS_ACTIVE)

    def test_dashboard_requires_view_permission(self):
        url = reverse('accounts:system_dashboard')
        self.login(self.unpermitted)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(self.resident)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(make_staff(permissions={'system': ['view']}))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_email_endpoints_require_preview_emails(self):
        url_prev = reverse('accounts:system_email_preview', kwargs={'template_name': 'appt_approved'})
        url_edit = reverse('accounts:system_email_edit', kwargs={'template_name': 'appt_approved'})
        permitted = make_staff(permissions={'system': ['preview_emails']})
        self.login(permitted)
        self.assertEqual(self.client.get(url_prev).status_code, 200)
        self.assertEqual(self.client.get(url_edit).status_code, 200)
        for user in (self.unpermitted, self.resident):
            self.login(user)
            self.assertEqual(self.client.get(url_prev).status_code, 403)
            self.assertEqual(self.client.get(url_edit).status_code, 403)
            self.assertEqual(self.client.post(url_edit, {'content': 'Subject: x\n\ny'}).status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.post(reverse('accounts:system_post_category_create'), {'name': 'Anon'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertFalse(PostCategory.objects.filter(name='Anon').exists())

    def test_get_requests_do_not_write(self):
        self.login(self.admin)
        before = ActivityLog.objects.count()
        response = self.client.get(reverse('accounts:system_post_category_create'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ActivityLog.objects.count(), before)


class AuditTests(SettingsTestCase):
    """Every write produces an ActivityLog row attributed to the actor."""

    def test_every_write_is_audited(self):
        post = self.client.post
        post(reverse('accounts:system_barangay_info_update'), {'name': 'Audit Brgy', 'city': 'Audit City'})
        self.assertEqual(self.audit('SystemConfig', 'update').count(), 1)

        post(reverse('accounts:system_post_category_create'), {'name': 'Audit cat'})
        cat = PostCategory.objects.get(name='Audit cat')
        post(reverse('accounts:system_post_category_edit', kwargs={'category_id': cat.id}), {'name': 'Audit cat', 'is_active': '0'})
        post(reverse('accounts:system_post_category_delete', kwargs={'category_id': cat.id}))
        self.assertEqual([a for a in self.audit('PostCategory').order_by('id').values_list('action', flat=True)],
                         ['create', 'update', 'delete'])
        self.assertIn('is_active', self.audit('PostCategory', 'update').get().details)

        post(reverse('accounts:system_document_type_create'), {'name': 'Audit doc', 'fee': '3'})
        doc = DocumentType.objects.get(name='Audit doc')
        post(reverse('accounts:system_document_type_edit', kwargs={'doc_id': doc.id}), {'name': 'Audit doc', 'fee': '4'})
        post(reverse('accounts:system_document_type_delete', kwargs={'doc_id': doc.id}))
        self.assertEqual(self.audit('DocumentType').count(), 3)

        post(reverse('accounts:system_health_service_create'), {'name': 'Audit svc'})
        svc = HealthCareService.objects.get(name='Audit svc')
        post(reverse('accounts:system_health_service_edit', kwargs={'svc_id': svc.id}), {'name': 'Audit svc', 'is_free': '0'})
        post(reverse('accounts:system_health_service_delete', kwargs={'svc_id': svc.id}))
        self.assertEqual(self.audit('HealthCareService').count(), 3)

        post(reverse('accounts:system_concern_category_create'), {'name': 'Audit concern'})
        concern = ConcernCategory.objects.get(name='Audit concern')
        post(reverse('accounts:system_concern_category_edit', kwargs={'cat_id': concern.id}), {'name': 'Audit concern'})
        post(reverse('accounts:system_concern_category_delete', kwargs={'cat_id': concern.id}))
        self.assertEqual(self.audit('ConcernCategory').count(), 3)

        n = _n()
        post(reverse('accounts:system_staff_account_create'), {'email': f'audit{n}@barangay.test', 'username': f'audit{n}'})
        staff = User.objects.get(username=f'audit{n}')
        self.assertEqual(self.audit('StaffAccount', 'create').count(), 1)
        post(reverse('accounts:system_staff_account_disable', kwargs={'user_id': staff.id}))
        self.assertEqual(self.audit('StaffAccount', 'disable').count(), 1)

        for log in ActivityLog.objects.filter(action_type__in=[
                'SystemConfig', 'PostCategory', 'DocumentType', 'HealthCareService', 'ConcernCategory', 'StaffAccount']):
            self.assertEqual(log.actor_id, self.admin.id)

    def test_failed_writes_are_not_audited(self):
        before = ActivityLog.objects.count()
        self.client.post(reverse('accounts:system_document_type_create'), {'name': 'Bad fee', 'fee': '-1'})
        self.client.post(reverse('accounts:system_post_category_delete', kwargs={'category_id': 999999}))
        self.assertEqual(ActivityLog.objects.count(), before)

    def test_staff_created_log_never_contains_password(self):
        n = _n()
        self.client.post(reverse('accounts:system_staff_account_create'),
                         {'email': f'pw{n}@barangay.test', 'username': f'pw{n}'})
        log = self.audit('StaffAccount', 'create').get()
        self.assertNotIn('password:', log.details.lower())
