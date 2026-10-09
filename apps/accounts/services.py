"""
Service functions for Accounts & Resident Registrations.
Centralizes state changes, temporary password generation, audit logging, and email dispatches.
"""

import string
import secrets
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError

from django.db.models import Q
from apps.accounts.models import User, Resident
from apps.core.uploads import validate_upload
from apps.core.validators import validate_ph_mobile
from apps.accounts.system_utils import parse_bool
from apps.chat.models import Notification
from apps.chat.services import create_notification
from apps.history.utils import log_activity, send_templated_email

logger = logging.getLogger(__name__)


# Temporary password alphabet: no look-alike characters (O 0 l I 1).
TEMP_PASSWORD_LENGTH = 12
_TEMP_PW_LOWER = 'abcdefghijkmnopqrstuvwxyz'
_TEMP_PW_UPPER = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
_TEMP_PW_DIGITS = '23456789'
# No '&', '<', '>', quotes: the plain-text email templates are rendered with
# Django's autoescape, which would turn '&' into '&amp;' in the email.
_TEMP_PW_SYMBOLS = '!@#$%^*-_=+'


def generate_temp_password(length=TEMP_PASSWORD_LENGTH):
    """
    Random temporary password (default 12 characters) from the secrets module.
    Always contains at least one lowercase letter, uppercase letter, digit and
    symbol; look-alike characters are excluded so it can be typed from an email.
    """
    length = max(length, TEMP_PASSWORD_LENGTH)
    classes = (_TEMP_PW_LOWER, _TEMP_PW_UPPER, _TEMP_PW_DIGITS, _TEMP_PW_SYMBOLS)
    alphabet = ''.join(classes)
    chars = [secrets.choice(group) for group in classes]
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def clean_ph_mobile(value, required=False, label='Mobile number'):
    """
    Validate a mobile number with the shared 09XXXXXXXXX rule.
    Returns the stripped value ('' when blank and not required); raises ValueError.
    """
    value = (value or '').strip()
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return ''
    try:
        validate_ph_mobile(value)
    except DjangoValidationError as exc:
        raise ValueError(exc.messages[0])
    return value


def clean_upload(file_obj):
    """Shared upload check (extension + magic bytes + size); raises ValueError."""
    try:
        validate_upload(file_obj)
    except DjangoValidationError as exc:
        raise ValueError(exc.messages[0])
    return file_obj


def calculate_age(birthdate):
    """
    Calculates age from birthdate on the server. Never stored in DB.
    Validates boundary and sanity of date.
    """
    if not birthdate:
        return 0
    today = timezone.localdate()
    if birthdate > today:
        raise ValueError("Birthdate cannot be in the future.")
    if birthdate.year < 1900 or birthdate.year > 9999 or len(str(abs(birthdate.year))) != 4:
        raise ValueError("Please enter a valid birthdate.")
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def dispatch_email_on_commit(template_name, to_email, context, ref_table='', ref_id=''):
    """
    Dispatches templated emails inside transaction.on_commit with try/except,
    ensuring mail delivery issues never block database transactions.
    """
    transaction.on_commit(
        lambda: send_templated_email(template_name, to_email, context, ref_table, ref_id)
    )


def clean_demographics(data):
    """
    Validate and normalise the Resident demographic inputs shared by self-registration,
    staff registration and the staff edit form. Returns model field values.
    gender may be blank (legacy records); civil_status defaults to single.
    Raises ValueError on anything outside the model choices.
    """
    gender = str(data.get('gender') or '').strip().lower()
    gender = {'m': Resident.GENDER_MALE, 'f': Resident.GENDER_FEMALE}.get(gender, gender)  # legacy one-letter input
    if gender and gender not in dict(Resident.GENDER_CHOICES):
        raise ValueError("Select a valid gender.")
    civil_status = str(data.get('civil_status') or Resident.CIVIL_SINGLE).strip().lower()
    if civil_status not in dict(Resident.CIVIL_STATUS_CHOICES):
        raise ValueError("Select a valid civil status.")
    return {
        'gender': gender,
        'civil_status': civil_status,
        'is_solo_parent': parse_bool(data, 'is_solo_parent', False),
        'is_pwd': parse_bool(data, 'is_pwd', False),
        'is_4ps': parse_bool(data, 'is_4ps', False),
    }


