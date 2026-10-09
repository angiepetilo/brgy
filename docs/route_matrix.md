# Route Authorization Matrix

This document maps every application route to its access controls, required permissions, and expected response per role.

### Roles Defined:
- **Anonymous**: Unauthenticated public user.
- **Resident**: Authenticated resident with `role='resident'` and active status.
- **Staff (No Assignment)**: Staff user with no `StaffAssignment` (default-deny for scoped actions).
- **Scoped Staff**: Staff user assigned to a specific service area (e.g., Health, Documents).
- **Admin**: Superuser or `role='admin'` / `Kapitan` with full administrative privileges.

### JSON callers (API routes):
"302 (Login)" and "403 / Deny" below describe HTML requests. A request counts as a JSON
caller when its path contains `/api/`, its `Accept` header includes `application/json`, or it
sends `X-Requested-With: XMLHttpRequest` (`apps.core.http.wants_json`). JSON callers get:

- **401** `{"error": "...", "requires_login": true, "login_url": "/accounts/login/?next=..."}`
  instead of the login redirect: anonymous, inactive account (logged out) or idle-expired session.
- **403** `{"error": "..."}` instead of the HTML 403 page: missing permission in `require_perm`,
  or any `PermissionDenied` raised in a view (`apps.core.middleware.JsonExceptionMiddleware`).

So every `/appointments/api/*` and `/statistics/api/*` route answers 401 JSON to anonymous users.

### Rate limits and lockouts (HTTP 429 + `Retry-After`)
JSON callers get `{"error": "...", "retry_after": N}`; others get `429.html`. Limits are set in `RATE_LIMITS` (`RATE_LIMIT_<NAME>` env):
- `password_reset` 5/15m per IP (POST `/accounts/password-reset/`), `signup` 5/h per IP (POST `/accounts/signup/`)
- `public_booking` 10/h per user (`/appointments/api/public-book/`), `email_validation` 20/h per user (`/appointments/api/validate-email/`); both refuse anonymous callers (401) before the external email API is called
- `chat_send` 30/m per user (POST `/chat/<id>/`, POST concern replies, and WebSocket messages)
- `statistics_export` 20/h per user (`/statistics/export/excel/`, `/statistics/export/pdf/`)
- Login: 5 failures per username+IP, 10 per username, 20 per IP within 15 minutes lock login POSTs for 15 minutes (same generic message for every account).

`/media/appointments/` and `/media/id_proofs/` are denied (403) to everyone; `/media/id_photos/` to non-staff.

