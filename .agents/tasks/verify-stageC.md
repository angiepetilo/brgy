# Stage C verification: Blotter module + settlement-rate statistics

Fresh implementation (no `verdict-stageC.json` existed). Work done in place; nothing committed, live `db.sqlite3` NOT migrated.

## Gate commands (from `c:\brgy`, `$env:PYTHONUTF8='1'`)
```
& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log
  ======= 685 passed, 1 warning, 217 subtests passed in 200.18s (0:03:20) =======
  (baseline after Stage B: 566 passed; Stage C adds 105 tests in tests/blotter and 14 in
   tests/statistics/test_blotter_metrics.py)
& 'c:\brgy\.venv\Scripts\python.exe' manage.py check
  System check identified no issues (0 silenced).
& 'c:\brgy\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
  No changes detected            (exit 0)
node --check static/js/blotter.js      -> exit 0
node --check static/js/statistics.js   -> exit 0
& 'c:\brgy\.venv\Scripts\python.exe' manage.py showmigrations blotter   (live db, unchanged)
  [ ] 0005_blotter_schema
  [ ] 0006_seed_blotter_permissions
```

## Migrations, validated on a COPY of the newest backup only
- `blotter/0005_blotter_schema` (schema) and `blotter/0006_seed_blotter_permissions` (data, reversible, ORM-only).
- Why 0005, not 0001: the live DB (and the backup) still have `django_migrations` rows `blotter 0001_initial .. 0004_*`
  from the old, removed blotter app (its tables are gone). A new `0001_initial` would be treated as already applied
  and the tables would never be created. Django ignores recorded migrations that are not on disk, so 0005/0006
  apply cleanly on both fresh and existing databases. Documented in the migration docstring.
- Script `scratch/migcheck_c.py`: copy `backups/db.sqlite3.20261007-182028.pre-migrate.bak` -> `scratch/migcheck_c.sqlite3`,
  `PRIVATE_MEDIA_ROOT` pointed at a scratch folder, `migrate`, reverse blotter to 0005, re-apply. Output (`scratch/migcheck_c.log`):
