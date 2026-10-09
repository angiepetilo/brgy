"""
Data migration: rewrite User.phone_number and Resident.contact_no to the
canonical 09XXXXXXXXX form (apps.core.validators.normalize_ph_mobile).

- '0917-111-2222', '0917 111 2222', '+63 917 111 2222', '639171112222' -> '09171112222'
- valid values are kept as they are; blank values stay blank
- values that cannot be normalized are NOT changed or deleted. Their ids are
  printed and logged (logger 'apps.migrations') so an admin can fix them by
  hand (Residents page > Edit, or Django admin). See docs/deployment.md.

Reverse is a no-op: the original formatting is not needed by any code.
"""
from django.db import migrations

from apps.core.migration_utils import normalize_phone_field


def forwards(apps, schema_editor):
    normalize_phone_field(apps, 'accounts', 'User', 'phone_number')
    normalize_phone_field(apps, 'accounts', 'Resident', 'contact_no')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_phone_validators'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
