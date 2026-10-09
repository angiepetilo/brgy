# Stage D verification: site-wide UI redesign (iteration 2)

`verdict-stageD.json` existed (CHANGES_REQUESTED, 6 findings), so this iteration fixes every finding from `review-stageD.md`. The work was done in place. No git operations were run. The live DB was not touched (no migrate, nothing written to `db.sqlite3`). Iteration 1 notes (Lucide vendoring, theme.css, FA removal, civic feed order) still apply and are not repeated.

## Findings and fixes

1. **Raw emoji in the appointment date filter (blocking).** `templates/appointments/appointment_list.html` options now read `Yesterday` / `Tomorrow`. The ⏪ and ⏩ glyphs are gone.
2. **Gap in the emoji scanner's ranges (blocking).** `tests/ui/test_no_emoji.py` now also covers U+2300–23FF and U+2B00–2BFF. The self-test adds samples for ⏪, ⏩, ⌛, ⭐ and ⬆. The widened scan finds no other hits in templates or first-party JS/CSS.
3. **Green text failing AA contrast.** Small text that used `#16A34A` now uses `#111827`, or `#6B7280` for the "Registered residents" caption. Green stays as a 1px border on badges and as icon colour (`cls='icon-success'`).
   - Templates fixed: `records_hub.html` (2), `health_schedule.html` (2), `concern_detail.html`, `messages/chat_view.html`, `landing.html` (2), `history/overview.html` (3) and the stepper "3" in `appointment_list.html`.
   - Script-built text fixed: the "Valid 11-digit mobile number" feedback in `landing.js`, `appointments.js` and `phone_input.js`.
   - Icon-only boxes and status dots keep green. They are non-text UI, where 3:1 is enough.
   - New guard `test_green_is_not_used_for_small_text`, with a self-test. It flags any inline-styled element that has a text label, a font size of 15px or less, and `color: #16A34A`. It also flags `style.color = '#16A34A'` in JS.
4. **Off-palette rgba tints.**
   - The `statistics.js` revenue fill is now `rgba(30, 58, 138, 0.12)`, which is navy at alpha.
   - The `records_hub.html` department badges now use a `#F3F4F6` background, keeping their palette icon colours.
   - New `test_rgb_and_rgba_colours_use_the_palette` checks every `rgb()`/`rgba()` in templates (emails excluded) and first-party CSS/JS against the palette, with black allowed for overlays. It has a self-test. No other off-palette tints remain.
5. **Lucide README pointed to the wrong file.** `static/vendor/lucide/README.md` now names `static/js/icons.js`. `test_vendor_readme_records_version_and_license` asserts the path and that the file exists.
6. **Gaps in visual coverage.** Fixed by the true-375px pass described under "Visual verification" below.

The 375px pass found real layout bugs, and all were fixed without changing behaviour:
- **Page wrappers overflowed the centre column.** Wrappers centred with `margin: Xrem auto` shrink-wrapped to their min-content, so they overflowed the column on phones and ran under the right sidebar on desktop (officer permissions). `theme.css` now makes them fill the column. Their inline `max-width` still applies.
- **Two-column form grids did not fit on phones.** Signup grids now collapse to one column below 560px (`.grid-stack-sm`).
- **The officer-permissions assign form was a fixed five-column grid.** It is now `auto-fit minmax(min(180px,100%),1fr)`, and its controls are `width: 100%`.
- **Landing cards overflowed.** The landing "Announcements" grid uses `minmax(min(360px,100%),1fr)`.
- **Header actions did not fit.** Below 480px, the top bar brand can shrink and the landing header wraps, so the right-hand actions fit.
- **Emergency post headers clipped their badges.** The header rows now wrap (`flex-wrap`).
- **The chat inbox was squeezed side by side.** On phones (767px and below) the list is now stacked above the conversation. The empty "No chats selected" pane is hidden when no conversation is open. This is layout only: the same links and IDs are kept.

## Commands and results

```
& 'c:\brgy\.venv\Scripts\python.exe' -m pytest -n 4 -p no:cacheprovider *> scratch\run.log
  ======= 724 passed, 1 warning, 261 subtests passed in 223.65s (0:03:43) =======
  (Iteration 1: 719 passed. +5 new tests in tests/ui. The warning was already there.)
  PASSED tests/accounts/test_route_crawler.py::AutomatedRouteCrawlTests::test_crawl_every_route_enforces_auth_and_permissions
  PASSED tests/security/test_csp.py::TemplateInlineJsScanTests::test_no_inline_script_bodies
  PASSED tests/security/test_csp.py::TemplateInlineJsScanTests::test_no_inline_event_handlers_or_javascript_urls
  PASSED tests/security/test_csp.py::TemplateInlineJsScanTests::test_no_external_cdns

& 'c:\brgy\.venv\Scripts\python.exe' manage.py check
  System check identified no issues (0 silenced).          (exit 0)

& 'c:\brgy\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
  No changes detected                                      (exit 0)

node --check static\js\*.js
  node failures=0 of 18
```

## Visual verification

The check was done with headless Chrome against a **throwaway DB**. Scripts are kept in `scratch/visual/`: `visual.py` and `overflow.py`.
- **Server.** `scratch/visual/visual.sqlite3` was migrated and seeded with an admin, a resident, a hotline, posts, an appointment and a blotter case. It was served by a threaded WSGI wrapper that injects a session cookie per persona, instead of `runserver`, so the browser is logged in without a password. All servers were stopped afterwards, and the scratch DB and Chrome profile were deleted.
- **True 375px.** `--headless=new` will not size a window below about 500px. So each page was loaded in a same-origin 375x812 `<iframe>`, which is a real 375px viewport: media queries and `innerWidth` are 375. The scratch wrapper strips `X-Frame-Options`/CSP for that frame only. In the probe output, `vw` is 375 for every page.
- **Coverage.** 57 pages:
  - every parameter-free GET page, as admin (46)
  - landing, login and signup, anonymous
  - the 8 resident key pages
- **Checks.** For each page, at 375px and 1366px:
  - `scrollWidth` against the viewport (horizontal page overflow)
  - elements spilling out of the centre column outside any scroll container
  - a screenshot, saved in `scratch/visual/shots375/` and `scratch/visual/shots1366/`, plus full-window desktop shots in `scratch/visual/shots/`
- **Result, final run.** 0 pages overflow horizontally at 375px or at 1366px. The only remaining spill is a 4px absolutely positioned `span` on the admin feed, which is still inside the viewport.
- **Pages viewed by eye.** Landing (anonymous and admin), signup, feed, emergency, announcements, appointments, statistics, system settings, blotter new, chat and officer permissions.
- **Cache gotcha.** Iteration 1's narrow shots were 500px layouts cropped to 375px. One early run in this iteration also used a cached `theme.css`. The final runs used a fresh Chrome profile.

## Not verified / caveats

- **WCAG.** Navy (10.4:1) and red (4.8:1) on white pass AA for normal text. Green is now kept to borders, dots and icons. Full WCAG compliance needs manual testing with assistive technologies and an expert accessibility review.
- **Device testing.** There was no real-device testing, and MySQL was not run.
- **Pages not covered.** The 375px pass covered only parameter-free pages. Detail and edit pages that need IDs (resident edit, case detail, chat room with an open conversation) were not rendered in a browser.
- **Minor items seen but not changed.**
  - Bottom-nav labels truncate ("APPOINTM…", "RESIDEN…") at 375px.
  - The left sidebar card renders below the content at about 250px wide on phones.
  - The Notifications bell is icon-only (`aria-label`) below 1280px.
