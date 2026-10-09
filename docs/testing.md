# Testing

All automated tests live in `tests/`, one folder per module. The folder is named `tests`
(not `test`) because a top-level `test` package would shadow Python's standard library
`test` package.

## Running (like `php artisan test`)

Install dev tools once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

| Goal | Command |
| --- | --- |
| Whole suite | `python -m pytest` |
| One module | `python -m pytest tests/appointments` |
| One file | `python -m pytest tests/security/test_part_i.py` |
| Filter by name | `python -m pytest -k booking` |
| Stop at first failure | `python -m pytest -x` |
| Re-run only last failures | `python -m pytest --lf` |
| Parallel | `python -m pytest -n auto` |
| Django runner | `python manage.py test tests` |

Tests are written as Django `TestCase` classes, so both runners work. For parallel runs use
`pytest -n auto`; Django's own `--parallel` flag crashes on Windows when a test fails
(it cannot pickle tracebacks without `tblib`). If you see `UnicodeEncodeError` on the Windows
console, set `$env:PYTHONUTF8 = '1'` first.
`pytest.ini` restricts collection to `tests/` so files in `scratch/` are never run.

## Layout

```
tests/
  base.py            shared factories and BaseTestCase
  accounts/          registration, approval, residents, permissions, route crawler
  appointments/      booking, documents, health services
  chat/              threads, notifications, websocket security
  communications/    feed, announcements, emergency
  history/           activity log, email log
  security/          login throttle, headers, rate limits, uploads
  records/           records hub: officer search, RBI residents, print views
  residents/         RBI demographics, selectors, registration forms, demographics migration
  settings/          system settings: backend services, UI, BarangayInfo migration
  statistics/        selectors, JSON API, exports, permission migration, static manifest
  blotter/           blotter: models/TRANSITIONS, permission migration, services (numbering,
                     transitions, audit), policies (RBAC, purok scope, confidential), API, pages
  core/              shared validators, factories smoke tests
  ui/                Stage D design system: no Font Awesome/CDNs/emoji, {% icon %} tag + sprite,
                     icon labels on rendered pages, theme/palette assets, key pages per role,
                     feed civic order (emergency > services > pinned > feed), feed query count
  architecture/      layer rules (views do not query the ORM, etc.)
```

## Factories (`tests/base.py`)

```python
from tests.base import BaseTestCase, make_admin, make_staff, make_resident_user

class ExampleTests(BaseTestCase):
    def test_staff_can_view(self):
        staff = make_staff(permissions={'residents': ['view']})
        self.login(staff)
        ...
```

Available: `make_admin`, `make_staff(permissions=...)`, `make_resident_user`, `make_purok`,
`make_resident_profile`, `make_document_type`, `make_health_service`, `make_appointment`,
`grant`. Default password for every factory user is `tests.base.DEFAULT_PASSWORD`.

`make_appointment` uses the canonical columns (`appt_date`, `time_window`, `document_type` FK). The data migration seeds the four standard document types (clearance, residency, indigency, noa), so use `get_document_type(code, name)` (get-or-create) instead of creating them again; `name` is unique.

Migration tests (`tests/appointments/test_data_layer.py`) use `MigrationExecutor` with `TransactionTestCase` and migrate back to the leaf nodes in `tearDown`.

Other migration tests use the same pattern: `tests/residents/test_migration_demographics.py`, `tests/settings/test_migration_barangay_info.py`, `tests/statistics/test_permission_migration.py` and `tests/appointments/test_migration_fee_backfill.py`.

Stage A (bug fixes) test files:

| File | Covers |
|---|---|
| `tests/core/test_core_tags.py` | `display_name` filter for nullable user FKs |
| `tests/appointments/test_status_ui.py` | stepper and action buttons per status, action routes, table pills, legacy status scan |
| `tests/appointments/test_migration_fee_backfill.py` | appointments 0016 `fee_at_booking` backfill, forward and reverse |
| `tests/records/test_health_records_null_staff.py` | records hub and print views with NULL `processed_by` / `issued_by` |
| `tests/residents/test_population_rule.py` | population rule across selectors, RBI table, statistics API, puroks, households |
| `tests/residents/test_resident_edit.py` | resident edit with and without an RBI profile, safe redirect |
| `tests/settings/test_stage_a_rules.py` | staff-disable target rules, clearing document requirements |
| `tests/statistics/test_api_auth.py` | 401/403 JSON for API callers, filter scope note, session-expired JS |

