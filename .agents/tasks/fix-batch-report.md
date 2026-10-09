# Fix batch report: barangay portal (Stages 0 to 5)

Scope: the review items on duplicate Appointment columns, split resident demographics, empty Statistics page, empty System Settings tabs, the Records officer filter, and the hard-coded admin phone.

## Final verification (run in this step)

| Check | Result |
| --- | --- |
| `pytest -n 4 -p no:cacheprovider` | 404 passed, 0 failed, 1 warning, 95 subtests passed (134 s) |
| `manage.py test tests` (Django runner, serial) | Ran 404 tests, OK (434 s) |
| `manage.py check` | no issues |
| `manage.py makemigrations --check --dry-run` | No changes detected (no model/migration drift) |
| `manage.py check --deploy` (informational, settings not changed) | 6 warnings: W004 (HSTS), W008 (SSL redirect), W009 (SECRET_KEY length/strength), W012 (session cookie secure), W016 (CSRF cookie secure), W018 (DEBUG True). These are the "insecure defaults" item below. |

Real-data migration proof. Backup used: `backups\db.sqlite3.20261007-141940.bak` (684,032 bytes, still present). A fresh copy of the backup was migrated with `DB_NAME` pointing at the copy. The live `db.sqlite3` was not touched.

| Table | Before | After |
| --- | --- | --- |
| Appointment | 4 | 4 |
| Resident | 7 | 7 |
| DocumentType | 7 | 7 |
| User | 9 | 9 |
| HealthCareService | 6 | 6 |

Migrations applied to the copy, in order, all OK: accounts 0013, 0014, 0015, 0016, 0017; appointments 0014, 0015. `pragma integrity_check` = ok before and after. Schema change observed: `appointments_appointment` 31 to 26 columns; `accounts_user` lost `civil_status`, `is_4ps`, `is_pwd`, `is_senior`; `accounts_resident` gained `gender`, `civil_status`, `is_solo_parent`, `is_pwd`, `is_4ps`.

Live database state: `db.sqlite3` is still at the old level (accounts 0013 to 0017 and appointments 0014 to 0015 are unapplied, confirmed with `showmigrations`). To apply it: stop the app, confirm the backup exists, then run `c:\brgy\.venv\Scripts\python.exe manage.py migrate`.

## Per stage

### Stage 0: safety and baseline (tests: 139 passed)
- Files: `.gitignore` (ignores `backups/`), `backups/` (new, holds the backup), `docs/backup_restore.md` (section 0 "Before migrating"), `tests/communications/test_feed_layout.py` (stale sidebar assertions made case-insensitive).
- Baseline before this batch was already green after the stale assertion fix.

### Stage 1: Appointment canonical data layer (tests: 158 passed, +19)
- Six mirrored column pairs collapsed into one set: `appt_date`, `time_window`, `purpose`, `healthcare_service`, `document_type` (FK), separate `admin_notes` / `rejection_reason`, plus `fee_at_booking`. The `save()` sync is gone (`reference_no` generation stays). Legacy status aliases, `DOC_*`, `DOCUMENT_CHOICES` and `HealthService` were removed.
- Migrations: `appointments/0014_backfill_canonical_appointments` (data only, reversible), `0015_canonical_appointment_schema` (schema only, reversible).
- Files touched: `apps/appointments/{models,forms,admin,services,views}.py`, `apps/appointments/management/commands/send_appointment_reminders.py`, `apps/communications/{context_processors,views}.py`, `apps/records/views.py`, `apps/accounts/system_services.py`, `apps/accounts/selectors.py` (new, `get_contact_number`), `apps/statistics/views.py` (interim), `seed_demo_data.py`, `bootstrap_barangay.py`, `config/settings.py`, `.env.example`, templates (`landing.html`, `signup.html`, appointments list/table/detail/form, records templates), `tests/base.py` and the tests that used old names.
- Fixes requested: Records officer search uses `position`, `committee`, `user__*` instead of the nonexistent `title`; the `0917-111-2222` fallback now comes from Barangay Info (then `settings.BARANGAY_CONTACT`, default empty).
- New tests: `tests/appointments/test_data_layer.py` (14), `tests/records/test_officer_search.py` (5).

