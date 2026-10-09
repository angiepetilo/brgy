# Data Retention & Lifecycle Policy
> **DRAFT: PENDING DATA PROTECTION OFFICER (DPO) REVIEW**
> This policy document is a draft version subject to formal review and ratification by the designated Barangay Data Protection Officer.

This policy specifies the retention periods, configurable system settings, and automated scheduled purge routines for the Barangay Information & Management System.

---

## 1. Summary of Retention Schedules

| Data Category | Retention Period | Configuration Setting | Scheduled Task |
|---|---|---|---|
| **Rejected Registrations** | 90 Days | `REJECTED_REGISTRATION_RETENTION_DAYS` (default: `90`) | `cleanup_rejected_registrations` (Weekly) |
| **Read Notifications** | 90 Days | `READ_NOTIFICATION_RETENTION_DAYS` (default: `90`) | `purge_read_notifications` (Weekly) |
| **Audit Logs (ActivityLog & EmailLog)** | 1 Year Minimum (365 Days) | `AUDIT_LOG_RETENTION_DAYS` (default: `365`) | Monitored & archived annually |
| **Active Resident Accounts** | Indefinite (Active residency) | N/A | N/A |
| **Uploaded ID Photos (Active)** | Lifecycle of active account | N/A | Secure private storage |
| **Uploaded ID Photos (Rejected)** | 90 Days | Linked to rejected registration purge | Automated file unlinking |

---

## 2. Configuration Settings (.env)

These settings can be overridden in the production `.env` configuration file:

```ini
# Days to retain rejected registrations before permanent purge
REJECTED_REGISTRATION_RETENTION_DAYS=90

# Days to retain in-app notifications marked as read
READ_NOTIFICATION_RETENTION_DAYS=90

# Minimum days to retain immutable audit trail before historical archive
AUDIT_LOG_RETENTION_DAYS=365
```

---

## 3. Automated Maintenance Procedures

### Rejected Registrations Purge (`cleanup_rejected_registrations`)
- Runs weekly via cron.
- Identifies all `User` records where `status = 'rejected'` and `reviewed_at` is older than `REJECTED_REGISTRATION_RETENTION_DAYS`.
- Deletes uploaded identification proof files (`id_proof`, `id_photo`) from disk.
- Removes the user record and associated resident application profile.
- Emits an activity log entry documenting the count of purged applications.

### Read Notifications Purge (`purge_read_notifications`)
- Runs weekly via cron.
- Selects `Notification` records where `is_read = True` and `created_at` exceeds `READ_NOTIFICATION_RETENTION_DAYS`.
- Permanently deletes records to keep database tables lightweight and fast.
- Unread notifications are **never** purged.

### Audit Log Retention
- Government auditing rules require tracking official actions for a minimum of 1 year.
- Historical `ActivityLog` and `EmailLog` records older than `AUDIT_LOG_RETENTION_DAYS` are dumped to compressed off-server cold storage during yearly audits rather than wiped blindly.
