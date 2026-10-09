# Blotter module with settlement-rate statistics

Stage C adds a new `apps/blotter` app for Katarungang Pambarangay case records. It has three models: cases, parties and hearings. Case numbers follow `BLT-YYYY-NNNN` and are assigned with retries. Statuses move through a fixed transition map that the service layer enforces. Permissions come from eight registered `blotter.*` actions, a data migration seeds them, purok scope follows the plan's rule, and confidential cases are gated. Statistics gains a blotter block (by status, type and purok, a monthly filed/settled/closed series, settlement rate and average days to settle), its own API, CSV and print sections, two KPI cards and a line chart. The layering matches the plan, and the coder's evidence shows the full suite green (685 passed), `check` clean and `makemigrations --check` clean.

Watch for: Django admin can create a case with an empty `case_no` and edit `status` directly, which skips the numbering, the timestamps and the audit log (confirmed). Edit and hearing guards read the "closed" state before taking the row lock (confirmed, low impact). Notes on non-terminal transitions of confidential cases are thrown away without a message (confirmed). The live database was not migrated, so the plan's C1 live-DB step is still open (confirmed, deferred like Stages A and B).

**Verdict**: APPROVED

## High-level view

The app follows the requested layers. Views and API handlers are thin wrappers. `policies` owns permission, scope and confidentiality. `selectors` always starts from `policies.visible_cases(user)`, so every page and API read is scoped, and an out-of-scope case answers 404 rather than 403. `services` owns every write: it checks permission and scope, runs `full_clean`, does the work in a transaction and writes `log_activity`. The app is in `INSTALLED_APPS` and mounted at `blotter/` with the `blotter` namespace.

Case numbering takes the length-aware max for the year and inserts inside a savepoint. On a unique clash it counts upward for up to 5 attempts. Status changes lock the row, check `TRANSITIONS`, and stamp `settled_at`, `escalated_at` and `closed_at` (every terminal status sets `closed_at`). Audit text leaves out narratives and party names, and notes on confidential cases stay out of the log.

RBAC grants match the plan exactly. Punong Barangay gets all 8 actions, Secretary gets view/create/edit, Kagawad Peace and Order gets 6, Tanod gets view/create, and residents are always denied. Purok scope matches the plan's C2 rule: a user limited to puroks sees only their puroks, cases with no purok are hidden from them, an `all`/`general`/`punong barangay` service-area assignment overrides the limit, and everyone else sees every purok. This is looser than appointments, which deny by default; the plan chose it on purpose. Migrations start at `0005` because the live DB still has rows for the removed blotter app's `0001..0004`. That choice is documented and was tested on a backup copy, forward and reverse.

The statistics block gives aggregates only. The overall settlement rate is a cohort figure: settled divided by closed, among cases filed in the period. The monthly rate is a closure-month figure. Both are documented, but they will not always reconcile.

The gaps are around the edges. Django admin is a write path that skips the services. Two guards check state before taking the lock. Confidential mediation notes are dropped. The live DB is not migrated yet.

<details>
<summary>Issues (5)</summary>

1. **Admin bypasses case numbering and lifecycle**: `BlotterCaseAdmin` allows adding a case (it saves with `case_no=''`, and the second one hits a unique-constraint 500) and editing `status` without timestamps or audit. Set `has_add_permission` to False and make `status` read-only, or route admin saves through `services`.
2. **Terminal check before lock**: `update_case` and `add_hearing` test `case.is_terminal` on the unlocked instance. Check again on the `select_for_update` row (`update_case`), or lock the case in `add_hearing`.
3. **Confidential mediation notes discarded**: in `transition_case`, notes on a non-terminal move of a confidential case are neither stored nor logged, and the user is not told. Store them somewhere access-controlled (for example, on the case) or hide the notes field for that move.
4. **Live DB migration still pending**: plan C1 asks for a `...C.bak` backup and `migrate` on `db.sqlite3`. Blotter 0005/0006 (and the A/B migrations) are unapplied on the live DB. Run them once the user confirms.
5. **Two settlement-rate definitions**: the overall rate (cases filed in the period) and the monthly rate (closures in the month) can disagree on the same screen. Add a label or tooltip in the KPI/chart note that says which is which.

</details>

<details><summary>Details</summary>

### Django admin as an unguarded write path

