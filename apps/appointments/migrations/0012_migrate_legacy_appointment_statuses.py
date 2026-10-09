from django.db import migrations


def migrate_legacy_statuses_to_pending(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    # Migrate submitted, under_review, approved_scheduled, ready_for_pickup
    updated_pending = Appointment.objects.filter(status__in=['submitted', 'under_review']).update(status='pending')
    updated_approved = Appointment.objects.filter(status__in=['approved_scheduled', 'ready_for_pickup']).update(status='approved')
    if updated_pending or updated_approved:
        print(f"Migrated {updated_pending} appointments to 'pending' and {updated_approved} to 'approved'.")


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0011_alter_appointment_preferred_date_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_statuses_to_pending, reverse_migration),
    ]
