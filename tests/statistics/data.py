"""
Known dataset for the statistics tests. Every expected number in the tests is derived
from this file by hand, so change both together.

Residents (non-archived unless noted)
    Alpha : A1 male   70 married  PWD
            A2 female 35 married  solo parent, 4Ps
            A3 female 10 single
            (archived female 50, in a household whose only member is archived)
    Beta  : B1 male   40 single
            B2 other  20 separated 4Ps
    none  : U1 (no gender) 60 widowed            -> exactly 60 is a senior
Households: Alpha 2 (+1 dead), Beta 1, no purok 1.

Appointments (M0 = this month, M1/M2/M3 = 1/2/3 months back; dt_cert fee 100, dt_permit fee 25)
    a1  ua cert    completed fee_at_booking 120.00  M0
    a2  ua cert    completed fee_at_booking None    M1        (falls back to 100.00)
    a3  ub permit  completed fee_at_booking 0.00    M1        (free snapshot stays 0)
    a4  ub permit  completed fee_at_booking None    M2        (falls back to 25.00)
    a5  ua cert    pending                          M0
    a6  ub permit  rejected                         M1
    a7  ua health  completed                        M0
    a8  ub cert    no_show                          M2
    a9  ua cert    completed fee 500.00             14 months back (always out of range)
    a10 walk-in cert completed fee 10.00            M0

Completing a document appointment makes a post_save signal create its IssuedDocumentLog
(and a QR image), so a1-a4, a9 and a10 are issued; a7 is health care and is not.
"""
import atexit
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Household
from apps.accounts.selectors import years_ago
from apps.appointments.models import Appointment
from apps.statistics.selectors import _month_start
from tests.base import (
    make_document_type, make_health_service, make_appointment, make_purok,
    make_resident_profile, make_resident_user,
)


# Completed documents get a QR image from a signal; keep those files out of the real media folder.
TEMP_MEDIA = tempfile.mkdtemp(prefix='brgy-stats-media-')
atexit.register(shutil.rmtree, TEMP_MEDIA, ignore_errors=True)


def seed():
    today = timezone.localdate()
    d = {'today': today}
    d['M'] = {n: _month_start(today, n) for n in (0, 1, 2, 3, 14)}

    alpha, beta = make_purok('Alpha'), make_purok('Beta')
    d['alpha'], d['beta'] = alpha, beta

    ua, ub = make_resident_user(), make_resident_user()
    d['ua'], d['ub'] = ua, ub

    h_alpha1 = Household.objects.create(household_name='Alpha 1', purok=alpha)
    h_alpha2 = Household.objects.create(household_name='Alpha 2', purok=alpha)
    h_dead = Household.objects.create(household_name='Alpha dead', purok=alpha)
    h_beta = Household.objects.create(household_name='Beta 1', purok=beta)
    h_none = Household.objects.create(household_name='Nowhere', purok=None)

    make_resident_profile(user=ua, purok=alpha, gender='male', birthdate=years_ago(today, 70),
                          civil_status='married', is_pwd=True, household=h_alpha1)
    make_resident_profile(purok=alpha, gender='female', birthdate=years_ago(today, 35),
                          civil_status='married', is_solo_parent=True, is_4ps=True, household=h_alpha2)
    make_resident_profile(purok=alpha, gender='female', birthdate=years_ago(today, 10),
                          civil_status='single', household=h_alpha2)
    make_resident_profile(purok=alpha, gender='female', birthdate=years_ago(today, 50),
                          civil_status='single', is_archived=True, household=h_dead)
    make_resident_profile(user=ub, purok=beta, gender='male', birthdate=years_ago(today, 40),
                          civil_status='single', household=h_beta)
    make_resident_profile(purok=beta, gender='other', birthdate=years_ago(today, 20),
                          civil_status='separated', is_4ps=True, household=h_beta)
    make_resident_profile(purok=None, gender='', birthdate=years_ago(today, 60),
                          civil_status='widowed', household=h_none)

    cert = make_document_type('Test Certificate', fee='100.00')
    permit = make_document_type('Test Permit', fee='25.00')
    checkup = make_health_service('Test Checkup')
    d['cert'], d['permit'], d['checkup'] = cert, permit, checkup

    def appt(resident, when, status, document_type=None, fee=None, **extra):
        return make_appointment(
            resident=resident, appt_date=when, status=status, document_type=document_type,
            fee_at_booking=fee, **extra)

    M = d['M']
    C, P = Appointment.STATUS_COMPLETED, Appointment.STATUS_PENDING
    d['a1'] = appt(ua, M[0].replace(day=1), C, cert, Decimal('120.00'))
    d['a2'] = appt(ua, M[1].replace(day=15), C, cert)
    d['a3'] = appt(ub, M[1].replace(day=20), C, permit, Decimal('0.00'))
    d['a4'] = appt(ub, M[2].replace(day=10), C, permit)
    d['a5'] = appt(ua, M[0].replace(day=2), P, cert)
    d['a6'] = appt(ub, M[1].replace(day=5), Appointment.STATUS_REJECTED, permit)
    d['a7'] = make_appointment(
        resident=ua, category=Appointment.CATEGORY_HEALTHCARE, document_type=None,
        healthcare_service=checkup, appt_date=M[0].replace(day=3), status=C)
    d['a8'] = appt(ub, M[2].replace(day=12), Appointment.STATUS_NO_SHOW, cert)
    d['a9'] = appt(ua, M[14].replace(day=10), C, cert, Decimal('500.00'))
    d['a10'] = appt(None, M[0].replace(day=4), C, cert, Decimal('10.00'))

    # A range that starts three months back so M3 is a month without any revenue.
    d['range'] = {'date_from': M[3].isoformat(), 'date_to': date(
        today.year, today.month, 28).isoformat()}
    return d