`case_no` is `editable=False` and has no default, and `BlotterCaseAdmin` lists it in `readonly_fields`. Creating a case from the admin therefore saves `case_no=''` (confirmed). The second admin-created case fails the unique constraint with a 500. `status` is editable in the admin, so a superuser can set `settled` without `settled_at` or `closed_at` and without an ActivityLog row. Statistics then count the case as closed while `avg_days_to_settle` and the monthly series miss it. The timeline in `selectors.status_timeline` handles cases that have no audit rows, but it cannot recover timestamps that were never stamped. Only superusers can reach the admin, which is why this is not blocking.

### Lock ordering in update and hearing services

`transition_case` checks `next_statuses` on the locked row, which is correct. `update_case` checks `case.is_terminal` on the caller's instance, and the `locked` row it then edits is never checked again. `add_hearing` takes no lock at all. If a case is settled at the same moment someone edits it or records a hearing, the edit or hearing can land on a closed case (confirmed in code). The window is small and the effect is a data-quality problem, not a security one.

### Confidential cases: visibility and notes

Visibility is enforced once in `visible_cases`, which every read path uses. Notes handling has one asymmetry. For terminal moves, notes go into `resolution_notes`. For a confidential case moving to `under_mediation`, notes are kept only when the case is not confidential. Otherwise they disappear without a message to the user (confirmed).

### Settlement-rate semantics in Statistics

```
overall:  settled / (settled+escalated+dismissed+withdrawn)   among cases with filed_at in range
monthly:  count(settled_at in month) / count(closed_at in month)
```

Take a period with a January filing that settles in March. It counts toward March's monthly rate, and toward the overall rate only if it was filed inside the range. The docstring covers this, but the KPI card and the chart note both say "settlement rate" without that detail.

### Live database migration status

Both migrations are reversible and use only the ORM. The evidence shows them applied forward, reversed and re-applied on a backup copy. `showmigrations` on the live `db.sqlite3` lists both blotter migrations, and appointments 0016–0020, as unapplied. The plan's live-DB step for C (back up as `...C.bak`, migrate, re-count) is therefore still open, as are those for A and B. Running it needs the user's confirmation.

### Test coverage

`tests/blotter` (105 tests) covers numbering and uniqueness, every legal and illegal transition, timestamps, audit rows (including that names and confidential notes stay out), RBAC per seeded role and for the kapitan, purok scope with the `all` override and a union of two puroks, confidential visibility, IDOR returning 404 on pages and API, 400 validation for JSON and form input, the rate-limit 429, anonymous 401 and resident 403, PH mobile validation on parties, list filters and pagination, buttons per role, and the no-inline-JS check. `tests/statistics/test_blotter_metrics.py` pins exact numbers (60.0% rate, 11.4 average days, monthly rows, purok filter), the empty state (None and zeros), API auth, CSV and print sections, and the absence of leaks.

Not tested: creating or editing a case through Django admin, a concurrent edit or hearing during a transition, notes on a confidential case moving to mediation, and real two-connection number clashes.

</details>

<details>
<summary>File map</summary>

- `apps/blotter/models.py`: BlotterCase, BlotterParty, BlotterHearing, TRANSITIONS/TERMINAL
- `apps/blotter/policies.py`: `can`, purok scope, `visible_cases`, transition permissions
- `apps/blotter/selectors.py`: filter parsing, list/detail, purok and handler choices, timeline
- `apps/blotter/services.py`: create (numbering), update, transition, hearing, delete, audit
- `apps/blotter/forms.py`: case form, party formset, transition and hearing forms
- `apps/blotter/api.py`: JSON list/detail/create/transition
- `apps/blotter/views.py`, `urls.py`, `admin.py`: HTML pages, routes, admin registration
- `apps/blotter/migrations/0005_blotter_schema.py`, `0006_seed_blotter_permissions.py`: schema and seeded rules
- `apps/accounts/permissions.py`: `blotter` registry entry and default grants
- `apps/statistics/selectors.py`, `api.py`, `urls.py`, `views.py`: blotter block, API, CSV sections
- `templates/blotter/*`, `templates/statistics/overview.html`, `print_report.html`, `templates/includes/sidebar.html`: UI
- `static/js/blotter.js`, `static/js/statistics.js`, `static/css/blotter*.css`: party rows, chart, print CSS
- `config/settings.py`, `config/urls.py`: INSTALLED_APPS, `blotter_create` rate, mount
- `tests/blotter/*`, `tests/statistics/test_blotter_metrics.py`: new tests
- Docs: route matrix, admin/staff guides, testing, README

Full diff: `git diff` in `c:\brgy` (Stage C files are untracked; `git status` lists them).

</details>