### Stage 2: Residents are the single demographics source (tests: 218 passed, +60)
- `Resident` gains `gender`, `civil_status` (lowercase choices), `is_solo_parent`, `is_pwd`, `is_4ps`; seniors are derived from birthdate (60+), never stored. `User.is_senior/is_pwd/is_4ps/civil_status` removed. The capitalisation bug in civil-status counts is gone because statistics now read lowercase Resident values through shared selectors.
- Migrations: `accounts/0013_resident_demographics` (schema), `0014_backfill_resident_demographics` (data, reversible), `0015_drop_user_demographics` (schema).
- Files touched: `apps/accounts/{models,forms,services,views,admin,selectors,system_services}.py`, `apps/records/views.py`, `templates/records/records_hub.html`, `templates/accounts/{residents_tabbed,signup}.html`, `seed_demo_data.py`, `bootstrap_barangay.py`, signup payloads in `tests/accounts` and `tests/security`.
- New tests in `tests/residents/` (demographics model, selectors, registration forms, demographics migration) and `tests/records/test_rbi_residents.py`.

### Stage 3: System Settings backend (tests: 281 passed, +63)
- `apps/accounts/system_utils.py` (new): `parse_bool`, `with_unchecked_checkboxes`, `safe_int`. Unchecked Active boxes now really switch items off (hidden "0" input pattern).
- `system_views.py`: `_settings_redirect` uses canonical tab/subtab names; `_run_service` maps ValueError to its message, missing objects to a fixed message, and anything else to a generic message with `logger.exception`.
- `BarangayInfo` gains `city` and `province`; optional fields can be cleared; logo validated (image, 2 MB); contact number validated (7 to 15 chars of digits, spaces, dashes, parentheses).
- Email templates: catalog-driven whitelist on read, preview and write; Django syntax check, `Subject:` rule (not for `password_reset_email`), 20 KB limit, atomic write, audit entry. Catalog gains `staff_created` and `password_reset_email`.
- Delete/update services return "no longer exists" instead of a 500 for missing ids.
- Migration: `accounts/0016_barangayinfo_city_province` (schema).
- Tests: `tests/settings/test_settings_backend.py`, `tests/settings/test_migration_barangay_info.py`.

### Stage 4: System Settings UI (tests: 323 passed, then 329 after review fixes)
- `templates/accounts/system/system_dashboard.html` rebuilt (no inline JS, no `onclick`, no `|safe`); the four empty tabs now show real tables and forms. `static/js/system_settings.js` (new) holds all JS with delegated listeners and a config element for URLs. Dialog roles, Escape-to-close and focus return were added.
- `system_views.py` adds `ending_soon_ids` and `can{}` permission flags to the context. Edit controls appear only for actions the user holds.
- Review fixes: `password_reset_email` saves without a Subject; email save needs `system.edit` (owner decision); the logo placeholder has no src until a file is chosen.
- Tests: `tests/settings/test_settings_ui.py` (49 by the plan's count; the review's spot run counted 48).

### Stage 5: Statistics backend, API and UI (tests: 404 passed, +75)
- `apps/statistics/selectors.py` (one source of numbers for API, CSV and print page), `api.py`, `views.py`, `urls.py`. Five JSON routes under `/statistics/api/` (summary, demographics, purok-density, appointments, revenue). Filters: `date_from`, `date_to`, `purok`; 400 on bad input; `no-store`.
- Data now shown: population, gender, sectors (Senior/PWD/Solo Parent/4Ps), civil status, age bands, purok density with the highest flagged, appointments by status/category/service, monthly revenue from completed document fees.
- UI: `templates/statistics/{overview,print_report}.html`, `static/js/statistics.js`, `static/css/statistics.css`, vendored Chart.js 4.5.1 in `static/vendor/chartjs/`. CSV export is formula-injection safe.
- Permissions: `statistics` `view`/`export` registered; Punong Barangay (all) and Secretary (view, export) by default. Migration `accounts/0017_seed_statistics_permissions` (data only, reversible). Sidebar link uses a new `user_can` template tag.
- Tests: `tests/statistics/` (79 tests, incl. the `slow` manifest test); the interim `tests/residents/test_statistics_source.py` was removed.