| Route | Name | Required Auth / Permission | Anon | Resident | Staff (No Assign) | Scoped Staff | Admin |
|---|---|---|---|---|---|---|---|
| `/` | `landing` | Public | 200 | 200 | 200 | 200 | 200 |
| `^media/(?P<path>.*)$` | - | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `^static/(?P<path>.*)$` | - | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/change-password/` | `change_password` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/dashboard/` | `dashboard` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/id-photo/<int:resident_id>/` | `serve_id_photo` | Owner or Staff/Admin | 302 (Login) | Owner Only (403 others) | 403 / Deny | 200 | 200 |
| `/accounts/login/` | `login` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/logout/` | `logout` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/officers/permissions/` | `officers_permissions` | officers.assign_permissions | 302 (Login) | 403 / Deny | 403 / Deny | 403 / Deny | 200 |
| `/accounts/password-reset/` | `password_reset` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/password-reset/complete/` | `password_reset_complete` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/password-reset/confirm/<uidb64>/<token>/` | `password_reset_confirm` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/password-reset/done/` | `password_reset_done` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/pending/` | `pending_approval` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/profile/` | `profile` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/profile/avatar/remove/` | `remove_avatar` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/accounts/residents/` | `residents_tabbed` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/residents/<int:resident_id>/needs/` | `update_resident_needs` | residents.edit_needs | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if assigned | 200 |
| `/accounts/residents/<int:user_id>/approve/` | `resident_approve_direct` | accounts.approve / accounts.reject | 302 (Login) | 403 / Deny | 403 / Deny | 403 / Deny | 200 |
| `/accounts/residents/<int:user_id>/delete/` | `resident_delete` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/residents/<int:user_id>/edit/` | `resident_edit` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/residents/<int:user_id>/reject/` | `resident_reject_direct` | accounts.approve / accounts.reject | 302 (Login) | 403 / Deny | 403 / Deny | 403 / Deny | 200 |
| `/accounts/residents/<int:user_id>/resend-temp-password/` | `resend_temp_password` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/residents/assign/` | `assign_resident_officer` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/residents/register/` | `staff_register_resident` | residents.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (Scoped) | 200 |
| `/accounts/signup/` | `signup` | Public | 200 | 200 | 200 | 200 | 200 |
| `/accounts/system/` | `system_dashboard` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/barangay-info/update/` | `system_barangay_info_update` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/categories/<int:category_id>/delete/` | `system_post_category_delete` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/categories/<int:category_id>/edit/` | `system_post_category_edit` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/categories/create/` | `system_post_category_create` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/concerns/<int:cat_id>/delete/` | `system_concern_category_delete` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/concerns/<int:cat_id>/edit/` | `system_concern_category_edit` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/concerns/create/` | `system_concern_category_create` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/documents/<int:doc_id>/delete/` | `system_document_type_delete` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/documents/<int:doc_id>/edit/` | `system_document_type_edit` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/documents/create/` | `system_document_type_create` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/emails/<str:template_name>/preview/` | `system_email_preview` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/health-services/<int:svc_id>/delete/` | `system_health_service_delete` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/health-services/<int:svc_id>/edit/` | `system_health_service_edit` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/health-services/create/` | `system_health_service_create` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/staff/<int:user_id>/disable/` | `system_staff_account_disable` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/accounts/system/staff/create/` | `system_staff_account_create` | system.view / Admin Only | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/admin/` | `index` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/(?P<url>.*)$` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/^(?P<app_label>auth|accounts|appointments|communications|chat|history)/$` | `app_list` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/` | `accounts_household_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/<path:object_id>/change/` | `accounts_household_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/<path:object_id>/delete/` | `accounts_household_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/<path:object_id>/history/` | `accounts_household_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/household/add/` | `accounts_household_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/` | `accounts_purok_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/<path:object_id>/change/` | `accounts_purok_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/<path:object_id>/delete/` | `accounts_purok_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/<path:object_id>/history/` | `accounts_purok_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/purok/add/` | `accounts_purok_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/` | `accounts_resident_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/<path:object_id>/change/` | `accounts_resident_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/<path:object_id>/delete/` | `accounts_resident_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/<path:object_id>/history/` | `accounts_resident_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/resident/add/` | `accounts_resident_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/` | `accounts_user_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/<id>/password/` | `auth_user_password_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/<path:object_id>/change/` | `accounts_user_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/<path:object_id>/delete/` | `accounts_user_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/<path:object_id>/history/` | `accounts_user_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/accounts/user/add/` | `accounts_user_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/` | `appointments_appointment_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/<path:object_id>/change/` | `appointments_appointment_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/<path:object_id>/delete/` | `appointments_appointment_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/<path:object_id>/history/` | `appointments_appointment_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/appointment/add/` | `appointments_appointment_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/` | `appointments_healthcareservice_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/<path:object_id>/change/` | `appointments_healthcareservice_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/<path:object_id>/delete/` | `appointments_healthcareservice_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/<path:object_id>/history/` | `appointments_healthcareservice_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/healthcareservice/add/` | `appointments_healthcareservice_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/` | `appointments_issueddocumentlog_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/<path:object_id>/change/` | `appointments_issueddocumentlog_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/<path:object_id>/delete/` | `appointments_issueddocumentlog_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/<path:object_id>/history/` | `appointments_issueddocumentlog_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/appointments/issueddocumentlog/add/` | `appointments_issueddocumentlog_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/` | `auth_group_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/<path:object_id>/change/` | `auth_group_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/<path:object_id>/delete/` | `auth_group_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/<path:object_id>/history/` | `auth_group_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/auth/group/add/` | `auth_group_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/autocomplete/` | `autocomplete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/` | `chat_message_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/<path:object_id>/change/` | `chat_message_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/<path:object_id>/delete/` | `chat_message_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/<path:object_id>/history/` | `chat_message_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/message/add/` | `chat_message_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/` | `chat_notification_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/<path:object_id>/change/` | `chat_notification_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/<path:object_id>/delete/` | `chat_notification_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/<path:object_id>/history/` | `chat_notification_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/chat/notification/add/` | `chat_notification_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/` | `communications_announcement_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/<path:object_id>/change/` | `communications_announcement_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/<path:object_id>/delete/` | `communications_announcement_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/<path:object_id>/history/` | `communications_announcement_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/announcement/add/` | `communications_announcement_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/` | `communications_postcategory_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/<path:object_id>/change/` | `communications_postcategory_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/<path:object_id>/delete/` | `communications_postcategory_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/<path:object_id>/history/` | `communications_postcategory_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/communications/postcategory/add/` | `communications_postcategory_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/` | `history_activitylog_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/<path:object_id>/change/` | `history_activitylog_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/<path:object_id>/delete/` | `history_activitylog_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/<path:object_id>/history/` | `history_activitylog_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/activitylog/add/` | `history_activitylog_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/` | `history_emaillog_changelist` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/<path:object_id>/` | - | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/<path:object_id>/change/` | `history_emaillog_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/<path:object_id>/delete/` | `history_emaillog_delete` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/<path:object_id>/history/` | `history_emaillog_history` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/history/emaillog/add/` | `history_emaillog_add` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/jsi18n/` | `jsi18n` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/login/` | `login` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/logout/` | `logout` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/password_change/` | `password_change` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/password_change/done/` | `password_change_done` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/admin/r/<path:content_type_id>/<path:object_id>/` | `view_on_site` | Django Admin Superuser | 302 (Login) | 302 (Admin Login) | 302 (Admin Login) | 302 (Admin Login) | 200 |
| `/announcements/` | `announcements_hub` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/appointments/` | `list` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/appointments/<int:pk>/` | `detail` | Appointment Owner or Scoped Staff / Admin | 302 (Login) | Owner Only (IDOR safe) | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/approve/` | `approve` | appointments.approve (Scope-checked) | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/complete/` | `complete` | appointments.approve (Scope-checked) | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/delete/` | `delete` | Appointment Owner or Scoped Staff / Admin | 302 (Login) | Owner Only (IDOR safe) | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/edit/` | `edit` | Appointment Owner or Scoped Staff / Admin | 302 (Login) | Owner Only (IDOR safe) | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/noshow/` | `noshow` | Appointment Owner or Scoped Staff / Admin | 302 (Login) | Owner Only (IDOR safe) | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/<int:pk>/supporting-id/` | `supporting_id` | Owner, Admin/Kapitan, or Scoped Staff; streams the private file (`FileResponse`, `nosniff`), view is audited | 302 (Login) | Owner Only (404 others) | 403 / Deny | 200 if in scope, else 403 | 200 |
| `/appointments/<int:pk>/reject/` | `reject` | appointments.approve (Scope-checked) | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if in scope | 200 |
| `/appointments/api/public-book/` | `api_public_book` | Public | 200 | 200 | 200 | 200 | 200 |
| `/appointments/api/services/` | `api_services` | Public | 200 | 200 | 200 | 200 | 200 |
| `/appointments/api/slots/` | `api_slots` | Public | 200 | 200 | 200 | 200 | 200 |
| `/appointments/api/validate-email/` | `api_validate_email` | Public | 200 | 200 | 200 | 200 | 200 |
| `/appointments/new/` | `create` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/appointments/schedule/` | `health_schedule` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/appointments/schedules/manage/` | `schedule_manage` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/appointments/schedules/manage/<int:pk>/delete/` | `schedule_delete` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/appointments/schedules/manage/<int:pk>/edit/` | `schedule_edit` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/appointments/services/` | `service_list` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/appointments/services/<int:pk>/delete/` | `service_delete` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/appointments/services/<int:pk>/edit/` | `service_update` | appointments.manage_schedule / manage_services | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if Health Staff | 200 |
| `/chat/` | `inbox` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/chat/<int:user_id>/` | `room` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/chat/concern/<int:concern_id>/` | `concern_detail` | Thread participant or Handler / Admin | 302 (Login) | Participant Only (IDOR safe) | Allowed if assigned | Allowed if assigned | 200 |
| `/chat/concern/<int:concern_id>/reassign/` | `reassign_concern` | chat.resolve / Assigned Handler / Admin | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if assigned | 200 |
| `/chat/concern/<int:concern_id>/status/` | `update_concern_status` | chat.resolve / Assigned Handler / Admin | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if assigned | 200 |
| `/chat/concern/new/` | `submit_concern` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/chat/messages/<int:message_id>/attachment/` | `serve_attachment` | Message sender / recipient or Thread Handler | 302 (Login) | Participant Only (IDOR safe) | 403 / Deny | Allowed if assigned | 200 |
| `/chat/notifications/` | `notifications_list` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/chat/notifications/<int:notif_id>/open/` | `open_notification` | Notification Recipient Only | 302 (Login) | Recipient Only (IDOR safe) | Recipient Only | Recipient Only | 200 |
| `/chat/notifications/<int:notif_id>/read/` | `mark_notification_read` | Notification Recipient Only | 302 (Login) | Recipient Only (IDOR safe) | Recipient Only | Recipient Only | 200 |
| `/chat/notifications/mark-all-read/` | `mark_all_read` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/chat/notifications/unread-count/` | `unread_notifications_count` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/` | `feed` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/` | `announcements_list` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/` | `announcement_detail` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/delete/` | `delete_announcement` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/edit/` | `edit_announcement` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/extend/` | `extend_announcement` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/mark-done/` | `mark_done_announcement` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/<int:pk>/reopen/` | `reopen_announcement` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/announcements/create/` | `create_announcement_alias` | communications.create / post_<category> | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if authorized cat | 200 |
| `/communications/announcements/new/` | `create_announcement` | communications.create / post_<category> | 302 (Login) | 403 / Deny | 403 / Deny | Allowed if authorized cat | 200 |
| `/communications/emergency/` | `emergency_list` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/manage/history/` | `manage_history` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/posts/<int:post_id>/comment/` | `comment_post` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/communications/posts/<int:post_id>/react/` | `react_post` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/dashboard/` | - | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/emergency/` | `emergency_hub` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/feed/` | `feed` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/history/` | `overview` | History / Audit Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/history/emails/<int:email_id>/resend-failed/` | `resend_failed_email` | History / Audit Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/history/emails/<int:email_id>/resend/` | `resend_email` | History / Audit Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 403 / Deny | 200 |
| `/history_overview/` | `history_overview` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/home/` | `home` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/landing/` | `landing_page` | Public | 200 | 200 | 200 | 200 | 200 |
| `/messages/` | `messages_hub` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/records/` | `hub` | Records Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 (Scoped) | 200 |
| `/records/documents/<int:pk>/print/` | `print_document` | Records Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 (Scoped) | 200 |
| `/records/health/<int:pk>/print/` | `print_health` | Records Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 (Scoped) | 200 |
| `/records_hub/` | `records_hub` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
| `/statistics/` | `overview` | Statistics Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 | 200 |
| `/statistics/export/excel/` | `export_excel` | Statistics Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 | 200 |
| `/statistics/export/pdf/` | `export_pdf` | Statistics Module (Staff/Admin) | 302 (Login) | 403 / Redirect | 403 / Deny | 200 | 200 |
| `/statistics/api/summary/` | `api_summary` | statistics.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/statistics/api/demographics/` | `api_demographics` | statistics.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/statistics/api/purok-density/` | `api_purok_density` | statistics.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/statistics/api/appointments/` | `api_appointments` | statistics.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/statistics/api/revenue/` | `api_revenue` | statistics.view | 302 (Login) | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/statistics/api/blotter/` | `api_blotter` | statistics.view | 401 JSON | 403 / Deny | 403 / Deny | 200 (if granted) | 200 |
| `/blotter/` | `blotter:case_list` | blotter.view | 302 (Login) | 403 | 403 | 200 (scoped) | 200 |
| `/blotter/new/` | `blotter:case_create` | blotter.create (POST rate limited) | 302 (Login) | 403 | 403 | 200 (if granted) | 200 |
| `/blotter/<int:pk>/` | `blotter:case_detail` | blotter.view + scope | 302 (Login) | 403 | 403 | 200 / 404 out of scope | 200 |
| `/blotter/<int:pk>/edit/` | `blotter:case_edit` | blotter.edit + scope, open cases | 302 (Login) | 403 | 403 | 200 / 404 | 200 |
| `/blotter/<int:pk>/transition/` | `blotter:case_transition` | POST; mediate / settle / escalate / edit per target | 302 (Login) | 403 | 403 | 302 / 403 / 404 | 302 |
| `/blotter/<int:pk>/hearings/add/` | `blotter:hearing_add` | POST; blotter.mediate | 302 (Login) | 403 | 403 | 302 / 404 | 302 |
| `/blotter/<int:pk>/delete/` | `blotter:case_delete` | POST; blotter.delete | 302 (Login) | 403 | 403 | 302 / 404 | 302 |
| `/blotter/<int:pk>/print/` | `blotter:case_print` | blotter.view + scope | 302 (Login) | 403 | 403 | 200 / 404 | 200 |
| `/blotter/api/cases/` | `blotter:api_list` | GET; blotter.view | 401 JSON | 403 JSON | 403 JSON | 200 (scoped) | 200 |
| `/blotter/api/cases/create/` | `blotter:api_create` | POST; blotter.create, rate limited | 401 JSON | 403 JSON | 403 JSON | 201 / 400 / 429 | 201 |
| `/blotter/api/cases/<int:pk>/` | `blotter:api_detail` | GET; blotter.view + scope | 401 JSON | 403 JSON | 403 JSON | 200 / 404 JSON | 200 |
| `/blotter/api/cases/<int:pk>/transition/` | `blotter:api_transition` | POST; permission per target | 401 JSON | 403 JSON | 403 JSON | 200 / 400 / 403 / 404 | 200 |
| `/stats_overview/` | `stats_overview` | Authenticated User | 302 (Login) | 200 | 200 | 200 | 200 |
### Statistics API notes
- All six `/statistics/api/*` routes are GET only (other methods return 405), need `statistics.view`, and send `Cache-Control: no-store`.
- Query filters: `date_from`, `date_to` (`YYYY-MM-DD`) and `purok` (id). A bad value returns `400 {"error": "..."}`.
- Date filters bound appointments, revenue and blotter cases only. Population, sector and purok density figures are a live snapshot.
- `/statistics/export/excel/` and `/statistics/export/pdf/` need `statistics.export`. The HTML view (`/statistics/`) needs `statistics.view`.
- Default grants: Punong Barangay (all) and Secretary (`view`, `export`). The blotter block is aggregate counts only (no case numbers, names or narratives); `blotter.*` rights do not open it.

### Blotter notes
- Residents never get blotter access. Purok-assigned staff see only their purok's cases unless they also hold a service-area `All` assignment; confidential cases need `blotter.view_confidential`. A case outside the caller's scope answers 404 (HTML and JSON), never 403, so case ids cannot be probed.
- API errors: `400 {"errors": {field: [...]}}` (party errors under `errors.parties`), 401/403 JSON for auth, 429 with `Retry-After` when `RATE_LIMITS['blotter_create']` (default `20/h` per user, shared by the HTML form and the API) is exceeded. POSTs need the CSRF token.

### System Settings tabs (`/accounts/system/?tab=<tab>&subtab=<subtab>`)
| `tab` | `subtab` | Content |
| --- | --- | --- |
| `barangay_info` (default) | - | Name, address, city, province, contact, office hours, venue, logo |
| `post_categories` | - | Announcement / discussion categories |
| `document_health` | `documents` (default), `health` | Document prices and requirements; health services |
| `user_management` | `staff` (default), `concerns` | Staff accounts and term ends; concern categories and routing |
| `email_templates` | - | Preview and edit the email catalog |

Unknown tabs fall back to `barangay_info`. Old names (`documents`, `health_services`, `staff_accounts`, `concern_categories`) are still accepted and mapped to the tab and subtab above. Every settings POST redirects back to its canonical tab and subtab.
