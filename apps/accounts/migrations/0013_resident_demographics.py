"""
Schema-only migration (1 of 3): Resident becomes the single demographics source.

Adds gender, civil_status, is_solo_parent, is_pwd and is_4ps to Resident. The data copy
from User is the SEPARATE migration 0014 and the removal of the User columns is 0015
(MySQL DDL is not transactional, so schema and data are never mixed in one file).
Seniors are not stored; they are derived from Resident.birthdate.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_barangayinfo_resident_no_consent_reason_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='resident',
            name='gender',
            field=models.CharField(
                blank=True, default='', max_length=10,
                choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
            ),
        ),
        migrations.AddField(
            model_name='resident',
            name='civil_status',
            field=models.CharField(
                default='single', max_length=20,
                choices=[
                    ('single', 'Single'), ('married', 'Married'), ('widowed', 'Widowed'),
                    ('separated', 'Separated'), ('divorced', 'Divorced'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='resident',
            name='is_solo_parent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='resident',
            name='is_pwd',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='resident',
            name='is_4ps',
            field=models.BooleanField(default=False),
        ),
    ]
