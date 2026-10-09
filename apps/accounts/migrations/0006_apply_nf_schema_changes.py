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

    # 0005 already defines and executes these operations for any un-faked migration run.
    # Leaving operations empty prevents duplicate column errors on fresh databases (MySQL/tests).
    operations = []
