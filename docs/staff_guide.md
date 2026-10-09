# Barangay e-Portal — Staff Quick Reference Guide

A practical, one-page guide for Barangay Secretaries, Health Workers (BHWs), Desk Officers, and Purok Leaders.

---

### 1. Logging In & First-Time Access
1. Check your email for your 12-character temporary password (mixed case, digits and a symbol, e.g. `Tq7#mVw2pK!x`).
2. Log in at `/accounts/login/`.
3. You will immediately be prompted to create your **permanent password** (minimum 8 characters; must differ from your temporary one).
4. Once completed, you will enter your personalized Staff Dashboard.

---

### 2. Processing Appointments (`/appointments/`)
- **Queue Overview**: Filter by Date (*Today, Tomorrow, Past Due*) or Service (*Documents / Health Center*).
- **Evaluating a Request**:
  - Open appointment detail to inspect applicant name, purpose, and preferred schedule.
  - **Approve**: Confirms slot and triggers automated confirmation email to resident.
  - **Reject**: When rejecting, always choose or enter a respectful, clear reason so the resident understands.
  - **Mark Completed**: Click after the clearance is released or health checkup is finished.
  - **Mark No-Show**: If resident did not arrive during their scheduled time window.

---

### 3. Managing Resident Needs Attention (`/accounts/residents/`)
- Staff can record vulnerable resident sectors (Senior Citizens, PWDs, Solo Parents, Low-Income Families):
  1. Open the resident's profile card in the Directory.
  2. Toggle **Needs Attention** checkbox.
  3. Select applicable vulnerability categories and enter operational notes.
  4. **Data Privacy Consent Confirmation**:
     You must confirm: *"The resident (or guardian) has been told why this information is recorded and who can see it, and agrees to it."* If consent was impossible (e.g. emergency hospital transport), enter the justification in the reason field.
  5. Click **Save Needs Information**.

---

### 4. Handling Resident Concerns & Tickets (`/chat/`)
- Resident concerns appear in your **Concerns Inbox**:
  - **Status: Submitted**: New ticket awaiting staff review.
  - **Status: Seen**: Automatically marked once you open the ticket.
  - **Status: In Progress**: You have responded or coordinated with the field team.
  - **Status: Resolved**: Issue resolved (e.g. garbage collected, streetlight repaired).
- **Direct Messages**: Residents in your assigned Purok can message you directly for quick questions.

---

### 5. Publishing Announcements (`/communications/announcements/create/`)
- Choose the authorized category for your department (*Health, Public Advisory, Community Event*).
- Enter title, formatted body text, and optional banner image.
- Set publication date and optional expiration date.
- For time-limited events (e.g., medical mission), click **Mark as Done** after completion to archive the notice with a completed badge.

---

### 5a. Blotter: filing and mediating cases (`/blotter/`)
- **File a case** (needs `blotter.create`): click **File a case**, fill in the incident (type, date, optional time, location, purok, narrative) and add the parties. At least one complainant and one respondent are required; use **Add party** for witnesses or more parties. Mobile numbers are optional but must be 11 digits starting with 09. The case number (`BLT-YYYY-NNNN`) is assigned on save.
- **Mediate**: on the case page, **Under mediation** (needs `blotter.mediate`) opens mediation; record each hearing with its date, outcome notes and who attended.
- **Close**: **Settled** (`settle`) or **Escalated** (`escalate`) from mediation; **Dismissed** or **Withdrawn** (`edit`) where allowed. Closed cases cannot be edited or reopened. Notes typed when closing become the resolution notes.
- Only the buttons your role allows are shown. Purok-assigned staff see only their purok's cases; confidential cases need `blotter.view_confidential`.
- **Print summary** gives a one-page case record for signing or Save as PDF.

---

### 6. Security & Duty Etiquette
- **Never share passwords**: Temporary passwords expire in 7 days; accounts lock for 15 minutes after 5 failed login attempts.
- **Session Timeout**: Portal sessions automatically expire after 30 minutes of idle time. Always log out when stepping away from the desk.
- **Resident Privacy**: ID photos and sensitive demographic data are confidential under Republic Act No. 10173.
