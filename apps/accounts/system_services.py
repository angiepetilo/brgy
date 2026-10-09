"""
System Administration Services for BARANGAY.PH (PART G).
Provides validation, state mutations, and before/after audit logging for:
- Barangay Information
- Post Categories (dynamic permissions, settings)
- Document Types & Requirements (ordering, pricing, reference guards)
- Health Care Services (is_free, reference guards)
- Concern Categories (routing targets)
- Staff Account Management (temporary password email, term ends, disabling)
- Email Templates (catalog, preview, validated and audited editing)

Conventions
-----------
* Services raise ``ValueError`` with a message that is safe to show to the user.
  Anything else is treated as an internal error by the views (logged, generic message).
* Checkbox flags go through ``system_utils.parse_bool``: CREATE passes the documented
  default, UPDATE passes the object's current value (see that module for the full rule).
* Every write calls ``log_activity``.
"""

import os
import re
import tempfile
import datetime
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from django.template import Context, Engine, TemplateSyntaxError
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User, BarangayInfo, StaffAssignment, Officer
from apps.accounts.services import generate_temp_password
from apps.accounts.system_utils import parse_bool, safe_int
from apps.appointments.models import DocumentType, Requirement, HealthCareService, Appointment
from apps.chat.models import ConcernCategory
from apps.communications.models import PostCategory
from apps.history.utils import log_activity, send_templated_email


def _get_or_missing(model, pk, label):
    """Fetch by primary key or raise a clean ValueError (never a bare DoesNotExist)."""
    try:
        return model.objects.get(pk=pk)
    except (model.DoesNotExist, TypeError, ValueError):
        raise ValueError(f"That {label} no longer exists. Refresh the page and try again.")


def _clean_name(data, label, max_length):
    name = str(data.get('name') or '').strip()
    if not name:
        raise ValueError(f"{label} name is required.")
    if len(name) > max_length:
        raise ValueError(f"{label} name must be {max_length} characters or fewer.")
    return name


# 1. BARANGAY INFORMATION
CONTACT_NO_RE = re.compile(r'^[0-9 ()\-]{7,15}$')
LOGO_MAX_BYTES = 2 * 1024 * 1024
LOGO_FORMATS = {'PNG', 'JPEG', 'GIF', 'WEBP'}
BARANGAY_INFO_FIELDS = ('name', 'address', 'city', 'province', 'contact_no', 'office_hours', 'venue')
BARANGAY_INFO_OPTIONAL = ('address', 'city', 'province', 'contact_no', 'office_hours', 'venue')


def _validate_logo(logo_file):
    """Image only (PNG/JPEG/GIF/WEBP), max 2 MB, verified with Pillow."""
    from PIL import Image

    if getattr(logo_file, 'size', 0) > LOGO_MAX_BYTES:
        raise ValueError("The logo must be 2 MB or smaller.")
    try:
        image = Image.open(logo_file)
        image_format = image.format
        image.verify()
    except Exception:
        raise ValueError("The logo must be a valid image file (PNG, JPEG, GIF or WEBP).")
    finally:
        try:
            logo_file.seek(0)
        except Exception:
            pass
    if image_format not in LOGO_FORMATS:
        raise ValueError("The logo must be a PNG, JPEG, GIF or WEBP image.")


def _barangay_snapshot(info):
    snap = {field: getattr(info, field) for field in BARANGAY_INFO_FIELDS}
    snap['has_logo'] = bool(info.logo)
    return snap


