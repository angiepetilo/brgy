# Stage A verification

## Iteration 2 (fixes for review-stageA.md / verdict-stageA.json)

1. **Null-author crash (blocking), fixed.** `templates/communications/{feed,announcements_list,emergency_list}.html` now render `post.author_position|upper` with no `default:post.author.get_role_display` (`author_position` already returns "Barangay Official" when author is NULL). New `tests/communications/test_null_author.py` (3 tests) deletes the author (SET_NULL) and checks that each page returns 200 and shows `[BARANGAY OFFICIAL]`. A template grep found no other `default:fk.attr` chain on a nullable FK: the remaining ones are CASCADE FKs or sit inside `{% if %}` guards.
2. **Session-expired link, fixed.** `static/js/statistics.js` `showSessionExpired()` now always uses `defaultLoginUrl()` (`/accounts/login/?next=<current page path+query>`). The server's `login_url` is no longer read. The server still sends `login_url` for other API clients. New test `test_api_auth.py::test_session_expired_link_returns_to_current_page`. `node --check static\js\statistics.js` exits 0.
3. **Live DB migration to 0016: explicitly DEFERRED.** This stage's instructions say "Do NOT apply migrations to the live db.sqlite3 in this stage (the final step applies migrations after backup)", and that overrides the plan's A4 live-verify step. The final step must:
   - back up to `backups\db.sqlite3.<ts>.A.bak`
   - count rows before
   - migrate
   - count rows after
   - run `pragma integrity_check`
   - confirm `showmigrations` shows `[X] 0016_backfill_fee_at_booking`

   Current state: `[X] 0015_canonical_appointment_schema`, `[ ] 0016_backfill_fee_at_booking`. The migration has already been exercised on a backup copy (see below).
4. **Duplicate `_wants_json`, fixed.** It was removed from `apps/accounts/system_views.py`, and the view now uses `apps.core.http.wants_json`. The email-template JS (`system_settings.js`) sends `X-Requested-With: XMLHttpRequest`, so its behaviour is unchanged. The view reads `request.POST`, so the old `content_type == 'application/json'` branch was never reachable.
5. **`population()` docstring, fixed.** It now names the `counted_residents_q` rule.

### Gate commands (iteration 2, from `c:\brgy`, `$env:PYTHONUTF8='1'`)

```
& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log
======= 463 passed, 1 warning, 95 subtests passed in 148.74s (0:02:28) ========

& 'c:\brgy\.venv\Scripts\python.exe' manage.py check
System check identified no issues (0 silenced).

& 'c:\brgy\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
No changes detected   (exit 0)

& 'c:\brgy\.venv\Scripts\python.exe' manage.py showmigrations appointments   (tail)
 [X] 0015_canonical_appointment_schema
 [ ] 0016_backfill_fee_at_booking
```
The suite now has 463 tests against a baseline of 404, with no failures. Iteration 1 had 459, and this iteration adds 4 new tests.

---

## Iteration 1

No `verdict-stageA.json` existed, so Stage A was implemented from scratch. Work was done in place: no worktree, branch, commit, reset, stash, clean or checkout. The live `db.sqlite3` was not migrated (`showmigrations` still lists `appointments 0016_backfill_fee_at_booking` as `[ ]`).

## Gate commands (run from `c:\brgy`, `$env:PYTHONUTF8='1'`)

```
& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log
======= 459 passed, 1 warning, 95 subtests passed in 152.19s (0:02:32) ========
```
Baseline before any change: `404 passed, 1 warning` (in `scratch\baseline.log`). The run has 55 new tests and no failures. The one warning was already in the baseline.

```
& 'c:\brgy\.venv\Scripts\python.exe' manage.py check
System check identified no issues (0 silenced).

& 'c:\brgy\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
No changes detected

node --check static\js\statistics.js        -> exit 0
node --check static\js\appointment_detail.js -> exit 0
```

## Migration 0016 tested on a COPY of the backup

The copy came from `backups\db.sqlite3.20261007-182028.pre-migrate.bak` and was saved as `scratch\dbcopy.sqlite3` (`DB_NAME=scratch/dbcopy.sqlite3`). It was migrated to `appointments 0015`, then to `0016`:

```
--- before 0016
appointments 4
doc_null_fee 3
doc_with_fee [(1, None, 0.00), (2, None, 0.00), (3, None, 0.00)]
integrity ok
Applying appointments.0016_backfill_fee_at_booking... OK
--- after 0016
appointments 4
doc_null_fee 0
doc_with_fee [(1, 0.00, 0.00), (2, 0.00, 0.00), (3, 0.00, 0.00)]
integrity ok
```
- Reverse (`migrate appointments 0015`) prints `Unapplying appointments.0016_backfill_fee_at_booking... OK`.
- The copy and the probe script were deleted afterwards.
- In this backup the document types have fee 0.00. The live run copies whatever fees are set at migrate time.
- MySQL could not be reached (port 3306 is closed), so portability was reasoned, not run. The migration is ORM-only (`filter` plus `bulk_update`) and has no raw SQL.

## Item by item

- **A0.** New `apps/core` app (`CoreConfig`, label `core`), added to `INSTALLED_APPS` before the other local apps.
  - Added the `display_name` filter in `apps/core/templatetags/core_tags.py`.
  - Removed the dead `system_services.get_staff_terms_ending_soon`.
  - Tests: `tests/core/test_core_tags.py`.
