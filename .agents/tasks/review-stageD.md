# Site-wide Flat 2.0 redesign with vendored Lucide (iteration 2)

Stage D replaces Font Awesome and Google Fonts CDN links with vendored Lucide icons and a system font stack, adds a single design-token stylesheet (`theme.css`) with the restricted palette from `barangay_agent_prompt.md`, restyles about 60 templates to the civic hierarchy (emergency/hotline → services → pinned → feed), and guards the result with a new `tests/ui` package. The coder's verify note reports that all 6 findings from the first review were fixed: raw emoji removed from the appointment filter, the emoji scanner extended to cover U+2300–23FF and U+2B00–2BFF, green text replaced with dark gray, off-palette rgba tints replaced with navy-at-alpha and gray-100, the Lucide README corrected to point to `icons.js`, and a true 375px visual pass completed that found and fixed real layout bugs (overflow, grid collapse, chat stacking). The full test suite passes with 724 tests (up from 719), the route crawler and CSP scans stay green, and the visual check covered 57 pages at 375px and 1366px against a throwaway database.

**Verdict**: APPROVED

## High-level view

Font Awesome is gone from templates, CSS, JS and Python. No `fa-` class, no cdnjs link, no Google Fonts. Lucide `lucide-static@1.52.0` is vendored as a 124-symbol sprite with a README recording version, integrity and ISC license. The `{% icon %}` tag renders `aria-hidden` inline SVG through `format_html`, and the JS helper `BrgyUI.icon` reads the sprite path from `data-icon-sprite` on `<body>`. An unknown icon name fails loudly. The icon-label test walks 20 rendered pages and confirms every icon has visible text or aria-label. The README now correctly points to `static/js/icons.js`.

`theme.css` holds the restricted palette (canvas #F9FAFB, cards #FFFFFF, navy #1E3A8A/#172F70, red #DC2626, green #16A34A, grays #111827 through #F3F4F6), 1px #E5E7EB borders, 8-12px radii, a 16px base and a system font stack. It bans gradients and shadows, defines always-on `:focus-visible` rings, includes a skip link and a `prefers-reduced-motion` block that turns off transitions and Chart.js animation. The legacy `main.css` stays as the source of truth for the three-column layout. The temporary cdnjs CSP allowance is removed.

The feed and landing pages follow the civic hierarchy from the design doc: emergency alerts and hotline first, then service shortcuts, then pinned announcements as anchors (never in tabs), then the chronological feed. The emergency stack uses the visibility-aware queryset so anonymous visitors only see posts they are allowed to see. A no-growth query test guards against N+1.

The emoji scanner now covers U+2300–23FF (⏪ ⏩ ⌛ ⏰) and U+2B00–2BFF (⭐ ⬆ ⬛), with self-test samples. It finds no emoji in templates or first-party JS/CSS. The palette test now covers `rgba()` in templates (excluding emails) and first-party CSS/JS, allowing only palette RGB triples plus black. The green-text guard flags any inline-styled element with a text label, font size ≤15px, and `color: #16A34A`. All three tests pass with self-tests.

The 375px visual pass used headless Chrome with a throwaway DB served by a threaded WSGI wrapper that injects session cookies per persona. Each page was loaded in a same-origin 375x812 iframe, which is a true 375px viewport (media queries and `innerWidth` both report 375). The pass covered 57 pages (every parameter-free GET page as admin, plus landing/login/signup anonymous and 8 resident pages) and checked horizontal overflow, column spills and screenshots at both 375px and 1366px. It found and fixed six real layout bugs: page wrappers overflowing the centre column, two-column forms not collapsing on phones, a fixed five-column officer-permissions grid, landing card overflow, header actions clipping and emergency badge wrapping. The inbox now stacks the conversation list above the conversation on phones. The final run reports 0 pages overflow and all layout issues resolved. Full WCAG compliance still needs manual testing with assistive technologies and an expert review.

The CSP scan, route crawler and full test suite (724 tests) pass. `manage.py check` and `makemigrations --check` are clean. `node --check` passes on all 18 JS files. Base-template IDs used by JS are intact. No new inline `<script>`, no `on*=` handlers, no cdnjs. MySQL was not run.

## Not tested

The 375px pass covered only parameter-free pages. Detail and edit pages requiring IDs (resident edit, case detail, chat room with an open conversation) were not rendered. The chat inbox stacking refactor was verified by structure only, not interaction. Real-device testing on Android/iOS was not done. MySQL was not run, so the throwaway test used SQLite only.

<details>
<summary>File map</summary>

- **Icon system**: `apps/core/icons.py`, `templatetags/core_tags.py`, `management/commands/build_icon_sprite.py`: registry, aliases, `{% icon %}` tag, sprite builder
- **Vendored Lucide**: `static/vendor/lucide/{sprite.svg,README.md,LICENSE}`: 1.52.0 subset
- **JS icon helper**: `static/js/icons.js`: `BrgyUI.icon` and `iconElement`
- **Design tokens**: `static/css/theme.css`: palette, borders, radii, component classes, reduced-motion block
- **Palette pass**: `static/css/{main,statistics,blotter}.css`, `static/js/*.js`: FA removed, palette applied, chart colours use navy/red/gray
- **Base shell**: `templates/base.html`: CDNs removed, `theme.css` linked, top nav with Lucide icons and labels, skip link, bottom nav (Home added, Records hidden from residents)
- **Feed hierarchy**: `templates/communications/feed.html`, `templates/landing.html`, `apps/communications/{selectors,views}.py`: emergency/hotline → services → pinned → feed
- **Module restyling** (60 templates): FA → `{% icon %}`, palette pass, font-size pass, aria-labels, forms and CSRF intact
- **Records department icons**: `apps/records/views.py`: FA names replaced with Lucide
- **Dead file removed**: `templates/chat/chat_view.html`
- **Docs**: `compile_scss.py`, `docs/{admin_guide,testing}.md`: SCSS guard, Stage D notes
- **Tests**: `tests/ui/{test_no_fontawesome,test_no_emoji,test_icon_labels,test_base_assets,test_icons,test_key_pages}.py`, `tests/ui/{scan,pages}.py`: FA scan, emoji scan (widened ranges), icon-label walker, palette and rgba checker, green-text guard, icon registry cross-check, feed-order assertion
- **Test adjustments**: `tests/communications/test_feed_layout.py`, `tests/security/test_csp.py`, `tests/security/test_part_i.py`: FA icon assertions updated to Lucide, CSP scan adjusted

Full diff: `git diff HEAD` in `c:\brgy` (uncommitted). The working tree also holds uncommitted Stages A–C.

</details>
