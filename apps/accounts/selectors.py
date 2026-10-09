"""
Read-only queries for the accounts app.

Views and context processors call these helpers instead of embedding lookups
or hard-coded fallbacks, so every screen shows the same, database-driven value.
"""
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

# Age bands as (code, label, min_age, max_age). max_age None means open-ended.
AGE_BANDS = [
    ('0_17', '0-17', 0, 17),
    ('18_29', '18-29', 18, 29),
    ('30_44', '30-44', 30, 44),
    ('45_59', '45-59', 45, 59),
    ('60_plus', '60+', 60, None),
]


def get_contact_number():
    """
    Official Barangay contact number shown to the public.

    Order: BarangayInfo.contact_no (editable in System Settings), then
    settings.BARANGAY_CONTACT, then an empty string. No literal number lives in code.
    """
    from apps.accounts.models import BarangayInfo

    info = BarangayInfo.get_solo()
    number = (info.contact_no or '').strip()
    if number:
        return number
    return (getattr(settings, 'BARANGAY_CONTACT', '') or '').strip()


# ---------------------------------------------------------------------------
# Demographics (Resident is the single source; archived residents never count)
# ---------------------------------------------------------------------------

def years_ago(today, years):
    """
    The date `years` before `today`. Feb 29 falls back to Feb 28 when the target
    year has no Feb 29 (never date.replace(year=...), which raises ValueError).
    """
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return date(today.year - years, 2, 28)


def senior_cutoff(today=None):
    """Residents born on or before this date are seniors (age >= Resident.SENIOR_AGE)."""
    from apps.accounts.models import Resident

    return years_ago(today or timezone.localdate(), Resident.SENIOR_AGE)


def counted_residents_q(prefix=''):
    """
    Population rule as a Q on Resident (``prefix`` e.g. 'residents__' from Purok).

    A Resident counts when it is not archived AND it either has no portal account
    (staff-registered) or its linked account is active. Pending, rejected and
    disabled sign-ups do not count.
    """
    from apps.accounts.models import User

    return Q(**{f'{prefix}is_archived': False}) & (
        Q(**{f'{prefix}user__isnull': True}) | Q(**{f'{prefix}user__status': User.STATUS_ACTIVE})
    )


def active_residents(purok_id=None):
    """Residents that count toward the population (see counted_residents_q), optionally in one purok."""
    from apps.accounts.models import Resident

    qs = Resident.objects.filter(counted_residents_q())
    if purok_id:
        qs = qs.filter(purok_id=purok_id)
    return qs


def seniors(queryset=None, today=None):
    """Queryset twin of Resident.is_senior: filters by birthdate, nothing is stored."""
    if queryset is None:
        queryset = active_residents()
    return queryset.filter(birthdate__lte=senior_cutoff(today))


def population(purok_id=None):
    """Counted residents (counted_residents_q): not archived, and no linked user or an active one."""
    return active_residents(purok_id).count()


def by_gender(purok_id=None):
    """[{'code', 'label', 'count'}] for every gender choice plus 'Not specified' (legacy blank)."""
    from apps.accounts.models import Resident

    counts = dict(
        active_residents(purok_id).values_list('gender').annotate(n=Count('id')).order_by()
    )
    rows = [
        {'code': code, 'label': label, 'count': counts.get(code, 0)}
        for code, label in Resident.GENDER_CHOICES
    ]
    rows.append({'code': '', 'label': 'Not specified', 'count': counts.get('', 0)})
    return rows


def by_civil_status(purok_id=None):
    """[{'code', 'label', 'count'}] for every civil status choice (zero filled)."""
    from apps.accounts.models import Resident

    counts = dict(
        active_residents(purok_id).values_list('civil_status').annotate(n=Count('id')).order_by()
    )
    return [
        {'code': code, 'label': label, 'count': counts.get(code, 0)}
        for code, label in Resident.CIVIL_STATUS_CHOICES
    ]


def by_sector(purok_id=None, today=None):
    """
    Special sectors. A resident can belong to several, so these do not sum to the
    population. Seniors are derived from birthdate.
    """
    totals = active_residents(purok_id).aggregate(
        senior=Count('id', filter=Q(birthdate__lte=senior_cutoff(today))),
        pwd=Count('id', filter=Q(is_pwd=True)),
        solo_parent=Count('id', filter=Q(is_solo_parent=True)),
        four_ps=Count('id', filter=Q(is_4ps=True)),
    )
    return [
        {'code': 'senior', 'label': 'Senior Citizens (60+)', 'count': totals['senior']},
        {'code': 'pwd', 'label': 'Persons with Disability (PWD)', 'count': totals['pwd']},
        {'code': 'solo_parent', 'label': 'Solo Parents', 'count': totals['solo_parent']},
        {'code': '4ps', 'label': '4Ps Beneficiaries', 'count': totals['four_ps']},
    ]


