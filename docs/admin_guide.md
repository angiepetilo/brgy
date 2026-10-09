# Barangay e-Portal — Administrator One-Page Guide

Welcome to the Barangay Administrative Management Console. This guide outlines your day-to-day operations, governance tools, and security duties.

---

### 1. Daily Administrative Workflow
1. **Review Pending Registrations (`/accounts/residents/?tab=pending`)**:
   - Inspect applicant ID photos and residency proofs.
   - Click **Approve** to generate a secure temporary password (valid for 7 days) and dispatch approval email.
   - If documents are insufficient, click **Decline / Reject** and select a clear reason.
2. **Review Appointments Queue (`/appointments/`)**:
   - Oversee document clearance requests and health center bookings.
   - Reassign unhandled appointments to duty officers.
3. **Emergency Broadcasts (`/communications/announcements/create/`)**:
   - Post urgent weather, flood, or curfew alerts under category **Emergency Alert** to trigger portal-wide banner alerts.

---

### 2. Staff Management & Granular Permissions
- **Add Staff Account (`/accounts/system/staff/create/`)**:
  - Enter name, email, and designated position (e.g. Secretary, BHW, Tanod).
  - A 7-day temporary password is generated and emailed to the officer.
- **Assign Duty Scopes (`/accounts/residents/assign/`)**:
  - Assign staff to specific **Purok Jurisdictions** (e.g. Purok 1) or **Service Areas** (Health, Documents).
  - Staff permissions strictly enforce that officers only access records within their assigned scope.
- **Configure Action-Level Rights (`/accounts/officers/permissions/`)**:
  - Toggle module-level capabilities (`approve`, `edit`, `delete`, `post_category`) per officer role.
- **Deactivate Staff (`/accounts/system/staff/<id>/disable/`)**:
  - Disabling a staff account immediately revokes login access and auto-reassigns their unresolved concerns.

---

### 3. System Settings (`/accounts/system/`)
Five tabs. Controls appear only for actions your account holds; view-only staff see the data with disabled forms. Unchecking an Active box switches the item off.
- **Barangay Info** (`?tab=barangay_info`): Official name (required), address, city, province, contact number, office hours, hall venue and logo (image, max 2 MB, optional remove). Contact numbers accept 7 to 15 digits with spaces, dashes or parentheses. Clearing a field clears it everywhere. The contact number is what the public booking page and documents show; nothing is hard-coded.
- **Post Categories** (`?tab=post_categories`): Create, edit and delete announcement channels (e.g. Youth Sports, Senior Welfare). System categories cannot be deleted.
- **Document & Health** (`?tab=document_health`):
  - Documents sub-tab: price table (fee in ₱, "Free" when 0), requirements and active flag. A document type already used by appointments cannot be deleted; switch it to inactive instead.
  - Health sub-tab: clinic services with schedule, Free/Paid and active flag. A service with schedules or appointments cannot be deleted.
- **User Management** (`?tab=user_management`): Staff sub-tab lists staff accounts with term end dates (warning badge when a term ends within 30 days), create and disable (not yourself). Concerns sub-tab manages concern categories and their routing. A link leads to Officer Roles and Permissions.
- **Email Templates** (`?tab=email_templates`): Preview any template with sample data. Saving needs `system.edit`; preview-only staff cannot edit. Templates are checked for Django syntax, must start with `Subject:` (except `password_reset_email`), and are limited to 20 KB.
- Every change is written to the activity log.

### 3a. Statistics (`/statistics/`)
- Needs `statistics.view`; CSV export and print need `statistics.export`. Punong Barangay and Secretary have both by default. Grant others under Officer Roles and Permissions.
- Filters: date from, date to, purok. Dates bound appointments, revenue and blotter cases only. Population, gender, sector (Senior, PWD, Solo Parent, 4Ps), civil status, age bands and purok density are a live snapshot of the Resident records (archived residents excluded).
- Senior is derived from birthdate (60 and over), not stored. Gender, civil status, PWD, Solo Parent and 4Ps are stored on the Resident record and edited from the Residents page.
- Purok density ranks puroks by household count; the highest is flagged.
- Monthly revenue is the sum of fees for completed document appointments, by appointment month. The fee recorded at booking is used, falling back to the current document fee.
- Blotter: cases filed in the period by status, type and purok; settlement rate = settled / closed (closed = settled + escalated + dismissed + withdrawn) among those cases; average days from filing to settlement; and a monthly filed vs settled chart (settled and closed counted by the month they happened). Counts only: no names, case numbers or narratives, so confidential cases are counted without exposing them.

### 3b. Blotter (`/blotter/`)
- Katarungang Pambarangay incident records: case list with filters, case filing with parties, hearings, status changes and a printable summary. JSON API under `/blotter/api/`.
- Statuses: Filed -> Under mediation / Dismissed / Withdrawn; Under mediation -> Settled / Escalated / Withdrawn. Settled, Escalated, Dismissed and Withdrawn are final.
- Default permissions (edit under Officer Roles and Permissions):