- **A1.** New `apps/appointments/selectors.py` with `status_steps` and `allowed_actions`, checked against `check_user_perm` and the staff scope.
  - `appointment_detail_view` passes `status_steps` and `allowed_actions`. The hard-coded legacy `status_order` is removed.
  - Detail template: the stepper comes from `status_steps`. Each of the Approve, Reject, Complete and No-Show buttons shows only when its action is allowed:
    - pending: Approve, Reject
    - approved: Complete, No-Show
    - completed, rejected, no_show: none
  - Each button posts to `appointments:approve`, `:reject`, `:complete` or `:noshow`.
  - The inline `onclick` handlers moved to `static/js/appointment_detail.js` (`data-confirm`, `data-action`).
  - `table.html` pills are now pending, approved, completed, rejected and no_show.
  - `appointment_list.html`:
    - The CSS classes are canonical.
    - The stepper is Pending, Approved, Completed.
    - The edit-modal status `<select>` is gone (dead UI: `update_appointment_service` refuses status changes), along with its JS line.
  - Grep over `templates/appointments`, `templates/records`, `templates/accounts`, `static/js` and `apps/appointments` (migrations excluded) finds only English prose ("Submitted on", "submitted successfully") and the `registration_submitted` context flag.
  - Tests: `tests/appointments/test_status_ui.py` (15 tests).
- **A2.** `display_name` replaces the `default:fk.attr` chains on nullable FKs in:
  - `records_hub.html` (issued_to, issued_by, processed_by)
  - `print_health_record.html`, `print_document.html`
  - `appointment_detail.html`
  - `chat/concern_detail.html`
  - `communications/{announcements_list,emergency_list,feed,announcement_detail}.html`
  - Tests: `tests/records/test_health_records_null_staff.py`.
- **A3.** Added `accounts.selectors.counted_residents_q(prefix)`. It is used by `active_residents()`, `population_per_purok()`, `households_per_purok()` and the residents dashboard counters in `accounts.services`, so all of them follow one rule.
  - Records RBI and Statistics pick up the rule through the selectors.
  - Tests: `tests/residents/test_population_rule.py`.
  - No existing exact-count test needed changing.
- **A4.** `apps/appointments/migrations/0016_backfill_fee_at_booking.py` is data-only, uses the ORM only, and reverses with `RunPython.noop`. Booking still snapshots the fee.
  - Tests: `tests/appointments/test_migration_fee_backfill.py`.
- **A5.** `disable_staff_account_service` raises an error when:
  - the target is not staff, admin or kapitan ("Only staff accounts can be disabled here.")
  - the target is a superuser and the actor is not
  - the actor targets their own account (this block was kept)
  - Tests: `tests/settings/test_stage_a_rules.py`, including the view message.
- **A6.** Saving a document type now always deletes and recreates its `Requirement` rows, so an empty textarea leaves 0 rows.
  - Tests: `tests/settings/test_stage_a_rules.py`.
- **A7.** New `accounts.services.update_resident_account_service`: atomic, calls `log_activity`, returns `(user, resident_or_None)`.
  - The view shows the warning "...has no resident (RBI) profile, so demographics were not saved."
  - The redirect only follows a same-site referer; anything else goes to `residents_tabbed`.
  - Tests: `tests/residents/test_resident_edit.py`.
- **A8.**
  - `apps/core/http.py` (`wants_json`, `json_error`, `json_login_required`, `json_forbidden`) and `apps/core/middleware.py: JsonExceptionMiddleware`, placed after `MessageMiddleware`.
  - `ApprovalGateMiddleware` returns 401 JSON for anonymous, inactive and idle-expired JSON callers.
  - `require_perm` returns 401 or 403 JSON when `wants_json`.
  - `statistics.js`:
    - on a 401, a redirect or a non-JSON body, it shows "Your session expired, please log in again." with a "Log in" link built with DOM APIs
    - on a 403, it shows the permission message
  - The overview page has the note "Date filters apply to appointments and revenue only. Resident and household figures are a current snapshot."
  - Tests: `tests/statistics/test_api_auth.py`.
- **A9.** Updated `docs/route_matrix.md` (JSON 401/403 section) and `docs/testing.md` (Stage A test files, `MEDIA_ROOT` note).

## Existing tests changed (expected effect of A8)

- `tests/statistics/test_api.py::test_anonymous_is_redirected_to_login` is now `test_anonymous_gets_401_json_with_login_url`.
- `tests/appointments/test_part_c.py::test_booking_requires_authentication`: an anonymous POST to `/appointments/api/public-book/` now expects 401 JSON with `login_url` containing `next=`, and checks that no appointment was created.
- `tests/accounts/test_route_crawler.py`: the crawl GETs `/accounts/logout/`, which ends the admin session. After that, admin requests to `/api/` routes get 401 JSON instead of 302. 401 is allowed for the admin persona on `/api/` paths only.

## Notes for the reviewer

- On the landing page:
  - The anonymous health-service fetch gets 401 JSON and leaves the select unchanged, the same silent fallback as before.
  - The booking submit now shows the server `error` text instead of the generic "Network error".
  - This is a one-token change to the existing inline script in `landing.html`.
- The right-hand "Status Management" form on the detail page (`AppointmentStatusUpdateForm`) was not part of Stage A and is unchanged. It uses canonical model choices.
- The suite already wrote QR images into `media/qr_codes/` before this stage (some existing tests have no `MEDIA_ROOT` override). The new tests use `TEMP_MEDIA`. Existing files were not deleted.