def update_barangay_info_service(actor, data, logo_file=None):
    """
    Updates official Barangay Information.
    - name is required.
    - Optional fields are assigned from the submitted value, so an empty string CLEARS them.
      A key that is absent from ``data`` (partial programmatic payload) is left unchanged.
    - contact_no is empty, or a mobile/landline number (digits, spaces, dashes, parentheses; 7-15 chars).
    - The logo is replaced only when a file is uploaded, or removed when ``clear_logo`` is truthy.
    Logs before and after values in ActivityLog.
    """
    info = BarangayInfo.get_solo()
    old_vals = _barangay_snapshot(info)

    name = str(data.get('name') or '').strip()
    if not name:
        raise ValueError("Barangay name is required.")
    if len(name) > 150:
        raise ValueError("Barangay name must be 150 characters or fewer.")

    values = {}
    for field in BARANGAY_INFO_OPTIONAL:
        if field in data:
            values[field] = str(data.get(field) or '').strip()

    for field, limit in (('city', 100), ('province', 100), ('office_hours', 120), ('venue', 150)):
        if len(values.get(field, '')) > limit:
            raise ValueError(f"{field.replace('_', ' ').capitalize()} must be {limit} characters or fewer.")

    contact_no = values.get('contact_no', '')
    if contact_no:
        digits = sum(ch.isdigit() for ch in contact_no)
        if not CONTACT_NO_RE.match(contact_no) or digits < 7:
            raise ValueError(
                "Contact number must be a mobile or landline number "
                "(digits, spaces, dashes and parentheses only, 7 to 15 characters)."
            )

    if logo_file:
        _validate_logo(logo_file)

    with transaction.atomic():
        info.name = name
        for field, value in values.items():
            setattr(info, field, value)
        if logo_file:
            info.logo = logo_file
        elif parse_bool(data, 'clear_logo', False):
            info.logo = None
        info.save()

        new_vals = _barangay_snapshot(info)
        log_activity(
            actor=actor,
            action='update',
            action_type='SystemConfig',
            target_id=str(info.id),
            target_name="Barangay Information",
            details=f"Updated BarangayInfo. Before: {old_vals} -> After: {new_vals}"
        )
    return info


# 2. POST CATEGORIES
def _post_category_snapshot(cat):
    return {
        'name': cat.name,
        'expires': cat.expires,
        'default_end': cat.default_end,
        'notify_on_post': cat.notify_on_post,
        'is_active': cat.is_active,
        'order': cat.order,
    }


def create_or_update_post_category_service(actor, data, category_id=None):
    """
    Creates or updates a PostCategory:
    - Names unique case-insensitive.
    - System categories cannot have is_system removed (is_system is only read on create).
    - Logs before and after values.
    """
    cat = _get_or_missing(PostCategory, category_id, 'post category') if category_id else None
    name = _clean_name(data, 'Category', 50)

    existing_q = PostCategory.objects.filter(name__iexact=name)
    if cat:
        existing_q = existing_q.exclude(id=cat.id)
    if existing_q.exists():
        raise ValueError(f"A post category with name '{name}' already exists.")
    slug_q = PostCategory.objects.filter(slug=slugify(name).replace('-', '_'))
    if cat:
        slug_q = slug_q.exclude(id=cat.id)
    if slug_q.exists():
        raise ValueError(f"A post category with a name similar to '{name}' already exists.")

    default_end = data.get('default_end', 'none')
    if default_end not in ['end_of_month', 'none']:
        default_end = 'none'
    order = safe_int(data.get('order', 0), 0)

    if cat:
        old_vals = _post_category_snapshot(cat)
        cat.name = name
        cat.expires = parse_bool(data, 'expires', cat.expires)
        cat.default_end = default_end
        cat.notify_on_post = parse_bool(data, 'notify_on_post', cat.notify_on_post)
        cat.is_active = parse_bool(data, 'is_active', cat.is_active)
        cat.order = order
        cat.save()

        log_activity(
            actor=actor,
            action='update',
            action_type='PostCategory',
            target_id=str(cat.id),
            target_name=cat.name,
            details=f"Updated PostCategory '{cat.name}'. Before: {old_vals} -> After: {_post_category_snapshot(cat)}"
        )
    else:
        cat = PostCategory.objects.create(
            name=name,
            expires=parse_bool(data, 'expires', True),
            default_end=default_end,
            notify_on_post=parse_bool(data, 'notify_on_post', False),
            is_system=parse_bool(data, 'is_system', False),
            is_active=parse_bool(data, 'is_active', True),
            order=order
        )
        log_activity(
            actor=actor,
            action='create',
            action_type='PostCategory',
            target_id=str(cat.id),
            target_name=cat.name,
            details=f"Created PostCategory '{cat.name}' (expires={cat.expires}, default_end={cat.default_end}, notify={cat.notify_on_post}, system={cat.is_system}, active={cat.is_active})"
        )
    return cat


def delete_post_category_service(actor, category_id):
    """
    Deletes a PostCategory:
    - System categories (Health and Emergency) CANNOT be deleted.
    - Logs deletion.
    """
    cat = _get_or_missing(PostCategory, category_id, 'post category')
    if cat.is_system or cat.name.lower() in ['health', 'emergency alert', 'emergency']:
        raise ValueError("System categories (such as Health and Emergency Alert) cannot be deleted.")

    cat_name = cat.name
    cat.delete()

    log_activity(
        actor=actor,
        action='delete',
        action_type='PostCategory',
        target_id=str(category_id),
        target_name=cat_name,
        details=f"Deleted PostCategory '{cat_name}'."
    )
    return True


