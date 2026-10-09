# System Settings backend: checkbox parsing, canonical redirects, hardened email templates

Stage 3 replaces the `bool(data.get('is_active', True))` pattern with a documented `parse_bool` plus a view-level `with_unchecked_checkboxes`, so an unchecked box now switches a flag off on create and on update for post category, document type, health service and concern category. Redirects go through one `_settings_redirect(tab, subtab)` helper, and all views run through `_run_service`, which shows `ValueError` text, maps missing objects to a fixed message, and logs anything else with `logger.exception` behind a generic message. `BarangayInfo` gains `city`/`province` (migration 0016, blank defaults), optional fields are clearable, and the email-template editor gets a catalog-driven whitelist, Django syntax validation, a `Subject:` rule, atomic writes and an audit row. Evidence: the coder's recorded gate (`pytest -n 4 ... ` = 281 passed, check and makemigrations clean) is in plan.md; one spot-check of `tests/settings/test_settings_backend.py` and `test_migration_barangay_info.py` gave 63 passed.

Watch for: (1) `email_template_edit_view` is still guarded by `system.preview_emails`, so a preview-only staff member can rewrite templates that carry temp passwords and reset links (confirmed, non-blocking, already flagged by the coder). (2) `disable_staff_account_service` does not check that the target is a staff account (confirmed, non-blocking). (3) Clearing the requirements textarea on a document type leaves the old `Requirement` rows (confirmed, non-blocking).

**Verdict**: APPROVED

## High-level view

Checkbox handling follows one rule: `parse_bool` is pure parsing with the default for missing or unknown values. Services pass the documented default on create and the current value on update. Views fill `'0'` for every checkbox the form owns but did not post. That makes "unchecked" reliably False for every model in scope, and the tests drive it through the real views for all four models.

Error handling and redirects are centralized. The only text that reaches the browser is a `ValueError`/`ValidationError` message, the fixed "no longer exists" message, or the generic message. The email JSON endpoints use the same mapping with status 400. Every view redirects to canonical `tab`/`subtab` values, and a test asserts the views module contains no legacy names.

The email editor is now safe to save from: whitelist on read, preview and write, syntax and sample-render checks before anything touches disk, and a temp-file `os.replace`. The remaining gap is authorization, not validation: the edit route is gated by the preview permission.

<details>
<summary>Issues (4)</summary>

1. **Email edit gated by preview permission** (confirmed) — require `system.edit` (or a new `edit_emails` rule) for POST in `email_template_edit_view`; keep `preview_emails` for GET and preview. Templates carry `temp_password` and reset URLs.
2. **Staff disable has no target check** (confirmed) — `disable_staff_account_service` disables any `User` id, including admins, superusers and residents. Restrict to `role=staff` and refuse superusers or admins.
3. **Requirements cannot be cleared** (confirmed) — `create_or_update_document_type_service` only resyncs `Requirement` rows `if req_lines:`, so an emptied textarea sets `requirements_needed=''` while the old rows stay. Delete the rows when the field is submitted empty.
4. **Reject ValueError text from incidental sources** (possible) — `str(e)` of any `ValueError` is shown, including ones from ORM coercion such as a non-numeric `officer_id` in staff creation. Harmless today; validate `officer_id` explicitly if it bothers you.

</details>

<details>
<summary>Details</summary>

## Permission on email template writes

`email_template_edit_view` serves GET (source), POST (save) and shares `@require_perm('system', 'preview_emails')`. The registry has no separate write rule for emails. `staff_created.txt` embeds `{{ temp_password }}` and `password_reset_email.txt` embeds the reset link, so anyone holding only the preview permission can change what those emails say or link to. The syntax, subject and audit checks reduce accidents but do not address this. The fix is small: split the check by method, or require `system.edit` for POST. The coder noted this and left it unchanged, which is a reasonable scope call for Stage 3, but it should be closed in Stage 4 or earlier.

## Staff disable accepts any user id

The lookup now returns a clean "no longer exists" error, but the service never checks `role`, `is_superuser` or admin status of the target. Only self-disable is blocked. A user with `manage_staff` can post another user's id to the disable route and deactivate an admin or a resident. The docstring also promises "Reassigns open concerns", which the function does not do.

## Requirements sync on document types

```python
req_lines = [r.strip() for r in requirements_text.split('\n') if r.strip()]
if req_lines:
    doc.requirements.all().delete()
    ...
```

Submitting an empty requirements field writes `requirements_needed=''` but keeps the `Requirement` rows, so the stored text and the checklist disagree. The same block deletes and recreates all rows on every save, which changes their ids. Nothing in the diff shows a dependency on those ids, so it is only worth revisiting if Stage 4 or appointments start referencing requirements.

## Coverage notes

Tests are consolidated into `test_settings_backend.py` and `test_migration_barangay_info.py` instead of the five files the plan named; coverage matches the plan list. Email tests patch `email_template_dir` to a temp copy, so repo templates are not modified. Not tested: permission split between preview and edit for emails (the test asserts the current behavior), and disabling a non-staff target.

</details>

<details>
<summary>File map</summary>

- `apps/accounts/system_utils.py`: new `parse_bool`, `with_unchecked_checkboxes`, `safe_int`
- `apps/accounts/system_services.py`: lookup helper, barangay info rewrite, flag parsing, email catalog/validation/atomic write
- `apps/accounts/system_views.py`: `_settings_redirect`, `_run_service`, `_json_error`, checkbox lists
- `apps/accounts/selectors.py`: tab normalization, dashboard data
- `apps/accounts/services.py`: `_truthy` replaced by `parse_bool`
- `apps/accounts/models.py` and `migrations/0016_barangayinfo_city_province.py`: city, province
- `templates/accounts/system/system_dashboard.html`: legacy tab conditions removed
- `tests/settings/`: backend and migration tests

Full diff: `git diff` plus untracked files (no commits in this batch).

</details>
