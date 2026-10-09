# Statistics module: selectors, JSON API, CSV/print export and Chart.js UI

Stage 5 replaces the empty statistics page with a read-only aggregate layer (`apps/statistics/selectors.py`) that feeds three surfaces: five JSON routes under `/statistics/api/`, a CSV export, and a print report. Permissions move from `admin_only` to a new `statistics` module (`view`, `export`), seeded for Punong Barangay and Secretary, with a data migration for existing databases. Demographics come from `Resident` through `apps.accounts.selectors` (seniors derived from birthdate, fixed civil-status labels). Revenue sums `Coalesce(fee_at_booking, document_type__fee)` over completed document appointments. Chart.js 4.5.1 is vendored locally and the overview page is a shell that fetches the API.

Watch for: date filters only bound appointments, not the resident/household snapshot, and the page text does not say so (confirmed, minor). A session that expires mid-use shows a JSON-parse error rather than a login prompt (likely, minor). Production still runs plain `StaticFilesStorage` because `STATICFILES_STORAGE` is ignored by Django 5.2 (confirmed, pre-existing, out of scope by plan). Evidence: the coder's full gate (404 passed, `check` clean, `makemigrations --check` clean) plus my one spot-check, `tests/statistics/test_static_manifest.py` and `test_api.py`: 13 passed.

**Verdict**: APPROVED

## High-level view

Everything numeric lives in one module. `build_report()` and the per-block functions are pure ORM aggregates, and the API, CSV and print page all call them, so the three surfaces cannot drift. The CSV is generated from the same report dict the print page renders, and tests compare CSV cells against `build_report` and against the JSON API.

Filter handling is strict and centralised in `parse_filters`. Bad dates, `date_from > date_to`, ranges over ten years and unknown purok ids raise one `FilterError`, which the API turns into a 400 JSON body, the CSV/print views into a 400 text response, and the overview page into an inline message. Defaults are the last twelve months ending this Manila month.

Permissions are view-gated for the page and API and export-gated for CSV/print, with `require_perm` outside `require_GET`. Residents get 403, anonymous users get a login redirect, and staff holding only `system.edit` are denied. The seed migration is additive and reversible.

Chart.js is served from `static/vendor/chartjs/` with a README pinning version, source and hashes. The one local edit (stripped `sourceMappingURL`) is documented and is what lets `collectstatic` succeed under the WhiteNoise manifest backend. A slow test proves hashed URLs resolve for the three statistics assets.

<details>
<summary>Issues (4)</summary>

1. **Date filter scope not shown on the page** (confirmed, minor) — KPI cards for population, sectors and purok density ignore `date_from`/`date_to`, but the "Showing X to Y" line reads as if everything is bounded. Add "(appointments and revenue only)" or a note on the demographic cards.
2. **Expired session during fetch** (likely, minor) — a 302 to the login page is followed by `fetch`, returns 200 HTML, and `response.json()` throws, so the user sees a parse error. Treat `response.redirected` or a non-JSON content type as "session expired, sign in again".
3. **Summary endpoint recomputes every block** (confirmed, minor) — `summary_block` runs demographics, density, appointments and revenue, and the page then calls the other four endpoints as well, so each page load does the work twice. Acceptable at barangay scale; revisit if data grows.
4. **Production static storage unchanged** (confirmed, pre-existing) — `STATICFILES_STORAGE` is ignored by Django 5.2, so production serves unhashed files. Already in the plan's final-report list; fix with `STORAGES` in a separate change.

</details>

<details>
<summary>Details</summary>

## One report, three surfaces

`selectors.py` has no request object and no writes. The API wrappers pick one block each, the CSV is built from `build_report` through `_csv_rows`, and `print_report.html` renders the same dict. `get_statistics_data` and the `admin_only` import are gone. `test_csv_numbers_equal_the_api_numbers` and `test_csv_numbers_equal_the_json_api` pin equality for summary, gender, civil status, purok density, status counts and the monthly revenue series including the TOTAL row. CSV cells starting with `= + - @ \t \r` get a `'` prefix, and a test uses a document type named `=HYPERLINK(...)` to prove it.

## Filter scope on the page

Demographics and household counts ignore the date window. The selector docstring and the stage notes say so, but the page text does not (see issue 1): an evaluator who narrows the range sees unchanged population cards. A lone `date_to` backs up twelve months and a lone `date_from` runs to the end of the current month.

## Metric derivations

Seniors are derived from birthdate with a Feb 29 fallback, civil-status rows use the stored lowercase codes (the capitalisation mismatch is gone), and age bands sum to population by test. Purok density excludes households whose members are all archived, appends Unassigned unranked, and flags `is_highest` only when the top purok holds something.

Revenue buckets by `TruncMonth('appt_date')` on a `DateField` and zero-fills in Python. That avoids MySQL timezone-table dependence, and the month labels are Manila calendar months. Deleted document types surface as "Unspecified" instead of vanishing from the totals. Blotter settlement rates are not exposed because no Blotter module exists; this is the plan's deferral, and the selector docstring says where a block would be added.

## Permissions migration

Migration `0017` uses `get_or_create`, so a customised rule is not overwritten, and its reverse deletes only the Punong Barangay/Secretary statistics rules. `DefaultRuleTests` asserts no other position holds an allowed statistics rule.

## Front end and static assets

`statistics.js` writes every value with `textContent`, discards stale responses via a request counter, and no `|safe`, `innerHTML`, `onclick` or inline script exists in `templates/statistics/` or the JS. The usability gap is session expiry: fetch follows the login redirect, `.json()` fails, and the user sees a parse error (issue 2).

The SHA-256 of the shipped `chart.umd.js` matches the README's "as shipped" hash and the trailing `sourceMappingURL` is gone. The slow manifest test runs `collectstatic` under `CompressedManifestStaticFilesStorage` into a temp root and checks that hashed names for Chart.js, `statistics.js` and `statistics.css` are emitted and exist on disk.

## Test coverage

Selectors, API, export/page, permission-migration and manifest behaviour are covered with a seeded dataset that includes archived residents, unassigned households, null `fee_at_booking` rows and out-of-range appointments. The API tests cover 200, 403, anonymous redirect, 400 on bad dates and `date_from > date_to`, purok filtering and 405 on POST. Not tested: JS behaviour (no browser run), and MySQL execution of `TruncMonth`/`Coalesce`, which the coder reported as unreachable.

</details>

<details>
<summary>File map</summary>

- `apps/statistics/selectors.py`: pure aggregates, filter parsing, `build_report`
- `apps/statistics/api.py`: five GET JSON views, `no-store`, 400 on bad filters
- `apps/statistics/views.py`: thin overview, CSV export, print report
- `apps/statistics/urls.py`: page, export and `api/*` routes
- `apps/accounts/permissions.py`: `statistics` module and Secretary defaults
- `apps/accounts/migrations/0017_seed_statistics_permissions.py`: data-only seed, reversible
- `apps/accounts/templatetags/perm_tags.py`: `user_can` tag
- `templates/statistics/{overview,print_report}.html`, `templates/includes/sidebar.html`: UI shell, print page, permission-gated link
- `static/js/statistics.js`, `static/css/statistics.css`: chart loader and styles
- `static/vendor/chartjs/`: Chart.js 4.5.1, license, pinned README
- `tests/statistics/*`: selectors, API, export/pages, migration, manifest tests

Full diff: `git diff` in `c:\brgy` (tree is uncommitted).

</details>
