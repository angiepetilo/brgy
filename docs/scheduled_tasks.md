# Scheduled Tasks & Background Jobs Configuration

This document specifies how to schedule automated background maintenance commands for **BARANGAY.PH**:

1. `send_queued_emails`:
   - **Frequency:** Every minute (`* * * * *`).
   - **Purpose:** Processes queued outbox emails with exponential backoff (attempt 1: immediate, attempt 2: +1 min, attempt 3: +5 min; marks `failed` after 3 attempts). Secret emails (containing temporary passwords) are excluded from the outbox and are sent immediately upon transaction commit.

2. `send_appointment_reminders`:
   - **Frequency:** Daily at 08:00 AM Asia/Manila time (`0 8 * * *`).
   - **Purpose:** Dispatches appointment reminder emails for appointments scheduled for tomorrow in `Asia/Manila`. Sets `reminder_sent_at` timestamp on appointment records to ensure strict idempotency (runs only once per appointment). Skips non-approved appointments.

3. `expire_posts`:
   - **Frequency:** Daily at midnight Asia/Manila time (`0 0 * * *`).
   - **Purpose:** Idempotent command that flags past-due announcements as `expired`.

4. `cleanup_rejected_registrations`:
   - **Frequency:** Daily at 01:00 AM Asia/Manila time (`0 1 * * *`).
   - **Purpose:** Purges registration records and deletes ID photo files from disk after N retention days (default 90). Anonymizes audit logs (`Rejected Registration #{id}`) with zero personal names or details preserved. Allows applicant to register again with the same email.

5. `cleanup_read_notifications`:
   - **Frequency:** Daily at 02:00 AM Asia/Manila time (`0 2 * * *`).
   - **Purpose:** Deletes read notifications older than N retention days (default 90 days).

---

## 1. Linux / Unix (Crontab)

Open crontab for the application user:
```bash
crontab -e
```

Add the following cron entries:
```cron
# 1. Outbox Email Dispatcher - Runs every minute
* * * * * cd /path/to/brgy && /path/to/brgy/.venv/bin/python manage.py send_queued_emails >> /var/log/brgy_emails.log 2>&1

# 2. Appointment Reminders - Runs daily at 08:00 AM (Asia/Manila time)
0 8 * * * cd /path/to/brgy && /path/to/brgy/.venv/bin/python manage.py send_appointment_reminders >> /var/log/brgy_reminders.log 2>&1

# 3. Post Expiration - Runs daily at midnight (Asia/Manila time)
0 0 * * * cd /path/to/brgy && /path/to/brgy/.venv/bin/python manage.py expire_posts >> /var/log/brgy_expire_posts.log 2>&1

# 4. Rejected Registration Cleanup - Runs daily at 01:00 AM (Asia/Manila time)
0 1 * * * cd /path/to/brgy && /path/to/brgy/.venv/bin/python manage.py cleanup_rejected_registrations --days 90 >> /var/log/brgy_reg_cleanup.log 2>&1

# 5. Read Notifications Cleanup - Runs daily at 02:00 AM (Asia/Manila time)
0 2 * * * cd /path/to/brgy && /path/to/brgy/.venv/bin/python manage.py cleanup_read_notifications --days 90 >> /var/log/brgy_notif_cleanup.log 2>&1
```

---

## 2. Windows (PowerShell & Task Scheduler)

### Option A: Running Manually via PowerShell
```powershell
Set-Location -Path "C:\brgy"
& "C:\brgy\.venv\Scripts\python.exe" manage.py send_queued_emails
& "C:\brgy\.venv\Scripts\python.exe" manage.py send_appointment_reminders
& "C:\brgy\.venv\Scripts\python.exe" manage.py expire_posts
& "C:\brgy\.venv\Scripts\python.exe" manage.py cleanup_rejected_registrations --days 90
& "C:\brgy\.venv\Scripts\python.exe" manage.py cleanup_read_notifications --days 90
```

### Option B: Register Windows Scheduled Tasks
Run in an elevated PowerShell terminal:

```powershell
$AppDir = "C:\brgy"
$PythonExe = "C:\brgy\.venv\Scripts\python.exe"

# 1. Outbox Email Dispatcher (Every minute)
$Action1 = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py send_queued_emails" -WorkingDirectory $AppDir
$Trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "BarangayPH_SendQueuedEmails" -Action $Action1 -Trigger $Trigger1 -Description "Send queued outbox emails every minute" -User "SYSTEM"

# 2. Appointment Reminders (Daily at 08:00 AM)
$Action2 = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py send_appointment_reminders" -WorkingDirectory $AppDir
$Trigger2 = New-ScheduledTaskTrigger -Daily -At 8:00am
Register-ScheduledTask -TaskName "BarangayPH_AppointmentReminders" -Action $Action2 -Trigger $Trigger2 -Description "Send appointment reminders for tomorrow" -User "SYSTEM"

# 3. Post Expiration (Daily at midnight)
$Action3 = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py expire_posts" -WorkingDirectory $AppDir
$Trigger3 = New-ScheduledTaskTrigger -Daily -At 12:00am
Register-ScheduledTask -TaskName "BarangayPH_ExpirePosts" -Action $Action3 -Trigger $Trigger3 -Description "Daily expiration of past-due public announcements" -User "SYSTEM"

# 4. Rejected Registration Cleanup (Daily at 01:00 AM)
$Action4 = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py cleanup_rejected_registrations --days 90" -WorkingDirectory $AppDir
$Trigger4 = New-ScheduledTaskTrigger -Daily -At 1:00am
Register-ScheduledTask -TaskName "BarangayPH_CleanupRegistrations" -Action $Action4 -Trigger $Trigger4 -Description "Purge rejected registrations and ID photos older than 90 days" -User "SYSTEM"

# 5. Read Notifications Cleanup (Daily at 02:00 AM)
$Action5 = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py cleanup_read_notifications --days 90" -WorkingDirectory $AppDir
$Trigger5 = New-ScheduledTaskTrigger -Daily -At 2:00am
Register-ScheduledTask -TaskName "BarangayPH_CleanupNotifications" -Action $Action5 -Trigger $Trigger5 -Description "Purge read notifications older than 90 days" -User "SYSTEM"
```
