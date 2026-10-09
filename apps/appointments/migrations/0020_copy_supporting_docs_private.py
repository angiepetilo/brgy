"""
Data migration: copy existing Appointment.supporting_id files from public
MEDIA_ROOT to PRIVATE_MEDIA_ROOT, keeping the same relative name so every
stored row still resolves (e.g. appointments/supporting_docs/x.jpg).

- Originals are never deleted. After checking the private copies, an admin may
  remove MEDIA_ROOT/appointments/ by hand (docs/backup_restore.md).
- Missing source files are skipped and their appointment ids logged.
- A private copy that already exists is left as is (safe to re-run).
- Reverse copies files back to MEDIA_ROOT when they are missing there.
"""
import logging
import os
import shutil

from django.conf import settings
from django.db import migrations

logger = logging.getLogger('apps.migrations')


def _copy_all(apps, src_root, dst_root, direction):
    Appointment = apps.get_model('appointments', 'Appointment')
    missing = []
    copied = 0
    rows = Appointment.objects.exclude(supporting_id='').exclude(supporting_id__isnull=True)
    for pk, name in rows.values_list('pk', 'supporting_id').iterator():
        rel = os.path.normpath(str(name))
        if rel.startswith('..') or os.path.isabs(rel):
            missing.append(pk)
            continue
        src = os.path.join(str(src_root), rel)
        dst = os.path.join(str(dst_root), rel)
        if os.path.exists(dst):
            continue
        if not os.path.isfile(src):
            missing.append(pk)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    if missing:
        message = f'[appointments.supporting_id {direction}] source file missing for appointment ids: {missing}'
        print(f'\n  {message}')
        logger.warning(message)
    return copied, missing


def forwards(apps, schema_editor):
    _copy_all(apps, settings.MEDIA_ROOT, settings.PRIVATE_MEDIA_ROOT, 'to private')


def backwards(apps, schema_editor):
    _copy_all(apps, settings.PRIVATE_MEDIA_ROOT, settings.MEDIA_ROOT, 'to public')


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0019_supporting_id_private'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
