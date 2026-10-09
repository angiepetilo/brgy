# Stage A bug fixes, second pass: canonical appointment statuses, NULL-FK display, population rule, JSON auth errors

This pass checks the iteration-2 fixes for the five findings from the first Stage A review, and re-checks every Stage A requirement against the code. All five findings are resolved. The communications feed and the announcement and emergency lists no longer chain `default:post.author.get_role_display`. The statistics "Log in" link always returns to the current page. The duplicate `_wants_json` is gone, and the `population()` docstring names the rule. The live 0016 migration is now explicitly deferred to the final step, because this stage's instructions forbid migrating the live DB. Evidence: 463 tests passed (baseline 404, no failures), `check` is clean, `makemigrations --check` reports no changes, and `node --check` passes on both changed JS files.

Watch for: the live DB still shows 0016 unapplied, so the final step has to run the backup, row-count and integrity sequence listed in verify-stageA.md (confirmed, deferred by instruction). The detail page's old "Status Management" form still saves any status directly. It bypasses the services, the permission and scope checks and the audit log (confirmed, pre-existing, not in the Stage A plan). `resident_delete_view` still redirects to the raw `HTTP_REFERER` (confirmed, outside A7's scope).

**Verdict**: APPROVED

## High-level view

The appointment lifecycle is now computed in `apps/appointments/selectors.py`. `status_steps` and `allowed_actions` mirror the service transitions: pending offers Approve and Reject, approved offers Complete and No-Show, and completed, rejected and no_show are terminal. Actions are intersected with `check_user_perm` and the staff appointment scope. A grep over the scoped templates, `static/js` and `apps/appointments` finds no legacy status ids, only English prose ("Submitted on", "submitted successfully").

NULL-FK display goes through one `display_name` filter. It is used in the records hub, both print views, appointment detail and concern detail. The three communications lists now render `author_position` directly; that property already falls back to "Barangay Official" when there is no author. New null-author tests cover all three pages.

A single `counted_residents_q` rule (not archived, and either no user or an active user) drives `active_residents`, the per-purok population, the household counts and the residents dashboard counters. Records and Statistics inherit the rule through those selectors.

The 0016 backfill is data only, uses the ORM only, batches its updates and reverses with a no-op. Its test covers four cases: a NULL document row, an existing snapshot, a health row and a row with no document type, plus the reverse run.

JSON callers now get 401 or 403 JSON from the gate middleware (anonymous, inactive and idle-expired users), from `require_perm` and from `JsonExceptionMiddleware`. `statistics.js` handles a 401, a redirect or an HTML body by showing a session-expired message with a DOM-built link back to the current page.

<details>
<summary>Issues (3)</summary>

1. **Live DB still at appointments 0015 (non-blocking, deferred)**: the final step must back up to `backups\db.sqlite3.<ts>.A.bak`, record row counts, migrate, re-count, run `pragma integrity_check` and confirm `[X] 0016_backfill_fee_at_booking`. On the live data the backfill copies whatever document fees are set when it runs.
2. **`resident_delete_view` raw referer redirect (non-blocking)**: `apps/accounts/views.py` still calls `redirect(request.META.get('HTTP_REFERER') or ...)`. Switch it to the new `_safe_back` helper when this file is next touched (Stage B security work is a natural place).
3. **Status Management form bypass (non-blocking, pre-existing)**: in `appointment_detail_view`, the `update_status` POST saves `AppointmentStatusUpdateForm` directly. That skips the transition services, `check_user_perm`, the staff scope check and `log_activity`. Remove the form, or route it through the services, in a later stage.

</details>

<details>
<summary>Details</summary>

### Status Management form bypasses the transition table (confirmed, pre-existing)

The new buttons are gated, but the right-hand "Status Management" form on the same page still gives staff a second way to change status. `appointment_detail_view` (around `views.py:988`) saves `AppointmentStatusUpdateForm` straight to the model for any admin or staff user:

```python
status_form = AppointmentStatusUpdateForm(request.POST, instance=appointment)
if status_form.is_valid():
    updated_apt = status_form.save(commit=False)
    updated_apt.processed_by = user
    updated_apt.save()
```

That path skips:

- the approve, reject, complete and no-show services
- `check_user_perm`
- `check_staff_appointment_scope`
- `log_activity`

So a pending request can jump straight to completed with no issued-document log and no audit entry. The form existed before Stage A and the plan does not cover it, so it does not block this stage. It does undercut D3's single source of truth, though, and it should be removed or routed through the services. Stage B or D are reasonable places to do that.

### Resident edit field clearing (confirmed)

`update_resident_account_service` writes `phone_number` and `street_address` unconditionally, so a blank field clears both. The old inline view behaved the same way, and Stage B's phone validation will cover this input. `resident_delete_view`, next to it in the same file, still redirects to the raw `HTTP_REFERER` rather than going through the new `_safe_back`.

### Tests

New or changed test files with test counts:

- `core/test_core_tags` (5)
- `appointments/test_status_ui` (15)
- `records/test_health_records_null_staff` (3)
- `communications/test_null_author` (3)
- `residents/test_population_rule` (4)
- `appointments/test_migration_fee_backfill` (2)
- `settings/test_stage_a_rules` (10)
- `residents/test_resident_edit` (5)
- `statistics/test_api_auth` (12, including the new link-target test)

The changes to existing tests (`test_api`, `test_part_c` and the route crawler) follow from the 302-to-401 switch, and the evidence explains each one. Not tested: how the landing page's anonymous booking flow handles a 401 in the browser. Only the server side is covered, and that JS is moving to `landing.js` in Stage B.

</details>

<details>
<summary>File map</summary>

- `apps/core/` (new): `CoreConfig`, `http.py` (wants_json, json_error, json_login_required, json_forbidden), `middleware.py` (JsonExceptionMiddleware), `templatetags/core_tags.py` (display_name)
- `config/settings.py`: adds `apps.core` and `JsonExceptionMiddleware`
- `apps/appointments/selectors.py` (new): `status_steps`, `allowed_actions`
- `apps/appointments/views.py`: the detail view uses the selectors
- `apps/appointments/migrations/0016_backfill_fee_at_booking.py` (new): data backfill
- `apps/accounts/selectors.py`: `counted_residents_q`, and the population, purok and household queries use it
- `apps/accounts/services.py`: dashboard counters use the rule; new `update_resident_account_service`
- `apps/accounts/system_services.py`: disable rules, requirement clearing, dead helper removed
- `apps/accounts/system_views.py`: uses the shared `wants_json`
- `apps/accounts/views.py`: resident edit goes through the service; `_safe_back`
- `apps/accounts/middleware.py`, `apps/accounts/permissions.py`: 401/403 JSON
- `templates/appointments/{appointment_detail,table,appointment_list}.html`: canonical statuses and the selectors
- `templates/records/*`, `templates/chat/concern_detail.html`, `templates/communications/*`: `display_name`, and the author badge with no `default:` chain
- `templates/statistics/overview.html`: date-filter scope note
- `static/js/appointment_detail.js` (new), `static/js/statistics.js`: delegated handlers; session-expired link to the current page
- `docs/route_matrix.md`, `docs/testing.md`
- `tests/...`: the files listed above

The working tree is uncommitted against `c7a94cb`. View the full diff with `git diff` plus the untracked files listed by `git status`.

</details>
