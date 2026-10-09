"""Helpers shared by the blotter tests (users bound to the seeded officer positions)."""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Officer, StaffAssignment, User
from apps.blotter.models import BlotterParty
from tests.base import DEFAULT_PASSWORD, _n

ALL_ACTIONS = ['view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential']


def seeded_user(position, committee='', scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value='all'):
    """Active staff user assigned to the seeded Officer row (call seed_default_permissions first)."""
    officer = Officer.objects.filter(position=position, committee=committee).first()
    assert officer is not None, f'No seeded officer {position}/{committee}'
    n = _n()
    user = User.objects.create_user(
        username=f'blt{n}', email=f'blt{n}@barangay.test', password=DEFAULT_PASSWORD,
        role=User.ROLE_STAFF, is_staff=True, is_approved=True, status=User.STATUS_ACTIVE,
        first_name='Officer', last_name=str(n),
    )
    StaffAssignment.objects.create(user=user, officer=officer, scope_type=scope_type, scope_value=scope_value)
    return user


def case_data(**overrides):
    data = {
        'incident_type': 'dispute',
        'incident_date': timezone.localdate() - timedelta(days=1),
        'location': 'Corner of Rizal St.',
        'narrative': 'Neighbours argued over a fence line.',
    }
    data.update(overrides)
    return data


def two_parties(**complainant):
    first = {'role': BlotterParty.ROLE_COMPLAINANT, 'full_name': 'Maria Santos', 'contact_no': '09171234567'}
    first.update(complainant)
    return [first, {'role': BlotterParty.ROLE_RESPONDENT, 'full_name': 'Pedro Reyes'}]


def api_payload(**overrides):
    payload = {
        'incident_type': 'noise',
        'incident_date': (timezone.localdate() - timedelta(days=2)).isoformat(),
        'location': 'Purok basketball court',
        'narrative': 'Loud videoke past midnight.',
        'parties': [
            {'role': 'complainant', 'full_name': 'Ana Cruz', 'contact_no': '09181234567'},
            {'role': 'respondent', 'full_name': 'Jose Lim', 'address': 'Block 2'},
        ],
    }
    payload.update(overrides)
    return payload


def form_post(**overrides):
    """POST data for the HTML case form (formset prefix 'parties')."""
    data = {
        'incident_type': 'dispute',
        'incident_date': (timezone.localdate() - timedelta(days=1)).isoformat(),
        'location': 'Market road',
        'narrative': 'Dispute over a debt.',
        'parties-TOTAL_FORMS': '3',
        'parties-INITIAL_FORMS': '0',
        'parties-MIN_NUM_FORMS': '0',
        'parties-MAX_NUM_FORMS': '1000',
        'parties-0-role': 'complainant',
        'parties-0-full_name': 'Lorna Diaz',
        'parties-0-contact_no': '09191234567',
        'parties-1-role': 'respondent',
        'parties-1-full_name': 'Ramon Uy',
        'parties-2-role': '',
        'parties-2-full_name': '',
    }
    data.update(overrides)
    return data