def register_resident_service(cleaned_data, id_photo_file=None):
    """
    Sign up creates User (pending) + Resident, saves the ID photo, and sends Email 2 (reg_received.txt).
    Enforces age >= 18 on server.
    """
    email = cleaned_data['email'].strip().lower()
    first_name = cleaned_data['first_name'].strip()
    middle_name = cleaned_data.get('middle_name', '').strip()
    last_name = cleaned_data['last_name'].strip()
    birthdate = cleaned_data['birthdate']
    contact_no = cleaned_data['contact_no'].strip()
    address = cleaned_data['address'].strip()
    purok = cleaned_data.get('purok')

    # Server-side under-18 and sanity checks
    age = calculate_age(birthdate)
    if age < 18:
        raise ValueError("This portal is for residents 18 and above.")

    demographics = clean_demographics(cleaned_data)
    clean_ph_mobile(contact_no, required=True)
    if id_photo_file:
        clean_upload(id_photo_file)

    # Check if a previously rejected user is signing up again (reuse record, reset to pending)
    user = User.objects.filter(email__iexact=email).first()
    if user and user.status == User.STATUS_REJECTED:
        user.first_name = first_name
        user.last_name = last_name
        user.status = User.STATUS_PENDING
        user.rejection_reason = ''
        user.reviewed_by = None
        user.reviewed_at = None
        user.phone_number = contact_no
        user.address = address
        user.purok = purok
        user.set_unusable_password()
        user.save()
    elif not user:
        base_username = email.split('@')[0].replace('.', '_').replace('-', '_')
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=User.ROLE_RESIDENT,
            status=User.STATUS_PENDING,
            must_change_password=False,
            phone_number=contact_no,
            address=address,
            purok=purok,
        )
        user.set_unusable_password()
        user.save()

    # Create or update Resident profile
    resident, _ = Resident.objects.update_or_create(
        user=user,
        defaults={
            'first_name': first_name,
            'middle_name': middle_name,
            'last_name': last_name,
            'birthdate': birthdate,
            'contact_no': contact_no,
            'address': address,
            'purok': purok,
            'consent_recorded': True,
            'consent_recorded_date': timezone.localdate(),
            **demographics,
        }
    )
    if id_photo_file:
        # Private storage only (served by accounts:serve_id_photo). The legacy
        # public User.id_proof copy is no longer written.
        resident.id_photo = id_photo_file
        resident.save(update_fields=['id_photo'])

    # Log registration in ActivityLog
    log_activity(
        actor=user,
        action='create',
        action_type='Resident Registration',
        target_id=str(resident.id),
        target_name=resident.get_full_name(),
        details=f"Resident self-registration submitted by {email}."
    )

    # Send Email 2 inside transaction.on_commit
    dispatch_email_on_commit(
        template_name='reg_received',
        to_email=email,
        context={
            'first_name': first_name,
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Barangay'),
        },
        ref_table='Resident',
        ref_id=str(resident.id),
    )

    # Notify admins of new pending registration
    admins = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_superuser=True),
        status=User.STATUS_ACTIVE
    ).distinct()
    for admin in admins:
        create_notification(
            recipient=admin,
            title="New Pending Registration",
            message=f"{first_name} {last_name} ({email}) registered and is awaiting verification.",
            url="/accounts/residents/?tab=pending",
            action_type="registration"
        )

    return user, resident


