"""
Schema-only migration (B) for the canonical Appointment layer.

Data is moved by the SEPARATE migration 0014 (MySQL DDL is not transactional, so data
and schema changes never share a file). Only portable schema operations are used, so it
runs on SQLite and MySQL.

Reversibility: `preferred_date` was NOT NULL without a default, so re-adding it on the way
back would fail on a table that already has rows. It is first given a placeholder default
(never used by the application); the reverse of 0014 then refills it from `appt_date`.
"""
import datetime

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0014_backfill_canonical_appointments'),
    ]

    operations = [
        # Placeholder default so the column can be re-created when reversing.
        migrations.AlterField(
            model_name='appointment',
            name='preferred_date',
            field=models.DateField(default=datetime.date(1970, 1, 1), help_text='DEPRECATED: Use appt_date instead. Selected date for processing or appointment'),
        ),
        # Old indexes must go before the columns they reference.
        migrations.RemoveIndex(
            model_name='appointment',
            name='appointment_status_98d565_idx',
        ),
        migrations.RemoveIndex(
            model_name='appointment',
            name='appointment_status_4ac55f_idx',
        ),
        migrations.RemoveField(
            model_name='appointment',
            name='preferred_date',
        ),
        migrations.RemoveField(
            model_name='appointment',
            name='preferred_time_slot',
        ),
        migrations.RemoveField(
            model_name='appointment',
            name='purpose_notes',
        ),
        migrations.RemoveField(
            model_name='appointment',
            name='health_service',
        ),
        # Legacy CharField document_type goes; the FK takes over its name.
        migrations.RemoveField(
            model_name='appointment',
            name='document_type',
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='document_type_fk',
            new_name='document_type',
        ),
        migrations.AlterField(
            model_name='appointment',
            name='document_type',
            field=models.ForeignKey(blank=True, help_text='Requested document (null for health care appointments)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='appointments.documenttype'),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='appt_date',
            field=models.DateField(db_index=True, help_text='Selected date for processing or appointment'),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='admin_notes',
            field=models.TextField(blank=True, help_text='Staff remarks or instructions for the applicant (not the rejection reason)'),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='rejection_reason',
            field=models.TextField(blank=True, default='', help_text='Reason shown to the applicant when the request is rejected'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['status', 'appt_date'], name='appt_status_date_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['appt_date', 'time_window'], name='appt_date_window_idx'),
        ),
    ]
