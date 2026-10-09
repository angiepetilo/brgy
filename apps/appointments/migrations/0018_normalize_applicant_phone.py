"""
Data migration: rewrite Appointment.applicant_phone to 09XXXXXXXXX.
Same rules as accounts 0019_normalize_phone_numbers: invalid values are kept
unchanged and their ids printed/logged; reverse is a no-op.
"""
from django.db import migrations

from apps.core.migration_utils import normalize_phone_field


def forwards(apps, schema_editor):
    normalize_phone_field(apps, 'appointments', 'Appointment', 'applicant_phone')


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0017_applicant_phone_validator'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