def approve_resident_service(user, admin_user, link_resident_id=None, request=None):
    """
    Approve: status = active, generate a 12-character temporary password (secrets; mixed case, digit, symbol),
    must_change_password = True, temp_password_expires_at = now + 7 days, send Email 3 (reg_approved.txt).
    Never logs the temporary password.
    Offers to link to existing resident record with same name and birthdate instead of duplicating.
    """
    temp_pw = generate_temp_password()
    user.set_password(temp_pw)  # stored hashed!
    user.status = User.STATUS_ACTIVE
    user.is_approved = True
    user.must_change_password = True
    user.temp_password_expires_at = timezone.now() + timezone.timedelta(days=7)
    user.reviewed_by = admin_user
    user.reviewed_at = timezone.now()
    user.rejection_reason = ''
    user.save()

    # Link to existing unlinked resident record ONLY IF explicitly confirmed by admin
    target_resident = None
    if link_resident_id:
        target_resident = Resident.objects.filter(id=link_resident_id, user__isnull=True).first()
        if not target_resident:
            raise ValueError(f"Resident record #{link_resident_id} not found or is already linked to another account.")
        if target_resident.age is not None and target_resident.age < 18:
            raise ValueError("Staff-registered minors cannot be linked to a self-signup portal account.")

        # Field merge rules:
        # User account data wins: user link, ID photo, contact_no, address, purok
        # Existing resident data kept: household, needs_attention, needs_categories, notes, consent
        if hasattr(user, 'resident_profile') and user.resident_profile and user.resident_profile.id != target_resident.id:
            old_stub = user.resident_profile
            if old_stub.id_photo and not target_resident.id_photo:
                target_resident.id_photo = old_stub.id_photo
            if old_stub.contact_no:
                target_resident.contact_no = old_stub.contact_no
            if old_stub.address:
                target_resident.address = old_stub.address
            if old_stub.purok:
                target_resident.purok = old_stub.purok
            # Demographics stay as the existing record has them; the applicant's
            # self-reported gender only fills a blank (legacy) value.
            if not target_resident.gender and old_stub.gender:
                target_resident.gender = old_stub.gender
            old_stub.delete()

        target_resident.user = user
        target_resident.save()
        log_activity(
            actor=admin_user,
            action='merge',
            action_type='Resident',
            target_id=str(target_resident.id),
            target_name=target_resident.get_full_name(),
            details=f"Admin confirmed merge: linked approved user {user.email} into resident #{target_resident.id}. Merged fields: user, contact_no, id_photo, address. Retained resident fields: household, needs_attention."
        )

    # History audit log (password is NEVER logged)
    log_activity(
        actor=admin_user,
        action='approve',
        action_type='User Account',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details=f"Approved user registration for {user.email}. Temporary password issued (expires in 7 days)."
    )

    # In-app notification
    create_notification(
        recipient=user,
        title="Account Approved!",
        message="Your Barangay portal account has been approved. Please set your permanent password to continue.",
        url="/home/",
        action_type="approval"
    )

    # Send Email 3: reg_approved.txt immediately (never stores temp_password)
    first_name = user.first_name
    if not first_name and hasattr(user, 'resident_profile'):
        first_name = user.resident_profile.first_name
    first_name = first_name or user.username

    email_sent, email_err = send_templated_email(
        template_name='reg_approved',
        to_email=user.email,
        context={
            'first_name': first_name,
            'email': user.email,
            'temp_password': temp_pw,
            'login_url': '/accounts/login/',
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Barangay'),
        },
        ref_table='User',
        ref_id=str(user.id),
    )

    msg = f"Account for {user.email} approved."
    if not email_sent:
        msg += f" (Email delivery failed: {email_err}. Please use 'Resend temporary password'.)"
    else:
        msg += " Login email dispatched."

    return {
        'status': 'ok',
        'message': msg,
        'email_sent': email_sent,
        'email_error': email_err if not email_sent else '',
        'linked_resident': target_resident,
    }


def resend_temporary_password_service(user, admin_user, request=None):
    """
    Admin action to issue a fresh 12-character temporary password,
    reset expiry to now + 7 days, force password change, and resend reg_approved.txt.
    Password is stored hashed and NEVER logged.
    """
    temp_pw = generate_temp_password()
    user.set_password(temp_pw)
    user.must_change_password = True
    user.temp_password_expires_at = timezone.now() + timezone.timedelta(days=7)
    user.save()

    # Log action (NEVER log the password)
    log_activity(
        actor=admin_user,
        action='update',
        action_type='User Account',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details=f"Admin reissued temporary password for {user.email}. New 7-day expiry set."
    )

    first_name = user.first_name
    if not first_name and hasattr(user, 'resident_profile'):
        first_name = user.resident_profile.first_name
    first_name = first_name or user.username

    email_sent, email_err = send_templated_email(
        template_name='reg_approved',
        to_email=user.email,
        context={
            'first_name': first_name,
            'email': user.email,
            'temp_password': temp_pw,
            'login_url': '/accounts/login/',
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Barangay'),
        },
        ref_table='User',
        ref_id=str(user.id),
    )

    msg = f"A new temporary password was sent to {user.email} (expires in 7 days)." if email_sent else f"A new temporary password was generated, but sending email failed: {email_err}."
    return {
        'status': 'ok',
        'email_sent': email_sent,
        'email_error': email_err if not email_sent else '',
        'message': msg,
    }


