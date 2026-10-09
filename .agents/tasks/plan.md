# Implementation Plan: batch 2 (Stages A to D)

Work IN PLACE in `c:\brgy`. No git worktree, branch, commit, reset, stash, clean or checkout. Never print `.env` values (there is no `.env` right now; `manage.py` loads one with dotenv if it exists, pytest does not).

## Common rules for every item

- Shell: PowerShell. Before every Python command run `$env:PYTHONUTF8='1'`. Python is `& 'c:\brgy\.venv\Scripts\python.exe'`. Send noisy output to `c:\brgy\scratch\*.log` and read the tail.
- Full suite (from `c:\brgy`): `& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log`. The baseline is 404 passed, 0 failed.
- Module run: `& 'c:\brgy\.venv\Scripts\python.exe' -m pytest tests/<module> -p no:cacheprovider *> scratch\mod.log`
- Stage gate. All of these must be clean before a stage's verdict:
  1. full suite green
  2. `manage.py check`
  3. `manage.py makemigrations --check --dry-run` reports "No changes detected"
  4. `node --check` on every changed `static/js/*.js` file
- New migrations:
  - ORM only, reversible, schema and data in separate files.
  - Before applying to the live DB, copy `db.sqlite3` to `c:\brgy\backups\db.sqlite3.<yyyyMMdd-HHmmss>.<stage>.bak` (`Get-Date -Format yyyyMMdd-HHmmss`).
  - Record the row counts of the touched tables, run `manage.py migrate`, re-count and confirm they are unchanged. Also run `pragma integrity_check`.
  - Use a small script in `scratch/`, then delete it.
- MySQL is NOT reachable (port 3306 closed). Portability is reasoned, not executed. Every stage report must say so.
- Architecture for new or changed code:
  - Views stay thin.
  - Read-only queries go in `selectors.py`.
  - Writes go in services and call `apps.history.utils.log_activity`.
  - JSON endpoints live in `api.py`.
  - Shared validators and helpers live in `apps/core`.
  - No hard-coded business values.
  - New templates have no inline JS.
- Tests are Django `TestCase`. Use the factories in `tests/base.py`. Every new test folder needs an `__init__.py`.
- Facts from the live DB (read-only probe during planning):
  - Statuses are already canonical: approved 1, completed 1, pending 1, rejected 1.
  - 3 document appointments have `fee_at_booking` NULL.
  - Phones use dashes, e.g. `0917-111-2222` (6 users and 6 residents) plus `09472750431`.
  - 1 `supporting_id` file is at `appointments/supporting_docs/angie_gwapa.jpg`.
  - `brgy_cache_table` exists.
  - Migrations are at accounts 0017 and appointments 0015.

## Decisions (made during exploration)

- **D1. Shared app `apps/core`.** Create it in Stage A and add `'apps.core'` to `INSTALLED_APPS`. It is a plain `AppConfig` with label `core` and no models. It holds `http.py` (JSON-or-HTML error helpers), `validators.py`, `net.py` (`get_client_ip`), `ratelimit.py`, `middleware.py` (security headers), `uploads.py`, `templatetags/core_tags.py` (`display_name`, `icon`) and `icons.py`. One place, so later stages don't duplicate helpers.
- **D2. Nullable FK display.** Do not chain `default:obj.fk.attr`. That raises `VariableDoesNotExist` when the FK is NULL because filter arguments are resolved strictly. Add a `display_name` filter in `core_tags` with the form `{{ user|display_name:"Fallback" }}`, which returns full name, then username, then the fallback. Use it everywhere the chain pattern appears on a nullable FK.
- **D3. Appointment stepper and actions are computed in Python, not template string tests.**
  - Add `apps/appointments/selectors.py` (new) with `status_steps(appointment)`, returning a list of `{code, label, state}` where state is `done`, `current` or `upcoming`.
  - Add `allowed_actions(appointment, user)` in the same file, returning a set drawn from `{'approve','reject','complete','no_show'}`. It is intersected with `check_user_perm` (`appointments.approve`, `.reject`, `.complete`, `.no_show`) and `check_staff_appointment_scope`.
  - The transitions match the services. `reject_appointment_service` only allows pending. So pending offers approve and reject; approved offers complete and no_show; completed, rejected and no_show offer nothing.
  - The stepper is Pending, Approved, Completed. Rejected shows the existing alert. No-show shows Pending and Approved done, then a terminal "No-Show" step.
- **D4. The list edit modal status select is dead UI.** `update_appointment_service` refuses status changes, so remove the `<select name="status">` from the edit modal in `appointment_list.html`. Status changes only go through the action buttons and routes.
- **D5. JSON auth errors.** `apps/core/http.py`:
  - `wants_json(request)` is true when the path contains `/api/`, or `Accept` includes `application/json`, or `X-Requested-With: XMLHttpRequest`.
  - `json_error(status, message, **extra)` builds the error response.
  - `ApprovalGateMiddleware` returns 401 `{"error": "...", "requires_login": true, "login_url": "/accounts/login/?next=..."}` for unauthenticated non-public JSON requests. It does the same for inactive users after logout.
  - `require_perm` returns 401 or 403 JSON when `wants_json`.
  - Add a `handler403` path for JSON as well: a `PermissionDenied` raised inside API views becomes 403 JSON through a small `core.middleware.JsonExceptionMiddleware.process_exception`, applied only when `wants_json`.
- **D6. Brute force uses the `user_login_failed` signal.**
  - Today `UserLoginForm` never calls `authenticate()` for unknown usernames, so no signal fires. Change the form to take `request` (`UserLoginForm(request, data=...)`). It then always calls `authenticate(request, username=<resolved username or the raw identifier>, password=...)`, so unknown users fire the signal too and timing is roughly the same.
  - Counters live in `apps/accounts/login_security.py`. Receivers connect in a new `AccountsConfig.ready()`.
  - The identifier is the submitted login string, stripped and lowercased.
- **D7. Rate limits** come from the `apps.core.ratelimit.ratelimit(key, rate, methods=('POST',), scope=None)` decorator. It uses fixed-window counters in the default cache (`cache.add` then `cache.incr`). Over the limit it returns 429 with `Retry-After`: JSON when `wants_json`, otherwise the new `templates/429.html`. The login lockout keeps its own logic (D6).
- **D8. CSP without a new dependency.**
  - Django 5.2 has no built-in CSP, so write `apps.core.middleware.SecurityHeadersMiddleware`, placed right after `SecurityMiddleware`.
  - Header name: `Content-Security-Policy`, or `Content-Security-Policy-Report-Only` when `CSP_REPORT_ONLY=True`.
  - It also sets `Permissions-Policy`. Keep `SECURE_CROSS_ORIGIN_OPENER_POLICY='same-origin'`, which already sends COOP.
  - The policy string is built from a `CSP_DIRECTIVES` dict in settings.
- **D9. External CDNs.**
  - Remove Google Fonts. Use the stack `Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, so Inter is used only if installed locally. No font download, which suits slow mobile data.
  - In Stage B, vendor FullCalendar 6.1.11 under `static/vendor/fullcalendar/` (`index.global.min.js`; the 6.x global bundle injects its own CSS, so drop the CSS link) with README and MIT LICENSE.
  - Font Awesome stays as a CDN link until Stage D. `CSP_DIRECTIVES` gets a temporary `style-src`/`font-src` allowance for `https://cdnjs.cloudflare.com` in Stage B, marked `# TEMP until Stage D`. Stage D removes it together with FA. This is the only temporary deviation from the requested policy, and the Stage B report must state it.
