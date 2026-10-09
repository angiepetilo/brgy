"""Both registration paths and the staff edit form collect and persist demographics."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts import selectors
from apps.accounts.forms import ResidentRegistrationForm
from apps.accounts.models import Resident, User
from apps.accounts.services import (
    register_resident_service,
    staff_register_resident_service,
    update_resident_demographics_service,
)
from apps.history.models import ActivityLog
from tests.base import BaseTestCase, make_admin, make_purok, make_resident_profile, make_resident_user, make_staff
from tests.base import JPEG_BYTES, PNG_BYTES


def adult_birthdate():
    return selectors.years_ago(timezone.localdate(), 30) - timedelta(days=5)


class SelfRegistrationFormTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.purok = make_purok('Reg Purok')

    def _data(self, **overrides):
        data = {
            'first_name': 'Ana', 'last_name': 'Reyes', 'birthdate': adult_birthdate().isoformat(),
            'contact_no': '09171234567', 'email': 'ana.reyes@example.com', 'purok': self.purok.id,
            'address': '1 Rizal St', 'privacy_consent': 'on',
            'gender': 'female', 'civil_status': 'married',
        }
        data.update(overrides)
        return data

    def _form(self, **overrides):
        photo = SimpleUploadedFile('id.jpg', JPEG_BYTES, content_type='image/jpeg')
        return ResidentRegistrationForm(self._data(**overrides), {'id_photo': photo})

    def test_gender_is_required(self):
        form = self._form(gender='')
        self.assertFalse(form.is_valid())
        self.assertIn('gender', form.errors)

    def test_bad_gender_and_civil_status_are_rejected(self):
        form = self._form(gender='robot', civil_status='complicated')
        self.assertFalse(form.is_valid())
        self.assertIn('gender', form.errors)
        self.assertIn('civil_status', form.errors)

    def test_sector_checkboxes_are_optional(self):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['is_pwd'])

    def test_signup_post_persists_demographics_on_the_resident(self):
        photo = SimpleUploadedFile('id.jpg', JPEG_BYTES, content_type='image/jpeg')
        data = self._data(is_solo_parent='on', is_pwd='on', is_4ps='on')
        data['id_photo'] = photo
        response = self.client.post(reverse('accounts:signup'), data)
        self.assertEqual(response.status_code, 200)
        resident = Resident.objects.get(user__email='ana.reyes@example.com')
        self.assertEqual(resident.gender, 'female')
        self.assertEqual(resident.civil_status, 'married')
        self.assertTrue(resident.is_solo_parent and resident.is_pwd and resident.is_4ps)

    def test_signup_page_renders_the_new_fields(self):
        html = self.client.get(reverse('accounts:signup')).content.decode()
        for name in ('gender', 'civil_status', 'is_solo_parent', 'is_pwd', 'is_4ps'):
            self.assertIn(f'name="{name}"', html)

    def test_service_rejects_bad_choices_even_without_the_form(self):
        cleaned = {**self._data(), 'purok': self.purok, 'birthdate': adult_birthdate(), 'gender': 'robot'}
        with self.assertRaises(ValueError):
            register_resident_service(cleaned)
        self.assertFalse(User.objects.filter(email='ana.reyes@example.com').exists())


class StaffRegistrationServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.purok = make_purok('Staff Reg Purok')

    def _data(self, **overrides):
        data = {
            'first_name': 'Lito', 'last_name': 'Cruz', 'birthdate': adult_birthdate().isoformat(),
            'purok': self.purok, 'gender': 'male', 'civil_status': 'widowed',
            'is_solo_parent': 'on', 'is_4ps': '1',
        }
        data.update(overrides)
        return data

    def test_stores_gender_civil_status_and_sector_flags(self):
        resident = staff_register_resident_service(self.admin, self._data())
        resident.refresh_from_db()
        self.assertIsNone(resident.user)
        self.assertEqual((resident.gender, resident.civil_status), ('male', 'widowed'))
        self.assertTrue(resident.is_solo_parent)
        self.assertTrue(resident.is_4ps)
        self.assertFalse(resident.is_pwd)

    def test_values_are_normalised_to_lowercase_codes(self):
        resident = staff_register_resident_service(self.admin, self._data(gender='FEMALE', civil_status='Married'))
        self.assertEqual((resident.gender, resident.civil_status), ('female', 'married'))

    def test_bad_gender_is_rejected_and_nothing_is_created(self):
        with self.assertRaises(ValueError):
            staff_register_resident_service(self.admin, self._data(gender='robot'))
        self.assertEqual(Resident.objects.count(), 0)

    def test_bad_civil_status_is_rejected(self):
        with self.assertRaises(ValueError):
            staff_register_resident_service(self.admin, self._data(civil_status='complicated'))

    def test_missing_civil_status_defaults_to_single(self):
        data = self._data()
        del data['civil_status']
        self.assertEqual(staff_register_resident_service(self.admin, data).civil_status, 'single')

    def test_staff_without_create_permission_is_refused(self):
        staff = make_staff(permissions={'residents': ['view']})
        with self.assertRaises(PermissionDenied):
            staff_register_resident_service(staff, self._data())

    def test_register_view_persists_the_posted_demographics(self):
        self.login(self.admin)
        response = self.client.post(reverse('accounts:staff_register_resident'), {
            'first_name': 'Nena', 'last_name': 'Lopez', 'birthdate': adult_birthdate().isoformat(),
            'gender': 'female', 'civil_status': 'separated', 'is_pwd': '1', 'purok': str(self.purok.id),
        })
        self.assertEqual(response.status_code, 302)
        resident = Resident.objects.get(last_name='Lopez')
        self.assertEqual((resident.gender, resident.civil_status, resident.is_pwd), ('female', 'separated', True))
        self.assertEqual(resident.purok, self.purok)


class ResidentEditTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.user = make_resident_user(first_name='Old', last_name='Name')
        self.resident = make_resident_profile(user=self.user, first_name='Old', last_name='Name')
        self.url = reverse('accounts:resident_edit', args=[self.user.id])

    def _post(self, **overrides):
        data = {'first_name': 'New', 'last_name': 'Name', 'email': self.user.email,
                'gender': 'male', 'civil_status': 'divorced', 'is_solo_parent': '1', 'is_4ps': '1'}
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_edit_persists_demographics_on_the_resident_and_audits_it(self):
        self.login(self.admin)
        self.assertEqual(self._post().status_code, 302)
        self.resident.refresh_from_db()
        self.assertEqual((self.resident.gender, self.resident.civil_status), ('male', 'divorced'))
        self.assertTrue(self.resident.is_solo_parent and self.resident.is_4ps)
        self.assertFalse(self.resident.is_pwd)
        self.assertTrue(ActivityLog.objects.filter(
            action_type='ResidentDemographics', target_id=str(self.resident.id)).exists())

    def test_unchecked_boxes_clear_the_flags(self):
        self.resident.is_pwd = True
        self.resident.save()
        self.login(self.admin)
        self._post()
        self.resident.refresh_from_db()
        self.assertFalse(self.resident.is_pwd)

    def test_bad_input_changes_nothing(self):
        self.login(self.admin)
        self._post(gender='robot')
        self.resident.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.resident.first_name, 'Old')
        self.assertEqual(self.user.first_name, 'Old')
        self.assertEqual(self.resident.gender, '')

    def test_edit_does_not_write_demographics_to_the_user(self):
        self.login(self.admin)
        self._post()
        self.user.refresh_from_db()
        self.assertFalse(hasattr(self.user, 'civil_status'))

    def test_staff_without_edit_permission_gets_403(self):
        self.login(make_staff(permissions={'residents': ['view']}))
        self.assertEqual(self._post().status_code, 403)
        self.resident.refresh_from_db()
        self.assertEqual(self.resident.gender, '')

    def test_staff_with_edit_permission_can_edit(self):
        self.login(make_staff(permissions={'residents': ['view', 'edit']}))
        self.assertEqual(self._post().status_code, 302)
        self.resident.refresh_from_db()
        self.assertEqual(self.resident.gender, 'male')

    def test_service_enforces_permission_itself(self):
        staff = make_staff(permissions={'residents': ['view']})
        with self.assertRaises(PermissionDenied):
            update_resident_demographics_service(self.resident, staff, {'gender': 'male'})

    def test_missing_select_keeps_the_stored_value(self):
        self.resident.gender = 'female'
        self.resident.civil_status = 'married'
        self.resident.save()
        update_resident_demographics_service(self.resident, self.admin, {'is_pwd': '1'})
        self.resident.refresh_from_db()
        self.assertEqual((self.resident.gender, self.resident.civil_status), ('female', 'married'))
        self.assertTrue(self.resident.is_pwd)


class ResidentsPageTests(BaseTestCase):
    def test_register_modal_and_edit_fields_render_for_an_admin(self):
        self.login(make_admin())
        html = self.client.get(reverse('accounts:residents_tabbed'), {'tab': 'records'}).content.decode()
        self.assertIn('id="registerResidentModal"', html)
        self.assertIn(reverse('accounts:staff_register_resident'), html)
        self.assertIn('js/resident_register_modal.js', html)
        self.assertIn('id="edit-res-gender"', html)
        self.assertIn('<option value="single">Single</option>', html)
        self.assertNotIn('<option value="Single">', html)

    def test_register_button_is_hidden_without_create_permission(self):
        self.login(make_staff(permissions={'residents': ['view']}))
        html = self.client.get(reverse('accounts:residents_tabbed'), {'tab': 'records'}).content.decode()
        self.assertNotIn('id="registerResidentModal"', html)