def reject_resident_service(user, admin_user, reason, request=None):
    """
    Reject: reason box is required. status = rejected, send Email 5 (reg_rejected.txt).
    The person may sign up again.
    """
    if not reason or not reason.strip():
        raise ValueError("A rejection reason is required.")

    clean_reason = reason.strip()
    user.status = User.STATUS_REJECTED
    user.is_approved = False
    user.rejection_reason = clean_reason
    user.reviewed_by = admin_user
    user.reviewed_at = timezone.now()
    user.save()

    # History audit log
    log_activity(
        actor=admin_user,
        action='reject',
        action_type='User Account',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details=f"Registration rejected for {user.email}. Reason: {clean_reason}"
    )

    # Send Email 5: reg_rejected.txt inside transaction.on_commit
    first_name = user.first_name
    if not first_name and hasattr(user, 'resident_profile'):
        first_name = user.resident_profile.first_name
    first_name = first_name or user.username

    dispatch_email_on_commit(
        template_name='reg_rejected',
        to_email=user.email,
        context={
            'first_name': first_name,
            'reason': clean_reason,
            'register_url': '/accounts/signup/',
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Barangay'),
        },
        ref_table='User',
        ref_id=str(user.id),
    )

    return {
        'status': 'ok',
        'message': f"Registration for {user.email} marked rejected and notice dispatched."
    }


def change_password_service(user, new_password):
    """
    Completes forced first-time password change. Sets permanent password and resets must_change_password.
    """
    user.set_password(new_password)
    user.must_change_password = False
    user.temp_password_expires_at = None
    user.save()

    log_activity(
        actor=user,
        action='update',
        action_type='User Account',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details="User successfully updated temporary password to permanent password."
    )
    return True


def create_staff_account_service(admin_user, email, first_name, last_name, role=User.ROLE_STAFF):
    """
    Admin-created staff accounts: use temporary password (expires in 7 days), forced password change,
    and sends Email 3 (reg_approved.txt).
    """
    email = email.strip().lower()
    temp_pw = generate_temp_password()

    base_username = email.split('@')[0].replace('.', '_').replace('-', '_')
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    user = User.objects.create(
        username=username,
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=role,
        status=User.STATUS_ACTIVE,
        is_staff=True if role in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_KAPITAN] else False,
        must_change_password=True,
        temp_password_expires_at=timezone.now() + timezone.timedelta(days=7),
        reviewed_by=admin_user,
        reviewed_at=timezone.now(),
    )
    user.set_password(temp_pw)
    user.save()

    log_activity(
        actor=admin_user,
        action='create',
        action_type='Staff Account',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details=f"Admin created {role} account for {email}."
    )

    dispatch_email_on_commit(
        template_name='reg_approved',
        to_email=user.email,
        context={
            'first_name': first_name.strip(),
            'email': user.email,
            'temp_password': temp_pw,
            'login_url': '/accounts/login/',
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Barangay'),
        },
        ref_table='User',
        ref_id=str(user.id),
    )

    return user


def disable_account_service(admin_user, target_user, reason=''):
    """
    Admin can disable an account at the end of a term. Keeps that person's history.
    Blocks disabling the last active administrator.
    """
    from django.db.models import Q
    if target_user.role == User.ROLE_ADMIN or target_user.is_superuser:
        active_admins = User.objects.filter(
            Q(role=User.ROLE_ADMIN) | Q(is_superuser=True),
            status=User.STATUS_ACTIVE
        ).exclude(id=target_user.id).count()
        if active_admins == 0:
            raise ValueError("Cannot disable the last active administrator account.")

    target_user.status = User.STATUS_DISABLED
    target_user.save()

    log_activity(
        actor=admin_user,
        action='disable',
        action_type='User Account',
        target_id=str(target_user.id),
        target_name=target_user.get_full_name() or target_user.username,
        details=f"Account disabled at end of term / administrative action. Reason: {reason or 'Term concluded'}"
    )
    return target_user


def update_permission_rule_service(actor, officer, module, action, allowed):
    """
    Updates or creates a PermissionRule and logs the change (actor, before, after, time).
    """
    from apps.accounts.models import PermissionRule
    rule, created = PermissionRule.objects.get_or_create(
        officer=officer,
        module=module,
        action=action,
        defaults={'allowed': allowed}
    )
    before_val = "none" if created else ("allowed" if rule.allowed else "denied")
    after_val = "allowed" if allowed else "denied"

    if created or rule.allowed != allowed:
        rule.allowed = allowed
        rule.save()
        log_activity(
            actor=actor,
            action='update' if not created else 'create',
            action_type='PermissionRule',
            target_id=str(rule.id),
            target_name=f"{officer.position} - {module}.{action}",
            details=f"Permission for {officer.position} on {module}.{action} changed from {before_val} to {after_val}."
        )
    return rule