# 3. DOCUMENT TYPES & REQUIREMENTS
def _parse_fee(raw):
    """Decimal fee >= 0 with at most 2 decimals and 10 digits; ValueError with a clean message otherwise."""
    text = str(raw if raw is not None else '').strip().replace(',', '') or '0.00'
    try:
        fee = Decimal(text)
    except InvalidOperation:
        raise ValueError("Invalid price/fee amount. Enter a number such as 50.00.")
    if not fee.is_finite():
        raise ValueError("Invalid price/fee amount. Enter a number such as 50.00.")
    if fee < Decimal('0.00'):
        raise ValueError("Fee cannot be negative.")
    fee = fee.quantize(Decimal('0.01'))
    if fee > Decimal('99999999.99'):
        raise ValueError("Fee is too large.")
    return fee


def _document_snapshot(doc):
    return {'name': doc.name, 'fee': str(doc.fee), 'order': doc.order, 'is_active': doc.is_active}


def create_or_update_document_type_service(actor, data, doc_id=None):
    """
    Creates or updates DocumentType and its checklist requirements:
    - Price (fee) >= 0.
    - Order >= 0.
    - Names unique case-insensitive.
    - Logs before/after values.
    """
    doc = _get_or_missing(DocumentType, doc_id, 'document type') if doc_id else None
    name = _clean_name(data, 'Document type', 150)

    existing_q = DocumentType.objects.filter(name__iexact=name)
    if doc:
        existing_q = existing_q.exclude(id=doc.id)
    if existing_q.exists():
        raise ValueError(f"A document type with name '{name}' already exists.")

    fee = _parse_fee(data.get('fee', '0.00'))
    order = safe_int(data.get('order', 0), 0)
    code = str(data.get('code') or '').strip()[:50]
    description = str(data.get('description') or '').strip()
    requirements_text = str(data.get('requirements_needed') or '').strip()

    with transaction.atomic():
        if doc:
            old_vals = _document_snapshot(doc)
            doc.name = name
            doc.code = code or slugify(name).replace('-', '_')[:50]
            doc.description = description
            doc.fee = fee
            doc.order = order
            doc.is_active = parse_bool(data, 'is_active', doc.is_active)
            doc.requirements_needed = requirements_text
            doc.save()

            log_activity(
                actor=actor,
                action='update',
                action_type='DocumentType',
                target_id=str(doc.id),
                target_name=doc.name,
                details=f"Updated DocumentType '{doc.name}'. Before: {old_vals} -> After: {_document_snapshot(doc)}"
            )
        else:
            doc = DocumentType.objects.create(
                name=name,
                code=code or slugify(name).replace('-', '_')[:50],
                description=description,
                fee=fee,
                order=order,
                is_active=parse_bool(data, 'is_active', True),
                requirements_needed=requirements_text
            )
            log_activity(
                actor=actor,
                action='create',
                action_type='DocumentType',
                target_id=str(doc.id),
                target_name=doc.name,
                details=f"Created DocumentType '{doc.name}' (fee=₱{doc.fee}, order={doc.order}, active={doc.is_active})"
            )

        # Sync checklist requirements: the textarea is the full list, so an
        # empty textarea clears every Requirement row.
        req_lines = [r.strip() for r in requirements_text.split('\n') if r.strip()]
        doc.requirements.all().delete()
        for idx, r_name in enumerate(req_lines, start=1):
            Requirement.objects.create(document_type=doc, name=r_name[:200], order=idx)

    return doc


def delete_document_type_service(actor, doc_id):
    """
    Deletes a DocumentType:
    - Never delete when referenced by appointments.
    - Logs deletion.
    """
    doc = _get_or_missing(DocumentType, doc_id, 'document type')
    referenced = Appointment.objects.filter(document_type_id=doc_id).exists()

    if referenced:
        raise ValueError(f"Cannot delete document type '{doc.name}' because it is referenced by existing appointments. Please deactivate it instead.")

    doc_name = doc.name
    doc.delete()

    log_activity(
        actor=actor,
        action='delete',
        action_type='DocumentType',
        target_id=str(doc_id),
        target_name=doc_name,
        details=f"Deleted DocumentType '{doc_name}'."
    )
    return True


