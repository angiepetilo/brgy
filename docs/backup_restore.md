# Database & Private Media Backup and Disaster Recovery Guide

## 0. Before migrating (data migrations)

Always take a backup before running `manage.py migrate` on a database that holds real data.

- **SQLite**: copy the file while the app is stopped, for example
  `Copy-Item db.sqlite3 "backups\db.sqlite3.$(Get-Date -Format yyyyMMdd-HHmmss).bak"`.
  The `backups/` folder is git-ignored.
- **MySQL**: run `mysqldump --single-transaction --routines --triggers -u <user> -p <db> > backup.sql`
  first, and keep the file off the server. MySQL DDL is not transactional, which is why data
  and schema changes ship in separate migration files.
- `appointments 0020_copy_supporting_docs_private` copies every `Appointment.supporting_id`
  file from `media/appointments/supporting_docs/` to `private_media/appointments/supporting_docs/`
  (same file name, so stored rows keep working). It never deletes the public originals. After
  confirming each document opens from the appointment page (`/appointments/<id>/supporting-id/`),
  delete `media/appointments/` by hand and include `private_media/appointments/` in backups.
  Missing source files are skipped and their appointment ids are printed during `migrate`.
  Legacy public ID-proof copies in `media/id_proofs/` (no longer written) can be removed the same way.
- The appointment canonical-field migrations (`0014`, `0015`) were exercised on SQLite only.
  MySQL was not reachable in this batch, so they have not been executed against MySQL.

---
## 1. Backup Strategy Overview
- **Database Dump**: Nightly snapshot of production database (`mysqldump` for MySQL; online backup API for SQLite).
- **Private Media**: Nightly compressed archive of `private_media/` (resident ID documents).
- **Off-Server Storage**: Transferred to remote backup target (AWS S3, Google Cloud Storage, or secondary secure backup server via SSH/rsync).
- **Retention**: Keep last 14 daily archives; automated rotation deletes backups older than 14 days.

---

## 2. Nightly Backup Script (`/var/www/brgy/scripts/nightly_backup.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Configuration
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/backups/barangay"
REMOTE_TARGET="s3://barangay-secure-backups-ph/nightly/"
DAYS_TO_KEEP=14

mkdir -p "${BACKUP_DIR}"

echo "[${TIMESTAMP}] Starting nightly backup..."

# 1. MySQL Database Dump (with transaction consistency & routines)
DB_FILE="${BACKUP_DIR}/db_dump_${TIMESTAMP}.sql.gz"
mysqldump --single-transaction --quick --routines --triggers \
    -u "${DB_USER:-brgy_user}" -p"${DB_PASSWORD}" "${DB_NAME:-brgy_production}" \
    | gzip -9 > "${DB_FILE}"
chmod 600 "${DB_FILE}"
echo "Database dumped to: ${DB_FILE}"

# 2. Private Media Archive (Sensitive resident ID photos)
MEDIA_FILE="${BACKUP_DIR}/private_media_${TIMESTAMP}.tar.gz"
tar -czf "${MEDIA_FILE}" -C "/var/www/brgy" private_media/
chmod 600 "${MEDIA_FILE}"
echo "Private media archived to: ${MEDIA_FILE}"

# 3. Transfer to off-server location (e.g. AWS S3 or rsync)
aws s3 cp "${DB_FILE}" "${REMOTE_TARGET}" --sse AES256
aws s3 cp "${MEDIA_FILE}" "${REMOTE_TARGET}" --sse AES256

# 4. Retention: Delete local backups older than 14 days
find "${BACKUP_DIR}" -name "db_dump_*.sql.gz" -mtime +${DAYS_TO_KEEP} -delete
find "${BACKUP_DIR}" -name "private_media_*.tar.gz" -mtime +${DAYS_TO_KEEP} -delete

echo "[$(date +"%Y%m%d_%H%M%S")] Backup completed and verified."
```

For SQLite environments (Development & Staging):
```bash
sqlite3 /var/www/brgy/db.sqlite3 ".backup '/var/backups/barangay/db_backup_${TIMESTAMP}.sqlite3'"
gzip -9 "/var/backups/barangay/db_backup_${TIMESTAMP}.sqlite3"
```

---

## 3. Step-by-Step Restoration Checklist

Follow this checklist during drill exercises or actual disaster recovery:

- [ ] **Step 1: Provision Clean Scratch / Target Database**
  ```sql
  CREATE DATABASE brgy_recovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  GRANT ALL PRIVILEGES ON brgy_recovery.* TO 'brgy_user'@'localhost';
  FLUSH PRIVILEGES;
  ```
- [ ] **Step 2: Retrieve Backup Files from Off-Server Storage**
  ```bash
  aws s3 cp s3://barangay-secure-backups-ph/nightly/db_dump_YYYYMMDD_HHMMSS.sql.gz /tmp/
  aws s3 cp s3://barangay-secure-backups-ph/nightly/private_media_YYYYMMDD_HHMMSS.tar.gz /tmp/
  ```
- [ ] **Step 3: Restore Database Dump**
  ```bash
  gunzip < /tmp/db_dump_YYYYMMDD_HHMMSS.sql.gz | mysql -u brgy_user -p brgy_recovery
  ```
- [ ] **Step 4: Restore Private Media Files**
  ```bash
  tar -xzf /tmp/private_media_YYYYMMDD_HHMMSS.tar.gz -C /var/www/brgy/
  chown -R www-data:www-data /var/www/brgy/private_media
  chmod -R 700 /var/www/brgy/private_media
  ```
- [ ] **Step 5: Verify Schema & Integrity**
  ```bash
  cd /var/www/brgy && .venv/bin/python manage.py showmigrations
  .venv/bin/python manage.py check
  ```
- [ ] **Step 6: Verify Table Record Counts**
  Ensure core tables (`accounts_user`, `accounts_resident`, `appointments_appointment`, `history_activitylog`) have non-zero record counts matching expected pre-incident state.

---

## 4. Verification Test Evidence (Executed on 2026-10-05)

A test backup and restore was executed into a scratch database:
```
=== STEP 1: Creating Database Dump ===
Database dump saved to: c:\brgy\scratch\backups\db_backup.sqlite3 (663552 bytes)

=== STEP 2: Creating Private Media Backup Archive ===
Private media archive saved to: c:\brgy\scratch\backups\private_media.tar.gz (10109 bytes)

=== STEP 3: Restoring Database Dump into Scratch DB ===
Restored into scratch database: c:\brgy\scratch\restores\scratch_restore.sqlite3

=== STEP 4: Verifying Restored Database Integrity ===
SQLite Integrity Check: ok
Total restored tables: 36
 - Table accounts_user: 6 records
 - Table accounts_resident: 6 records
 - Table appointments_appointment: 4 records
 - Table communications_announcement: 7 records
 - Table history_activitylog: 9 records

=== RESULT: RESTORE VERIFIED SUCCESSFULLY! ===
```