def create_staff_assignment_service(actor, user, officer, scope_type, scope_value):
    """
    Creates a StaffAssignment and logs the change (actor, before, after, time).
    """
    from apps.accounts.models import StaffAssignment
    assignment = StaffAssignment.objects.create(
        user=user,
        officer=officer,
        scope_type=scope_type,
        scope_value=scope_value
    )
    log_activity(
        actor=actor,
        action='create',
        action_type='StaffAssignment',
        target_id=str(assignment.id),
        target_name=f"{user.username} -> {officer.position}",
        details=f"Assigned staff {user.get_full_name() or user.username} ({user.email}) to {officer.position} with scope {scope_type}={scope_value}."
    )
    return assignment


def delete_staff_assignment_service(actor, assignment_id):
    """
    Deletes a StaffAssignment and logs the change.
    """
    from apps.accounts.models import StaffAssignment
    assignment = StaffAssignment.objects.get(id=assignment_id)
    details = f"Removed assignment {assignment.user.username} as {assignment.officer.position} (scope: {assignment.scope_type}={assignment.scope_value})."
    target_name = f"{assignment.user.username} -> {assignment.officer.position}"
    assignment.delete()
    log_activity(
        actor=actor,
        action='delete',
        action_type='StaffAssignment',
        target_id=str(assignment_id),
        target_name=target_name,
        details=details
    )
    return True


def staff_register_resident_service(staff_user, data):
    """
    Staff-registered residents/households:
    - Have no User and may include minors. The 18+ rule applies only to account creation.
    - Minimal fields for minors / residents: first_name, last_name, birthdate, purok.
    - Can create or link Household.
    - Logged in ActivityLog.
    """
    from apps.accounts.models import Household, Purok, Resident
    from apps.accounts.permissions import has_perm
    from django.db.models import Q

    if not (staff_user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or staff_user.is_superuser or has_perm(staff_user, 'residents', 'create')):
        raise PermissionDenied("You do not have permission to register residents.")

    first_name = data.get('first_name', '').strip()
    middle_name = data.get('middle_name', '').strip()
    last_name = data.get('last_name', '').strip()
    birthdate = data.get('birthdate')
    contact_no = data.get('contact_no', '').strip()
    address = data.get('address', '').strip()
    purok_val = data.get('purok')

    if not first_name or not last_name or not birthdate:
        raise ValueError("First name, last name, and birthdate are required.")

    if isinstance(birthdate, str):
        from django.utils.dateparse import parse_date
        birthdate = parse_date(birthdate)
        if not birthdate:
            raise ValueError("Invalid birthdate format.")

    today = timezone.localdate()
    if birthdate > today:
        raise ValueError("Birthdate cannot be in the future.")

    demographics = clean_demographics(data)
    contact_no = clean_ph_mobile(contact_no, label='Contact number')

    purok = None
    if isinstance(purok_val, Purok):
        purok = purok_val
    elif purok_val:
        purok = Purok.objects.filter(Q(id=purok_val) if str(purok_val).isdigit() else Q(name__iexact=str(purok_val))).first()

    household = None
    household_id = data.get('household_id')
    if household_id:
        household = Household.objects.filter(id=household_id).first()

    with transaction.atomic():
        resident = Resident.objects.create(
            user=None,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            birthdate=birthdate,
            contact_no=contact_no,
            address=address,
            purok=purok,
            household=household,
            **demographics,
        )

        if data.get('create_household'):
            household_name = data.get('household_name') or f"Family of {last_name}"
            household = Household.objects.create(
                head=resident,
                household_name=household_name,
                address=address,
                purok=purok
            )
            resident.household = household
            resident.save(update_fields=['household'])

        log_activity(
            actor=staff_user,
            action='create',
            action_type='Resident',
            target_id=str(resident.id),
            target_name=resident.get_full_name(),
            details=f"Staff {staff_user.username} registered resident {resident.get_full_name()} (Age: {resident.age})"
        )

    return resident