def age_bands(purok_id=None, today=None):
    """
    {'bands': [{'code', 'label', 'count'}], 'minors': int}. Bands cover every resident
    exactly once. The first band has no lower bound, so a bad future birthdate still
    lands somewhere instead of vanishing from the totals.
    """
    today = today or timezone.localdate()
    aggregates = {}
    for code, _label, low, high in AGE_BANDS:
        condition = Q()
        if low:  # age >= low  <=>  birthdate <= years_ago(low)
            condition &= Q(birthdate__lte=years_ago(today, low))
        if high is not None:  # age <= high  <=>  birthdate > years_ago(high + 1)
            condition &= Q(birthdate__gt=years_ago(today, high + 1))
        aggregates[code] = Count('id', filter=condition)
    totals = active_residents(purok_id).aggregate(**aggregates)
    bands = [
        {'code': code, 'label': label, 'count': totals[code]}
        for code, label, _low, _high in AGE_BANDS
    ]
    return {'bands': bands, 'minors': totals['0_17']}


def population_per_purok(purok_id=None):
    """[{'purok_id', 'name', 'count'}] residents per purok, with an Unassigned bucket."""
    from apps.accounts.models import Purok

    puroks = Purok.objects.order_by('name')
    if purok_id:
        puroks = puroks.filter(id=purok_id)
    rows = list(
        puroks.annotate(n=Count('residents', filter=counted_residents_q('residents__')))
        .values('id', 'name', 'n')
    )
    result = [{'purok_id': r['id'], 'name': r['name'], 'count': r['n']} for r in rows]
    if not purok_id:
        result.append({
            'purok_id': None,
            'name': 'Unassigned',
            'count': active_residents().filter(purok__isnull=True).count(),
        })
    return result


def households_per_purok(purok_id=None):
    """
    [{'purok_id', 'name', 'households'}] for the purok density report, zero filled and
    ending with an Unassigned bucket (skipped when filtering by purok). Households have
    no archive flag, so one whose members no longer count (archived, or linked to a
    non-active account) is not counted.
    """
    from apps.accounts.models import Household, Purok

    dead = Household.objects.annotate(
        member_total=Count('members'),
        member_active=Count('members', filter=counted_residents_q('members__')),
    ).filter(member_total__gt=0, member_active=0).order_by().values('pk')

    counts = {
        row['purok']: row['n']
        for row in Household.objects.exclude(pk__in=dead).values('purok').annotate(n=Count('id')).order_by()
    }
    puroks = Purok.objects.order_by('name')
    if purok_id:
        puroks = puroks.filter(id=purok_id)
    result = [
        {'purok_id': p.id, 'name': p.name, 'households': counts.get(p.id, 0)}
        for p in puroks
    ]
    if not purok_id:
        result.append({'purok_id': None, 'name': 'Unassigned', 'households': counts.get(None, 0)})
    return result


# ---------------------------------------------------------------------------
# System Settings dashboard
# ---------------------------------------------------------------------------
SYSTEM_TABS = ('barangay_info', 'post_categories', 'document_health', 'user_management', 'appointment_setup', 'account', 'email_templates')
SYSTEM_SUBTABS = {
    'document_health': ('documents', 'health'),
    'user_management': ('staff', 'concerns'),
}
# Old tab names still accepted on incoming links; normalised to (tab, subtab).
SYSTEM_LEGACY_TABS = {
    'documents': ('document_health', 'documents'),
    'health_services': ('document_health', 'health'),
    'staff_accounts': ('user_management', 'staff'),
    'concern_categories': ('user_management', 'concerns'),
}


def normalize_system_tab(tab, subtab=''):
    """Return the canonical (tab, subtab) for the System Settings page. subtab is '' when the tab has none."""
    tab = (tab or '').strip()
    subtab = (subtab or '').strip()
    if tab in SYSTEM_LEGACY_TABS:
        return SYSTEM_LEGACY_TABS[tab]
    if tab not in SYSTEM_TABS:
        tab = 'barangay_info'
    valid = SYSTEM_SUBTABS.get(tab)
    if not valid:
        return tab, ''
    return tab, (subtab if subtab in valid else valid[0])


def staff_terms_ending_soon(days=30):
    """Active staff/admin/kapitan users whose term ends within the next ``days`` days."""
    from apps.accounts.models import User

    today = timezone.localdate()
    return User.objects.filter(
        role__in=[User.ROLE_STAFF, User.ROLE_ADMIN, User.ROLE_KAPITAN],
        status=User.STATUS_ACTIVE,
        term_end__isnull=False,
        term_end__gte=today,
        term_end__lte=today + timedelta(days=days),
    ).order_by('term_end')


def system_dashboard_data():
    """All database reads for the System Settings page, in one place."""
    from apps.accounts.models import BarangayInfo, User, Officer
    from apps.appointments.models import DocumentType, HealthCareService
    from apps.chat.models import ConcernCategory
    from apps.communications.models import PostCategory

    return {
        'info': BarangayInfo.get_solo(),
        'post_categories': PostCategory.objects.all().order_by('order', 'name'),
        'document_types': DocumentType.objects.all().prefetch_related('requirements').order_by('order', 'name'),
        'health_services': HealthCareService.objects.all().order_by('name'),
        'concern_categories': ConcernCategory.objects.all().order_by('name'),
        'staff_users': User.objects.filter(
            role__in=[User.ROLE_STAFF, User.ROLE_ADMIN, User.ROLE_KAPITAN]
        ).prefetch_related('staff_assignments__officer').order_by('last_name', 'first_name'),
        'terms_ending_soon': staff_terms_ending_soon(30),
        'officers': Officer.objects.all().order_by('position'),
    }
