"""B6: every model, form and API that accepts a mobile number enforces 09XXXXXXXXX."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.forms import ProfileUpdateForm, ResidentRegistrationForm
from apps.accounts.models import Resident
from apps.core.validators import PH_MOBILE_MESSAGE
from tests.base import (
    BaseTestCase, get_clearance_type, make_admin, make_appointment, make_purok,
    make_resident_profile, make_resident_user, make_staff, upload_jpeg,
)

BAD = ['0917-123-4567', '+639171234567', '0917123456', '0917 123 4567', '0917abc4567']


class ModelFullCleanTests(TestCase):

    def test_user_phone_number(self):
        user = make_resident_user(phone_number='09171234567')
        user.full_clean()
        for value in BAD:
            user.phone_number = value
            with self.subTest(value=value), self.assertRaises(ValidationError) as ctx:
                user.full_clean()
            self.assertIn('phone_number', ctx.exception.message_dict)

    def test_resident_contact_no(self):
        resident = make_resident_profile(purok=make_purok())
        resident.contact_no = ''
        resident.full_clean(exclude=['id_photo'])  # blank allowed
        for value in BAD:
            resident.contact_no = value
            with self.subTest(value=value), self.assertRaises(ValidationError) as ctx:
                resident.full_clean(exclude=['id_photo'])
            self.assertEqual(ctx.exception.message_dict['contact_no'], [PH_MOBILE_MESSAGE])

    def test_appointment_applicant_phone(self):
        apt = make_appointment(resident=make_resident_user())
        apt.applicant_phone = '09171234567'
        apt.full_clean(exclude=['supporting_id'])
        apt.applicant_phone = '0917-123-4567'
        with self.assertRaises(ValidationError) as ctx:
            apt.full_clean(exclude=['supporting_id'])
        self.assertIn('applicant_phone', ctx.exception.message_dict)


class FormTests(TestCase):

    def _signup_data(self, phone):
        return {
            'first_name': 'Ana', 'last_name': 'Reyes', 'birthdate': '1990-01-01', 'contact_no': phone,
            'email': 'ana.reyes@example.com', 'purok': make_purok().id, 'address': 'Street',
            'gender': 'female', 'civil_status': 'single', 'privacy_consent': 'on',
        }

    def test_signup_form(self):
        ok = ResidentRegistrationForm(self._signup_data('09171234567'), {'id_photo': upload_jpeg()})
        self.assertTrue(ok.is_valid(), ok.errors)
        for value in BAD:
            form = ResidentRegistrationForm(self._signup_data(value), {'id_photo': upload_jpeg()})
            with self.subTest(value=value):
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors['contact_no'], [PH_MOBILE_MESSAGE])

    def test_signup_widget_has_mobile_attributes(self):
        html = str(ResidentRegistrationForm()['contact_no'])
        for attr in ('inputmode="numeric"', 'pattern="09[0-9]{9}"', 'maxlength="11"', 'data-phone'):
            self.assertIn(attr, html)

    def test_profile_form(self):
        user = make_resident_user()
        base = {'first_name': 'A', 'last_name': 'B', 'email': user.email, 'status_message': ''}
        self.assertTrue(ProfileUpdateForm({**base, 'phone_number': '09171234567'}, instance=user).is_valid())
        self.assertTrue(ProfileUpdateForm({**base, 'phone_number': ''}, instance=user).is_valid())
        form = ProfileUpdateForm({**base, 'phone_number': '0917-123-4567'}, instance=user)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['phone_number'], [PH_MOBILE_MESSAGE])
        html = str(ProfileUpdateForm(instance=user)['phone_number'])
        for attr in ('inputmode="numeric"', 'pattern="09[0-9]{9}"', 'maxlength="11"', 'data-phone'):
            self.assertIn(attr, html)


class ViewAndApiTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()

    def _messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_signup_view_shows_clear_message(self):
        data = FormTests._signup_data(self, '0917-123-4567')
        data['id_photo'] = upload_jpeg()
        response = self.client.post(reverse('accounts:signup'), data)
        self.assertContains(response, PH_MOBILE_MESSAGE)
        self.assertFalse(Resident.objects.filter(first_name='Ana', last_name='Reyes').exists())

    def test_profile_view(self):
        user = self.login(make_resident_user(phone_number='09170000000'))
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'A', 'last_name': 'B', 'email': user.email, 'phone_number': '+639171234567',
        })
        self.assertContains(response, PH_MOBILE_MESSAGE)
        user.refresh_from_db()
        self.assertEqual(user.phone_number, '09170000000')

    def test_resident_edit_rejects_bad_phone(self):
        self.login(make_admin())
        resident_user = make_resident_user(phone_number='09170000000')
        response = self.client.post(reverse('accounts:resident_edit', args=[resident_user.id]), {
            'first_name': 'New', 'phone_number': '0917-123-4567', 'civil_status': 'single',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(PH_MOBILE_MESSAGE, self._messages(response))
        resident_user.refresh_from_db()
        self.assertEqual((resident_user.first_name, resident_user.phone_number), ('Resident', '09170000000'))

    def test_staff_register_resident_rejects_bad_phone(self):
        self.login(make_admin())
        response = self.client.post(reverse('accounts:staff_register_resident'), {
            'first_name': 'Minor', 'last_name': 'Child', 'birthdate': '2015-01-01',
            'contact_no': '0917 123 4567', 'civil_status': 'single',
        })
        self.assertIn(PH_MOBILE_MESSAGE, self._messages(response))
        self.assertFalse(Resident.objects.filter(first_name='Minor', last_name='Child').exists())

    def test_staff_register_resident_allows_blank_phone(self):
        self.login(make_admin())
        self.client.post(reverse('accounts:staff_register_resident'), {
            'first_name': 'Minor', 'last_name': 'Child', 'birthdate': '2015-01-01',
            'contact_no': '', 'civil_status': 'single',
        })
        self.assertTrue(Resident.objects.filter(first_name='Minor', last_name='Child').exists())

    @mock.patch('apps.appointments.views.validate_email_address', return_value=(True, 'ok', {}))
    def test_public_booking_api_rejects_bad_phone(self, _validator):
        self.login(make_resident_user())
        next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) or 7)
        base = {
            'first_name': 'Ana', 'last_name': 'Reyes', 'age': '30', 'address': 'Street',
            'email': 'ana@example.com', 'category': 'document', 'document_type': get_clearance_type().pk,
            'appt_date': next_monday.isoformat(), 'time_window': 'morning', 'purpose': 'Work',
        }
        for value in BAD:
            with self.subTest(value=value):
                response = self.client.post(reverse('appointments:api_public_book'), {**base, 'phone_number': value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['errors']['phone_number'], PH_MOBILE_MESSAGE)
        ok = self.client.post(reverse('appointments:api_public_book'), {**base, 'phone_number': '09171234567'})
        self.assertNotIn('phone_number', ok.json().get('errors', {}))
