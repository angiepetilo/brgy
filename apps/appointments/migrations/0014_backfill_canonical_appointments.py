"""
Data-only migration (A) for the canonical Appointment layer.

Runs while the legacy columns (preferred_date, preferred_time_slot, purpose_notes,
health_service, the CharField document_type, document_type_fk) still exist, so the
historical models expose both the legacy and the canonical columns. The schema change
that drops the legacy columns is the SEPARATE migration 0015 (MySQL DDL is not
transactional, so data and schema are never mixed in one file).

Forward rules
-------------
* DocumentType rows exist for clearance/residency/indigency/noa. Matching is by code or
  case-insensitive name; only missing rows are created (fee 0). Existing fees never change.
* document_type_fk is filled from the legacy CharField for document requests (code, then
  case-insensitive name). An unmatched non-empty value becomes an INACTIVE DocumentType
  (fee 0) so history is preserved without making it newly bookable.
* Health requests never carry a document type.
* appt_date / purpose / healthcare_service are filled from the legacy columns only when
  the canonical value is empty; otherwise the canonical value wins.
* time_window: both time_window and preferred_time_slot carried the column default
  ('morning') whenever nobody chose a value, and the old save() never synced two
  non-empty values. With only two choices, a non-default value ('afternoon') in either
  column is the deliberate one, so 'afternoon' wins if either column holds it.
* rejection_reason / admin_notes become separate concepts: rejected rows keep
  rejection_reason (falling back to admin_notes); other rows get rejection_reason='' and
  keep any text that only lived in rejection_reason by moving it to admin_notes.

Reverse copies the canonical values back into the legacy columns. It never fails on
empty values.
"""
from django.db import migrations

BATCH = 500

LEGACY_DOCUMENTS = [
    ('clearance', 'Barangay Clearance'),
    ('residency', 'Certificate of Residency'),
    ('indigency', 'Certificate of Indigency'),
    ('noa', 'Notice of Award (NOA)'),
]


def _flush(model, rows, fields):
    if rows:
        model.objects.bulk_update(rows, fields, batch_size=BATCH)
        rows.clear()


def _find_doc_type(DocumentType, value):
    value = (value or '').strip()
    if not value:
        return None
    return (
        DocumentType.objects.filter(code__iexact=value).order_by('id').first()
        or DocumentType.objects.filter(name__iexact=value).order_by('id').first()
    )


def backfill_forward(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    DocumentType = apps.get_model('appointments', 'DocumentType')

    # 1. Make sure the four standard document types exist (never touch fees).
    for code, label in LEGACY_DOCUMENTS:
        existing = _find_doc_type(DocumentType, code) or _find_doc_type(DocumentType, label)
        if existing is None:
            DocumentType.objects.create(name=label, code=code, fee=0, is_active=True)
        elif not existing.code:
            existing.code = code
            existing.save(update_fields=['code'])

    cache = {}

    def resolve_doc_type(legacy_value):
        key = legacy_value.strip().lower()
        if key not in cache:
            match = _find_doc_type(DocumentType, legacy_value)
            if match is None:
                match = DocumentType.objects.create(
                    name=legacy_value.strip()[:150], code='', fee=0, is_active=False,
                )
            cache[key] = match
        return cache[key]

    fields = [
        'document_type_fk', 'appt_date', 'time_window', 'purpose',
        'healthcare_service', 'rejection_reason', 'admin_notes',
    ]
    batch = []
    for apt in Appointment.objects.all().order_by('pk').iterator(chunk_size=BATCH):

        # Document type
        if apt.category == 'healthcare':
            apt.document_type_fk = None
        elif apt.document_type_fk_id is None and (apt.document_type or '').strip():
            apt.document_type_fk = resolve_doc_type(apt.document_type)

        # Date / time / purpose / health service
        if apt.appt_date is None:
            apt.appt_date = apt.preferred_date
        apt.time_window = 'afternoon' if 'afternoon' in (apt.time_window, apt.preferred_time_slot) else 'morning'
        if not (apt.purpose or '').strip():
            apt.purpose = apt.purpose_notes or ''
        if apt.healthcare_service_id is None and apt.health_service_id is not None:
            apt.healthcare_service_id = apt.health_service_id

        # Separate admin notes and rejection reason
        if apt.status == 'rejected':
            if not (apt.rejection_reason or '').strip():
                apt.rejection_reason = apt.admin_notes or ''
        else:
            if not (apt.admin_notes or '').strip() and (apt.rejection_reason or '').strip():
                apt.admin_notes = apt.rejection_reason
            apt.rejection_reason = ''

        batch.append(apt)
        if len(batch) >= BATCH:
            _flush(Appointment, batch, fields)
    _flush(Appointment, batch, fields)


def backfill_reverse(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    fields = [
        'preferred_date', 'preferred_time_slot', 'purpose_notes',
        'health_service', 'document_type',
    ]
    batch = []
    qs = Appointment.objects.all().select_related('document_type_fk').order_by('pk')
    for apt in qs.iterator(chunk_size=BATCH):
        if apt.appt_date is not None:
            apt.preferred_date = apt.appt_date
        apt.preferred_time_slot = apt.time_window or 'morning'
        apt.purpose_notes = apt.purpose or ''
        apt.health_service_id = apt.healthcare_service_id
        dt = apt.document_type_fk
        apt.document_type = ((dt.code or dt.name) if dt is not None else '')[:150]
        batch.append(apt)
        if len(batch) >= BATCH:
            _flush(Appointment, batch, fields)
    _flush(Appointment, batch, fields)


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0013_alter_documenttype_options_alter_requirement_options_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_forward, backfill_reverse),
    ]
