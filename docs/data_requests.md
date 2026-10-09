# Resident Data Privacy & Erasure Requests (DPA Compliance Guide)
> **DRAFT: PENDING DATA PROTECTION OFFICER (DPO) REVIEW**
> This compliance guide is a draft document subject to review and final sign-off by the Barangay Data Protection Officer.

## 1. Statutory Context
Under Republic Act No. 10173 (Philippine Data Privacy Act of 2012), data subjects (residents) have the statutory right to:
1. **Be Informed**: Clear disclosure of data collection, processing, and retention purposes.
2. **Access**: Right to request reasonable access to their personal data held by the Barangay.
3. **Rectification**: Right to dispute inaccuracy or error and have it corrected.
4. **Erasure or Blocking**: Right to suspend, withdraw, or order the blocking, removal, or destruction of their personal data from the filing system.

---

## 2. In-App Anonymization & Archive Action

### Location in System
1. Log in to the administrative panel at `/admin/` (or via Django Admin).
2. Navigate to **Accounts > Residents**.
3. Select the resident(s) submitting a formal deletion/erasure request.
4. From the **Action** dropdown menu, select:
   `Archive & Anonymize selected residents (Data Privacy Act Request)`
5. Click **Go**.

### What Happens During Anonymization:
- **First Name**: Set to `"Anonymized"`.
- **Last Name**: Set to `"Resident-<ID>"`.
- **Middle Name**: Cleared.
- **Contact Number**: Cleared.
- **Address**: Set to `"Redacted"`.
- **Private ID Photo**: Permanently deleted from server storage (`private_media/id_photos/`).
- **Archive Status**: Marked `is_archived = True` (excluded from active community directories, roster exports, and active lists).
- **Linked Portal Account** (if resident has signed up):
  - Account status marked `disabled` (`is_active = False`).
  - Username randomized to `deleted_<user_id>`.
  - Email randomized to `anonymized_<user_id>@deleted.local`.
  - Password set to unusable password (`set_unusable_password()`).
  - User ID proof deleted.
- **Audit Logging**: An immutable entry is created in `ActivityLog` recording:
  - Actor: Admin/Officer who approved the request
  - Action: `anonymize`
  - Action Type: `Resident Record`
  - Timestamp: Exact date and time
  - Details: Record ID, previous full name, and Data Privacy Act compliance reference.

---

## 3. Resident Request Verification Workflow

1. **Intake**: Resident requests deletion either in person at the Barangay Hall or by emailing the official Data Protection Officer.
2. **Identity Verification**: The Barangay Secretary or Administrator verifies the requester's identity.
3. **Pending Obligation Check**: Verify that the resident has no active pending cases, blotter disputes, or unliquidated barangay obligations.
4. **Execution**: The authorized admin executes the anonymization action in the Admin console.
5. **Confirmation**: A formal confirmation letter or email receipt is issued to the requester.
