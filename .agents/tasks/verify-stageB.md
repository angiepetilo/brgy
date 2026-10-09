# Stage B verification: security hardening and phone validation

Fresh implementation (no `verdict-stageB.json` existed). Work done in place; nothing committed, live `db.sqlite3` NOT migrated.

## Gate commands (from `c:\brgy`, `$env:PYTHONUTF8='1'`)

```
& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log
  ======= 566 passed, 1 warning, 181 subtests passed in 180.17s (0:03:00) =======
  (baseline before Stage B: 463 passed)

& 'c:\brgy\.venv\Scripts\python.exe' manage.py check
  System check identified no issues (0 silenced).

& 'c:\brgy\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
  No changes detected            (exit 0)

DEBUG=False SECRET_KEY=<64 random chars> ALLOWED_HOSTS=example.com manage.py check --deploy
  System check identified no issues (1 silenced).     (exit 0; W021 HSTS preload silenced on purpose)
  Also asserted by tests/security/test_settings_hardening.py::DeployCheckTests (subprocess).

node --check static/js/{main,phone_input,post_modal,appointment_detail,system_settings,websocket,
                        landing,residents,appointments,chat_room,inbox,announcement_form,feed}.js
  all ok
```

## pip-audit

```
& 'c:\brgy\.venv\Scripts\python.exe' -m pip_audit -r requirements.txt *> scratch\audit.log
  No known vulnerabilities found   (exit 0)
```
No findings, so no pins changed. Side note: `channels_redis` is used when `REDIS_URL` is set but is not in `requirements.txt` (pre-existing; not changed).

## Migrations, validated on a COPY of the newest backup only

New: `accounts 0018_phone_validators` (schema, state-only AlterField), `0019_normalize_phone_numbers` (data, reverse no-op),
`appointments 0017_applicant_phone_validator` (schema), `0018_normalize_applicant_phone` (data, reverse no-op),
`0019_supporting_id_private` (schema: ImageField -> FileField, private storage; varchar(100) on both SQLite and MySQL),
`0020_copy_supporting_docs_private` (data: copy files, reverse copies back, never deletes).