- **D10. Upload validation** lives in `apps/core/uploads.py`:
  - `validate_upload(file, allowed=('jpg','png','webp','pdf'), max_bytes=5 MB)` checks both the extension and the magic bytes (JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`, WEBP `RIFF....WEBP`, PDF `%PDF-`).
  - `random_upload_to(prefix)` is a deconstructible class that returns `<prefix>/<uuid4hex>.<ext>`.
  - `Appointment.supporting_id` becomes a `FileField`, because `ImageField` rejects PDFs. It moves to private storage at `PRIVATE_MEDIA_ROOT/appointments/supporting_docs`.
- **D11. SCSS is stale.** Compiling `static/scss/main.scss` today gives 75,716 bytes, which does not match the committed `static/css/main.css` (77,571 bytes). `main.css` is the source of truth. Do NOT run `compile_scss.py`. The design tokens go in a new plain `static/css/theme.css`, loaded after `main.css`. Add a comment at the top of `compile_scss.py` and in `docs/testing.md` saying the SCSS is out of sync and must not be recompiled over `main.css`.
- **D12. Lucide.**
  - Vendor `lucide-static@1.52.0`. This is the npm registry "latest" checked during planning; record the exact version you download.
  - Get it with `npm pack lucide-static@1.52.0` into `scratch\lucide\` and extract.
  - Build a SUBSET sprite `static/vendor/lucide/sprite.svg` with only the icons the site uses, so low-end phones don't download the roughly 1 MB full sprite. Use a management command `apps/core/management/commands/build_icon_sprite.py --source <extracted icons dir>` that reads the names in `apps/core/icons.py: ICON_NAMES`.
  - `static/vendor/lucide/README.md` records the version, the source tarball sha (from `npm view lucide-static@1.52.0 dist.integrity`), the ISC license and the rebuild command. Add `LICENSE`.
  - Lucide 1.x canonical ids differ from the design doc names: `alert-triangle` is `triangle-alert`, `home` is `house`. `icons.py` keeps an `ALIASES` map so the doc names work.
- **D13. Civic hierarchy on the feed.** There is no hotline model and none is added. The top stack holds:
  - active emergency posts (`Announcement.category='emergency'`, not expired)
  - the official hotline from `apps.accounts.selectors.get_contact_number()`
  - a link to the emergency list

  The middle stack is document and health service shortcuts from active `DocumentType` and `HealthCareService`. Then come pinned announcements as fixed anchors, then the chronological feed. The data comes from a new `apps/communications/selectors.py: feed_context(user)`.
- **D14. Blotter numbering.** `case_no` is unique and generated in `services.create_case` inside `transaction.atomic()`: next number after the max `BLT-YYYY-%`. If `IntegrityError` hits on save, retry up to 5 times inside a savepoint. This is safer than Appointment, which has a unique constraint but no retry. `closed_at` (set on any terminal transition) is added to the model, because dismissed and withdrawn have no timestamp of their own and the monthly settlement rate needs a closure month.
- **D15. Blotter permissions** are registered centrally in `apps/accounts/permissions.py`, the same way `statistics` is. They are seeded by `apps/blotter/migrations/0002_seed_blotter_permissions.py` (data only, the 0017 pattern) and also added to `seed_default_permissions()` for fresh installs.

---

## Stage A: Bugs

- [ ] A0. Create `apps/core` and remove dead code.
  - Create `apps/core/__init__.py`, `apps.py` (`CoreConfig`, name `apps.core`, label `core`), `templatetags/__init__.py` and `templatetags/core_tags.py` with the `display_name` filter (D2). Add `'apps.core'` to `INSTALLED_APPS` in `config/settings.py`, before the other local apps.
  - Delete the unused `get_staff_terms_ending_soon` in `apps/accounts/system_services.py` (~line 687). The duplicate `selectors.staff_terms_ending_soon` is the one in use; grep confirms no callers.
  - Files: `apps/core/*`, `config/settings.py`, `apps/accounts/system_services.py`.
  - Tests: `tests/core/test_core_tags.py` covers user with full name, user with username only, None with fallback, and None without fallback (empty string).
  - Verify: `pytest tests/core` passes, then `manage.py check`.

- [ ] A1. Legacy appointment status ids. **Needs verification in implementation**: the DB rows are canonical, but the templates and the view still carry legacy ids.
  - `apps/appointments/views.py` `appointment_detail_view` (~line 1055): delete the hard-coded `status_order` and pass `status_steps` and `allowed_actions` from the new `apps/appointments/selectors.py` (D3).
  - `templates/appointments/appointment_detail.html`:
    - lines 41-53: render the stepper from `status_steps` (`step-item {{ step.state }}`).
    - lines 179-207: show Approve, Reject, Complete and No-Show only if the code is in `allowed_actions`. They post to `appointments:approve`, `:reject`, `:complete` and `:noshow`.
    - Move every `onclick` (confirm dialogs, reject box toggle) to a new `static/js/appointment_detail.js` with `data-confirm="..."` and `data-action="toggle-reject"` delegated listeners. Load it in `{% block extra_js %}`.
    - Replace `default:appointment.processed_by.username` and `issued_by.username` with `display_name` (lines 158 and 244).
  - `templates/appointments/table.html` lines 43-55: switch to pending, approved, completed, rejected and no_show pills.
  - `templates/appointments/appointment_list.html`:
    - CSS classes `.status-submitted`, `.status-under_review`, `.status-approved_scheduled`, `.status-ready_for_pickup` (~lines 354-376) become `.status-pending`, `.status-approved`, `.status-completed`, `.status-rejected`, `.status-no_show`.
    - Stepper labels (~line 731) become canonical.
    - Remove the edit modal status `<select>` (~lines 1376-1386) per D4.
    - Fix any status literals in the inline script (calendar colours).
  - Grep until nothing remains: `submitted|under_review|approved_scheduled|ready_for_pickup|for_pickup|released|cancelled` over `templates/appointments`, `templates/records`, `templates/accounts`, `static/js` and `apps/appointments`. Keep `chat` concern `status == 'submitted'` (a valid `Concern` status) and the English word "Submitted" in prose.
  - Files: `apps/appointments/selectors.py` (new), `apps/appointments/views.py`, `templates/appointments/{appointment_detail,table,appointment_list}.html`, `static/js/appointment_detail.js` (new).
  - Tests: `tests/appointments/test_status_ui.py`.
    - For each of the 5 statuses: `status_steps` states are exact, and the detail page for admin shows exactly the expected buttons with the right `action=` URLs.
    - Approved shows Complete and No-Show, not Approve or Reject.
    - A resident sees no action buttons.
    - Posting to each route moves the status (approve, reject, complete, noshow).
    - `table.html` renders a pill per status.
    - A static scan of `templates/appointments` and `static/js` for the legacy ids finds nothing.
  - Verify: `pytest tests/appointments` passes.

- [ ] A2. Records hub crash for a NULL `processed_by`.
  - Use `display_name` in `templates/records/records_hub.html` (lines 439, 442, 513) and `templates/records/print_health_record.html` (141), `print_document.html` (101, 119).
  - Also fix the same pattern on nullable FKs: `chat/concern_detail.html` 59 (`assigned_handler`), `communications/{announcements_list,emergency_list,feed}.html` and `announcement_detail.html` (author lines 106/72/59).
  - Files: the templates listed.
  - Tests: `tests/records/test_health_records_null_staff.py` creates a completed health appointment with `processed_by=None` and checks that `records:hub?tab=document_health&subtab=health` returns 200 and contains "Health Officer", and that `records:print_health` returns 200.
  - Verify: `pytest tests/records` passes.

- [ ] A3. Population rule.
  - In `apps/accounts/selectors.py` add `counted_residents_q(prefix='')`, which returns `Q(<p>is_archived=False) & (Q(<p>user__isnull=True) | Q(<p>user__status=User.STATUS_ACTIVE))`.
  - Use it in `active_residents()`.
  - In `population_per_purok()` replace `Q(residents__is_archived=False)` with `counted_residents_q('residents__')`.
  - In `households_per_purok()` change the "dead household" member test to `counted_residents_q('members__')`.
  - Records (`apps/records/views.py`, which already uses `selectors.active_residents()`) and statistics pick it up with no further change.
  - Files: `apps/accounts/selectors.py`.
  - Tests: `tests/residents/test_population_rule.py`. Residents with no user, an active user, a pending user, a rejected user, a disabled user and archived: population counts only the first two. The RBI table on the records hub lists only those two. Statistics `api/demographics` population matches. Purok and household counts follow the same rule.
  - Verify: `pytest tests/residents tests/records tests/statistics`. Update any existing exact-number expectation that relied on the old rule and note it in findings.

- [ ] A4. Backfill `fee_at_booking`.
  - New data migration `apps/appointments/migrations/0016_backfill_fee_at_booking.py`. Forward: for `category='document'`, `fee_at_booking IS NULL` and `document_type` not null, set it to `document_type.fee`, iterating rows with `apps.get_model`. Reverse is `migrations.RunPython.noop`.
  - Keep `book_appointment_service` snapshotting (`services.py:256-272`); it is unchanged.
  - Tests: `tests/appointments/test_migration_fee_backfill.py` uses the `MigrationExecutor` pattern from `tests/residents/test_migration_demographics.py`.
    - A NULL fee doc appointment gets the fee.
    - An existing fee is untouched.
    - A health appointment stays NULL.
    - Reverse runs.
  - Live DB: back up as `...A.bak` and migrate. Expect 3 rows backfilled. Appointment count stays 4.
  - Verify: `pytest tests/appointments`. `showmigrations appointments` shows 0016 applied.

- [ ] A5. Restrict `disable_staff_account_service`.
  - In `apps/accounts/system_services.py:660` raise `ValueError` when:
    - the target's role is not in staff, admin or kapitan ("Only staff accounts can be disabled here.")
    - the target is a superuser and `actor.is_superuser` is false
  - Keep the self-disable block.
  - Tests: add to `tests/settings/test_settings_backend.py` (or the new `tests/settings/test_disable_staff_rules.py`): resident target rejected; superuser target rejected for a non-superuser admin and allowed for a superuser actor; staff target disabled and audited; self rejected. Also go through the view `system_staff_account_disable` and check that the error message is shown.
  - Verify: `pytest tests/settings`.

- [ ] A6. An empty requirements textarea must clear the rows.
  - In `create_or_update_document_type_service` (`system_services.py:340-345`), always run `doc.requirements.all().delete()` when updating, then recreate from `req_lines`. An empty list leaves zero rows.
  - Tests: a document with 2 requirements updated with an empty textarea has 0 `Requirement` rows and `requirements_needed == ''`. Updating with 3 lines gives 3 rows in order.
  - Verify: `pytest tests/settings`.

- [ ] A7. Resident edit on a user with no Resident profile.
  - Move the writes out of `resident_edit_view` (`apps/accounts/views.py:360-404`) into `apps/accounts/services.py: update_resident_account_service(actor, user, data)`. It is atomic, calls `log_activity`, and returns `(user, resident_or_None)`.
  - The view shows `messages.warning("Account details for X were updated, but this user has no resident (RBI) profile, so demographics were not saved.")` when the resident is None. Demographics are not silently dropped.
  - Also replace `redirect(request.META['HTTP_REFERER'])` with a safe redirect: `url_has_allowed_host_and_scheme`, falling back to `accounts:residents_tabbed`.
  - Tests: `tests/residents/test_resident_edit.py`. With a profile you get a success message and the fields are saved. Without a profile you get the warning text and the User is updated. Bad demographics are rejected with nothing saved. An offsite referer redirects to `residents_tabbed`.
  - Verify: `pytest tests/residents tests/accounts`.

- [ ] A8. Statistics session expiry and filter scope note.
  - Implement D5:
    - `apps/core/http.py` (`wants_json`, `json_error`)
    - `ApprovalGateMiddleware` in `apps/accounts/middleware.py`: unauthenticated branch and inactive-user branch
    - `require_perm` in `apps/accounts/permissions.py`
    - `apps/core/middleware.py: JsonExceptionMiddleware` (`PermissionDenied` becomes 403 JSON when `wants_json`). Add it to `MIDDLEWARE` after `MessageMiddleware`.
  - `static/js/statistics.js` `fetchJson` (lines 73-88): on 401, or a non-JSON body after a redirect (`response.redirected` or content-type not JSON), show "Your session expired, please log in again." with a link `<a href="/accounts/login/?next=<current path>">Log in</a>`, built with DOM APIs and not `innerHTML`. On 403 show the permission message.
  - `templates/statistics/overview.html`: a visible note next to the filters: "Date filters apply to appointments and revenue only. Resident and household figures are a current snapshot."
  - Check the landing booking JS still handles 401 `requires_login` (it already reads that key).
  - Tests: `tests/statistics/test_api_auth.py`:
    - Anonymous GET on each `/statistics/api/*` returns 401 JSON with `requires_login`, not a 302.
    - A resident gets 403 JSON.
    - The overview page contains the note text.
    - A static check confirms `statistics.js` contains the session-expired string.
  - Run `tests/accounts/test_route_crawler.py`; anonymous 401 is already allowed.
  - Verify: `pytest tests/statistics tests/accounts tests/security`. `node --check static/js/statistics.js`.

- [ ] A9. Stage A gate. Run the full suite, `check` and `makemigrations --check`. Update `docs/route_matrix.md` (JSON 401/403 note) and `docs/testing.md` (new test files). Write the stage report into the verdict loop's report file.

Risks in A:
- A3 changes the population numbers shown, which is intended. Existing statistics and records tests with exact counts may need new fixtures.
- A8 changes the anonymous response for `/appointments/api/*` from 302 to 401. The crawler allows it. The landing page fetches `/appointments/api/services/` anonymously and now gets 401 JSON instead of a login HTML page, which is better. Confirm the landing JS degrades gracefully: it shows the "log in to book" message.

---

## Stage B: Security and phone validation

- [ ] B1. Client IP.
  - `apps/core/net.py: get_client_ip(request)`. If `settings.TRUSTED_PROXY_COUNT` (new, `env_int('TRUSTED_PROXY_COUNT', 0)`) is greater than 0 and `X-Forwarded-For` has at least that many entries, return `xff_list[-TRUSTED_PROXY_COUNT]` stripped. Otherwise return `REMOTE_ADDR`.
  - Replace `LoginThrottleMiddleware._get_ip` (`middleware.py:136`) and `apps/history/utils.py:53` with it. Grep `REMOTE_ADDR|X_FORWARDED` until only `net.py` remains.
  - Tests: `tests/core/test_client_ip.py`. Default ignores a spoofed XFF. Count 1 takes the last entry. Count 2 takes the second from last. Fewer entries than the count falls back to `REMOTE_ADDR`. Check that `log_activity` stores the same IP.

- [ ] B2. Login brute-force protection (D6).
  - New `apps/accounts/login_security.py`:
    - `record_failure(identifier, ip)` keys:
      - `lf:u_ip:{ident}:{ip}`: limit `LOGIN_FAILURE_LIMIT` (5), lock `LOGIN_LOCKOUT_SECONDS` (900)
      - `lf:ip:{ip}`: `LOGIN_IP_FAILURE_LIMIT` (env, 20)
      - `lf:u:{ident}`: `LOGIN_USER_FAILURE_LIMIT` (env, 10)
      - All windows equal `LOGIN_LOCKOUT_SECONDS`. Hash the identifier with sha256 in the key, so emails are not stored in cache keys.
    - `lock_remaining(identifier, ip)` returns seconds or 0.
    - `clear(identifier, ip)` clears the username+IP counter only.
    - `logger.warning` on every lock, without the password.
  - Receivers: `user_login_failed` takes the identifier from `credentials['username']` and the IP from `get_client_ip(request)`. `user_logged_in` clears for the submitted identifier and for the user's username and email. Connect them in `AccountsConfig.ready()` in `apps/accounts/apps.py`.
  - `UserLoginForm` (`forms.py:121`) takes `request` and always calls `authenticate(request, ...)`. `login_view` passes `request`.
  - `LoginThrottleMiddleware` becomes pre-check only. A login POST with any active lock returns 429 with `Retry-After`, rendering `accounts/login.html` with `throttled=True` and the generic message "Too many failed sign-in attempts. Please try again in N minutes." Add that block to `login.html`; it does not exist today. Delete the post-response "200 means failure" logic. Move the password-reset counter out of the middleware into B3.
  - Settings: `LOGIN_IP_FAILURE_LIMIT`, `LOGIN_USER_FAILURE_LIMIT`.
  - Tests: `tests/security/test_login_bruteforce.py`.
    - 5 failures lock username+IP, and the 6th returns 429 with `Retry-After`.
    - The message is identical for unknown and known users.
    - A different IP for the same user is still allowed until the per-user limit (10).
    - 20 failures across different usernames from one IP lock the IP.
    - A successful login clears the username+IP counter.
    - A spoofed XFF does not bypass the lock when `TRUSTED_PROXY_COUNT=0`.
    - A lock produces a log record (`assertLogs`).
  - `tests/security/test_part_i.py::test_i2_login_throttle_locks_after_5_failures` must stay green unchanged.

- [ ] B3. Rate limit decorator (D7).
  - `apps/core/ratelimit.py: ratelimit(key='ip'|'user', rate='5/15m', methods=('POST',))`. The rate parser accepts `s`, `m`, `h` and `d` with an optional count, such as `15m`. `key='user'` falls back to IP for anonymous users. Over the limit it returns 429 with `Retry-After`, as JSON when `wants_json`, otherwise `templates/429.html` (new, extends `base.html`, no inline JS).
  - Rate values come from settings dict `RATE_LIMITS = {'password_reset': '5/15m', 'signup': '5/h', 'public_booking': '10/h', 'email_validation': '20/h', 'chat_send': '30/m', 'statistics_export': '20/h', 'blotter_create': '20/h'}`. Each value can be overridden by env `RATE_LIMIT_<NAME>`.
  - Apply to:
    - password reset: wrap `PasswordResetView.as_view(...)` in `apps/accounts/urls.py`, key ip
    - `signup_view`: ip
    - `public_appointment_book_view`: user
    - `api_validate_email_view`: user
    - `chat_room_view` POST and the `concern_detail_view` reply POST: user
    - `stats_export_excel` and `stats_export_pdf`: user, GET
    - Blotter create (Stage C uses the same decorator)
  - Auth before the external API:
    - `api_validate_email_view` returns 401 JSON if the user is anonymous, before calling `validate_email_address`.
    - Move the `request.user.is_authenticated` check in `public_appointment_book_view` (now ~line 438) to the top of the function, before `validate_email_address` (~line 396).
  - Cache: keep the current `CACHES` (Redis if `REDIS_URL` is set, else `DatabaseCache` `brgy_cache_table`). The Django test runner creates the cache table automatically. Document `manage.py createcachetable` in `docs/deployment.md`; it already exists on the live DB.
  - Tests: `tests/security/test_rate_limits.py`, one test per endpoint. Exceed the configured rate (override it with `@override_settings(RATE_LIMITS=...)` for speed) and expect 429 with `Retry-After`, JSON for the API endpoints. For email validation and public booking, mock `apps.appointments.views.validate_email_address` and assert it is NOT called for anonymous users. Call `cache.clear()` in `setUp`.

- [ ] B4. Insecure default settings in `config/settings.py`.
  - When `DEBUG` is False, raise `ImproperlyConfigured` if:
    - `SECRET_KEY` is missing, equals the dev default string, or is shorter than 50 characters
    - `ALLOWED_HOSTS` is empty or contains `'*'`
  - `ALLOWED_HOSTS` default: `'*'` stays only when DEBUG is true; add `localhost,127.0.0.1,testserver`.
  - When DEBUG is False, these default to True: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`. Also default `SECURE_HSTS_SECONDS=31536000`. All stay env-overridable: `env_bool(key, default=not DEBUG)`.
  - `SECURE_HSTS_PRELOAD` defaults to False. Add `SILENCED_SYSTEM_CHECKS = ['security.W021']`, commented: preload is a manual hstspreload.org opt-in. This decision keeps `check --deploy` at zero warnings without committing the domain to the preload list.
  - Remove `SECURE_BROWSER_XSS_FILTER`. Set `SESSION_COOKIE_SAMESITE = CSRF_COOKIE_SAMESITE = 'Lax'`.
  - Add `TRUSTED_PROXY_COUNT`, `CSP_REPORT_ONLY`, `LOGIN_IP_FAILURE_LIMIT`, `LOGIN_USER_FAILURE_LIMIT`, `RATE_LIMIT_*` and `REDIS_URL` to `.env.example` with comments.
  - The test-time DEBUG default stays True, so the suite is unaffected.
  - Tests: `tests/security/test_settings_hardening.py`. Use `subprocess.run([sys.executable, '-c', 'import django; django.setup()'], env=...)` with `DJANGO_SETTINGS_MODULE=config.settings`.
    - DEBUG=False with no key, the dev key, a short key, `ALLOWED_HOSTS=*`, or empty hosts: non-zero exit with `ImproperlyConfigured` in stderr.
    - `manage.py check --deploy` with DEBUG=False, a strong 64-character random key and `ALLOWED_HOSTS=example.com`: return code 0 and "System check identified no issues".
    - In-process asserts for the samesite settings, and that `SECURE_BROWSER_XSS_FILTER` is absent.
  - Mark these tests `slow` only if they take more than 10 s.

- [ ] B5. CSP and removal of inline JS (D8, D9). This is the largest item in B. Do it template by template, running the module tests after each one.
  - Middleware `apps/core/middleware.py: SecurityHeadersMiddleware` builds the exact policy:
    - `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'`
    - plus the temporary FA CDN allowance (D9, removed in Stage D)
    - plus `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - `CSP_REPORT_ONLY=env_bool(..., False)`.
  - Move the inline `<script>` blocks to static files:
    - `landing.html` (262 lines: `enforcePhone11Digits`, `fetchFreeHealthServices`, booking modal, FullCalendar init) to `static/js/landing.js`
    - `accounts/residents_tabbed.html` (257 lines) to `static/js/residents.js`
    - `appointments/appointment_list.html` (366 lines) to `static/js/appointments.js`
    - `chat/chat_room.html` (72) to `static/js/chat_room.js`
    - `chat/inbox.html` (175) to `static/js/inbox.js`
    - `communications/announcement_form.html` (27) to `static/js/announcement_form.js`
    - `communications/feed.html` (12) to `static/js/feed.js`
  - Server data goes through `{{ value|json_script:"id" }}`. `<script type="application/json">` is allowed by the scan, and `JSON.parse` reads it in JS. URLs go in `data-*` attributes on a config element, the pattern in `system_dashboard.html` and `system_settings.js`.
  - Replace every `on*=` attribute, about 130 in templates. Counts per file: base 1, landing 15, pending_approval 1, residents_tabbed 22, appointment_detail 5 (done in A1), appointment_list 35, healthcare_services 1, health_schedule 2, table 3, concern_detail 1, inbox 2, announcements_list 3, announcement_detail 3, announcement_form 4, emergency_list 3, feed 4, create_post_modal 8, edit_post_modal 8, post_trigger_bar 4, messages/chat_view 1, print_document 1, print_health_record 1.
  - Use delegated listeners keyed on `data-action`/`data-confirm`, in the page JS or in shared `static/js/main.js`:
    - `data-confirm` on a submit button or form shows `confirm()`
    - `data-action="dismiss"` removes the parent
    - `data-action="print"`
    - `data-action="back"` replaces `javascript:history.back()` in 403/404/500 and `javascript:` hrefs in residents_tabbed (274, 275, 380, 385, 488, 489), healthcare_services (96, 97) and table.html (114, 115)
  - `post_modal.js` already exists for the modals; extend it.
  - `static/js/websocket.js:141-147` builds `onclick` in `innerHTML`. Rebuild the toast with `createElement` and `addEventListener`, set `linkUrl` through `location.assign` only when it starts with `/`, which also closes an injection risk.
  - Replace the FullCalendar CDN in `landing.html` with the vendored copy (D9). Grep for `cdn.jsdelivr`, `unpkg` and `googleapis` in templates and static, then remove. FA cdnjs stays until Stage D.
  - Tests: `tests/security/test_csp.py`.
    - (a) Walk `templates/` excluding `templates/emails`. Fail on `<script` without `src=` unless `type="application/json"`. Fail on `\son[a-z]+\s*=` attributes and on `javascript:` URLs. Report file and line.
    - (b) The same `on*=` and `javascript:` scan over `static/js/*.js` string literals, excluding `static/vendor`.
    - (c) GET `/`, `/accounts/login/`, and `/home/` as a resident: the CSP header contains `script-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, and `Permissions-Policy` is present.
    - (d) With `CSP_REPORT_ONLY=True`, the report-only header name is used.
    - (e) No `fonts.googleapis`, `fonts.gstatic` or `cdn.jsdelivr` in templates.
  - Update the existing assertions in `tests/settings/test_settings_ui.py:209` and `tests/statistics/test_export_and_pages.py:143,170`; they stay valid.
  - Manual-risk note: no browser is available. Verify each moved script with `node --check`, and check that every element id the JS queries still exists in the template. Write a scratch script that extracts `getElementById('x')` and `querySelector('#x')` ids from each new JS file and asserts that `id="x"` is in the paired template. Run it, record the result, then delete it.

- [ ] B6. Philippine mobile number validation.
  - `apps/core/validators.py`:
    - `PH_MOBILE_RE = r'^09\d{9}$'`
    - `validate_ph_mobile(value)` raises `ValidationError` with the message "Enter an 11-digit mobile number starting with 09 (digits only, e.g. 09171234567)."
    - `normalize_ph_mobile(raw)` returns the normalized string or None: strip non-digits; `63XXXXXXXXXX` (12 digits) becomes `0XXXXXXXXXX`; return the value only if it is valid. The migration and the forms share it.
  - Models get `validators=[validate_ph_mobile]` with `blank=True` kept: `User.phone_number`, `Resident.contact_no`, `Appointment.applicant_phone`, and Stage C's `BlotterParty.contact_no`. Schema migrations are `accounts/0018_phone_validators` and `appointments/0017_applicant_phone_validator`. `BarangayInfo.contact_no` is unchanged.
  - Data migrations, separate files, reverse noop: `accounts/0019_normalize_phone_numbers` (User and Resident) and `appointments/0018_normalize_applicant_phone`. Valid or normalizable values are rewritten. Invalid values are left as they are, and their ids are printed through `print()` and logged with `logging.getLogger('apps.migrations')`. On the live data, `0917-111-2222` becomes `09171112222`.
  - Forms and APIs:
    - `ResidentRegistrationForm.contact_no` (`forms.py:31`): placeholder `09171234567`, `validators`
    - `ProfileUpdateForm.phone_number`
    - `update_resident_account_service` (A7)
    - `staff_register_resident_service`
    - `public_appointment_book_view`: replace the ad-hoc regex at ~line 380 with `validate_ph_mobile` on the raw value. Dashes are now rejected, not stripped.
    - `appointments/forms.py`, if it has `applicant_phone`
    - the system staff create form, if it has a phone field
  - Frontend: every phone input gets `inputmode="numeric" pattern="09[0-9]{9}" maxlength="11"`. Add `static/js/phone_input.js` (delegated on `input[data-phone]`, strips non-digits and truncates to 11). Include it in `base.html` and `landing.html`, and remove `enforcePhone11Digits`.
  - Tests:
    - `tests/core/test_validators.py`: valid `09171234567`. Rejects dashes, spaces, letters, `+639...`, `639...`, 10 digits, 12 digits, and a leading `08`. `normalize` cases.
    - `tests/security/test_phone_validation.py`: `full_clean` on each of the 3 models. Each form and API rejects a bad number: signup, profile, resident edit, staff register, public booking JSON 400 with an `errors.phone_number` key.
    - `tests/residents/test_migration_phone_normalize.py`: the MigrationExecutor pattern with dash, `+63`, `63`, valid and garbage values; garbage is kept and its id reported.
  - Update existing tests and fixtures that post dashed phones; grep `tests/` for `09[0-9]{2}-`.
  - Live DB: back up as `...B.bak`, migrate, and confirm User 9, Resident 7 and Appointment 4 rows are unchanged. Record the normalized phone list, which should be all `09` and 11 digits.

- [ ] B7. Uploads (D10).
  - `Resident.id_photo` gets `validators=[validate_upload]` and `upload_to=random_upload_to('id')`, with storage unchanged (private). Validate in `register_resident_service` and `staff_register_resident_service` too, since they receive files directly.
  - `Appointment.supporting_id` becomes a `FileField(storage=private_supporting_storage, upload_to=random_upload_to('appointments/supporting_docs'), validators=[validate_upload])`. The callable storage lives in `apps/appointments/models.py`, rooted at `PRIVATE_MEDIA_ROOT`. Schema migration: `appointments/0019_supporting_id_private`.
  - Data migration `appointments/0020_copy_supporting_docs_private`. For each non-empty `supporting_id`, copy `MEDIA_ROOT/<name>` to `PRIVATE_MEDIA_ROOT/<name>`, keeping the same relative name so existing rows resolve. Skip files that are missing (log them) and never delete the originals. Reverse copies them back if absent. Document in `docs/backup_restore.md` that the public copies can be removed by hand after checking.
  - New view `appointments:supporting_id` at `appointments/<pk>/supporting-id/`. It uses the same access rule as `appointment_detail_view`: owner resident, admin or kapitan, or in-scope staff. It returns `FileResponse(as_attachment=False)` with a guessed content type and `X-Content-Type-Options: nosniff`. Access logs go through `log_activity`. The template link in `appointment_detail.html:126` points to it.
  - `ApprovalGateMiddleware`: deny `/media/appointments/` the way `/media/id_photos/` is denied.
  - `serve_id_photo_view` (`accounts/views.py:118`): it currently calls `mimetypes` without importing it, so it ALWAYS returns 404. **Needs verification; fix it.** Rewrite it with `FileResponse(resident.id_photo.open('rb'))`.
  - Tests: `tests/security/test_uploads.py`.
    - A `.jpg` file with text content is rejected.
    - A `.exe` is rejected.
    - A file of 6 MB is rejected.
    - Real 1x1 PNG, JPEG, WEBP and PDF bytes are accepted.
    - Stored names are random, not the original.
    - IDOR: resident B gets 403 or 404 on resident A's `supporting_id`, out-of-scope staff gets 403, and the owner and admin get 200 with the bytes.
    - `/media/appointments/...` is denied.
    - The id photo is served with 200 to its owner, 403 to another resident.
  - Use `override_settings(PRIVATE_MEDIA_ROOT=tmpdir, MEDIA_ROOT=tmpdir)`. The storage is callable, so the path is read at runtime; make sure of that.
  - Live DB: back up, migrate, and confirm `private_media/appointments/supporting_docs/angie_gwapa.jpg` exists and opens through the view.

- [ ] B8. Temporary passwords.
  - `generate_temp_password()` (`apps/accounts/services.py:24`) returns 12 characters built with `secrets`. It guarantees at least one lowercase letter, uppercase letter, digit and symbol, using the symbol set `!@#$%^&*-_=+` and no ambiguous characters such as `O0lI`. Shuffle with `secrets.SystemRandom().shuffle`.
  - Update the docstrings at lines 203 and 433 and the email templates that describe the format (grep `4 letters|letters + 4 digits` in `templates/emails` and `docs`).
  - Tests: `tests/security/test_temp_password.py` covers length 12, every class present, and 200 generated passwords all distinct. Update any existing test that asserts the old 8-character pattern; grep `tests` for `temp_pw` and `[a-z]{4}`.

- [ ] B9. Exception exposure.
  - `apps/appointments/views.py:520` and `:949` `except (ValueError, Exception)` become `except (ValueError, ValidationError, PermissionDenied) as e:` to show the message. Add `except Exception: logger.exception(...)` with the message "Something went wrong. Please try again or contact the Barangay Office."
  - Grep every `messages.error(request, str(e))` and `JsonResponse(... str(exc))`, and confirm each except clause is limited to those three types. Known ones: accounts views 367 and 425, chat views 189, 234, 272, 314, 336, 345, appointments 97, 433, 461.
  - Tests: `tests/security/test_error_exposure.py`. Patch the service to raise `RuntimeError('db secret')`: the response does not contain "db secret", the generic message is present, and `assertLogs` catches the exception. A `ValueError` message is still shown.

- [ ] B10. Dependency audit.
  - Run `& 'c:\brgy\.venv\Scripts\python.exe' -m pip_audit -r requirements.txt *> scratch\audit.log`; install with `pip install -r requirements-dev.txt` first if it is missing.
  - For each finding, if a fixed version exists: pin it exactly, reinstall, and run the full suite. Revert the pin if it goes red.
  - Report every finding (id, package, fixed version, action taken).

- [ ] B11. Stage B gate. Run the full suite, `check`, `makemigrations --check`, and `check --deploy` through the B4 test. Update `docs/deployment.md` (env vars, `TRUSTED_PROXY_COUNT`, `createcachetable`, CSP report-only rollout), `docs/route_matrix.md` (the `supporting-id` route) and `docs/testing.md`.

Migration order in B, with dependencies set explicitly:
- accounts 0018 (schema: phone validators, `id_photo` `upload_to`/validators), then 0019 (data: normalize)
- appointments 0017 (schema: `applicant_phone` validators), then 0018 (data: normalize), then 0019 (schema: `supporting_id` FileField/private), then 0020 (data: copy files)

Run `makemigrations` once per schema step and rename the files to these names. Validators and `upload_to` changes are state-only `AlterField`s on SQLite and MySQL; no column type changes except ImageField to FileField, which is varchar(100) in both.

Risks in B:
- B5 rewrites large templates with no browser check. The id-cross-check script and `node --check` are the only evidence; report that plainly.
- B6 changes validation behaviour: dashed input is now rejected. The user asked for this.
- The temporary FA CDN CSP allowance stays until Stage D.

---

## Stage C: Blotter module (Katarungang Pambarangay)

- [ ] C1. App skeleton, models and migrations.
  - Create `apps/blotter/` with `__init__.py`, `apps.py` (label `blotter`), `models.py`, `selectors.py`, `services.py`, `policies.py`, `forms.py`, `api.py`, `views.py`, `urls.py` (`app_name='blotter'`), `admin.py` and `migrations/`. Add `'apps.blotter'` to `INSTALLED_APPS`. Add `path('blotter/', include('apps.blotter.urls', namespace='blotter'))` to `config/urls.py`.
  - Models:
    - `BlotterCase`: `case_no` (CharField 20, unique, editable False); `incident_type` (choices: dispute, noise, theft, physical_injury, property_damage, domestic, threat, trespassing, other); `incident_date`; `incident_time` (null); `location`; `purok` (FK `accounts.Purok`, SET_NULL, null); `narrative` (TextField); `status` (choices: filed, under_mediation, settled, escalated, dismissed, withdrawn; default filed; db_index); `filed_at` (auto_now_add); `settled_at`, `escalated_at` and `closed_at` (null, D14); `resolution_notes`; `handled_by` and `recorded_by` (FK user, SET_NULL, null, related_names `blotter_cases_handled` and `blotter_cases_recorded`); `is_confidential` (bool); `created_at` and `updated_at`. Indexes on `(status, filed_at)` and `(purok, status)`. `TERMINAL` and `TRANSITIONS` dicts are class constants.
    - `BlotterParty`: `case` FK CASCADE `related_name='parties'`; `role` (complainant, respondent, witness); `resident` (FK `accounts.Resident`, SET_NULL, null); `full_name`; `address`; `contact_no` (blank, `validators=[validate_ph_mobile]`).
    - `BlotterHearing`: `case` FK CASCADE `related_name='hearings'`; `scheduled_at` (DateTime); `outcome_notes`; `complainant_attended` and `respondent_attended` (bool); `recorded_by`; `created_at`.
  - Migrations: `0001_initial` (schema). `0002_seed_blotter_permissions` (data, depends on accounts latest from B, `0019_normalize_phone_numbers`) seeds:
    - Punong Barangay: all 8 actions
    - Secretary: view, create, edit
    - Kagawad with committee `Peace and Order`: view, create, edit, mediate, settle, escalate
    - Tanod: view, create
    - Reverse deletes them.
  - In `apps/accounts/permissions.py` add `registry.register('blotter', ['view','create','edit','mediate','settle','escalate','delete','view_confidential'])` and the same defaults in `seed_default_permissions()`: the Secretary dict, the Peace and Order/Tanod loop split so the Tanod gets only view and create.
  - Admin: register the 3 models (read-only `case_no`).
  - Tests: `tests/blotter/test_models_migrations.py` covers choices, the TRANSITIONS map, and the permission migration forward and reverse (pattern from `tests/statistics/test_permission_migration.py`).
  - Live DB: back up as `...C.bak`, migrate, and confirm the Officer and PermissionRule counts grow only by the seeded rules.

- [ ] C2. Policies, selectors and services.
  - `policies.py`:
    - `scope_filter(user)` returns a Q or None (all). Admin and superuser: all. A user with any `StaffAssignment` of type purok and no service-area value in `{'all','general','punong barangay'}`: restricted to `purok__name__iexact` in those values. Everyone else with `blotter.view`: all.
    - `visible_cases(user)` = `BlotterCase` filtered by scope, excluding `is_confidential=True` unless `check_user_perm(user,'blotter','view_confidential')`. Residents get none.
    - `can_transition(user, case, to_status)` maps under_mediation to `mediate`, settled to `settle`, escalated to `escalate`, and dismissed and withdrawn to `edit`.
  - `selectors.py`: `case_list(user, filters)` (status, incident_type, purok, `date_from`/`date_to` on `incident_date`, `q` over case_no, narrative, location and party full_name; distinct; ordered `-filed_at`); `case_detail(user, pk)` (prefetch parties and hearings, Http404 if not visible); `status_timeline(case)` (built from `filed_at`, the hearings, `settled_at`/`escalated_at`/`closed_at`, and the ActivityLog rows for the case).
  - `services.py`:
    - `create_case(actor, data, parties)`: atomic, D14 numbering, at least one complainant and one respondent, party phones validated with `full_clean`, `log_activity`.
    - `update_case(actor, case, data)`
    - `transition_case(actor, case, to_status, notes='')`: `select_for_update`, checks `TRANSITIONS`, sets `settled_at`/`escalated_at` and `closed_at` on terminal, raises `ValueError` on illegal, `log_activity`.
    - `add_hearing(actor, case, data)`: not allowed on terminal cases.
    - `delete_case(actor, case)`
    - Every service checks permission and scope and raises `PermissionDenied`.
  - Tests:
    - `tests/blotter/test_services.py`: `BLT-<year>-0001` then `-0002`; numbering resets per year; uniqueness under a simulated collision (pre-create the next number and assert retry); every legal and illegal transition; timestamps set; audit rows.
    - `tests/blotter/test_policies.py`: RBAC per seeded role; purok scope; `all` override; confidential hidden without `view_confidential`.

- [ ] C3. JSON API, views, templates and nav.
  - `api.py`: `api_list` (GET, filters, paginated 20, 400 on a bad filter), `api_detail` (GET, 404 when not visible), `api_create` (POST JSON or form, `@ratelimit(key='user', rate=RATE_LIMITS['blotter_create'])`, 400 `{"errors": {...}}`), `api_transition` (POST `{to_status, notes}`). All use `require_perm('blotter', ...)` and give JSON 401/403 through D5. Routes go under `blotter/api/...`.
  - `views.py` (thin): `case_list`, `case_create` (GET form, POST via `services.create_case`), `case_detail`, `case_transition` (POST), `hearing_add` (POST), `case_print`.
  - `forms.py`: `BlotterCaseForm` and a party formset (`formset_factory`, extra=1, min complainant/respondent validated in the service).
  - Templates `templates/blotter/{case_list,case_form,case_detail,case_print}.html`. No inline JS, no `on*`. Use the Stage D tokens if they exist; otherwise plain classes that Stage D restyles.
  - `static/js/blotter.js`: add and remove dynamic party rows (clone a `<template>` element, update `TOTAL_FORMS`) and `data-confirm`.
  - Print CSS is `static/css/blotter_print.css` with `@media print`.
  - Sidebar: in `templates/includes/sidebar.html` add the Blotter link with `{% user_can request.user 'blotter' 'view' as can_view_blotter %}`. The bottom nav already treats `'blotter' in request.path` as Records.
  - Update the route crawler substitutions if the new URL params need them (`<int:pk>` already maps). Add `/blotter/` to its `ADMIN_PREFIXES`.
  - Tests:
    - `tests/blotter/test_api.py`: validation 400s; create returns 201 with `case_no`; transition 200 or 400; rate limit 429; anonymous 401 JSON; resident 403.
    - `tests/blotter/test_views.py`: list filters (status, type, purok, date range, search); pagination; detail buttons per role (only the allowed transitions are rendered); IDOR (out-of-scope and confidential case gives 404); party phone validation errors are shown; the print page returns 200; the sidebar link shows only with `blotter.view`.

- [ ] C4. Blotter statistics.
  - Add `blotter(filters)` to `apps/statistics/selectors.py`. Use `filed_at` (date) within `filters.date_from`/`date_to` and the purok filter. It returns:
    - `by_status`, `by_type` and `by_purok`: zero-filled choice rows
    - `months`: `[{month, label, filed, settled, closed, settlement_rate}]`, where filed is by the `filed_at` month, settled by the `settled_at` month, and closed by the `closed_at` month
    - `settlement_rate`: overall settled / closed (settled+escalated+dismissed+withdrawn) as a percentage with 1 decimal, or None when closed is 0
    - `avg_days_to_settle`: computed in Python from `values_list('filed_at','settled_at')` for portability, 1 decimal, or None
  - Aggregates only; confidential cases are counted but no fields are exposed.
  - Add it to `build_report`, add `blotter_cases` and `settlement_rate` to `_summarise`, and add `api.blotter` at route `api/blotter/` (`statistics.view`).
  - CSV: add `BLOTTER BY STATUS`, `BLOTTER BY TYPE`, `BLOTTER BY PUROK` and `BLOTTER MONTHLY` sections to `_csv_rows`. Print: a blotter section in `templates/statistics/print_report.html`.
  - UI: a KPI card for the settlement rate and a line chart of filed vs settled per month in `templates/statistics/overview.html` and `static/js/statistics.js` (`renderBlotter`), with an empty state.
  - Tests: `tests/statistics/test_blotter_metrics.py`. A fixture gives exact numbers, for example 3 settled, 1 escalated, 1 dismissed and 2 open, so the rate is 60.0 and the average days is exact through a frozen `filed_at`. Also: the empty state gives None and zeros; the API needs `statistics.view` (403 for a resident, 401 for anonymous); the CSV contains the sections; the print page contains the rate; the response has no narrative or names. Update `tests/statistics/test_static_manifest.py` if it lists JS files.

- [ ] C5. Stage C gate. Run the full suite, `check` and `makemigrations --check`. Update `docs/route_matrix.md` (blotter routes and API), `docs/admin_guide.md` (Blotter section and permissions table), `docs/staff_guide.md` (how to file and mediate) and `docs/testing.md`.

Risks in C:
- The KP rules (15-day mediation, Lupon, CFA issuance) are out of scope. Statuses follow the requested set only. Mention this in the report.

---

## Stage D: Site-wide UI redesign (per `c:\brgy\barangay_agent_prompt.md`)

- [ ] D1. Vendor Lucide and add the icon tag (D12).
  - `npm pack lucide-static@1.52.0` in `scratch\lucide`, then extract with `tar -xzf`.
  - Write `apps/core/icons.py` with `ICON_NAMES` (canonical ids) and `ALIASES`.
  - Write `apps/core/management/commands/build_icon_sprite.py` to build `static/vendor/lucide/sprite.svg` (`<symbol id="lucide-<name>" viewBox="0 0 24 24">` with stroke attributes on the symbol). Add `static/vendor/lucide/README.md` and `LICENSE`.
  - The `{% icon 'name' %}` simple tag in `core_tags` renders `<svg class="icon icon-<name>" aria-hidden="true" focusable="false" width="20" height="20"><use href="{% static 'vendor/lucide/sprite.svg' %}#lucide-<name>"></use></svg>`. It resolves aliases and raises `TemplateSyntaxError` for an unknown name.
  - JS-built icons use `BrgyUI.icon(name)` in `static/js/main.js`, reading `data-icon-sprite` from `<body>`.
  - Delete `scratch\lucide` after the build.
  - Tests: `tests/ui/test_icons.py`. Tag output; an alias resolves; an unknown name raises; every `{% icon %}` name in the templates exists as a symbol in `sprite.svg`.

- [ ] D2. Design tokens and base layout.
  - `static/css/theme.css` (D11). CSS variables:
    - `--color-canvas:#F9FAFB`, `--color-card:#FFFFFF`, `--color-primary:#1E3A8A`, `--color-danger:#DC2626`, `--color-success:#16A34A`
    - grays `#111827`, `#374151`, `#6B7280`, `#D1D5DB`, `#E5E7EB`
    - `--border:1px solid #E5E7EB`, `--radius:10px`, spacing scale, `--focus-ring:0 0 0 3px` (primary at 40%)
    - `font-size:16px` base, the font stack from D9
    - button, card, badge, table, form and alert component classes, the visually-hidden utility, `.icon` sizing
    - `@media (prefers-reduced-motion: reduce)` disables transitions
    - no gradients, no box-shadows beyond 0
  - `templates/base.html`:
    - Remove Google Fonts and the FA link.
    - Link `theme.css` after `main.css`.
    - Move the inline `<style>` block (lines 16-~300, gradients and translate hovers) into `theme.css`, rewritten flat.
    - Restyle the top bar, `includes/sidebar.html`, `includes/right_sidebar.html`, `includes/staff_roster.html`, the drawer and the bottom nav. Use Lucide icons with text labels and keep every id and class that `main.js`/`websocket.js` uses.
  - Remove the TEMP cdnjs allowance from `CSP_DIRECTIVES` (D9).
  - Delete the dead `templates/chat/chat_view.html`; no view or include references it (verified by grep).

- [ ] D3. Restyle the pages, in groups. Run the module tests after each group.
  - For every file:
    - Replace each `<i class="fa-...">` with `{% icon %}` next to a visible label. Icon-only buttons get `aria-label`.
    - Remove raw emoji.
    - Replace hard-coded colours outside the palette with token classes.
    - Keep forms, CSRF, names and the ids used by JS.
  - Groups:
    - (a) auth: `accounts/{login,signup,password_reset*,change_password,pending_approval}.html`, `403/404/500.html` (500 is standalone: link `theme.css` and drop the CDNs)
    - (b) landing and feed: `landing.html` and `communications/feed.html`, using the D13 hierarchy (`communications/selectors.py: feed_context`, used by `feed_view`; landing gets the same top stack from the existing context), plus `includes/{post_trigger_bar,create_post_modal,edit_post_modal}.html`, `communications/{announcements_list,announcement_detail,announcement_form,emergency_list,manage_history,post_extend,post_mark_done}.html`. Pinned announcements render in a fixed "Pinned notices" section above the feed, never inside a tab.
    - (c) appointments: `appointments/*.html`
    - (d) records and residents: `records/*.html`, `accounts/residents_tabbed.html`, `accounts/{dashboard,profile,officers_permissions}.html`. The `DEPARTMENTS[*]['icon']` values in `apps/records/views.py` become Lucide names (`stethoscope`, `shield`, `folder-open`, `coins`, `hand-heart`, `trophy`).
    - (e) chat: `chat/*.html`, `messages/chat_view.html`
    - (f) history, statistics and settings: `history/overview.html`, `statistics/*.html`, `accounts/system/system_dashboard.html`
    - (g) blotter templates from Stage C
  - `static/js/statistics.js`: set `PALETTE` to the design palette (navy, green, red, then grays) and `HIGHLIGHT` to `#DC2626` or navy.
  - Update the stale icon assertions in `tests/communications/test_feed_layout.py:147-194` (`fa-house` becomes the `house` icon, and so on), so the same structural intent is asserted with Lucide ids.

- [ ] D4. UI tests in `tests/ui/` (new package):
  - `test_no_fontawesome.py`: no `fa-` class pattern (`\bfa-[a-z]` and `\bfa[srb]?\s`) and no `cdnjs`/`font-awesome`/`fonts.googleapis` in templates (excluding emails) or `static/js`/`static/css` (excluding vendor).
  - `test_no_emoji.py`: scans templates (excluding `templates/emails` and test fixtures) for the ranges U+1F300-1FAFF, U+2600-27BF, U+1F000-1F2FF, U+1F900-1F9FF and U+FE0F.
  - `test_icon_labels.py`: render key pages as the right role and parse them with `html.parser`. Every `svg.icon` must have non-empty text in its parent element, or `aria-label`/`title` on the parent or grandparent.
  - `test_base_assets.py`: `base.html` output links `css/theme.css` and references `vendor/lucide/sprite.svg`, with no external stylesheet hosts.
  - `test_key_pages.py`: 200 for landing and login (anonymous); feed, appointments, chat inbox and profile (resident); records, residents, history, statistics, system and blotter (admin). The feed order is emergency block, then services block, then pinned block, then feed, asserted on the `data-section` attribute order.
  - The route crawler and `tests/security/test_csp.py` stay green.

- [ ] D5. Stage D gate. Run the full suite, `check`, `makemigrations --check` and `node --check` on all JS. Run `manage.py collectstatic --noinput --dry-run *> scratch\collect.log` (it must not fail on the vendored files). Update `docs/admin_guide.md` and `docs/testing.md`. The report must say:
  - no browser or visual check was done
  - WCAG AA contrast was reasoned from the palette (navy, red and green on white all exceed 4.5:1), but full WCAG validation needs manual testing with assistive technologies and an expert review
  - MySQL was not run

Risks in D:
- This is the largest diff. Restyling can break ids or classes that JS relies on. Rerun the B5 id cross-check script for every page JS file.
- Lucide 1.x naming: the alias map covers the design doc names.

---

## Already done vs needs verification

| Item | State |
| --- | --- |
| A1 legacy statuses | Data is canonical. **Templates and view still legacy**, confirmed by grep. Fix. |
| A2 NULL `processed_by` | **Confirmed pattern** at `records_hub.html:513` and 10+ similar chains. Fix and test. |
| A3 population rule | Confirmed: `active_residents()` filters only `is_archived`. Fix. |
| A4 fee backfill | 3 NULL rows on the live DB. Fix. |
| A5, A6, A7 | Confirmed in code (`system_services.py:660`, `:342`, `views.py:393`). Fix. |
| A8 | Confirmed: the middleware redirects anonymous users to the login HTML. Fix. |
| B2 | Confirmed: unknown usernames never call `authenticate()`, so the signal approach needs the form change. |
| B7 `serve_id_photo_view` | `mimetypes` is not imported, so it always 404s. **Needs verification in implementation**; fixed by the FileResponse rewrite. |
| Cache table | Exists on the live DB, and the test runner creates it. No action besides docs. |
| Phone data | 13 dashed values on the live DB; the B6 migration normalizes them. |
