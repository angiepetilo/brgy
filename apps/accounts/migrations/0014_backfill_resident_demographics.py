"""
Data-only migration (2 of 3): copy User demographics onto the linked Resident.

Runs while User.is_pwd / is_4ps / civil_status still exist (they are dropped by 0015).

Forward
-------
* Residents linked to a User: is_pwd <- User.is_pwd, is_4ps <- User.is_4ps,
  civil_status <- User.civil_status normalised to a lowercase code.
* Any Resident (linked or not): 'pwd' in needs_categories (comma separated, trimmed,
  case-insensitive) sets is_pwd=True. Existing True values are never cleared.
* civil_status: 'Single' -> 'single' etc. Blank or unknown values become 'single'.
* Seniors are NOT stored; they are derived from birthdate.
* Users holding demographics but without a linked Resident are left untouched and
  counted in the log (nothing can be copied to a record that does not exist).

Reverse
-------
Copies Resident.is_pwd / is_4ps / civil_status (capitalised, the legacy style) back onto
the linked User and recomputes User.is_senior from the birthdate.
"""
import logging

from django.db import migrations
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

BATCH = 500
CIVIL_CODES = {'single', 'married', 'widowed', 'separated', 'divorced'}
SENIOR_AGE = 60


def normalize_civil_status(value):
    code = str(value or '').strip().lower()
    return code if code in CIVIL_CODES else 'single'


def needs_pwd(needs_categories):
    tokens = [t.strip().lower() for t in str(needs_categories or '').split(',')]
    return 'pwd' in tokens


def _age(birthdate, today):
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def _flush(model, rows, fields):
    if rows:
        model.objects.bulk_update(rows, fields)
        rows.clear()


def _pages(queryset):
    """Yield lists of rows ordered by pk, so writes never interleave with an open cursor."""
    last_pk = 0
    while True:
        page = list(queryset.filter(pk__gt=last_pk).order_by('pk')[:BATCH])
        if not page:
            return
        yield page
        last_pk = page[-1].pk


def forwards(apps, schema_editor):
    Resident = apps.get_model('accounts', 'Resident')
    User = apps.get_model('accounts', 'User')
    fields = ['is_pwd', 'is_4ps', 'civil_status']
    batch = []

    for page in _pages(Resident.objects.select_related('user')):
        for resident in page:
            user = resident.user
            is_pwd = resident.is_pwd or needs_pwd(resident.needs_categories)
            is_4ps = resident.is_4ps
            civil_status = resident.civil_status
            if user is not None:
                is_pwd = is_pwd or bool(user.is_pwd)
                is_4ps = is_4ps or bool(user.is_4ps)
                civil_status = normalize_civil_status(user.civil_status)
            if (is_pwd, is_4ps, civil_status) != (resident.is_pwd, resident.is_4ps, resident.civil_status):
                resident.is_pwd = is_pwd
                resident.is_4ps = is_4ps
                resident.civil_status = civil_status
                batch.append(resident)
        _flush(Resident, batch, fields)

    orphans = User.objects.filter(resident_profile__isnull=True).filter(Q(is_pwd=True) | Q(is_4ps=True)).count()
    if orphans:
        logger.warning(
            'accounts.0014: %d user(s) with PWD/4Ps flags have no linked Resident; not migrated.', orphans
        )


def backwards(apps, schema_editor):
    Resident = apps.get_model('accounts', 'Resident')
    User = apps.get_model('accounts', 'User')
    today = timezone.localdate()
    fields = ['is_pwd', 'is_4ps', 'civil_status', 'is_senior']
    batch = []

    for page in _pages(Resident.objects.filter(user__isnull=False).select_related('user')):
        for resident in page:
            user = resident.user
            user.is_pwd = resident.is_pwd
            user.is_4ps = resident.is_4ps
            user.civil_status = (resident.civil_status or 'single').capitalize()
            user.is_senior = bool(resident.birthdate) and _age(resident.birthdate, today) >= SENIOR_AGE
            batch.append(user)
        _flush(User, batch, fields)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_resident_demographics'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
