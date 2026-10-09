"""
Shared test factories and base test case for the whole suite.

Usage:
    from tests.base import BaseTestCase, make_admin, make_staff, make_resident_user

Factories are plain functions so they can be used from TestCase.setUp,
setUpTestData, or pytest fixtures. Every factory accepts keyword overrides.
Keep this module free of assertions and free of business logic.
"""

import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client

from apps.accounts.models import (
    User, Resident, Purok, Officer, StaffAssignment, PermissionRule,
)
from apps.appointments.models import Appointment, DocumentType, HealthCareService

DEFAULT_PASSWORD = 'Str0ng-Test-Pass!'

# Minimal files whose first bytes pass apps.core.uploads.validate_upload
# (extension + magic bytes). Uploads with arbitrary bytes are rejected.
JPEG_BYTES = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + b'\x00' * 32 + b'\xff\xd9'
PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)
WEBP_BYTES = b'RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00/\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00'
PDF_BYTES = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def upload_jpeg(name='id.jpg'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, JPEG_BYTES, content_type='image/jpeg')


def upload_png(name='id.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, PNG_BYTES, content_type='image/png')

_counter = itertools.count(1)


def _n():
    """Monotonic counter used to build unique usernames and emails."""
    return next(_counter)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def make_admin(**overrides):
    n = _n()
    data = dict(
        username=f'admin{n}',
        email=f'admin{n}@barangay.test',
        password=DEFAULT_PASSWORD,
        role=User.ROLE_ADMIN,
        is_staff=True,
        is_superuser=True,
        is_approved=True,
        status=User.STATUS_ACTIVE,
        first_name='Admin',
        last_name=f'User{n}',
    )
    data.update(overrides)
    return User.objects.create_user(**data)


def make_officer(position='Secretary', committee='', **overrides):
    return Officer.objects.create(position=position, committee=committee, **overrides)


def grant(officer, module, *actions, allowed=True):
    """Create PermissionRule rows for officer on module for each action."""
    return [
        PermissionRule.objects.update_or_create(
            officer=officer, module=module, action=action,
            defaults={'allowed': allowed},
        )[0]
        for action in actions
    ]


def make_staff(permissions=None, scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
               scope_value='all', position='Secretary', **overrides):
    """
    Create an active staff user with one StaffAssignment.

    permissions: dict like {'residents': ['view', 'create'], 'appointments': ['approve']}
    """
    n = _n()
    data = dict(
        username=f'staff{n}',
        email=f'staff{n}@barangay.test',
        password=DEFAULT_PASSWORD,
        role=User.ROLE_STAFF,
        is_staff=True,
        is_approved=True,
        status=User.STATUS_ACTIVE,
        first_name='Staff',
        last_name=f'User{n}',
    )
    data.update(overrides)
    user = User.objects.create_user(**data)
    officer = make_officer(position=position)
    StaffAssignment.objects.create(
        user=user, officer=officer, scope_type=scope_type, scope_value=scope_value,
    )
    for module, actions in (permissions or {}).items():
        grant(officer, module, *actions)
    user.test_officer = officer
    return user


def make_resident_user(**overrides):
    n = _n()
    data = dict(
        username=f'resident{n}',
        email=f'resident{n}@barangay.test',
        password=DEFAULT_PASSWORD,
        role=User.ROLE_RESIDENT,
        is_approved=True,
        status=User.STATUS_ACTIVE,
        first_name='Resident',
        last_name=f'User{n}',
    )
    data.update(overrides)
    return User.objects.create_user(**data)


# ---------------------------------------------------------------------------
# Residents, puroks
# ---------------------------------------------------------------------------
def make_purok(name=None, **overrides):
    name = name or f'Purok {_n()}'
    purok, _ = Purok.objects.get_or_create(name=name, defaults=overrides)
    return purok


def make_resident_profile(user=None, purok=None, **overrides):
    n = _n()
    data = dict(
        first_name='Juan',
        last_name=f'Dela Cruz {n}',
        birthdate=date(1990, 1, 1),
        contact_no='09171234567',
        address='Sample Street',
        purok=purok,
        user=user,
    )
    data.update(overrides)
    return Resident.objects.create(**data)


# ---------------------------------------------------------------------------
# Appointment catalog and bookings
# ---------------------------------------------------------------------------
def make_document_type(name=None, fee='50.00', **overrides):
    n = _n()
    data = dict(
        name=name or f'Document {n}',
        code=f'doc_{n}',
        fee=Decimal(str(fee)),
        is_active=True,
    )
    data.update(overrides)
    return DocumentType.objects.create(**data)


def make_health_service(name=None, **overrides):
    data = dict(name=name or f'Health Service {_n()}', is_active=True, is_free=True)
    data.update(overrides)
    return HealthCareService.objects.create(**data)


def get_document_type(code, name, **defaults):
    """
    Return the DocumentType for `code` (or `name`), creating it only if missing.
    The data migration seeds the four standard types, so tests must not blindly
    create them again (name is unique).
    """
    return (
        DocumentType.objects.filter(code=code).first()
        or DocumentType.objects.filter(name=name).first()
        or DocumentType.objects.create(name=name, code=code, **{'fee': Decimal('0.00'), 'is_active': True, **defaults})
    )


def get_clearance_type():
    """Shared 'Barangay Clearance' DocumentType."""
    return get_document_type('clearance', 'Barangay Clearance')

def make_appointment(resident=None, days_ahead=2, **overrides):
    """
    Create a document appointment by default (canonical columns only).

    Pass `document_type=<DocumentType>` to choose the document. Health
    appointments (category='healthcare') get no document type.
    """
    when = date.today() + timedelta(days=days_ahead)
    data = dict(
        resident=resident,
        category=Appointment.CATEGORY_DOCUMENT,
        purpose='Employment requirement',
        appt_date=when,
        time_window=Appointment.TIME_SLOT_MORNING,
        status=Appointment.STATUS_PENDING,
    )
    data.update(overrides)
    if 'document_type' not in data and data['category'] == Appointment.CATEGORY_DOCUMENT:
        data['document_type'] = get_clearance_type()
    return Appointment.objects.create(**data)


# ---------------------------------------------------------------------------
# Blotter
# ---------------------------------------------------------------------------
def make_blotter_case(parties=None, filed_at=None, **overrides):
    """
    Insert a BlotterCase directly (no service, no audit row). case_no uses a
    'BLT-TST-' prefix so it never collides with real 'BLT-YYYY-' numbering.
    filed_at (aware datetime) is applied after insert because the field is auto_now_add.
    parties: list of (role, full_name) tuples; default one complainant and one respondent.
    """
    from django.utils import timezone
    from apps.blotter.models import BlotterCase, BlotterParty
    n = _n()
    data = dict(
        case_no=f'BLT-TST-{n:05d}',
        incident_type=BlotterCase.TYPE_DISPUTE,
        incident_date=timezone.localdate() - timedelta(days=1),
        location='Sample Street',
        narrative='Sample narrative.',
        status=BlotterCase.STATUS_FILED,
    )
    data.update(overrides)
    case = BlotterCase.objects.create(**data)
    if filed_at is not None:
        BlotterCase.objects.filter(pk=case.pk).update(filed_at=filed_at)
        case.refresh_from_db()
    if parties is None:
        parties = [(BlotterParty.ROLE_COMPLAINANT, f'Complainant {n}'), (BlotterParty.ROLE_RESPONDENT, f'Respondent {n}')]
    for role, name in parties:
        BlotterParty.objects.create(case=case, role=role, full_name=name)
    return case


# ---------------------------------------------------------------------------
# Base test case
# ---------------------------------------------------------------------------
class BaseTestCase(TestCase):
    """TestCase with a client and login helpers. Works with manage.py test and pytest."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    def login(self, user, password=DEFAULT_PASSWORD):
        ok = self.client.login(username=user.username, password=password)
        self.assertTrue(ok, f'Could not log in as {user.username}')
        return user

    def logout(self):
        self.client.logout()