# 4. HEALTH CARE SERVICES
def _health_snapshot(svc):
    return {'name': svc.name, 'is_free': svc.is_free, 'is_active': svc.is_active}


def create_or_update_health_service_service(actor, data, svc_id=None):
    """
    Creates or updates HealthCareService:
    - Names unique case-insensitive.
    - Logs before/after values.
    """
    svc = _get_or_missing(HealthCareService, svc_id, 'health service') if svc_id else None
    name = _clean_name(data, 'Health care service', 150)

    existing_q = HealthCareService.objects.filter(name__iexact=name)
    if svc:
        existing_q = existing_q.exclude(id=svc.id)
    if existing_q.exists():
        raise ValueError(f"A health service with name '{name}' already exists.")

    description = str(data.get('description') or '').strip()
    available_date = str(data.get('available_date') or '').strip()
    available_time = str(data.get('available_time') or '').strip()
    if len(available_date) > 120 or len(available_time) > 120:
        raise ValueError("Available date and time must each be 120 characters or fewer.")

    if svc:
        old_vals = _health_snapshot(svc)
        svc.name = name
        svc.description = description
        svc.available_date = available_date
        svc.available_time = available_time
        svc.is_free = parse_bool(data, 'is_free', svc.is_free)
        svc.is_active = parse_bool(data, 'is_active', svc.is_active)
        svc.save()

        log_activity(
            actor=actor,
            action='update',
            action_type='HealthCareService',
            target_id=str(svc.id),
            target_name=svc.name,
            details=f"Updated HealthCareService '{svc.name}'. Before: {old_vals} -> After: {_health_snapshot(svc)}"
        )
    else:
        svc = HealthCareService.objects.create(
            name=name,
            description=description,
            available_date=available_date,
            available_time=available_time,
            is_free=parse_bool(data, 'is_free', True),
            is_active=parse_bool(data, 'is_active', True)
        )
        log_activity(
            actor=actor,
            action='create',
            action_type='HealthCareService',
            target_id=str(svc.id),
            target_name=svc.name,
            details=f"Created HealthCareService '{svc.name}' (is_free={svc.is_free}, is_active={svc.is_active})"
        )
    return svc


def delete_health_service_service(actor, svc_id):
    """
    Deletes a HealthCareService:
    - Never delete when referenced by appointments or health schedules.
    - Logs deletion.
    """
    svc = _get_or_missing(HealthCareService, svc_id, 'health service')
    referenced = (
        Appointment.objects.filter(healthcare_service_id=svc_id).exists() or
        svc.schedules.exists()
    )

    if referenced:
        raise ValueError(f"Cannot delete health service '{svc.name}' because it is referenced by existing bookings or schedules. Please deactivate it instead.")

    svc_name = svc.name
    svc.delete()

    log_activity(
        actor=actor,
        action='delete',
        action_type='HealthCareService',
        target_id=str(svc_id),
        target_name=svc_name,
        details=f"Deleted HealthCareService '{svc_name}'."
    )
    return True


# 5. CONCERN CATEGORIES
def _concern_snapshot(cat):
    return {
        'name': cat.name,
        'routing_target_type': cat.routing_target_type,
        'routing_target_value': cat.routing_target_value,
        'is_active': cat.is_active,
    }