Copy of `backups/db.sqlite3.20261007-182028.pre-migrate.bak` -> `scratch/migcheck.sqlite3`, `migrate` with
`PRIVATE_MEDIA_ROOT` pointed at a scratch folder (live `private_media/` untouched). Result (`scratch/migcheck.log`):
```
before: {'accounts_user': 9, 'accounts_resident': 7, 'appointments_appointment': 4}
after:  {'accounts_user': 9, 'accounts_resident': 7, 'appointments_appointment': 4}
row counts unchanged: True
accounts_user.phone_number: 7 non-blank, all 09XXXXXXXXX: True
accounts_resident.contact_no: 7 non-blank, all 09XXXXXXXXX: True
appointments_appointment.applicant_phone: 1 non-blank, all 09XXXXXXXXX: True
supporting_id #4: appointments/supporting_docs/angie_gwapa.jpg -> private copy exists: True
integrity_check: ok
```
No invalid phone values in the backup, so no ids were reported. The copy and scratch folder were deleted afterwards.
Live DB (`showmigrations`): still pending accounts 0018-0019 and appointments 0016-0020 (Stage A's 0016 was not applied either). Apply with a fresh backup in a later step.
MySQL is NOT reachable (port 3306 closed); portability is reasoned (ORM-only RunPython, AlterField of validators/upload_to is state-only, FileField stays varchar(100)), not executed.

## What changed, per item

- **B1** `apps/core/net.py: get_client_ip` (REMOTE_ADDR; X-Forwarded-For entry `-TRUSTED_PROXY_COUNT` only when the setting > 0). Used by login security, rate limits and `log_activity`. `TRUSTED_PROXY_COUNT>0` also enables `SECURE_PROXY_SSL_HEADER` (otherwise `SECURE_SSL_REDIRECT` loops behind nginx). Grep for `HTTP_X_FORWARDED_FOR`/`'REMOTE_ADDR'` in `apps/` finds only `net.py` (enforced by a test).
- **B2** `apps/accounts/login_security.py` + receivers in `AccountsConfig.ready()`. Counters: username+IP 5, IP 20, username 10, window/lock 900 s; identifier sha256-hashed in keys. `UserLoginForm(request, ...)` always calls `authenticate(request, ...)` (unknown users fire the signal). `LoginThrottleMiddleware` is pre-check only: 429 + `Retry-After`, generic message added to `login.html`. Successful login clears username+IP. Lockouts logged on logger `apps.security.login` (no password, hashed identifier). `test_part_i::test_i2_login_throttle_locks_after_5_failures` unchanged and green.
- **B3** `apps/core/ratelimit.py` (`ratelimit(key, rate, methods)`, fixed window in the default cache, 429 + Retry-After, JSON via `wants_json` else new `templates/429.html`). `RATE_LIMITS` in settings, `RATE_LIMIT_<NAME>` env. Applied: password reset (ip), signup (ip), public booking (user), validate-email (user, GET+POST), chat room POST + concern reply POST (user) and the WebSocket consumer (same `chat_send` bucket; error frame shown by `chat_room.js`/`inbox.js`), statistics exports (user, GET). `blotter_create` rate defined for Stage C. `api_validate_email_view` and `public_appointment_book_view` return 401 for anonymous users before `validate_email_address` is called. The old password-reset counter in the middleware was removed.
- **B4** `config/settings.py`: with `DEBUG=False`, `ImproperlyConfigured` when SECRET_KEY is missing / dev default / `django-insecure*` / < 50 chars / < 5 unique chars, or ALLOWED_HOSTS empty or contains `*` (the key is never printed). Dev defaults unchanged (DEBUG True, `*`, dev key). Removed `SECURE_BROWSER_XSS_FILTER`; SameSite Lax on both cookies; SSL redirect, secure cookies, HSTS 31536000 + include-subdomains default on when DEBUG is False (env overridable); preload off and W021 silenced. `.env.example` documents every variable.
- **B5** `SecurityHeadersMiddleware` (after SecurityMiddleware) sends exactly the requested policy, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, COOP same-origin; `CSP_REPORT_ONLY` switches to the report-only header. No new dependency. All inline `<script>` blocks moved to `static/js/{landing,residents,appointments,chat_room,inbox,announcement_form,feed}.js`; every `on*=` handler (~130) and `javascript:` URL replaced by `data-*` attributes with delegated listeners (`main.js`: `data-confirm`, `data-action=dismiss|print|back|reload|scroll-to|click-target`, `data-auto-submit`; `post_modal.js`: `data-post-action`; page files: `data-call`, `data-row-action`, `data-res-action`). Server values formerly injected into JS now come from data attributes. Google Fonts removed (system font stack); Font Awesome 6.5.1 and FullCalendar 6.1.11 vendored under `static/vendor/` (README with npm integrity + SHA-256, licenses). **Deviation from plan D9, in the stricter direction:** Font Awesome is vendored now, so there is no temporary cdnjs allowance in the CSP. Also fixed while moving code: unescaped chat message HTML in `inbox.js` (XSS) and the toast `onclick` built from `link_url` in `websocket.js` (now DOM-built, only same-site paths followed); duplicate confirm handlers in `appointment_detail.js`/`system_settings.js` removed (main.js handles them).
- **B6** `apps/core/validators.py` (`validate_ph_mobile` = `^09\d{9}\Z`, ASCII only; `normalize_ph_mobile`; widget attrs). On `User.phone_number`, `Resident.contact_no`, `Appointment.applicant_phone` (blank allowed). Enforced in signup form, profile form, `update_resident_account_service` (resident edit), `staff_register_resident_service`, `register_resident_service`, public booking API (dashes now rejected instead of stripped; `errors.phone_number`). Inputs get `inputmode=numeric pattern=09[0-9]{9} maxlength=11 data-phone`; `static/js/phone_input.js` strips non-digits (loaded in base.html and landing.html). `BarangayInfo.contact_no` unchanged. Data migrations per above; how admins fix leftovers is in `docs/deployment.md` 2.4.
- **B7** `apps/core/uploads.py` (extension + magic bytes for jpg/png/webp/pdf, 5 MB, `RandomUploadTo` uuid names) on `Resident.id_photo` (+ signup form and `register_resident_service`) and `Appointment.supporting_id` (now FileField in `PrivateMediaStorage` rooted at `PRIVATE_MEDIA_ROOT`, read at runtime). New `appointments:supporting_id` view (FileResponse, nosniff, no-store, audited). `/media/appointments/` and `/media/id_proofs/` denied in middleware and documented for nginx. `serve_id_photo_view` streams with FileResponse. Signup no longer writes the public `User.id_proof` copy (pending page links to the protected view).
- **B8** `generate_temp_password()`: 12 chars, secrets-based, at least one lower/upper/digit/symbol, no `O0lI1`. Symbol set is `!@#$%^*-_=+` (no `&`: the plain-text email templates are rendered with autoescape and `&` would arrive as `&amp;`; a test checks the emailed password logs in). Docstrings, `docs/uat_checklist.md`, `docs/staff_guide.md`, email preview sample and `tests/accounts/test_part_a.py` updated.
- **B9** `apps/core/http.public_error_message` + `GENERIC_ERROR_MESSAGE`. `appointment_create_view` and `appointment_edit_view` (`except (ValueError, Exception)`) now show only ValueError/ValidationError/PermissionDenied messages and `logger.exception` the rest. Every other `messages.error(request, str(e))` / `JsonResponse(... str(exc))` was already limited to those types (or the statistics `FilterError`), checked by grep and a static test.

## New tests
`tests/core/test_client_ip.py`, `tests/core/test_validators.py`, `tests/security/{test_login_bruteforce,test_rate_limits,test_settings_hardening,test_csp,test_phone_validation,test_uploads,test_temp_password,test_error_exposure}.py`, `tests/residents/test_migration_phone_normalize.py` (103 new tests). Existing fixtures updated because fake bytes / dashed phones are now rejected: upload bytes in `tests/accounts/test_part_{a,b,g}.py`, `tests/residents/test_registration_forms.py`, and ONE line in `tests/security/test_part_i.py` (the signup `id_photo` now uses `JPEG_BYTES`; test logic unchanged); dashed phones in `tests/accounts/test_part_f.py`; the old 4+4 temp-password test in `test_part_a.py`.

## Frontend check (no browser available)
`node --check` passes for every changed JS file. A scratch script matched every `getElementById`/`querySelector('#..')` id in the moved JS files against their templates: all found, except 5 ids in `inbox.js` that live in `templates/chat/chat_view.html` (the conversation pane loaded into the inbox), which exist there. No click-through test in a real browser was possible; `CSP_REPORT_ONLY=True` is the documented fallback during rollout.

## Findings for the user (not changed here)
1. `User.is_kapitan_user` returns True for `role='staff'`, so every staff member passes the "admin or kapitan" branch on the appointment detail page and sees all appointments regardless of scope. The new supporting-document view uses a strict rule (only role=kapitan bypasses scope). Changing the property would change what staff can open; left for a decision.
2. The public booking API validates the typed phone number but `book_appointment_service` stores the user's profile phone, not the typed one (pre-existing).
3. `book_appointment_service` previously dropped the uploaded `supporting_id`; it now validates and saves it (privately), so the attachment link on the detail page works.
4. Existing tests write ID photos into the real `private_media/id_photos/` because that storage has a fixed path baked into migrations (an absolute Windows path, pre-existing). Test artifacts from this session were removed (only files not referenced by the live DB).
