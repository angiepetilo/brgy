"""
Schema-only migration (3 of 3): drop the demographics that moved to Resident.

The values were copied by 0014. Reversing re-creates the columns with their original
defaults; reversing 0014 then refills them from Resident.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_backfill_resident_demographics'),
    ]

    operations = [
        migrations.RemoveField(model_name='user', name='is_senior'),
        migrations.RemoveField(model_name='user', name='is_pwd'),
        migrations.RemoveField(model_name='user', name='is_4ps'),
        migrations.RemoveField(model_name='user', name='civil_status'),
    ]