Test count progression: 139, 158, 218, 281, 323 (329 after Stage 4 review fixes), 404.

## Docs updated in this step
- `docs/route_matrix.md`: five statistics API rows, API notes, System Settings tab/subtab table.
- `docs/admin_guide.md`: what each settings tab does, Statistics section, pre-migration backup note.
- `docs/testing.md`: new folders (`records`, `residents`, `settings`, `statistics`), the other migration tests, the `slow` marker, log pattern, MySQL note.
- `docs/backup_restore.md`: already had the `mysqldump` before-migrating section (Stage 0).

## NOT verified
- MySQL: port 3306 is closed on this machine. No migration, test or query was run against MySQL. Portability of the new migrations, `TruncMonth` and `Coalesce` is reasoned from ORM-only code, not executed.
- No browser or visual check of any page (System Settings modals, focus handling, Escape, the FileReader logo preview, Chart.js charts, print page). Evidence for the UI is rendered-HTML and JSON tests plus `node --check` on the JS. No `runserver` smoke test was run.
- The live `db.sqlite3` has not been migrated; only a copy of the backup was.
- `check --deploy` was run for information only; no settings were changed.

## Known risks and pre-existing issues (not fixed)
- Live DB needs `migrate`, after a backup. Migrations 0014 (appointments) and 0014 (accounts) move data; both are reversible, and the backup is the fallback.
- Appointments 0014 drops a stray `rejection_reason` on non-rejected rows when `admin_notes` is also filled (review of Stage 1). Unlikely in the local data (4 rows migrated).
- Existing document appointments have `fee_at_booking = NULL`; revenue falls back to the current `DocumentType.fee`, so later fee changes would alter historic revenue for those rows.
- Legacy status ids remain in `appointment_detail.html`, `table.html` and the list edit modal (`submitted`, `under_review`, ...); the detail stepper and Complete/No-Show buttons for `approved` appointments are affected (Stage 1 review).
- `records_hub.html` (~line 506) can raise `VariableDoesNotExist` for a completed health record whose `processed_by` is NULL.
- Pending and rejected sign-ups count in population and the RBI table (only archived residents are excluded).
- `disable_staff_account_service` does not check the target's role (only self-disable is blocked).
- Clearing the requirements textarea on a document type leaves the old `Requirement` rows.
- Resident edit flashes "updated" even when the User has no Resident profile.
- Statistics date filters do not bound the resident/household snapshot, and the page text does not say so; an expired session mid-use shows a JSON parse error instead of a login prompt.
- Logo preview uses a `data:` URL, so a future CSP needs `img-src data:`.
- `STATICFILES_STORAGE` is ignored by Django 5.2, so dev and tests use plain StaticFilesStorage. The production storage setting was not changed. The upstream `chart.umd.js` had its trailing `sourceMappingURL` comment removed because collectstatic failed on the missing map (documented in the vendor README).
- Kept inline `style` attributes in the settings template (they were already inline).

## Intentionally NOT in this batch
- Blotter module (and therefore blotter settlement-rate metrics). Suggested approach: new `blotter` app with case, parties and status models, then one more selector block in `apps/statistics/selectors.py`.
- Phone validation on models. Suggested approach: one shared regex validator (11-digit PH mobile format) on `User.phone_number`, `Resident.contact_no` and other phone fields, plus a migration-safe cleanup of existing values.
- Rate limiting and `X-Forwarded-For` hardening. The login lockout still trusts the header; use the client IP only when the request comes from a configured trusted proxy.
- Insecure defaults for `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`. Fail at startup when they are unsafe and `DEBUG` is off; see the six `check --deploy` warnings above.
- CSP header. Add a Content-Security-Policy (middleware or django-csp), starting in report-only mode. New templates were written without inline scripts to keep this cheap; existing inline `style` attributes and the `data:` logo preview need to be allowed.
