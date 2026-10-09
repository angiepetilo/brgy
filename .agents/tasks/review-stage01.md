# Appointment canonical data layer (Stage 0 + Stage 1)

The six mirrored Appointment column pairs are collapsed into one canonical set (`appt_date`, `time_window`, `purpose`, `healthcare_service`, `document_type` FK, separate `admin_notes` / `rejection_reason`, `fee_at_booking`). The `save()` sync is gone and only `reference_no` generation remains. A data-only migration (0014) backfills, a separate schema-only migration (0015) drops the legacy columns, and every consumer plus the officer search and admin-phone fixes were updated. The coder's recorded gate is `pytest -n 4 -p no:cacheprovider` = 158 passed, 0 failed, plus `check` and `makemigrations --check --dry-run` clean. That evidence is in plan.md and was not re-run here.

Watch for: (1) legacy status literals (`submitted`, `under_review`, `approved_scheduled`, `ready_for_pickup`) survive in `appointment_detail.html`, `table.html`, the list edit modal and `status_order` in the detail view, so staff cannot see the Complete / No-Show buttons for an `approved` appointment (confirmed, pre-existing, not blocking for this stage); (2) 0014 silently drops a stray `rejection_reason` on non-rejected rows when `admin_notes` is also filled (confirmed, low likelihood); (3) existing document appointments keep `fee_at_booking = NULL`, which Stage 5 revenue must handle (confirmed).

**Verdict**: APPROVED

## High-level view

The migration split is done as specified. 0014 only reads and rewrites rows through the ORM, creates missing DocumentType rows and never deletes anything. 0015 contains only portable schema operations. Its reverse works on populated tables because `preferred_date` gets a placeholder default first. The migration tests run both directions on seven deliberately malformed legacy rows.

Consumers were moved to the canonical names and the removed-name grep is enforced by a test (`RemovedNamesGoneTests`), which I confirmed independently with a repo grep. Fee snapshotting happens in `book_appointment_service` and `create_document_request`, so Settings price changes only affect new bookings. The booking test proves it.

Officer search now filters on real `Officer` fields. The admin phone comes from `BarangayInfo` through `get_contact_number()`. The only `0917-111-2222` left is the demo user in `seed_demo_data.py`, which the plan allows.

The remaining gaps are stale status strings in templates, one lossy edge in the backfill, and NULL historical fees.

<details>
<summary>Issues (4)</summary>

1. **Stale legacy status literals in UI** (confirmed) — `appointment_detail.html` (stepper, Approve / Complete / No-Show conditions), `views.py` `status_order`, `table.html` and the `appointment_list.html` edit-modal `<select>` still use `submitted/under_review/approved_scheduled/ready_for_pickup`. Replace with `pending/approved/completed/rejected/no_show` in the next cleanup pass (ideally before Stage 2 touches these templates). Also add a test that the detail page shows Complete for an `approved` row.
2. **Lossy rejection_reason fold in 0014** (confirmed) — a non-rejected row with both `admin_notes` and a different `rejection_reason` loses the latter. Append it to `admin_notes` instead of discarding, and add a test row for that case. Not applied to the live DB yet, so the fix is cheap.
3. **Historical `fee_at_booking` is NULL** (confirmed) — the 4 local rows and any other pre-existing document rows have no snapshot. Stage 5 revenue must treat NULL as unknown (or backfill from the current fee by an explicit, documented decision).
4. **No test that approved appointments expose Complete / No-Show** (likely) — the page-render test only covers a rejected row, which is why issue 1 slipped through.

</details>

<details>
<summary>Details</summary>

## Backfill rules in 0014 and what they can lose

The migration is data-only and uses historical models, with no raw SQL. It only creates DocumentType rows (missing standard types at fee 0, inactive rows for unmatched custom names) and rewrites Appointment columns in batches. Nothing is deleted. Existing fees are untouched, which the test asserts. The `time_window` rule ("afternoon in either column wins") is a sound reading of the data, because both columns defaulted to `morning`. It reproduces the real local row #2 (`afternoon`), which I confirmed in `scratch/migrate-copy.sqlite3`.

The one lossy path is the notes fold. For a non-rejected row the code does:

```python
if not (apt.admin_notes or '').strip() and (apt.rejection_reason or '').strip():
    apt.admin_notes = apt.rejection_reason
apt.rejection_reason = ''
```

If both fields are non-empty and different, the rejection text is overwritten with no trace. The old `save()` mirrored them, so real data probably has them equal, but direct writes (admin, `update()`) could have diverged them. The test only covers the "admin_notes empty" case (a4). The reverse direction cannot restore it either, because the reverse only refills the legacy date, slot, purpose, service and document columns.

## Schema migration 0015 and reversibility

0015 uses only portable operations, but on MySQL DDL is not transactional, so a failure mid-file leaves a partial schema. The backup note in `docs/backup_restore.md` covers that. MySQL was not reachable, so portability is reasoned, not executed. The live `db.sqlite3` is still at 0013; the backup `.bak` exists and `backups/` is ignored.

## Status literals left behind by the alias removal

The `STATUS_*` constants are gone from Python, but the strings they held are still used as data in templates and in `status_order` (`appointment_detail.html` lines ~45-49, 179, 194; `table.html` lines ~43-49; `appointment_list.html` CSS classes and the edit-modal options at ~1379-1381). Real statuses are `pending`, `approved`, `completed`, `rejected` and `no_show`. The consequences:

- the detail page shows Approve for an already `approved` appointment;
- Complete and No-Show appear only for `approved_scheduled` or `ready_for_pickup`, so they never appear;
- the stepper never highlights the current step;
- the edit modal offers options the status field cannot hold.

The coder listed the stepper as a known pre-existing issue, and the plan's zero-reference list named Python constants, so this does not fail the stage's stated criteria. It is still the same dead-code class the user asked to remove and it breaks a staff workflow, so it should be scheduled explicitly.

## Test coverage

Covered: the forward and backward migrations on populated legacy rows, removed names via a repo scan, canonical booking, fee snapshot, health booking, reject writes only `rejection_reason`, page rendering and the contact fallback chain. `tests/records/test_officer_search.py` covers the officer search.

Not tested: the non-rejected row with two different note fields, a status-driven detail page for an `approved` row, any MySQL execution, and a reverse from 0015 to 0014 alone (placeholder `1970-01-01` dates are then visible in `preferred_date`).

</details>

<details>
<summary>File map</summary>

- `apps/appointments/models.py` — canonical fields, named indexes, `save()` sync removed, aliases removed
- `apps/appointments/migrations/0014_backfill_canonical_appointments.py` — data-only backfill, reversible
- `apps/appointments/migrations/0015_canonical_appointment_schema.py` — schema-only, portable
- `apps/appointments/{services,views,forms,admin}.py` and `management/commands/send_appointment_reminders.py` — canonical names, fee snapshot, DB-driven documents
- `apps/accounts/selectors.py` — `get_contact_number()`
- `apps/communications/{context_processors,views}.py` — `barangay_contact`, `document_types`
- `apps/records/views.py` — officer search on real fields, canonical ordering
- `templates/{landing,accounts/signup}.html`, `templates/appointments/*`, `templates/records/*` — canonical fields, no hard-coded phone
- `config/settings.py`, `.env.example` — empty contact default
- `.gitignore`, `backups/` — DB backup folder ignored
- `tests/appointments/test_data_layer.py`, `tests/records/test_officer_search.py` — new tests

Full diff: `git diff HEAD` in `c:\brgy` (the tree has many pre-existing uncommitted changes).

</details>