def create_or_update_concern_category_service(actor, data, cat_id=None):
    """
    Creates or updates ConcernCategory:
    - Names unique case-insensitive.
    - Routing target (service area or committee).
    - Logs before/after values.
    """
    cat = _get_or_missing(ConcernCategory, cat_id, 'concern category') if cat_id else None
    name = _clean_name(data, 'Concern category', 100)

    existing_q = ConcernCategory.objects.filter(name__iexact=name)
    if cat:
        existing_q = existing_q.exclude(id=cat.id)
    if existing_q.exists():
        raise ValueError(f"A concern category with name '{name}' already exists.")
    slug = slugify(name).replace('-', '_')
    slug_q = ConcernCategory.objects.filter(slug=slug)
    if cat:
        slug_q = slug_q.exclude(id=cat.id)
    if not slug or slug_q.exists():
        raise ValueError(f"A concern category with a name similar to '{name}' already exists or the name is not usable.")

    description = str(data.get('description') or '').strip()
    routing_type = data.get('routing_target_type', 'service_area')
    if routing_type not in ['service_area', 'committee']:
        routing_type = 'service_area'
    routing_value = str(data.get('routing_target_value') or '').strip()
    if len(routing_value) > 100:
        raise ValueError("Routing target must be 100 characters or fewer.")

    if cat:
        old_vals = _concern_snapshot(cat)
        cat.name = name
        cat.slug = slug
        cat.description = description
        cat.routing_target_type = routing_type
        cat.routing_target_value = routing_value
        cat.is_active = parse_bool(data, 'is_active', cat.is_active)
        cat.save()

        log_activity(
            actor=actor,
            action='update',
            action_type='ConcernCategory',
            target_id=str(cat.id),
            target_name=cat.name,
            details=f"Updated ConcernCategory '{cat.name}'. Before: {old_vals} -> After: {_concern_snapshot(cat)}"
        )
    else:
        cat = ConcernCategory.objects.create(
            name=name,
            slug=slug,
            description=description,
            routing_target_type=routing_type,
            routing_target_value=routing_value,
            is_active=parse_bool(data, 'is_active', True)
        )
        log_activity(
            actor=actor,
            action='create',
            action_type='ConcernCategory',
            target_id=str(cat.id),
            target_name=cat.name,
            details=f"Created ConcernCategory '{cat.name}' (routing={routing_type}:{routing_value}, active={cat.is_active})"
        )
    return cat


def delete_concern_category_service(actor, cat_id):
    """
    Deletes a ConcernCategory and logs the action.
    """
    cat = _get_or_missing(ConcernCategory, cat_id, 'concern category')
    cat_name = cat.name
    cat.delete()

    log_activity(
        actor=actor,
        action='delete',
        action_type='ConcernCategory',
        target_id=str(cat_id),
        target_name=cat_name,
        details=f"Deleted ConcernCategory '{cat_name}'."
    )
    return True


# 6. STAFF ACCOUNTS MANAGEMENT
def create_staff_account_service(actor, data):
    """
    Creates a staff account:
    - Generates a temporary password.
    - Sets term_end date.
    - Sends temporary password email (reg_approved.txt).
    - Logs creation.
    """
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip() or email.split('@')[0]
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()

    if not email:
        raise ValueError("Email address is required.")
    if User.objects.filter(email__iexact=email).exists():
        raise ValueError(f"An account with email '{email}' already exists.")
    if User.objects.filter(username__iexact=username).exists():
        raise ValueError(f"An account with username '{username}' already exists.")

    term_end_raw = data.get('term_end')
    term_end = None
    if term_end_raw:
        if isinstance(term_end_raw, str) and term_end_raw.strip():
            try:
                term_end = datetime.date.fromisoformat(term_end_raw.strip())
            except ValueError:
                raise ValueError("Term end must be a valid date (YYYY-MM-DD).")
        elif isinstance(term_end_raw, datetime.date):
            term_end = term_end_raw

    temp_pw = generate_temp_password()

    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=email,
            password=temp_pw,
            first_name=first_name,
            last_name=last_name,
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            is_staff=True,
            is_approved=True,
            must_change_password=True,
            temp_password_expires_at=timezone.now() + datetime.timedelta(days=7),
            term_end=term_end
        )

        # Assign officer position if provided
        officer_id = data.get('officer_id')
        officer = Officer.objects.filter(id=officer_id).first() if officer_id else Officer.objects.first()
        if officer:
            scope_type = data.get('scope_type', StaffAssignment.SCOPE_SERVICE_AREA)
            scope_value = data.get('scope_value', 'general')
            StaffAssignment.objects.create(
                user=user,
                officer=officer,
                scope_type=scope_type,
                scope_value=scope_value,
                term_end=term_end
            )

        log_activity(
            actor=actor,
            action='create',
            action_type='StaffAccount',
            target_id=str(user.id),
            target_name=user.get_full_name() or user.username,
            details=f"Created staff account '{user.email}' (term_end={term_end}). Dispatched temporary password."
        )

        # Dispatch staff_created email with temp password inside on_commit
        position_title = officer.position if (officer and hasattr(officer, 'position')) else (getattr(officer, 'name', 'Staff') if officer else 'Staff')
        transaction.on_commit(
            lambda: send_templated_email(
                template_name='staff_created',
                to_email=user.email,
                context={
                    'first_name': user.first_name or user.username,
                    'email': user.email,
                    'temp_password': temp_pw,
                    'login_url': '/accounts/login/',
                    'position': position_title,
                },
                ref_table='User',
                ref_id=str(user.id),
            )
        )

    return user