def update_resident_demographics_service(resident, actor, data):
    """
    Staff edit of a Resident's demographics (gender, civil status, solo parent, PWD, 4Ps).
    - requires residents.edit permission.
    - Resident is the single source; nothing is written to User.
    - logs before/after values.
    """
    from apps.accounts.permissions import has_perm
    if not (actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser or has_perm(actor, 'residents', 'edit')):
        raise PermissionDenied("You do not have permission to edit residents.")

    values = clean_demographics(data)
    fields = ('gender', 'civil_status', 'is_solo_parent', 'is_pwd', 'is_4ps')
    # Selects keep the stored value when the form did not send them; checkboxes
    # follow HTML semantics (unchecked = not sent = False).
    for field in ('gender', 'civil_status'):
        if field not in data:
            values[field] = getattr(resident, field)
    before = {f: getattr(resident, f) for f in fields}

    with transaction.atomic():
        for field in fields:
            setattr(resident, field, values[field])
        resident.save(update_fields=[*fields, 'updated_at'])
        changes = ', '.join(f"{f}: {before[f]!r} -> {values[f]!r}" for f in fields if before[f] != values[f])
        log_activity(
            actor=actor,
            action='update',
            action_type='ResidentDemographics',
            target_id=str(resident.id),
            target_name=resident.get_full_name(),
            details=f"Demographics updated for {resident.get_full_name()} by {actor.username}. {changes or 'No changes.'}"
        )
    return resident


def update_resident_account_service(actor, user, data):
    """
    Staff edit of a resident account from the Residents page.

    - Validates demographics first; a ValueError means nothing was saved.
    - Updates the User account fields (name, email, phone, address, purok).
    - When the user has a Resident (RBI) profile, mirrors the contact fields onto
      it and saves the demographics there.
    - Returns (user, resident_or_None). None means the user has no RBI profile,
      so demographics were NOT saved; the caller must tell the operator.
    """
    from apps.accounts.models import Purok
    from apps.accounts.permissions import has_perm
    if not (actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser or has_perm(actor, 'residents', 'edit')):
        raise PermissionDenied("You do not have permission to edit residents.")

    clean_demographics(data)  # reject bad input before anything is saved

    def text(key):
        return str(data.get(key, '') or '').strip()

    first_name, last_name, email = text('first_name'), text('last_name'), text('email')
    phone_number, street_address, purok_name = text('phone_number'), text('street_address'), text('purok')
    phone_number = clean_ph_mobile(phone_number, label='Phone number')

    with transaction.atomic():
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        user.phone_number = phone_number
        user.street_address = street_address
        if purok_name:
            user.purok, _ = Purok.objects.get_or_create(name=purok_name)
        user.save()

        resident = Resident.objects.filter(user=user).first()
        if resident is not None:
            resident.first_name = user.first_name
            resident.last_name = user.last_name
            resident.contact_no = phone_number
            resident.address = street_address
            resident.purok = user.purok
            resident.save()
            update_resident_demographics_service(resident, actor, data)

        log_activity(
            actor=actor,
            action='update',
            action_type='ResidentAccount',
            target_id=str(user.id),
            target_name=user.get_full_name() or user.username,
            details=(
                f"Resident account {user.username} updated by {actor.username}."
                + ('' if resident is not None else ' No RBI profile, demographics not saved.')
            ),
        )
    return user, resident


def update_resident_needs_service(resident, actor, data):
    """
    Updates needs attention data:
    - requires residents.edit_needs permission.
    - never exposed without permission.
    - logs every change.
    """
    from apps.accounts.permissions import has_perm
    if not (actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser or has_perm(actor, 'residents', 'edit_needs')):
        raise PermissionDenied("You do not have permission to edit needs-attention information.")

    needs_attention = bool(data.get('needs_attention'))
    categories = data.get('needs_categories') or data.get('needs_category') or ''
    if isinstance(categories, list):
        categories = ', '.join(categories)
    notes = data.get('needs_notes', '').strip()
    consent = bool(data.get('consent_recorded'))
    no_consent_reason = data.get('no_consent_reason', '').strip()

    if needs_attention and not consent and not no_consent_reason:
        raise ValueError("Setting needs attention requires consent to be recorded or a valid justification reason for recording without consent.")

    consent_date = data.get('consent_recorded_date')
    if consent and not consent_date:
        consent_date = timezone.localdate()
    elif not consent:
        consent_date = None

    with transaction.atomic():
        resident.needs_attention = needs_attention
        resident.needs_category = categories.split(',')[0].strip() if categories else ''
        resident.needs_categories = categories
        resident.needs_notes = notes
        resident.consent_recorded = consent
        resident.consent_recorded_date = consent_date
        resident.no_consent_reason = no_consent_reason if not consent else ''
        resident.needs_recorded_by = actor
        resident.needs_recorded_at = timezone.now()
        resident.save(update_fields=[
            'needs_attention', 'needs_category', 'needs_categories', 'needs_notes',
            'consent_recorded', 'consent_recorded_date', 'no_consent_reason',
            'needs_recorded_by', 'needs_recorded_at', 'updated_at'
        ])

        log_activity(
            actor=actor,
            action='update',
            action_type='ResidentNeeds',
            target_id=str(resident.id),
            target_name=resident.get_full_name(),
            details=f"Needs-attention updated for {resident.get_full_name()} by {actor.username}: needs_attention={needs_attention}, categories={categories}"
        )
    return resident