Tests that complete a document appointment trigger the QR signal; wrap them in
`@override_settings(MEDIA_ROOT=TEMP_MEDIA)` (`tests.statistics.data`) so no files land in `media/`.

`tests/statistics/test_static_manifest.py` is marked `slow`: it runs `collectstatic` under the WhiteNoise manifest storage. Skip slow tests with `python -m pytest -m "not slow"`.

Tip: redirect a long run to a log and read the tail, e.g. `python -m pytest -n 4 -p no:cacheprovider *> scratch\run.log`.

## Databases

The suite runs on SQLite by default (no setup). To run it on MySQL, point the environment at
a server where the user may create databases (Django creates and drops `test_<DB_NAME>`):

```powershell
$env:DB_ENGINE = 'django.db.backends.mysql'
$env:DB_NAME = 'brgy_dev'
$env:DB_USER = 'root'
$env:DB_PASSWORD = '...'
$env:DB_HOST = '127.0.0.1'
$env:DB_PORT = '3306'
.\.venv\Scripts\python.exe -m pytest
```

MySQL note: back up before migrating a real database (`mysqldump --single-transaction` first; see `docs/backup_restore.md`). The suite and the new migrations have been run on SQLite only; they have not been run against MySQL.

The pure-Python `PyMySQL` driver is used (pinned in `requirements.txt`); `config/settings.py`
registers it automatically when `DB_ENGINE` is MySQL.

## Cache table

Without `REDIS_URL` the cache (used by rate limiting) is a database table. Test runs create it
automatically. For a normal dev database run once:

```powershell
.\.venv\Scripts\python.exe manage.py createcachetable
```

## Conventions

- New tests go in the folder of the module they cover, named `test_<topic>.py`.
- Use the factories in `tests/base.py` instead of building users by hand.
- Each development task adds its own test files and must leave the whole suite green.

## Security tests (Stage B)
| File | Covers |
|---|---|
| `tests/core/test_client_ip.py` | `get_client_ip`: X-Forwarded-For ignored unless `TRUSTED_PROXY_COUNT` > 0 |
| `tests/core/test_validators.py` | `validate_ph_mobile` / `normalize_ph_mobile` cases |
| `tests/security/test_login_bruteforce.py` | signal-based lockouts per username+IP, IP, username; 429 + Retry-After; no enumeration |
| `tests/security/test_rate_limits.py` | 429 on every rate-limited endpoint; email API never called for anonymous users |
| `tests/security/test_settings_hardening.py` | unsafe production settings refuse to start; `check --deploy` clean (subprocess) |
| `tests/security/test_csp.py` | CSP / Permissions-Policy headers; templates have no inline scripts, `on*=` or `javascript:`; no CDNs |
| `tests/security/test_phone_validation.py` | 09XXXXXXXXX on models, forms, views and the booking API |
| `tests/residents/test_migration_phone_normalize.py` | phone normalization data migrations (forward, reverse, invalid ids reported) |
| `tests/security/test_uploads.py` | extension + magic bytes + 5 MB cap, random names, private supporting documents, IDOR, file-copy migration |
| `tests/security/test_temp_password.py` | 12-character temporary passwords |
| `tests/security/test_error_exposure.py` | unexpected exceptions logged, generic message shown |

Upload fixtures must use real file headers: `tests.base.JPEG_BYTES` / `PNG_BYTES` / `WEBP_BYTES` /
`PDF_BYTES` or `upload_jpeg()` / `upload_png()`. Arbitrary bytes named `.jpg` are rejected.

## UI tests (Stage D)

- `tests/ui` runs with the rest of the suite. The label check renders key pages per role and fails when an `<svg class="icon">` has no visible text next to it and no `aria-label`/`title` on its control.
- `static/scss` is out of sync with `static/css/main.css` (the source of truth). Do not run `compile_scss.py`; it exits unless passed `--i-know-scss-is-stale`.
- Automated tests do not prove visual quality or full WCAG compliance; that needs a browser check and manual testing with assistive technologies.
