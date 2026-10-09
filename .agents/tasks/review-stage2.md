# Residents as the single demographics source (Stage 2)

Stage 2 moves gender, civil status, solo-parent, PWD and 4Ps onto `Resident`, derives seniors from `birthdate` (age >= 60, never stored), and removes `User.is_senior/is_pwd/is_4ps/civil_status` through three separate migrations (0013 schema, 0014 data, 0015 schema). Statistics and the Records RBI tab now read `Resident` through shared selectors, and both registration paths plus the staff edit form collect and persist the new fields. The coder's recorded gate is 218 passed, 0 failed (`pytest -n 4`, `scratch\run.log` tail confirms it). I did not re-run the suite. I spot-checked `makemigrations --check --dry-run`, which reports no changes.

Watch for: rejected and pending sign-ups still count in population and the RBI (possible, documented decision); staff registration accepts a blank gender server-side (confirmed, minor); a merge on approval drops the applicant's self-declared PWD/4Ps/solo flags (confirmed, minor).

**Verdict**: APPROVED

## High-level view

Resident is now the only demographics store. The fields have the requested choices and defaults, and seniors have two implementations of the same rule: the `Resident.is_senior` property and the `selectors.seniors()` / `senior_cutoff()` queryset helper. Both agree at the 59/60 boundary, including the Feb 29 birthday.

The migration trio follows the plan. Schema is split from data, the data step is portable ORM (no raw SQL, paged `bulk_update`), and it reverses by refilling the User columns while they still exist. Civil status is lowercased with unknown or blank mapped to `single`, and `'pwd'` in `needs_categories` is tokenised rather than substring-matched.

Every consumer I could find moved: statistics, the RBI tab, the residents page, admin, the seed script, both registration paths and the edit view. `PersonalInfoForm`/`SettingsForm` are gone with no references left. `User.civil_status` was removed outright, so there is no sync to justify.

The remaining gaps are small and none of them block the stage. They are listed in the Issues section.

<details>
<summary>Issues (5)</summary>

1. **Pending and rejected sign-ups counted as inhabitants** (possible) — `active_residents()` only excludes `is_archived`, so a rejected applicant's Resident still shows in `population()`, gender/sector counts and the Records RBI tab. The plan accepted this (same rule as the dashboard). Decide in a later stage whether the census and RBI should also filter on the linked user's status.
2. **Blank gender accepted by the staff service** (confirmed) — `clean_demographics` allows `''`, and only the modal's HTML `required` enforces gender. A direct POST creates a "Not specified" resident that dilutes the gender report. Require gender in `staff_register_resident_service` for new registrations, and keep the blank tolerance for edits of legacy rows.
3. **Applicant flags discarded on merge** (confirmed) — in `approve_resident_service` with `link_resident_id`, only a blank `gender` is back-filled from the applicant's stub. Their self-declared `is_pwd/is_4ps/is_solo_parent` are deleted with the stub. The plan says to keep the existing record's values, so this is by design. Consider OR-ing the booleans so a declaration is not silently lost.
4. **Edit silently skips demographics when the User has no Resident** (likely) — `resident_edit_view` guards with `hasattr(..., 'resident_profile')` and still flashes "updated". It is harmless with the current data (both resident-less users are non-resident accounts). Show a notice or hide the fields when there is no profile.
5. **Duplicate `_truthy` helper and inline onclick** (confirmed) — `_truthy` in `services.py` is the placeholder for Stage 3's `parse_bool`, so it must be swapped there to leave one implementation. The Edit buttons in `residents_tabbed.html` extend an existing inline `onclick` payload with the new attributes. The new register modal correctly uses `data-action` and `static/js/resident_register_modal.js`.

</details>

<details>
<summary>Details</summary>

### Feb 29 boundary for the derived senior rule

`years_ago` falls back to Feb 28 instead of calling `date.replace`, which would raise. I walked a Feb 29 birth by hand: the property gives 59 on the day before a non-leap anniversary and 60 from Mar 1, and the cutoff comparison in `seniors()` and the age bands agrees on both days, so the three never disagree. The tests pin 59, 60, 61, one day short, the Feb 29 property/queryset pair and local date vs UTC.

### Migration trio 0013 / 0014 / 0015

```
0013 schema: add Resident fields
0014 data:   User flags + needs_categories 'pwd' -> Resident; civil_status -> lowercase/single
0015 schema: drop the four User columns
```

Users holding PWD/4Ps flags without a Resident are logged as a count rather than migrated (nothing to copy to). Reverse recomputes `is_senior` from birthdate and re-capitalises civil status. MySQL was not run (port 3306 closed, stated by the coder), so portability is reasoned from the ORM-only code and not executed.
### Issue 1 detail: who counts as an inhabitant

`register_resident_service` creates the Resident at sign-up, before approval. Nothing archives it on rejection. So a rejected or still-pending applicant appears in the RBI table and in the population figures that Stage 5 will chart. The plan and the coder both record that this matches the dashboard rule and the Stage 2 spec ("only archived is excluded"). I am not blocking on it, but it is the most likely source of a wrong headline number later.

</details>

<details>
<summary>File map</summary>

- `apps/accounts/models.py`: Resident fields, derived `is_senior`, `sector_labels`, local-date age; four User fields removed
- `apps/accounts/migrations/0013..0015`: schema add, data backfill (reversible), schema drop
- `apps/accounts/selectors.py`: demographics selectors, `years_ago`, `senior_cutoff`, `seniors`
- `apps/accounts/forms.py`: demographics fields on `ResidentRegistrationForm`; unused User forms removed
- `apps/accounts/services.py`: `clean_demographics`, both register services, `update_resident_demographics_service`, merge note
- `apps/accounts/views.py`: `resident_edit_view` persists demographics; template context for choices
- `apps/accounts/admin.py`: Resident list/filter fields
- `apps/records/views.py`, `templates/records/records_hub.html`: RBI tab iterates Residents with sector badges
- `apps/statistics/views.py`: reads the selectors
- `templates/accounts/{residents_tabbed,signup}.html`, `static/js/resident_register_modal.js`: forms and the modal
- `seed_demo_data.py`: demographics written to Resident
- `tests/residents/*`, `tests/records/test_rbi_residents.py`: model, selector, form, migration and statistics tests

</details>

