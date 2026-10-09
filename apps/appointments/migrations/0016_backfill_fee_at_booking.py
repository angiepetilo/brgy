"""
Data-only migration: backfill Appointment.fee_at_booking.

Document appointments booked before the fee snapshot existed have
fee_at_booking NULL. Forward copies the CURRENT DocumentType.fee into those rows
only (category='document', fee_at_booking NULL, document_type set). Rows that
already have a snapshot, health appointments and rows without a document type
are untouched. New bookings keep snapshotting in book_appointment_service.

ORM only (no raw SQL), so it runs the same on SQLite and MySQL. Reverse is a
no-op: the backfilled value is indistinguishable from a real snapshot, and
leaving it in place is harmless for the previous schema.
"""
from django.db import migrations

BATCH = 500


def backfill_fee_at_booking(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    rows = []
    qs = (
        Appointment.objects
        .filter(category='document', fee_at_booking__isnull=True, document_type__isnull=False)
        .select_related('document_type')
        .order_by('pk')
    )
    for apt in qs.iterator(chunk_size=BATCH):
        apt.fee_at_booking = apt.document_type.fee
        rows.append(apt)
        if len(rows) >= BATCH:
            Appointment.objects.bulk_update(rows, ['fee_at_booking'], batch_size=BATCH)
            rows.clear()
    if rows:
        Appointment.objects.bulk_update(rows, ['fee_at_booking'], batch_size=BATCH)


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0015_canonical_appointment_schema'),
    ]

    operations = [
        migrations.RunPython(backfill_fee_at_booking, migrations.RunPython.noop),
    ]