def assign_resident_officer_service(resident, officer, actor):
    """
    Admin/authorized staff assigns an individual resident to an officer. Logged.
    """
    from apps.accounts.permissions import has_perm
    if not (actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser or has_perm(actor, 'residents', 'assign')):
        raise PermissionDenied("You do not have permission to assign residents to officers.")

    with transaction.atomic():
        resident.assigned_officer = officer
        resident.save(update_fields=['assigned_officer', 'updated_at'])

        log_activity(
            actor=actor,
            action='update',
            action_type='ResidentAssignment',
            target_id=str(resident.id),
            target_name=resident.get_full_name(),
            details=f"Assigned resident {resident.get_full_name()} to officer {officer.position if officer else 'None'} by {actor.username}"
        )
    return resident


def assign_purok_residents_officer_service(purok, officer, actor):
    """
    Admin/authorized staff assigns all residents in a purok to an officer. Logged.
    """
    from apps.accounts.models import Resident
    from apps.accounts.permissions import has_perm
    if not (actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser or has_perm(actor, 'residents', 'assign')):
        raise PermissionDenied("You do not have permission to assign residents to officers.")

    with transaction.atomic():
        count = Resident.objects.filter(purok=purok, is_archived=False).update(assigned_officer=officer)

        log_activity(
            actor=actor,
            action='update',
            action_type='PurokAssignment',
            target_id=str(purok.id),
            target_name=purok.name,
            details=f"Bulk-assigned {count} residents in {purok.name} to officer {officer.position if officer else 'None'} by {actor.username}"
        )
    return count


