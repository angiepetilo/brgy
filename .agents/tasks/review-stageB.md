# Security hardening and 09XXXXXXXXX phone validation for the barangay portal (Stage B)

Stage B closes the security gaps from the user's list. The client IP now ignores X-Forwarded-For unless `TRUSTED_PROXY_COUNT > 0`. Login lockouts come from the `user_login_failed` signal and use three counters. Seven endpoints and the chat WebSocket get a fixed-window rate limiter. The app refuses to start in production with unsafe settings. A strict CSP is enforced, after every inline script and `on*=` handler was moved into static JS and the CDNs were vendored. Phone numbers must match one 11-digit `09XXXXXXXXX` rule on models, forms and APIs, with reversible normalization migrations. Uploads are checked by magic bytes and stored privately under random names, temporary passwords are 12-character `secrets` output, and raw exception text no longer reaches users. Watch for: the ~130 rewritten inline handlers were never clicked in a real browser (likely risk of broken buttons, `CSP_REPORT_ONLY` is the fallback). The per-account lockout is keyed on the typed string, so username and email aliases get separate budgets (confirmed). Shared-IP limits could block residents behind barangay Wi-Fi or carrier NAT (likely). The old public copies of supporting documents stay in `media/appointments/` until an admin deletes them (confirmed). The live DB is still unmigrated.

**Verdict**: APPROVED

## High-level view

`apps/core/net.get_client_ip` is now the only code that reads `REMOTE_ADDR` or `X-Forwarded-For`, and a test enforces this. Login security, rate limiting and audit logging all use it, so a forged header no longer changes the IP these features see when `TRUSTED_PROXY_COUNT=0`. Setting the count above 0 also enables `SECURE_PROXY_SSL_HEADER`, so deployments behind nginx must set it, or the default `SECURE_SSL_REDIRECT` loops.

Login throttling is split into two parts. Failures are counted in `user_login_failed` receivers. `LoginThrottleMiddleware` only checks for an active lock and, if one exists, returns 429 with `Retry-After` and one generic message. `UserLoginForm` always calls `authenticate(request, ...)`, so unknown usernames also fire the signal and run the hasher. The counters are username+IP (5), username (10) and IP (20), with a 900 s window and sha256-hashed identifiers. A successful login clears only the username+IP counter. Because counting keys on the typed identifier rather than the resolved account, an attacker can alternate username and email and get two per-account budgets.

The `ratelimit` decorator is on password reset, signup, public booking, email validation, chat room POST, concern reply POST and both statistics exports. The chat WebSocket shares the HTTP `chat_send` bucket. Email validation and public booking return 401 for anonymous users before `validate_email_address` runs. Limits are per IP for anonymous users, so the barangay-hall Wi-Fi or carrier NAT can trip the signup (5/h) and login IP (20) limits for real residents.

Settings now refuse to start when `DEBUG=False` and the key is missing, the dev key, `django-insecure*`, too short or low-entropy, or when ALLOWED_HOSTS is empty or contains `*`. `DEBUG=True` dev keeps working. Secure cookies, SSL redirect and HSTS (one year, include subdomains) default on in production. Cookies are SameSite Lax, the dead XSS-filter setting is gone, and HSTS preload is a documented, silenced opt-in.

`SecurityHeadersMiddleware` sends the planned policy exactly. The Font Awesome cdnjs allowance was dropped, which is stricter than plan D9, because FA and FullCalendar are now vendored. A scan test blocks new inline scripts, handlers and `javascript:` URLs, and an independent grep found none. The coder also fixed an XSS in the `inbox.js` message rendering and the `websocket.js` toast link. The only verification of the large template/JS rewrite is `node --check` plus an id cross-check script.

`validate_ph_mobile` (`^09\d{9}\Z`, ASCII only, strings only) is applied to the three model fields, signup, the profile form, the resident edit and both registration services, and the public booking API. Inputs get `data-phone` and `pattern`. The normalization migrations rewrite values that can be fixed, leave invalid values in place and report their ids, and reverse as a no-op. On a copy of the backup they left row counts unchanged.

Supporting documents are now private `FileField`s with magic-byte, 5 MB and random-name checks. They are streamed by a new permission-checked view whose scope rule is stricter than the detail page's. The `serve_id_photo_view` 404 bug is fixed by the import plus `FileResponse`. Migration 0020 copies files to private storage but never deletes the public originals.

<details>
<summary>Issues (7)</summary>

