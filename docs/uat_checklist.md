# User Acceptance Testing (UAT) Checklist

This checklist provides end-to-end, human-executable scenarios for Barangay officials, administrative staff, and residents prior to production sign-off.

---

### Scenario 1: Resident Self-Registration & Intake Notice
- [ ] 1. Open the landing page (`/`) and click **Sign Up**.
- [ ] 2. Fill out applicant details: Full Name, Birthdate (18+), Purok, Address, Phone Number, Email, and upload a valid ID photo.
- [ ] 3. Review the **Privacy Notice (Data Privacy Act of 2012)**.
- [ ] 4. Check the mandatory consent checkbox and click **Submit Registration for Verification**.
- [ ] 5. Confirm that the success modal displays: *"Registration Submitted! Please check your email for approval of account."*
- [ ] 6. Verify applicant receives Email 2 (`reg_received`): *"Application Received — Pending Barangay Verification"*.

---

### Scenario 2: Administrative Rejection with Reason
- [ ] 1. Log in as an Administrator (`/accounts/login/`).
- [ ] 2. Go to **Residents > Pending Applications**.
- [ ] 3. Click the View (Eye) action icon next to a test applicant.
- [ ] 4. Click **Decline / Reject Application**.
- [ ] 5. Select a preset rejection reason (e.g., *"Uploaded ID document is blurry or unreadable"*) or write a custom explanation.
- [ ] 6. Submit rejection.
- [ ] 7. Verify applicant receives Email 4 (`reg_rejected`) stating the specific rejection reason and inviting them to re-apply.
- [ ] 8. Verify applicant cannot log in and sees the specific rejection notice only after attempting login with their correct password (wrong credentials show generic error).

---

### Scenario 3: Admin Approval, Temporary Password, & Forced Password Change
- [ ] 1. In **Residents > Pending**, click View on an applicant with valid proof.
- [ ] 2. Click **Verify & Approve Resident**.
- [ ] 3. Verify applicant receives Email 3 (`reg_approved`) containing their 12-character temporary password (mixed case, digits and a symbol, e.g. `Tq7#mVw2pK!x`) and 7-day expiration notice.
- [ ] 4. Applicant enters their email and temporary password at `/accounts/login/`.
- [ ] 5. System immediately forces redirect to `/accounts/change-password/`. Every navigation attempt redirects back until changed.
- [ ] 6. Enter a password that is too short (< 8 chars), numeric only, or identical to the temporary password: verify validation error.
- [ ] 7. Set a valid permanent password (> 8 chars): verify successful login and redirect to `/home/`.
- [ ] 8. Verify any previous sessions are invalidated.

---

### Scenario 4: Resident Books a Document Appointment
- [ ] 1. Log in as an approved resident.
- [ ] 2. Navigate to **Appointments > Request Document**.
- [ ] 3. Select a document (e.g., *Barangay Clearance*). View fees, pickup venue, and checklist requirements.
- [ ] 4. Pick a preferred schedule and submit.
- [ ] 5. Verify the booking appears in resident's queue with status `Pending`.

---

### Scenario 5: Resident Books a Health Appointment (Free Services Only)
- [ ] 1. Navigate to **Appointments > Health Center Schedule**.
- [ ] 2. Verify that **only active, free scheduled services** (e.g. Immunization, Prenatal Consultation) are displayed.
- [ ] 3. Select an available date and time slot (Morning / Afternoon) and confirm booking.
- [ ] 4. Verify slot capacity decreases by 1.

---

### Scenario 6: Staff Review, Approval, & Confirmation Email
- [ ] 1. Log in as Barangay Health Worker (BHW) or Document Officer.
- [ ] 2. Open **Appointments Queue**.
- [ ] 3. Click **Approve** on the resident's appointment request.
- [ ] 4. Verify resident receives Email 5 (`appt_approved`) with date, time slot, venue, and required documents to bring.

---

### Scenario 7: Staff Rejection with Reason
- [ ] 1. Staff selects an invalid appointment request and clicks **Reject**.
- [ ] 2. Provide a clear reason (e.g. *"Doctor on emergency duty"* or *"Incomplete residency proof"*).
- [ ] 3. Verify resident receives Email 7 (`appt_rejected`) detailing the cancellation reason.

---

### Scenario 8: Automated Day-Before Appointment Reminder
- [ ] 1. Verify scheduler runs `send_appointment_reminders` daily at 3:00 PM.
- [ ] 2. Residents with approved appointments scheduled for tomorrow receive Email 6 (`appt_reminder`) with appointment summary and venue directions.

---

### Scenario 9: Health Announcement & Mark as Done
- [ ] 1. Health staff creates an announcement in category `Health` (e.g., *"Free Polio Vaccination This Saturday"*).
- [ ] 2. Verify announcement appears with Health badge in community feed.
- [ ] 3. After the event concludes, staff clicks **Mark as Done**.
- [ ] 4. Post moves to Completed state with green checkmark and is archived from urgent notices.

---

### Scenario 10: Emergency Alert Broadcast
- [ ] 1. Authorized officer posts an announcement in category `Emergency Alert`.
- [ ] 2. Verify top banner emergency alert activates across all resident screens.
- [ ] 3. Emergency post cannot be expired by standard daily expiration.

---

### Scenario 11: Resident Starts a Concern & Tracks Status Lifecycle
- [ ] 1. Resident navigates to **Concerns > Submit New Concern**.
- [ ] 2. Selects category (e.g. *Waste Management & Sanitation*), describes problem, attaches photo.
- [ ] 3. Initial ticket status displays as `Submitted`.
- [ ] 4. When assigned staff opens the ticket, status automatically updates to `Seen`.
- [ ] 5. Staff replies and updates status to `In Progress`.
- [ ] 6. Resident sees live status badge update and replies to staff in the message thread.
- [ ] 7. Staff marks ticket `Resolved`.

---

### Scenario 12: Direct Messaging an Officer
- [ ] 1. Resident navigates to **Officials Directory** or **Messages**.
- [ ] 2. Clicks **Message** on an assigned Purok Leader or Barangay Kagawad.
- [ ] 3. Sends inquiry. Officer receives notification and replies in direct chat.

---

### Scenario 13: Admin Creates New Post Category & Grants Permissions
- [ ] 1. Log in as Admin. Navigate to **System Settings > Categories**.
- [ ] 2. Add new category: *"Barangay Livelihood Program"*.
- [ ] 3. Navigate to **Officer Permissions**.
- [ ] 4. Locate *Kagawad - Livelihood* or *Secretary* and enable permission `communications.post_livelihood`.
- [ ] 5. Log in as that officer: verify they can post under the new category.

---

### Scenario 14: Admin Disables a Staff Account & Concern Auto-Reassignment
- [ ] 1. In **System Settings > Staff Accounts**, select a staff member and click **Disable Account**.
- [ ] 2. Any active open concerns assigned to that staff member are automatically reassigned to the department supervisor or admin queue.
- [ ] 3. Disabled staff user cannot log in and sees disabled account notification.
