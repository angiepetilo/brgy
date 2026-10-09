"""
Data-only migration: default rules for the `blotter` permission module.

Forward
-------
Existing Officer rows get these rules (get_or_create, so a rule an administrator
already edited is never overwritten):

    Punong Barangay              all 8 actions
    Secretary                    view, create, edit
    Kagawad (Peace and Order)    view, create, edit, mediate, settle, escalate
    Tanod                        view, create

Other positions (and residents) get nothing. No officers = no-op.

Reverse
-------
Deletes the blotter rules of those same officers for those same actions.
"""
from django.db import migrations

ALL_ACTIONS = ('view', 'create', 'edit', 'mediate', 'settle', 'escalate', 'delete', 'view_confidential')

# (position, committee or None for any committee, actions)
DEFAULTS = (
    ('Punong Barangay', None, ALL_ACTIONS),
    ('Secretary', None, ('view', 'create', 'edit')),
    ('Kagawad', 'Peace and Order', ('view', 'create', 'edit', 'mediate', 'settle', 'escalate')),
    ('Tanod', None, ('view', 'create')),
)


def _officers(Officer, position, committee):
    qs = Officer.objects.filter(position=position)
    if committee is not None:
        qs = qs.filter(committee=committee)
    return qs


def seed_blotter_rules(apps, schema_editor):
    Officer = apps.get_model('accounts', 'Officer')
    PermissionRule = apps.get_model('accounts', 'PermissionRule')
    for position, committee, actions in DEFAULTS:
        for officer in _officers(Officer, position, committee):
            for action in actions:
                PermissionRule.objects.get_or_create(
                    officer=officer, module='blotter', action=action,
                    defaults={'allowed': True},
                )


def remove_blotter_rules(apps, schema_editor):
    Officer = apps.get_model('accounts', 'Officer')
    PermissionRule = apps.get_model('accounts', 'PermissionRule')
    for position, committee, actions in DEFAULTS:
        officer_ids = list(_officers(Officer, position, committee).values_list('pk', flat=True))
        PermissionRule.objects.filter(
            officer_id__in=officer_ids,
            module='blotter',
            action__in=actions,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('blotter', '0005_blotter_schema'),
        ('accounts', '0019_normalize_phone_numbers'),
    ]

    operations = [
        migrations.RunPython(seed_blotter_rules, remove_blotter_rules),
    ]