1. **Lockout keyed on the typed identifier** (confirmed, non-blocking) — username and email aliases count separately, which doubles the per-account (10) and per-account+IP (5) budgets. Resolve the identifier to the account's username, when one exists, before counting in `on_login_failed` and in the middleware pre-check.
2. **Shared-IP limits on residents** (likely, non-blocking) — signup 5/h per IP and the login IP limit (20) can block legitimate residents registering from the barangay hall Wi-Fi or behind carrier NAT. Confirm these defaults with the user, or raise signup to a per-IP rate that fits walk-in registration days.
3. **Account lockout DoS** (confirmed, by design, non-blocking) — anyone can lock a known username, including admin accounts, for 15 minutes by sending 10 bad passwords from any IP. This is inherent in plan D6. Document it in `docs/deployment.md` and note that admins can clear the cache key or wait out the lock.
4. **Unverified handler rewrite** (likely risk, non-blocking) — about 130 `on*=` handlers and seven inline script blocks moved to delegated listeners with no browser click-through. Do a manual smoke test of landing booking, residents, appointments, inbox and feed before enforcing CSP, or roll out with `CSP_REPORT_ONLY=True` first, as documented.
5. **Public supporting-document originals remain** (confirmed, by design, non-blocking) — 0020 copies to `private_media` but leaves `media/appointments/`, which only Django middleware and the documented nginx rule protect. After migrating the live DB, delete the public copies once the private view serves them.
6. **Staff scope via `is_kapitan_user`** (confirmed, pre-existing, non-blocking) — pre-existing and reported by the coder: every `role=staff` user passes the kapitan branch on the appointment list and detail pages. The new private view is strict, so a staff member can see an appointment's detail page but get 403 on its attachment. Decide whether to fix the property in Stage C.
7. **Proxy count left at 0 behind nginx** (likely, deployment, non-blocking) — every client then shares the nginx IP, so 20 failed logins anywhere lock the login for everyone, and every rate-limit bucket keyed on IP is shared too. Make `TRUSTED_PROXY_COUNT=1` part of the nginx deployment checklist (it is already in `docs/deployment.md`) and verify it at go-live.

</details>

<details>
<summary>Details</summary>

## Client IP and proxy trust

Selection is right-to-left (`entries[-count]`), and a list shorter than the count falls back to `REMOTE_ADDR`. `tests/core/test_client_ip.py` and `test_login_bruteforce::test_spoofed_forwarded_for_does_not_bypass_lock` cover both the unit case and the end-to-end case. A deployment behind nginx that leaves the count at 0 records the proxy IP for every client, which turns the 20-per-IP login limit into a global limit (likely; documented in `docs/deployment.md`).

```
client ── nginx (appends REMOTE_ADDR) ── daphne
XFF: "<forged>, <real client>"    TRUSTED_PROXY_COUNT=1 → entries[-1] = real client
                                  TRUSTED_PROXY_COUNT=0 → REMOTE_ADDR (nginx), XFF ignored
```

## Signal-based login lockout

```
POST /accounts/login/
  LoginThrottleMiddleware ── lock_remaining(typed, ip) > 0 ? → 429 + Retry-After, generic text
  login_view → UserLoginForm(request).clean → authenticate(request, …) always
        ├─ fail → user_login_failed → record_failure(typed, ip): u_ip / u / ip counters
        └─ ok   → user_logged_in    → clear(u_ip) for typed, username, email
```

`/admin/login/` is not covered by the pre-check, but anonymous requests to `/admin/` are redirected by `ApprovalGateMiddleware` before they reach the admin form, so the admin login is not an unthrottled side door.

The identifier gap is confirmed. `on_login_failed` records under `request.POST['username']` after `normalize_identifier` (strip and lowercase), and the pre-check reads the same string. `juan` and `juan@barangay.test` therefore map to different `lf:u:` and `lf:u_ip:` keys, even though `UserLoginForm` resolves both to one account. `test_login_by_email_is_counted_under_the_typed_identifier` pins this behavior rather than testing against it. The cost is a doubled budget, not a bypass, so it does not block. Resolving the identifier with the form's existing `username__iexact | email__iexact` lookup, falling back to the typed string for unknown users, would make the per-account limit truly per account.

The per-username limit is also a lockout lever: 10 failures from anywhere lock the account for 15 minutes for its owner too. That follows from plan D6 and is common practice, but nothing in the docs tells an admin what to do when it happens.

## Rate limiter coverage and auth ordering

Named rates share one bucket per name, which is how the concern-reply POST and the WebSocket consumer (`hit('chat_send:user', 'u<pk>', …)`) share the `chat_send` budget with chat room POSTs. The no-external-call rule for anonymous users is tested twice: once through the client and once through a RequestFactory without middleware, so it holds even if `ApprovalGateMiddleware` changes.