def disable_staff_account_service(actor, staff_user_id):
    """
    Disables a staff account:
    - Only staff/admin/kapitan accounts; residents are handled in Residents.
    - A superuser target can only be disabled by a superuser actor.
    - Sets status=disabled, is_active=False.
    - Logs action.
    """
    user = _get_or_missing(User, staff_user_id, 'staff account')
    if user.id == actor.id:
        raise ValueError("You cannot disable your own administrator account.")
    if user.role not in (User.ROLE_STAFF, User.ROLE_ADMIN, User.ROLE_KAPITAN):
        raise ValueError("Only staff accounts can be disabled here.")
    if user.is_superuser and not getattr(actor, 'is_superuser', False):
        raise ValueError("Only a superuser can disable a superuser account.")

    old_status = user.status
    user.status = User.STATUS_DISABLED
    user.is_active = False
    user.save()

    log_activity(
        actor=actor,
        action='disable',
        action_type='StaffAccount',
        target_id=str(user.id),
        target_name=user.get_full_name() or user.username,
        details=f"Disabled staff account '{user.username}'. Status: {old_status} -> disabled."
    )
    return user


# 7. EMAIL TEMPLATES
# One catalog drives the dashboard list AND the filename whitelist (read, preview, write).
EMAIL_TEMPLATE_CATALOG = [
    {'name': 'appt_approved', 'title': 'Appointment Approved Notice', 'description': 'Sent when an appointment booking is approved by staff.'},
    {'name': 'appt_received', 'title': 'Appointment Received Confirmation', 'description': 'Sent to applicant immediately upon submitting an appointment request.'},
    {'name': 'appt_rejected', 'title': 'Appointment Rejected Notice', 'description': 'Sent when an appointment request is rejected with reason.'},
    {'name': 'appt_reminder', 'title': 'Appointment 24h Reminder', 'description': 'Scheduled automated reminder 24 hours prior to appointment date.'},
    {'name': 'reg_approved', 'title': 'Account Approved & Temporary Password', 'description': 'Sent when a resident or staff account is approved with temporary credentials.'},
    {'name': 'reg_received', 'title': 'Registration Received Notice', 'description': 'Sent upon resident online portal signup awaiting review.'},
    {'name': 'reg_rejected', 'title': 'Registration Rejected Notice', 'description': 'Sent when resident registration is declined with explanation.'},
    {'name': 'staff_created', 'title': 'Staff Account Created & Temporary Password', 'description': 'Sent to a new staff member with their temporary login credentials.'},
    {'name': 'password_reset_email', 'title': 'Password Reset Link', 'description': 'Sent when a user requests a password reset. The subject lives in a separate file, so this template has no Subject line.'},
]
EMAIL_TEMPLATE_NAMES = frozenset(item['name'] for item in EMAIL_TEMPLATE_CATALOG)
# Django's password reset flow takes the subject from password_reset_subject.txt.
EMAIL_TEMPLATES_WITHOUT_SUBJECT = frozenset({'password_reset_email'})
EMAIL_TEMPLATE_MAX_BYTES = 20 * 1024


def email_template_dir():
    return os.path.join(settings.BASE_DIR, 'templates', 'emails')


def _clean_email_template_name(template_name):
    """Return the whitelisted base name (no extension) or raise ValueError."""
    name = str(template_name or '').strip()
    if name.endswith('.txt'):
        name = name[:-4]
    if name not in EMAIL_TEMPLATE_NAMES:
        raise ValueError("Invalid template name specified.")
    return name


def _read_email_template(name):
    path = os.path.join(email_template_dir(), f"{name}.txt")
    if not os.path.isfile(path):
        raise ValueError(f"Template '{name}.txt' does not exist.")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _split_subject(text):
    """Split 'Subject: ...' first line from the body. Returns (subject, body, has_subject)."""
    lines = text.strip().split('\n', 1)
    if lines[0].lower().startswith('subject:'):
        return lines[0].split(':', 1)[1].strip(), (lines[1].strip() if len(lines) > 1 else ''), True
    return '', text.strip(), False


