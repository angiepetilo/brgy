"""B7: upload validation (extension + magic bytes + size), random names, private serving, IDOR."""
import importlib
import os
import shutil
import tempfile
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import StaffAssignment
from apps.accounts.services import staff_register_resident_service
from apps.appointments.services import book_appointment_service
from apps.core.uploads import validate_upload
from tests.base import (
    BaseTestCase, JPEG_BYTES, PDF_BYTES, PNG_BYTES, WEBP_BYTES, get_clearance_type, make_admin,
    make_appointment, make_purok, make_resident_profile, make_resident_user, make_staff,
)


def upload(name, content, content_type='application/octet-stream'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class ValidateUploadTests(TestCase):

    def test_accepts_real_files(self):
        for name, content in (('a.jpg', JPEG_BYTES), ('a.jpeg', JPEG_BYTES), ('a.png', PNG_BYTES),
                              ('a.webp', WEBP_BYTES), ('a.pdf', PDF_BYTES), ('A.JPG', JPEG_BYTES)):
            with self.subTest(name=name):
                validate_upload(upload(name, content))

    def test_rejects_text_renamed_to_jpg(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(upload('id.jpg', b'this is just text pretending to be a photo'))
        self.assertIn('not a valid', ctx.exception.messages[0])

    def test_rejects_mismatched_extension(self):
        with self.assertRaises(ValidationError):
            validate_upload(upload('id.png', JPEG_BYTES))  # JPEG bytes named .png

    def test_rejects_executable_and_unknown_types(self):
        for name, content in (('setup.exe', b'MZ\x90\x00'), ('page.html', b'<html>'), ('x.svg', b'<svg/>'),
                              ('noext', JPEG_BYTES), ('id.jpg.exe', JPEG_BYTES)):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_upload(upload(name, content))

    def test_rejects_files_over_5_mb(self):
        big = JPEG_BYTES + b'\x00' * (6 * 1024 * 1024)
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(upload('big.jpg', big))
        self.assertIn('5 MB', ctx.exception.messages[0])

    def test_file_position_is_restored(self):
        f = upload('a.png', PNG_BYTES)
        validate_upload(f)
        self.assertEqual(f.read(), PNG_BYTES)


class _PrivateMediaMixin:
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix='brgy-test-media-')
        self.private = os.path.join(self.tmp, 'private')
        self.public = os.path.join(self.tmp, 'public')
        self._override = override_settings(PRIVATE_MEDIA_ROOT=self.private, MEDIA_ROOT=self.public)
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()


class SupportingIdTests(_PrivateMediaMixin, BaseTestCase):

    def setUp(self):
        super().setUp()
        self.owner = make_resident_user()
        self.other = make_resident_user()
        self.apt = make_appointment(resident=self.owner)
        self.apt.supporting_id = upload('Juan Dela Cruz ID.jpg', JPEG_BYTES, 'image/jpeg')
        self.apt.save()
        self.url = reverse('appointments:supporting_id', args=[self.apt.pk])

    def test_stored_privately_with_random_name(self):
        name = self.apt.supporting_id.name
        self.assertTrue(name.startswith('appointments/supporting_docs/'))
        self.assertNotIn('Juan', name)
        self.assertRegex(os.path.basename(name), r'^[0-9a-f]{32}\.jpg$')
        self.assertTrue(os.path.isfile(os.path.join(self.private, name)))
        self.assertFalse(os.path.exists(os.path.join(self.public, name)))
        with self.assertRaises(ValueError):
            self.apt.supporting_id.url  # no public URL exists

    def test_owner_and_admin_get_the_file(self):
        for user in (self.owner, make_admin()):
            self.client.force_login(user)
            response = self.client.get(self.url)
            with self.subTest(user=user.username):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), JPEG_BYTES)
                self.assertEqual(response['Content-Type'], 'image/jpeg')
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_other_resident_cannot_fetch(self):
        self.client.force_login(self.other)
        self.assertIn(self.client.get(self.url).status_code, (403, 404))

    def test_out_of_scope_staff_cannot_fetch(self):
        staff = make_staff(permissions={'appointments': ['view']},
                           scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value='Health')
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_in_scope_staff_can_fetch(self):
        staff = make_staff(permissions={'appointments': ['view']},
                           scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value='Documents')
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_public_media_path_is_denied(self):
        self.client.force_login(self.owner)
        response = self.client.get('/media/' + self.apt.supporting_id.name)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/media/id_proofs/x.jpg').status_code, 403)

    def test_detail_page_links_to_the_protected_view(self):
        self.client.force_login(self.owner)
        html = self.client.get(reverse('appointments:detail', args=[self.apt.pk])).content.decode()
        self.assertIn(self.url, html)
        self.assertNotIn('/media/appointments/', html)

    def test_booking_rejects_fake_image(self):
        when = date.today() + timedelta(days=1)
        while when.weekday() >= 5:
            when += timedelta(days=1)
        data = {'category': 'document', 'document_type': get_clearance_type().pk, 'appt_date': when,
                'time_window': 'morning', 'purpose': 'Work',
                'supporting_id': upload('id.jpg', b'plain text', 'image/jpeg')}
        with self.assertRaises(ValueError):
            book_appointment_service(make_resident_user(), data)
        data['supporting_id'] = upload('id.pdf', PDF_BYTES, 'application/pdf')
        apt = book_appointment_service(make_resident_user(), data)
        self.assertTrue(apt.supporting_id.name.endswith('.pdf'))


class IdPhotoTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.owner = make_resident_user()
        self.resident = make_resident_profile(user=self.owner, purok=make_purok())
        self.resident.id_photo = upload('My Real Name.png', PNG_BYTES, 'image/png')
        self.resident.save()
        self.url = reverse('accounts:serve_id_photo', args=[self.resident.id])

    def tearDown(self):
        self.resident.id_photo.delete(save=False)
        super().tearDown()

    def test_random_name(self):
        self.assertNotIn('Real', self.resident.id_photo.name)
        self.assertRegex(os.path.basename(self.resident.id_photo.name), r'^[0-9a-f]{32}\.png$')

    def test_owner_gets_file_response(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(b''.join(response.streaming_content), PNG_BYTES)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_other_resident_forbidden(self):
        self.client.force_login(make_resident_user())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_signup_rejects_fake_id_photo(self):
        response = self.client.post(reverse('accounts:signup'), {
            'first_name': 'Fake', 'last_name': 'Photo', 'birthdate': '1990-01-01', 'contact_no': '09171234567',
            'email': 'fake.photo@example.com', 'purok': make_purok().id, 'address': 'Street',
            'gender': 'male', 'civil_status': 'single', 'privacy_consent': 'on',
            'id_photo': upload('id.jpg', b'text, not an image', 'image/jpeg'),
        })
        self.assertContains(response, 'not a valid')
        self.assertFalse(self.owner.__class__.objects.filter(email='fake.photo@example.com').exists())

    def test_signup_no_longer_writes_public_id_proof_copy(self):
        self.client.post(reverse('accounts:signup'), {
            'first_name': 'Real', 'last_name': 'Photo', 'birthdate': '1990-01-01', 'contact_no': '09171234567',
            'email': 'real.photo@example.com', 'purok': make_purok().id, 'address': 'Street',
            'gender': 'male', 'civil_status': 'single', 'privacy_consent': 'on',
            'id_photo': upload('id.jpg', JPEG_BYTES, 'image/jpeg'),
        })
        user = self.owner.__class__.objects.get(email='real.photo@example.com')
        self.assertFalse(user.id_proof)
        self.assertTrue(user.resident_profile.id_photo)
        user.resident_profile.id_photo.delete(save=False)


class SupportingDocsCopyMigrationTests(_PrivateMediaMixin, TestCase):
    """appointments 0020 copies public files to private storage with the same name, never deleting."""

    def _forwards(self):
        module = importlib.import_module('apps.appointments.migrations.0020_copy_supporting_docs_private')
        from django.apps import apps
        return module

    def test_copy_keeps_name_and_original(self):
        rel = 'appointments/supporting_docs/angie_gwapa.jpg'
        os.makedirs(os.path.join(self.public, 'appointments', 'supporting_docs'))
        with open(os.path.join(self.public, rel), 'wb') as fh:
            fh.write(JPEG_BYTES)
        apt = make_appointment(resident=make_resident_user())
        missing = make_appointment(resident=make_resident_user(), days_ahead=3)
        from apps.appointments.models import Appointment
        Appointment.objects.filter(pk=apt.pk).update(supporting_id=rel)
        Appointment.objects.filter(pk=missing.pk).update(supporting_id='appointments/supporting_docs/gone.jpg')

        module = self._forwards()
        from django.apps import apps as global_apps
        with self.assertLogs('apps.migrations', level='WARNING') as logs:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                module.forwards(global_apps, None)
        self.assertIn(str(missing.pk), '\n'.join(logs.output))
        self.assertTrue(os.path.isfile(os.path.join(self.private, rel)))
        self.assertTrue(os.path.isfile(os.path.join(self.public, rel)))  # original kept
        apt.refresh_from_db()
        self.assertEqual(apt.supporting_id.name, rel)
        with apt.supporting_id.open('rb') as fh:
            self.assertEqual(fh.read(), JPEG_BYTES)
        # Re-running is safe.
        with contextlib.redirect_stdout(io.StringIO()), self.assertLogs('apps.migrations', level='WARNING'):
            module.forwards(global_apps, None)
