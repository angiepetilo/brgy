"""
Data-only migration: default rules for the new `statistics` permission module.

Forward
-------
Every existing Officer whose position is Punong Barangay or Secretary gets
statistics.view and statistics.export (get_or_create, so an edited rule is never
overwritten). Other positions get nothing. No officers in the database = no-op.

Reverse
-------
Deletes the statistics.view / statistics.export rules of those same officers.
"""
from django.db import migrations

POSITIONS = ('Punong Barangay', 'Secretary')
ACTIONS = ('view', 'export')


def seed_statistics_rules(apps, schema_editor):
    Officer = apps.get_model('accounts', 'Officer')
    PermissionRule = apps.get_model('accounts', 'PermissionRule')
    for officer in Officer.objects.filter(position__in=POSITIONS):
        for action in ACTIONS:
            PermissionRule.objects.get_or_create(
                officer=officer, module='statistics', action=action,
                defaults={'allowed': True},
            )


def remove_statistics_rules(apps, schema_editor):
    PermissionRule = apps.get_model('accounts', 'PermissionRule')
    PermissionRule.objects.filter(
        officer__position__in=POSITIONS,
        module='statistics',
        action__in=ACTIONS,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_barangayinfo_city_province'),
    ]

    operations = [
        migrations.RunPython(seed_statistics_rules, remove_statistics_rules),
    ]