def get_dashboard_metrics(user):
    """
    Computes dashboard & Home Key Barangay Metrics:
    - Registered residents and portal accounts as separate numbers.
    - Needs-attention count.
    - Residents per purok leader (shows 'no leader assigned' when empty).
    - Pending registrations (sidebar badge).
    - Excludes archived, rejected, and disabled records.
    - Scoped counts for staff (service area or purok); admin/kapitan see barangay-wide.
    """
    from apps.accounts.models import Resident, User, Purok, StaffAssignment, Officer
    from django.db.models import Count, Q

    is_admin = bool(user and (user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or user.is_superuser))
    is_staff = bool(user and user.is_staff and not is_admin)

    from apps.accounts.selectors import counted_residents_q

    # Base queries use the shared population rule (not archived, and no account
    # or an active account), so these counters match Statistics and Records.
    residents_qs = Resident.objects.filter(counted_residents_q())
    portal_users_qs = User.objects.filter(role=User.ROLE_RESIDENT).exclude(status__in=[User.STATUS_REJECTED, User.STATUS_DISABLED])

    # Scoped filters for staff
    scoped_purok_ids = []
    if is_staff:
        assignments = user.staff_assignments.all()
        purok_scopes = [a.scope_value.strip().lower() for a in assignments.filter(scope_type=StaffAssignment.SCOPE_PUROK)]
        has_all_service = assignments.filter(scope_type=StaffAssignment.SCOPE_SERVICE_AREA, scope_value__in=['all', 'general', 'punong barangay']).exists()

        if not has_all_service and purok_scopes:
            purok_objs = Purok.objects.filter(name__iregex=r'(' + '|'.join(purok_scopes) + ')')
            scoped_purok_ids = list(purok_objs.values_list('id', flat=True))
            residents_qs = residents_qs.filter(purok_id__in=scoped_purok_ids)
            portal_users_qs = portal_users_qs.filter(purok_id__in=scoped_purok_ids)

    # 1. Registered residents count (inhabitant records in barangay registry)
    registered_residents_count = residents_qs.count()

    # 2. Portal accounts count (active verified accounts on web portal)
    portal_accounts_count = portal_users_qs.filter(status=User.STATUS_ACTIVE).count()

    # 3. Needs attention count (unarchived residents requiring attention)
    # Strictly hidden from users without residents.view_needs (returns None, no zero placeholder)
    from apps.accounts.permissions import has_perm
    can_view_needs = bool(
        user and (
            user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or
            user.is_superuser or
            has_perm(user, 'residents', 'view_needs')
        )
    )
    needs_attention_count = residents_qs.filter(needs_attention=True).count() if can_view_needs else None

    # 4. Pending registrations (awaiting review/approval)
    pending_registrations_count = portal_users_qs.filter(status=User.STATUS_PENDING).count()

    # Portal-eligible count (unarchived residents aged 18+; minors are excluded)
    today = timezone.now().date()
    eighteen_years_ago = today.replace(year=today.year - 18)
    portal_eligible_count = residents_qs.filter(birthdate__lte=eighteen_years_ago).count()

    # 5. Residents per purok leader (optimized with single query aggregation)
    from django.db.models import Count
    puroks = Purok.objects.all().order_by('name')
    if scoped_purok_ids:
        puroks = puroks.filter(id__in=scoped_purok_ids)

    puroks = list(puroks.annotate(
        res_count=Count('residents', filter=counted_residents_q('residents__'))
    ))

    # Pre-fetch all active purok assignments in one query
    assignments = {
        sa.scope_value.strip().lower(): (sa.user.get_full_name() or sa.user.username)
        for sa in StaffAssignment.objects.filter(
            scope_type=StaffAssignment.SCOPE_PUROK,
            user__status=User.STATUS_ACTIVE
        ).select_related('user')
    }

    # Pre-fetch purok leader officers in one query
    purok_officers = {}
    for o in Officer.objects.filter(
        position=Officer.POSITION_PUROK_LEADER,
        user__status=User.STATUS_ACTIVE,
        committee__isnull=False
    ).select_related('user'):
        if o.user and o.committee:
            purok_officers[o.committee.strip().lower()] = (o.user.get_full_name() or o.user.username)

    residents_per_purok_leader = []
    for p in puroks:
        p_name_lower = p.name.strip().lower()
        leader_name = assignments.get(p_name_lower) or purok_officers.get(p_name_lower) or "no leader assigned"
        residents_per_purok_leader.append({
            'purok': p,
            'purok_name': p.name,
            'leader_name': leader_name,
            'resident_count': p.res_count,
        })

    return {
        'registered_residents_count': registered_residents_count,
        'portal_accounts_count': portal_accounts_count,
        'needs_attention_count': needs_attention_count,
        'portal_eligible_count': portal_eligible_count,
        'pending_registrations_count': pending_registrations_count,
        'residents_per_purok_leader': residents_per_purok_leader,
    }


def anonymize_resident_service(resident, actor):
    """
    Anonymizes and archives a resident record upon request (Data Privacy Act right to erasure).
    - Anonymizes PII fields: first_name, last_name, middle_name, contact_no, address.
    - Removes private ID photo from storage.
    - Marks resident is_archived = True.
    - If linked to a User account, disables account and anonymizes username/email.
    - Logs the anonymization in ActivityLog.
    """
    with transaction.atomic():
        old_name = resident.get_full_name()
        res_id = resident.id

        resident.first_name = "Anonymized"
        resident.middle_name = ""
        resident.last_name = f"Resident-{res_id}"
        resident.contact_no = ""
        resident.address = "Redacted"
        resident.is_archived = True

        if resident.id_photo:
            try:
                resident.id_photo.delete(save=False)
            except Exception:
                pass
            resident.id_photo = None

        resident.save()

        user = resident.user
        if user:
            user.is_active = False
            user.status = User.STATUS_DISABLED
            user.email = f"anonymized_{user.id}@deleted.local"
            user.username = f"deleted_{user.id}"
            user.first_name = "Anonymized"
            user.last_name = f"Resident-{res_id}"
            user.phone_number = ""
            user.street_address = ""
            user.set_unusable_password()
            if user.id_proof:
                try:
                    user.id_proof.delete(save=False)
                except Exception:
                    pass
                user.id_proof = None
            user.save()

        log_activity(
            actor=actor,
            action='anonymize',
            action_type='Resident Record',
            target_id=str(res_id),
            target_name=f"Resident #{res_id}",
            details=f"Resident record #{res_id} ({old_name}) anonymized and archived upon request by {actor.username}."
        )
    return resident