def _email_sample_context():
    info = BarangayInfo.get_solo()
    today_str = timezone.now().date().strftime('%B %d, %Y')
    return {
        'first_name': 'Juan',
        'last_name': 'Dela Cruz',
        'email': 'juan.delacruz@example.ph',
        'barangay_name': info.name,
        'barangay_address': info.address,
        'barangay_contact': info.contact_no,
        'contact_no': info.contact_no,
        'office_hours': info.office_hours,
        'venue': info.venue,
        'date': today_str,
        'scheduled_date': today_str,
        'appointment_date': today_str,
        'service': 'Barangay Clearance',
        'service_name': 'Medical Consultation',
        'document_type': 'Barangay Clearance',
        'time_window': 'Morning (8:00 AM - 11:30 AM)',
        'scheduled_time': 'Morning (8:00 AM - 11:30 AM)',
        'appointment_time': 'Morning (8:00 AM - 11:30 AM)',
        'requirements_line': ' (2 Valid IDs, Cedula / CTC, Proof of Billing)',
        'temp_password': 'Tq7#mVw2pK!x',
        'reference_no': 'APT-2026-0042',
        'rejection_reason': 'The uploaded proof of identity was illegible. Please submit a valid clear government ID.',
        'reason': 'The uploaded proof of identity was illegible. Please submit a valid clear government ID.',
        'login_url': '/accounts/login/',
        'register_url': '/accounts/signup/',
        'position': 'Secretary',
        'domain': 'barangay.example.ph',
        'uid': 'MQ',
        'token': 'abc123-sample-token',
    }


def _compile_email_template(source):
    try:
        return Engine.get_default().from_string(source)
    except TemplateSyntaxError as exc:
        raise ValueError(f"The template has a syntax error: {exc}")


def render_email_template_preview(template_name):
    """
    Renders read-only preview of a whitelisted email template with sample data.
    """
    name = _clean_email_template_name(template_name)
    source = _read_email_template(name)
    rendered_text = _compile_email_template(source).render(Context(_email_sample_context())).strip()

    subject, body, has_subject = _split_subject(rendered_text)
    if not has_subject:
        subject, body = '', rendered_text

    return {
        'template_name': f"{name}.txt",
        'subject': subject,
        'body': body,
        'raw_text': rendered_text,
    }


def get_email_template_source(template_name):
    """
    Returns the raw template source code (including variables) and parsed subject/body for editing.
    """
    name = _clean_email_template_name(template_name)
    source = _read_email_template(name)
    subject, body, has_subject = _split_subject(source)
    if not has_subject:
        subject, body = '', source

    return {
        'template_name': f"{name}.txt",
        'subject': subject,
        'body': body,
        'raw_source': source,
        'has_subject': name not in EMAIL_TEMPLATES_WITHOUT_SUBJECT,
    }


def update_email_template_service(actor, template_name, content):
    """
    Saves edited template content back to the filesystem.
    - Filename must be in the catalog whitelist.
    - Content must be non-empty, <= 20 KB, valid Django template syntax, and renderable
      with the sample context.
    - First line must be 'Subject: ...' (except password_reset_email, whose subject is a separate file).
    - Written atomically (temp file + os.replace), UTF-8. Content is never written to the audit log.
    """
    name = _clean_email_template_name(template_name)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Template content cannot be empty.")
    content = content.replace('\r\n', '\n').replace('\r', '\n').strip() + '\n'
    if len(content.encode('utf-8')) > EMAIL_TEMPLATE_MAX_BYTES:
        raise ValueError("Template content is too large (limit is 20 KB).")

    subject, body, has_subject = _split_subject(content)
    if name not in EMAIL_TEMPLATES_WITHOUT_SUBJECT:
        if not has_subject or not subject:
            raise ValueError("The first line must be 'Subject: <your subject>'.")
        if not body:
            raise ValueError("The email body cannot be empty.")

    template = _compile_email_template(content)
    try:
        template.render(Context(_email_sample_context()))
    except Exception:
        raise ValueError("The template could not be rendered with sample data. Check the variables and tags.")

    directory = email_template_dir()
    target = os.path.join(directory, f"{name}.txt")
    if not os.path.isfile(target):
        raise ValueError(f"Template '{name}.txt' does not exist.")

    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    log_activity(
        actor=actor,
        action='update',
        action_type='EmailTemplate',
        target_id=name,
        target_name=f"{name}.txt",
        details=f"Edited email template '{name}.txt' ({len(content)} characters). Content not logged."
    )
    return True
