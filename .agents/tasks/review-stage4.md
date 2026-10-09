# System Settings UI: five working tabs, delegated JS, escaped output (second pass)

Stage 4 replaces the four empty-state tabs with real tables and forms driven by the Stage 3 context and routes, and moves all inline JS into `static/js/system_settings.js`, loaded with `{% static %}`. Every form posts to a `reverse()`d route with a CSRF token, redirects return to the canonical `tab`/`subtab`, and edit controls render only for actions the user holds. This pass checks the three fixes from the first review. The coder's re-gate is recorded in plan.md: `pytest -n 4` gave 329 passed, 1 warning, 95 subtests. `manage.py check` and `makemigrations --check` were clean, and `node --check` passed. One spot-check by me, `tests/settings/test_settings_ui.py`, gave 48 passed. plan.md says 49 tests, so the count is off by one, which is a bookkeeping slip. The template has no `|safe`, `onclick` or inline script body. Its only `<script>` tag is the external `system_settings.js`. No browser check was done by the coder or by me.

Watch for: no browser verification of modal focus, Escape, confirm dialogs or the FileReader logo preview (confirmed, informational, non-blocking). Nothing blocking remains.

**Verdict**: APPROVED

## High-level view

All five tabs render real data from `system_dashboard_data()`: documents with peso fee or "Free", health services with schedule, staff with positions and term end, concerns with routing. Sub-tab links and write redirects use the canonical names, and legacy names still resolve. Unchecking a box posts the hidden `0`, and the row shows Inactive after the redirect. System post categories get a disabled Delete button with no delete URL, and the delete view refuses them too.

The three blocking and non-blocking items from the first pass are closed. `password_reset_email` is handled: `get_email_template_source` returns `has_subject`, the JS hides and un-requires Subject, sends only the body, and the view discards any posted subject for that template. Email saving now needs `system.edit`, and the Edit button and modal render only with it, while Preview and GET of the source stay on `preview_emails`. The logo placeholder no longer carries an empty `src`.

<details>
<summary>Issues (3)</summary>

1. **No browser check** (confirmed, informational) — focus trap, Escape, focus return, confirm dialogs and the logo preview are covered only by rendered-HTML tests. Do one manual pass in a browser before release.
2. **Raw `content` bypasses the subject rule for the reset template** (possible, non-blocking) — a POST with `content` containing a `Subject:` line for `password_reset_email` is written as is. The UI never sends `content`, and only `system.edit` holders can reach it. Strip the line server-side if the API is ever exposed beyond this modal.
3. **Future CSP coupling** (confirmed, non-blocking) — modals toggle inline `style.display` and the logo preview uses a `data:` URL, so a strict CSP in a later stage needs `style-src 'unsafe-inline'` and `img-src data:` or a class-based toggle. The edit-URL placeholder replacement also assumes the first `/0/` in the path is the id.

</details>

<details>
<summary>Details</summary>

## Password reset template through the shared edit modal

The first review found that the shared edit modal always required Subject, so `password_reset_email` (whose subject lives in `password_reset_subject.txt`) could not be saved, and a typed subject would have landed in the body. The fix is in three places: the service payload exposes `has_subject`, the JS toggles `ee-subject-group` and the `required` flag, and the view blanks the subject for `EMAIL_TEMPLATES_WITHOUT_SUBJECT` before it builds content. Tests cover the payload flag, saving without a subject, ignoring a posted subject and the toggle markup. The one remaining gap is the raw `content` path listed in the issues.

## Email edit authority

`email_template_edit_view` stays under `preview_emails` for GET. A POST then checks `system.edit` and raises `PermissionDenied` otherwise. The template conditions the Edit button and the edit modal on `can.edit`, and the Edit button sits inside the `preview_emails` block, which fits because the GET source needs that permission. Tests assert that preview-only staff get 403 on POST and see no Edit button, and that staff with both permissions can save.

## Modal and script wiring

Endpoints live in a hidden config element with `/0/` and `/__name__/` placeholders that the JS fills in. All server text is written with `textContent` or `.value`, and the only `innerHTML` mention in the JS is the header comment. Multi-line descriptions and requirements sit in hidden readonly textareas, so they are escaped by the template. Single-line values in `data-*` attributes and `data-confirm` messages use normal autoescape, and tests cover script-tag and attribute-breakout names across the tabs.

## Coverage notes

The suite asserts visible seeded data per tab and sub-tab, form actions, CSRF presence, labels for every input, no `|safe`, RBAC for resident, staff without view and view-only staff, POST endpoints returning 403, deactivation by unchecking, system category delete refusal, redirect targets and messages, and logo upload into a temp `MEDIA_ROOT`. The file is named `test_settings_ui.py` rather than the plan's `test_system_dashboard_ui.py`. Not tested: anything that needs a browser.

</details>

<details>
<summary>File map</summary>

- `templates/accounts/system/system_dashboard.html`: five tabs with sub-tabs, modals, CSRF forms, no inline JS, Edit gated on `system.edit`
- `static/js/system_settings.js`: delegated handlers, config-driven URLs, email fetch with `has_subject` toggle, focus handling, logo preview
- `apps/accounts/system_views.py`: `ending_soon_ids` and `can{}` flags, POST permission check and subject handling in the email edit view
- `apps/accounts/system_services.py`: `has_subject` in the email source payload
- `tests/settings/test_settings_ui.py`: 48 UI, wiring, RBAC, escaping and flow tests

Full diff: `git diff` plus untracked files (no commits in this batch).

</details>
