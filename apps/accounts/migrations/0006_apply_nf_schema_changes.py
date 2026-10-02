# Migration 0006: Applies the structural changes that were skipped when 0005
# was faked (purok VARCHAR→FK, add street_address, alter address to legacy).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Completes the NF normalization started in 0005:
    - Adds street_address (atomic address field) to Household and User
    - Updates the address field label on User to LEGACY
    - Converts purok VARCHAR columns to proper FK columns pointing to accounts.Purok
    """

    atomic = False  # Required for SQLite FK column conversion

    dependencies = [
        ('accounts', '0005_purok_remove_household_address_and_more'),
    ]

    operations = [
        # ── Household ─────────────────────────────────────────────────────
        migrations.AddField(
            model_name='household',
            name='street_address',
            field=models.CharField(
                blank=True,
                default='',
                help_text='House/Unit number and street name only (e.g. 12-B Rizal St.)',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='household',
            name='purok',
            field=models.ForeignKey(
                blank=True,
                help_text='Purok zone this household belongs to',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='households',
                to='accounts.purok',
            ),
        ),

        # ── User ──────────────────────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='street_address',
            field=models.CharField(
                blank=True,
                default='',
                help_text='House/Unit number and street name (e.g. 22 Mabini St.)',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='address',
            field=models.TextField(
                blank=True,
                help_text='[LEGACY] Full residential address \u2014 use street_address + purok instead.',
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='purok',
            field=models.ForeignKey(
                blank=True,
                help_text='Purok jurisdiction inside the Barangay',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='residents',
                to='accounts.purok',
            ),
        ),
    ]