```
before: officers 12, rules 166, blotter_rules 0, users 9, residents 7, blotter tables []
  Applying accounts.0013 .. 0019 OK, appointments.0014 .. 0020 OK,
  Applying blotter.0005_blotter_schema... OK
  Applying blotter.0006_seed_blotter_permissions... OK
after:  officers 12, rules 189, blotter_rules 19, users 9, residents 7,
        tables blotter_blottercase, blotter_blotterhearing, blotter_blotterparty
blotter rules per officer:
  Kagawad / Peace and Order: view,create,edit,mediate,settle,escalate
  Punong Barangay: view,create,edit,mediate,settle,escalate,delete,view_confidential
  Secretary: view,create,edit
  Tanod: view,create
integrity_check: ok
officers unchanged: True
after reverse 0006: 0 blotter rules
after re-apply: 19 blotter rules
```
  Rule count grew by 23 = 19 blotter + 4 statistics (Stage A's `accounts/0017`, not yet applied on that backup);
  every other module's count is identical before and after. The copy and scratch folder were deleted afterwards.
- MySQL is not reachable here; portability is reasoned: ORM-only RunPython, no raw SQL, no tz-dependent SQL in the
  new statistics (date windows are aware datetimes, monthly bucketing is done in Python).

## What changed
- New app `apps/blotter` (`models`, `selectors`, `services`, `policies`, `forms`, `api`, `views`, `urls`, `admin`,
  `migrations`), in `INSTALLED_APPS` and mounted at `blotter/` (namespace `blotter`).
- Models: `BlotterCase` (case_no unique/non-editable, 9 incident types, 6 statuses, `TERMINAL`/`TRANSITIONS`
  constants, settled/escalated/closed timestamps, indexes `(status, filed_at)` and `(purok, status)`; future
  incident dates rejected), `BlotterParty` (contact_no uses `validate_ph_mobile`), `BlotterHearing`.
- Numbering `BLT-YYYY-NNNN` per filing year in `services.create_case`: next after the max (length-aware, so 10000
  follows 9999), saved in a savepoint; on a unique-constraint clash it tries the following numbers up to 5 times
  (counting up from the first candidate, so a stale snapshot cannot repeat the same number), then a user-facing error.
- Permissions: `registry.register('blotter', [8 actions])`; `seed_default_permissions()` gives Secretary
  view/create/edit, Kagawad Peace and Order 6 actions, Tanod view/create (PB gets all through the registry loop).
- `policies.py`: residents always denied; purok scope mirrors `check_staff_appointment_scope` (purok assignment
  restricts unless a service-area `all`/`general`/`punong barangay` assignment exists; admin/superuser all);
  confidential cases need `view_confidential`; transition permission per target (mediate/settle/escalate/edit).
- `services.py`: create/update/transition/add_hearing/delete; each checks permission + scope, validates with
  `full_clean`, runs in a transaction (`select_for_update` on transitions) and writes `log_activity`
  (no narrative or party names; notes of confidential cases are not copied into the audit log).
- UI (Stage D not landed, so base template + `static/css/blotter.css`, no inline JS): list with filters (status,
  type, purok, incident date range, search over case no./party name/narrative/location) + pagination; create form
  with dynamic party rows (`<template>` + `static/js/blotter.js`, renumbers TOTAL_FORMS); detail with parties,
  hearings, timeline (filing, hearings, audited status changes) and only the allowed transition buttons; edit
  (open cases only); delete (data-confirm); printable summary (`static/css/blotter_print.css`, `@media print`).
  Sidebar "Blotter" link with `{% user_can request.user 'blotter' 'view' %}` (skipped for residents, which also
  keeps the resident feed query count unchanged).
- JSON API `/blotter/api/cases/` (list, filters, 20/page, 400 on bad filter/page), `cases/create/` (JSON or form,
  400 `{"errors": ...}`, 201 with case_no, `@ratelimit(key='user', rate='blotter_create')`), `cases/<pk>/`
  (404 JSON out of scope), `cases/<pk>/transition/`. The HTML create POST uses the same rate-limit bucket.
- Statistics: `selectors.blotter(filters)` (by status/type/purok zero-filled, monthly filed/settled/closed with
  per-month rate, overall settlement rate = settled / closed among cases filed in the period, average days to
  settle; counts only), in `build_report`; `blotter_cases` and `settlement_rate` in the summary; `/statistics/api/blotter/`
  (`statistics.view`); CSV sections BLOTTER BY STATUS/TYPE/PUROK/MONTHLY + summary rows; print report section 9;
  overview KPI cards (cases, settlement rate) and a filed-vs-settled line chart with empty state (`renderBlotter`).
- Docs: `route_matrix.md`, `admin_guide.md` (Blotter section + permissions table), `staff_guide.md`, `testing.md`, README blotter section.

## Choices worth knowing
- Setting or clearing `is_confidential` needs `view_confidential` (otherwise the creator could lose sight of their own
  case); the checkbox is hidden for users without it and the API ignores the field for them.
- Closed (terminal) cases cannot be edited and take no hearings; hearings need `mediate`.
- A case outside the caller's scope answers 404, not 403, on every page and API route (no id probing).
- Existing tests changed only where Stage C changes the truth: the statistics scope note text, the report block set,
  `settlement_rate` being None on an empty DB, `/blotter/` added to the route crawler's admin prefixes, and
  `api_blotter` added to the statistics API auth list.
- Three pre-existing tests (`test_part_b`, `test_part_c`, `test_part_i`) compared UTC `timezone.now().date()` with the
  app's Manila `localdate()` and failed between 00:00 and 08:00 Manila (the gate ran at 00:27). Test-only fix:
  they now use `timezone.localdate()`; no app code changed.
- Out of scope (as planned): KP 15-day mediation clock, Lupon/Pangkat composition, Certificate to File Action.