The limiter is a fixed window, so a burst at a window boundary can reach twice the rate. Per-IP limits for anonymous users are where real-world NAT matters. Philippine mobile carriers use CGNAT heavily, and walk-in registration at the barangay hall shares one public IP, so signup at 5/h per IP is likely to block legitimate users on a busy day. The value is env-overridable (`RATE_LIMIT_SIGNUP`), so this is a defaults question for the user, not a code defect.

## CSP and the inline-JS removal

An independent grep of `templates/` for inline `<script>` bodies, `\son[a-z]+=`, `javascript:` and CDN hosts returned nothing. The scan test also checks itself against a known violation, so it cannot pass by matching nothing.

The risk is behavioral, not structural. Delegated `data-action` / `data-confirm` / `data-call` listeners replaced handlers across about 20 templates, and the verification note says plainly that no browser was available. A missed `data-*` attribute fails silently: the button does nothing and the browser shows no error. The CSP itself is not at fault. `CSP_REPORT_ONLY` would not reveal these failures either. It only helps with handlers that were missed and still inline.

## Phone validation

The validator also rejects non-strings, non-ASCII digits (which `\d` would otherwise accept) and a trailing newline. Model validators run only on `full_clean`, so the services carry the enforcement through `clean_ph_mobile`. Any value the normalization migration cannot fix stays in the row and will fail validation the next time that record is edited through a form (confirmed by the design, documented in `docs/deployment.md` 2.4). The copy of the backup had none.

## Private supporting documents and ID photos

`appointment_supporting_id_view` uses `get_viewable_appointment(strict_scope=True)`: owner, admin and role=kapitan pass, other staff need `check_staff_appointment_scope`, and other residents get 404. The detail page uses the non-strict rule, so out-of-scope staff can open the page and then get 403 on the attachment link (confirmed; it comes from the pre-existing `is_kapitan_user` quirk). The 0020 copy deliberately leaves the public originals, so until they are removed by hand they stay protected only by `ApprovalGateMiddleware`'s `/media/appointments/` deny under Django, and by the documented `location ^~ /media/appointments/ { deny all; }` under nginx.

## Evidence

The verification note, `scratch/run.log` (566 passed), `audit.log` (no known vulnerabilities), `check.log`, `mkcheck.log`, `deploy.log` and `migcheck.log` are all present. No source file under `apps/`, `config/`, `templates/`, `static/js/` or `tests/` was modified after the suite run, so the green run covers the reviewed code. MySQL portability is reasoned, not executed. The live DB still has accounts 0018–0019 and appointments 0016–0020 pending.

</details>

<details>
<summary>File map</summary>

- `apps/core/net.py` — new `get_client_ip`, XFF trusted only with `TRUSTED_PROXY_COUNT`
- `apps/accounts/login_security.py`, `apps.py`, `middleware.py`, `forms.py` — signal-based lockout, pre-check middleware, `authenticate(request)` always
- `apps/core/ratelimit.py`, `templates/429.html` — fixed-window decorator
- `apps/accounts/{views,urls}.py`, `apps/appointments/views.py`, `apps/chat/{views,consumers}.py`, `apps/statistics/views.py` — limiter applied, auth before the email API, generic errors, supporting-id view, id-photo `FileResponse`
- `config/settings.py`, `.env.example` — production guard, cookie/HSTS defaults, CSP, rate and lockout settings
- `apps/core/middleware.py` — `SecurityHeadersMiddleware`
- `templates/**`, `static/js/*.js`, `static/vendor/**` — inline JS removed, delegated listeners, vendored FA and FullCalendar, `phone_input.js`
- `apps/core/validators.py`, `migration_utils.py`, model and form files — PH mobile validator and normalization
- `apps/core/uploads.py`, `storage.py`, `apps/appointments/models.py` — upload validation, private storage
- `apps/accounts/services.py` — 12-character `secrets` temp passwords, phone/upload helpers
- `apps/core/http.py` — `public_error_message`, generic error text
- migrations: accounts 0018–0019, appointments 0017–0020
- `docs/{deployment,backup_restore,route_matrix,testing,...}.md` — env vars, nginx denies, cache table, CSP rollout
- tests: `tests/core/test_{client_ip,validators}.py`, `tests/security/test_{login_bruteforce,rate_limits,settings_hardening,csp,phone_validation,uploads,temp_password,error_exposure}.py`, `tests/residents/test_migration_phone_normalize.py`

Full diff: `git diff HEAD` in `c:\brgy` (Stage A and B are both uncommitted in the working tree).

</details>