| Role | view | create | edit | mediate | settle | escalate | delete | view_confidential |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Punong Barangay | yes | yes | yes | yes | yes | yes | yes | yes |
| Secretary | yes | yes | yes | | | | | |
| Kagawad (Peace and Order) | yes | yes | yes | yes | yes | yes | | |
| Tanod | yes | yes | | | | | | |
| Others / residents | | | | | | | | |

- Dismissed and Withdrawn need `edit`. Hearings need `mediate`. Only users with `view_confidential` can see, create or change confidential cases.
- Purok scope: staff with a purok assignment see and file only that purok's cases, unless they also have a service-area assignment of `All`.
- Every create, edit, status change, hearing and delete is in the activity log (no narrative or party names; notes of confidential cases are not copied there).
- Out of scope: the KP 15-day mediation clock, Lupon/Pangkat composition and Certificate to File Action issuance.

### 3c. Look and feel (Stage D design system)
- **Feed order** (`/feed/`): emergency alerts and the barangay hotline first, then document and health
  service shortcuts, then pinned notices, then the latest posts. The hotline is the contact number in
  System Settings > Barangay Info; pin a post to show it under "Pinned notices". The landing page shows
  the same emergency block above the hero.
- **Theme**: `static/css/theme.css` holds the palette (canvas `#F9FAFB`, cards white, navy `#1E3A8A`,
  red `#DC2626` for emergencies, green `#16A34A` for success, grays), 16px base text, 1px gray borders,
  no gradients or shadows. `main.css` is the legacy sheet; edit it directly, never run `compile_scss.py`
  (the SCSS sources are stale and the script refuses to run).
- **Icons**: local Lucide sprite (`static/vendor/lucide/`, lucide-static 1.52.0, ISC). Templates use
  `{% load core_tags %}{% icon 'file-text' %} Label`; scripts use `BrgyUI.icon('name')`. A new icon must be
  added to `apps/core/icons.py: ICON_NAMES` and the sprite rebuilt (`python manage.py build_icon_sprite`,
  steps in the vendor README). No emoji, no Font Awesome, no font or icon CDNs.

---

### 4. Data Privacy, Compliance & Auditing
- **Right to Erasure (`/admin/accounts/resident/`)**:
  - When a resident formally requests data removal, use the admin action:
    `Archive & Anonymize selected residents (Data Privacy Act Request)`.
  - PII is permanently stripped, ID photos deleted, account disabled, and action logged.
- **Activity & Email Logs (`/history/`)**:
  - Review immutable chronological logs of all staff approvals, status changes, and outgoing emails.
  - Filter failed emails and click **Resend** when needed.

---

### 5. Security & Login Protection
- **Phone Number Format**: All phone numbers must be in Philippine mobile format: 11 digits starting with `09` (e.g., `09171234567`). Forms validate and reject other formats. Old numbers with dashes or spaces were normalized by migrations; any remaining invalid numbers must be corrected manually.
- **Login Brute-Force Protection**: After 5 failed login attempts from the same IP and username, or 10 failures for the same username across all IPs, or 20 failures from one IP across all usernames, the account or IP is locked out for 15 minutes. The same generic message is shown for all accounts (valid or invalid) to prevent username enumeration.
- **Rate Limits**: Public endpoints are rate-limited to prevent abuse:
  - Password reset: 5 per 15 minutes per IP
  - Signup: 5 per hour per IP
  - Public booking: 10 per hour per user
  - Chat messages: 30 per minute per user
  - Statistics export: 20 per hour per user
  - Blotter case creation: 20 per hour per user
- **Environment Variables**: Production security settings are controlled via `.env` (see `docs/deployment.md`):
  - `SECRET_KEY`: Must be 50+ characters, random
  - `DEBUG`: Must be `False` in production
  - `ALLOWED_HOSTS`: Comma-separated list of valid domains
  - `TRUSTED_PROXY_COUNT`: Set to `1` behind nginx to enable proper IP detection for rate limits
  - `CSP_REPORT_ONLY`: Set to `True` temporarily when testing template changes, `False` to enforce Content Security Policy
  - Login and rate limit settings are configurable via `LOGIN_*` and `RATE_LIMIT_*` environment variables
- **Account Lockout Recovery**: If an admin is locked out due to failed login attempts, the lockout expires after 15 minutes. For immediate recovery, clear the cache counters (Redis: `redis-cli KEYS "lf:*" | xargs redis-cli DEL`; Database cache: `manage.py shell` then `from django.core.cache import cache; cache.clear()`).

---

### 6. Technical Support & Emergency Recovery
- **Security Check**: Run `.venv/bin/python manage.py check --deploy` periodically.
- **Before Upgrading / Migrating**: Back up first. SQLite: copy `db.sqlite3` to `backups/`. MySQL: `mysqldump --single-transaction --routines --triggers -u <user> -p <db> > backup.sql`, then `manage.py migrate`. The new migrations (accounts 0018-0019, appointments 0016-0020, blotter 0005-0006) have been applied to the live SQLite database on 2026-10-08; they have not been run against MySQL.
- **Database Backups**: Nightly dumps stored in off-site archive; see `docs/backup_restore.md` for restoration instructions.
