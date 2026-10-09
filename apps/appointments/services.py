"""
Service functions for Appointments and Document Requests.
Handles booking validation, prefilling, capacity checks, status transitions,
scope enforcement, notifications, audit logging, and templated email dispatches.
"""

import datetime
import logging
from datetime import date, timedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import PermissionDenied, ValidationError
from apps.core.uploads import validate_upload
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User
from apps.accounts.permissions import check_staff_appointment_scope
from apps.accounts.services import calculate_age
from apps.appointments.models import (
    Appointment,
    HealthCareService,
    HealthSchedule,
    DocumentType,
    Requirement,
    IssuedDocumentLog,
)
from apps.chat.models import Notification
from apps.chat.services import create_notification
from apps.history.utils import log_activity, log_email, send_templated_email

logger = logging.getLogger(__name__)


def notify_staff_pending_appointment(appointment):
    """
    Staff / admin receive notifications for:
    - new pending appointment in their scope.
    """
    from apps.accounts.models import User, StaffAssignment
    
    # 1. Admins and Kapitans receive all pending appointments
    admins = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_superuser=True),
        status=User.STATUS_ACTIVE
    ).distinct()
    for admin in admins:
        create_notification(
            recipient=admin,
            title=f"New Pending Appointment: {appointment.reference_no}",
            message=f"New appointment request for {appointment.get_service_title()} on {appointment.appt_date.strftime('%b %d, %Y')}.",
            url=f"/appointments/{appointment.id}/",
            action_type="appointment"
        )

    # 2. Staff members only if within their scope
    staff_users = User.objects.filter(
        role=User.ROLE_STAFF,
        status=User.STATUS_ACTIVE,
        is_approved=True
    ).distinct()

    resident_purok_name = None
    if appointment.resident:
        if hasattr(appointment.resident, 'resident_profile') and appointment.resident.resident_profile and appointment.resident.resident_profile.purok:
            resident_purok_name = appointment.resident.resident_profile.purok.name
        elif hasattr(appointment.resident, 'purok') and appointment.resident.purok:
            resident_purok_name = appointment.resident.purok.name

    for staff in staff_users:
        assignments = StaffAssignment.objects.filter(user=staff)
        if not assignments.exists():
            continue

        service_areas = [a.scope_value.strip().lower() for a in assignments.filter(scope_type=StaffAssignment.SCOPE_SERVICE_AREA)]
        puroks = [a.scope_value.strip() for a in assignments.filter(scope_type=StaffAssignment.SCOPE_PUROK)]

        in_scope = False
        if 'all' in service_areas or 'general' in service_areas:
            in_scope = True
        elif appointment.category == Appointment.CATEGORY_DOCUMENT and any('doc' in sa for sa in service_areas):
            in_scope = True
        elif appointment.category == Appointment.CATEGORY_HEALTHCARE and any('health' in sa for sa in service_areas):
            in_scope = True
        elif resident_purok_name and resident_purok_name in puroks:
            in_scope = True

        if in_scope:
            create_notification(
                recipient=staff,
                title=f"New Pending Appointment: {appointment.reference_no}",
                message=f"New appointment request for {appointment.get_service_title()} on {appointment.appt_date.strftime('%b %d, %Y')}.",
                url=f"/appointments/{appointment.id}/",
                action_type="appointment"
            )


def resolve_document_type(value):
    """
    Resolve an ACTIVE DocumentType from an id, a code or a (case-insensitive) name.
    An empty value falls back to the active 'clearance' type, then the first active type.
    An unknown value raises ValueError (no silent fallback to another document).
    """
    active = DocumentType.objects.filter(is_active=True)
    if isinstance(value, DocumentType):
        value = value.pk
    raw = str(value).strip() if value is not None else ''
    if not raw:
        return active.filter(code__iexact='clearance').first() or active.first()
    document_type = None
    if raw.isdigit():
        document_type = active.filter(id=int(raw)).first()
    if document_type is None:
        document_type = active.filter(code__iexact=raw).first() or active.filter(name__iexact=raw).first()
    if document_type is None:
        raise ValueError("A valid active document type must be selected.")
    return document_type


def book_appointment_service(user, data, request=None):
    """
    Books an appointment or document request.
    - Requires authenticated resident user.
    - Prefills name, address, email, phone, and calculates age from birthdate (read-only).
    - Auto-generates unique reference_no (APT-YYYY-NNNN).
    - Validates category:
        * Document: validates active DocumentType.
        * Health: validates active free health care service on schedule with capacity.
    - Sets status='pending'.
    - Dispatches Email 1 (appt_received.txt) on transaction commit.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required to book an appointment.")

    # 1. Prefill / extract identity details
    applicant_first_name = user.first_name.strip()
    applicant_middle_name = getattr(user, 'middle_name', '').strip()
    applicant_last_name = user.last_name.strip()
    applicant_email = user.email.strip().lower()
    applicant_phone = (user.phone_number or getattr(user, 'contact_no', '')).strip()

    # Address
    if hasattr(user, 'resident_profile') and user.resident_profile and user.resident_profile.address:
        applicant_address = user.resident_profile.address.strip()
    elif getattr(user, 'street_address', '').strip():
        applicant_address = user.street_address.strip()
    elif getattr(user, 'address', '').strip():
        applicant_address = user.address.strip()
    else:
        applicant_address = data.get('address', '').strip()

    # Age calculation from birthdate (server-side, read-only)
    birthdate = None
    if hasattr(user, 'resident_profile') and user.resident_profile and user.resident_profile.birthdate:
        birthdate = user.resident_profile.birthdate
    elif getattr(user, 'date_of_birth', None):
        birthdate = user.date_of_birth

    if birthdate:
        applicant_age = calculate_age(birthdate)
    else:
        raw_age = data.get('age')
        applicant_age = int(raw_age) if raw_age else 18

    # 2. Date & Time Window
    appt_date_raw = data.get('appt_date')
    if isinstance(appt_date_raw, str):
        appt_date = date.fromisoformat(appt_date_raw.strip())
    elif isinstance(appt_date_raw, date):
        appt_date = appt_date_raw
    else:
        appt_date = timezone.localdate()

    if appt_date < timezone.localdate():
        raise ValueError("Appointment date cannot be in the past.")

    if appt_date > timezone.localdate() + timedelta(days=60):
        raise ValueError("Appointments can only be booked up to 60 days in advance.")

    if appt_date.weekday() in (5, 6):
        raise ValueError("Appointments are only available on weekdays (Monday to Friday).")

    time_window = data.get('time_window') or Appointment.TIME_SLOT_MORNING
    category = data.get('category') or Appointment.CATEGORY_DOCUMENT
    purpose = (data.get('purpose') or '').strip()
    if not purpose:
        purpose = "General appointment request"

    document_type = None
    health_svc = None

    if category == Appointment.CATEGORY_DOCUMENT:
        document_type = resolve_document_type(
            data.get('document_type') or data.get('document_type_id')
        )
    elif category == Appointment.CATEGORY_HEALTHCARE:
        svc_val = data.get('healthcare_service') or data.get('health_service_id')
        if isinstance(svc_val, HealthCareService):
            health_svc = svc_val
        elif isinstance(svc_val, int) or (isinstance(svc_val, str) and str(svc_val).isdigit()):
            health_svc = HealthCareService.objects.filter(id=int(svc_val), is_active=True).first()
        else:
            health_svc = HealthCareService.objects.filter(name=str(svc_val), is_active=True).first()

        if not health_svc:
            raise ValueError("A valid active health care service must be selected.")

        if not health_svc.is_free:
            raise ValueError("Only free health care services can be booked on this schedule.")

        # Capacity check on HealthSchedule
        schedule = HealthSchedule.objects.filter(
            health_service=health_svc,
            service_date=appt_date,
            time_window=time_window
        ).first()

        if schedule:
            booked_count = Appointment.objects.filter(
                healthcare_service=health_svc,
                appt_date=appt_date,
                time_window=time_window,
                status__in=[
                    Appointment.STATUS_PENDING,
                    Appointment.STATUS_APPROVED,
                ]
            ).count()

            if booked_count >= schedule.capacity:
                raise ValueError(f"No available slots for {health_svc.name} on this date and time window (capacity full).")

    # Refuse duplicate pending or approved booking by the same resident for the same service and date
    active_statuses = [
        Appointment.STATUS_PENDING,
        Appointment.STATUS_APPROVED,
    ]
    existing_dup = Appointment.objects.filter(
        resident=user,
        appt_date=appt_date,
        category=category,
        status__in=active_statuses
    )
    if category == Appointment.CATEGORY_DOCUMENT:
        existing_dup = existing_dup.filter(document_type=document_type)
    elif category == Appointment.CATEGORY_HEALTHCARE:
        existing_dup = existing_dup.filter(healthcare_service=health_svc)

    if existing_dup.exists():
        raise ValueError("You already have an active appointment request for this service on this date.")

    # Optional supporting document: extension + magic bytes + 5 MB cap; stored privately.
    supporting_file = data.get('supporting_id')
    if not hasattr(supporting_file, 'read'):  # plain form values are not files
        supporting_file = None
    if supporting_file is not None:
        try:
            validate_upload(supporting_file)
        except ValidationError as exc:
            raise ValueError(exc.messages[0])

    # 3. Create appointment
    with transaction.atomic():
        # Snapshot the fee now so later price changes in Settings only affect NEW bookings.
        fee_val = document_type.fee if (category == Appointment.CATEGORY_DOCUMENT and document_type) else 0
        appointment = Appointment.objects.create(
            resident=user,
            applicant_first_name=applicant_first_name,
            applicant_middle_name=applicant_middle_name,
            applicant_last_name=applicant_last_name,
            applicant_age=applicant_age,
            applicant_address=applicant_address,
            applicant_email=applicant_email,
            applicant_phone=applicant_phone,
            category=category,
            document_type=document_type,
            healthcare_service=health_svc,
            appt_date=appt_date,
            time_window=time_window,
            purpose=purpose,
            fee_at_booking=fee_val,
            status=Appointment.STATUS_PENDING,
            supporting_id=supporting_file,
        )

        # 4. Dispatch Email 1 (appt_received.txt)
        email_ctx = {
            'first_name': applicant_first_name or 'Resident',
            'reference_no': appointment.reference_no,
            'service': appointment.get_service_title(),
            'date': appointment.appt_date.strftime('%B %d, %Y'),
            'time_window': appointment.get_time_window_display(),
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Poblacion'),
        }
        target_email = appointment.get_applicant_email()
        apt_id = str(appointment.id)
        transaction.on_commit(
            lambda: send_templated_email(
                'appt_received.txt',
                target_email,
                email_ctx,
                ref_table='Appointment',
                ref_id=apt_id
            )
        )

        # Log Activity
        log_activity(
            actor=user,
            action='create',
            action_type='Appointment',
            target_id=str(appointment.id),
            target_name=appointment.get_service_title(),
            details=f"Booked appointment {appointment.reference_no} for {appointment.get_service_title()}"
        )

        notify_staff_pending_appointment(appointment)

    return appointment


def approve_appointment_service(appointment, staff_user, request=None):
    """
    Approves an appointment or document request.
    - Inside transaction.atomic with select_for_update.
    - Status guard: approve only from pending. Second attempt does nothing and sends no email.
    - Scope check: verifies staff assignment matches service_area ('Health' or 'Documents') or purok.
    - If healthcare: locks HealthSchedule (select_for_update) and counts approved bookings against capacity.
    - Sets status='approved', processed_by=staff_user, processed_at=now.
    - Dispatches Email 4 (appt_approved.txt) with requirements_line and venue from settings.
    - Records ActivityLog.
    """
    with transaction.atomic():
        apt = Appointment.objects.select_for_update().get(id=appointment.id)

        # Idempotency guard: second attempt must do nothing and send no email
        if apt.status == Appointment.STATUS_APPROVED:
            return False

        # Status guard: approve only from pending
        if apt.status != Appointment.STATUS_PENDING:
            raise ValueError(f"Cannot approve appointment with status '{apt.get_status_display()}'. Must be pending.")

        # Check permission & scope inside service function
        if not check_staff_appointment_scope(staff_user, apt):
            raise PermissionDenied("Staff user does not have jurisdiction over this appointment scope.")

        # Healthcare capacity lock & re-check
        if apt.category == Appointment.CATEGORY_HEALTHCARE:
            svc = apt.healthcare_service
            if svc:
                sched = HealthSchedule.objects.select_for_update().filter(
                    health_service=svc,
                    service_date=apt.appt_date,
                    time_window=apt.time_window
                ).first()
                if sched:
                    approved_count = Appointment.objects.filter(
                        healthcare_service=svc,
                        appt_date=apt.appt_date,
                        time_window=apt.time_window,
                        status=Appointment.STATUS_APPROVED,
                    ).exclude(id=apt.id).count()

                    if approved_count >= sched.capacity:
                        raise ValueError(f"Cannot approve: capacity limit of {sched.capacity} has been reached for this slot.")

        apt.status = Appointment.STATUS_APPROVED
        apt.processed_by = staff_user
        apt.processed_at = timezone.now()
        apt.save()

        # Build requirements_line
        requirements_line = ""
        if apt.category == Appointment.CATEGORY_DOCUMENT:
            req_list = []
            if apt.document_type:
                req_list = list(apt.document_type.requirements.values_list('name', flat=True))
                if not req_list and apt.document_type.requirements_needed:
                    req_list = [apt.document_type.requirements_needed]
            if req_list:
                requirements_line = f" and the following requirements: {', '.join(req_list)}"

        if apt.category == Appointment.CATEGORY_HEALTHCARE:
            venue = getattr(settings, 'BARANGAY_HEALTH_CENTER_VENUE', 'Barangay Health Center')
        else:
            venue = getattr(settings, 'BARANGAY_VENUE', 'Barangay Hall Multi-Purpose Center')

        # Dispatch Email 4 (appt_approved.txt) on commit
        email_ctx = {
            'first_name': apt.applicant_first_name or (apt.resident.first_name if apt.resident else 'Resident'),
            'service': apt.get_service_title(),
            'date': apt.appt_date.strftime('%B %d, %Y'),
            'time_window': apt.get_time_window_display(),
            'venue': venue,
            'reference_no': apt.reference_no,
            'requirements_line': requirements_line,
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Poblacion'),
        }
        target_email = apt.get_applicant_email()
        apt_id = str(apt.id)
        transaction.on_commit(
            lambda: send_templated_email(
                'appt_approved.txt',
                target_email,
                email_ctx,
                ref_table='Appointment',
                ref_id=apt_id
            )
        )

        # Log Activity
        log_activity(
            actor=staff_user,
            action='approve',
            action_type='Appointment',
            target_id=str(apt.id),
            target_name=apt.get_service_title(),
            details=f"Approved appointment {apt.reference_no} for {apt.get_applicant_name()}"
        )

        # In-app notification
        if apt.resident:
            notif_msg = f"Your appointment for {apt.get_service_title()} has been APPROVED for {apt.appt_date.strftime('%B %d, %Y')} ({apt.get_time_window_display()})."
            create_notification(
                recipient=apt.resident,
                title="Appointment Approved!",
                message=notif_msg,
                url=f"/appointments/{apt.id}/",
                action_type="appointment"
            )

    return True


def reject_appointment_service(appointment, staff_user, reason, request=None):
    """
    Rejects an appointment with state of rejection reason.
    - Requires a non-empty reason.
    - Status guard: reject only from pending. Second attempt does nothing and sends no email.
    - Scope check inside service function.
    - Updates status='rejected', frees capacity slot.
    - Dispatches Email 6 (appt_rejected.txt).
    - Records ActivityLog.
    """
    if not reason or not str(reason).strip():
        raise ValueError("A reason is required to reject an appointment.")

    with transaction.atomic():
        apt = Appointment.objects.select_for_update().get(id=appointment.id)

        # Idempotency guard: second attempt must do nothing and send no email
        if apt.status == Appointment.STATUS_REJECTED:
            return False

        # Status guard: reject only from pending
        if apt.status != Appointment.STATUS_PENDING:
            raise ValueError(f"Cannot reject appointment with status '{apt.get_status_display()}'. Must be pending.")

        if not check_staff_appointment_scope(staff_user, apt):
            raise PermissionDenied("Staff user does not have jurisdiction over this appointment scope.")

        clean_reason = str(reason).strip()
        apt.status = Appointment.STATUS_REJECTED
        apt.rejection_reason = clean_reason
        apt.processed_by = staff_user
        apt.processed_at = timezone.now()
        apt.save()

        # Dispatch Email 6 (appt_rejected.txt)
        login_url = request.build_absolute_uri('/accounts/login/') if request else '/accounts/login/'
        email_ctx = {
            'first_name': apt.applicant_first_name or (apt.resident.first_name if apt.resident else 'Resident'),
            'service': apt.get_service_title(),
            'date': apt.appt_date.strftime('%B %d, %Y'),
            'time_window': apt.get_time_window_display(),
            'reason': clean_reason,
            'reference_no': apt.reference_no,
            'login_url': login_url,
            'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Poblacion'),
        }
        target_email = apt.get_applicant_email()
        apt_id = str(apt.id)
        transaction.on_commit(
            lambda: send_templated_email(
                'appt_rejected.txt',
                target_email,
                email_ctx,
                ref_table='Appointment',
                ref_id=apt_id
            )
        )

        # Log Activity
        log_activity(
            actor=staff_user,
            action='reject',
            action_type='Appointment',
            target_id=str(apt.id),
            target_name=apt.get_service_title(),
            details=f"Rejected appointment {apt.reference_no}. Reason: {clean_reason}"
        )

        if apt.resident:
            create_notification(
                recipient=apt.resident,
                title="Appointment Request Declined",
                message=f"Your request for {apt.get_service_title()} was declined. Reason: {clean_reason}",
                url=f"/appointments/{apt.id}/",
                action_type="appointment"
            )

    return True


def complete_appointment_service(appointment, staff_user, request=None):
    """
    Completes an appointment.
    - Status guard: complete only from approved. Second attempt does nothing.
    - Scope check inside service function.
    - Sets status='completed'.
    - Creates IssuedDocumentLog if category=document.
    - Records ActivityLog.
    """
    with transaction.atomic():
        apt = Appointment.objects.select_for_update().get(id=appointment.id)

        # Idempotency guard: second attempt does nothing
        if apt.status == Appointment.STATUS_COMPLETED:
            return False

        # Status guard: complete only from approved
        if apt.status != Appointment.STATUS_APPROVED:
            raise ValueError(f"Cannot complete appointment with status '{apt.get_status_display()}'. It must be approved first.")

        if not check_staff_appointment_scope(staff_user, apt):
            raise PermissionDenied("Staff user does not have jurisdiction over this appointment scope.")

        apt.status = Appointment.STATUS_COMPLETED
        apt.processed_by = staff_user
        apt.processed_at = timezone.now()
        apt.save()

        # If document, log issued clearance
        if apt.category == Appointment.CATEGORY_DOCUMENT and apt.resident:
            if not hasattr(apt, 'issued_log'):
                control_num = f"BRGY-{timezone.now().year}-{apt.id:04d}"
                IssuedDocumentLog.objects.get_or_create(
                    appointment=apt,
                    defaults={
                        'control_number': control_num,
                        'issued_to': apt.resident,
                        'issued_by': staff_user,
                    }
                )

        log_activity(
            actor=staff_user,
            action='complete',
            action_type='Appointment',
            target_id=str(apt.id),
            target_name=apt.get_service_title(),
            details=f"Marked appointment {apt.reference_no} as completed"
        )

        if apt.resident:
            create_notification(
                recipient=apt.resident,
                title="Document Completed!",
                message=f"Your request for {apt.get_service_title()} has been COMPLETED.",
                url=f"/appointments/{apt.id}/",
                action_type="appointment"
            )

    return True


def mark_no_show_service(appointment, staff_user, request=None):
    """
    Marks an appointment as no-show.
    - Status guard: no_show only from approved. Second attempt does nothing.
    - Date guard: block no_show before appt_date.
    - Scope check inside service function.
    - Sets status='no_show', frees capacity slot.
    - Records ActivityLog.
    """
    with transaction.atomic():
        apt = Appointment.objects.select_for_update().get(id=appointment.id)

        # Idempotency guard: second attempt does nothing
        if apt.status == Appointment.STATUS_NO_SHOW:
            return False

        # Status guard: no_show only from approved
        if apt.status != Appointment.STATUS_APPROVED:
            raise ValueError(f"Cannot mark appointment as No-Show with status '{apt.get_status_display()}'. It must be approved first.")

        if not check_staff_appointment_scope(staff_user, apt):
            raise PermissionDenied("Staff user does not have jurisdiction over this appointment scope.")

        # Date guard: block no_show before appt_date
        if timezone.localdate() < apt.appt_date:
            raise ValueError("Cannot mark an appointment as No-Show before the appointment date.")

        apt.status = Appointment.STATUS_NO_SHOW
        apt.processed_by = staff_user
        apt.processed_at = timezone.now()
        apt.save()

        log_activity(
            actor=staff_user,
            action='no_show',
            action_type='Appointment',
            target_id=str(apt.id),
            target_name=apt.get_service_title(),
            details=f"Marked appointment {apt.reference_no} as No-Show"
        )

        if apt.resident:
            create_notification(
                recipient=apt.resident,
                title="Appointment No-Show",
                message=f"Your appointment for {apt.get_service_title()} was marked as No-Show.",
                url=f"/appointments/{apt.id}/",
                action_type="appointment"
            )

    return True


# Backward compatibility alias:
noshow_appointment_service = mark_no_show_service


def send_appointment_status_email(appointment, status_title, custom_note=''):
    """
    Maintained for backward compatibility.
    """
    target_email = appointment.get_applicant_email()
    if not target_email:
        return False, "No email address found for applicant."

    applicant_name = appointment.get_applicant_name() or "Resident"
    service_title = appointment.get_service_title()
    ref_no = appointment.reference_no or f"APT-{appointment.id:04d}"

    ctx = {
        'first_name': applicant_name,
        'reference_no': ref_no,
        'service': service_title,
        'date': appointment.appt_date.strftime('%B %d, %Y') if appointment.appt_date else '',
        'time_window': appointment.get_time_window_display(),
        'barangay_name': getattr(settings, 'BARANGAY_NAME', 'Poblacion'),
    }
    return send_templated_email('appt_received.txt', target_email, ctx, ref_table='Appointment', ref_id=str(appointment.id))


def update_appointment_service(appointment, actor, data, request=None):
    """
    Service to update an appointment's date, time window, purpose, or admin notes.
    - Staff scope checked: actor must have jurisdiction over appointment.
    - Status CANNOT be changed directly here (must go through approve/reject/complete/no_show).
    - Validates date rules: no past date, no >60 days ahead, no weekends (Sat/Sun).
    - Checks duplicate active bookings by same resident on the new date.
    - Checks HealthSchedule capacity if category is healthcare.
    - Records ActivityLog.
    """
    with transaction.atomic():
        apt = Appointment.objects.select_for_update().get(id=appointment.id)

        if not check_staff_appointment_scope(actor, apt):
            raise PermissionDenied("Staff user does not have jurisdiction over this appointment scope.")

        new_date_val = data.get('appt_date')
        if new_date_val:
            if isinstance(new_date_val, datetime.date):
                new_date = new_date_val
            elif isinstance(new_date_val, datetime.datetime):
                new_date = new_date_val.date()
            else:
                try:
                    new_date = datetime.date.fromisoformat(str(new_date_val).strip())
                except ValueError:
                    raise ValueError("Invalid appointment date format.")

            today = timezone.localdate()
            if new_date < today:
                raise ValueError("Appointment date cannot be in the past.")
            if new_date > today + datetime.timedelta(days=60):
                raise ValueError("Appointment date cannot be more than 60 days in advance.")
            if new_date.weekday() in (5, 6):
                raise ValueError("Appointments are only available on weekdays (Monday to Friday).")

            apt.appt_date = new_date

        new_window = data.get('time_window')
        if new_window:
            if new_window not in [Appointment.TIME_SLOT_MORNING, Appointment.TIME_SLOT_AFTERNOON]:
                raise ValueError("Invalid time slot window selected.")
            apt.time_window = new_window

        # Check duplicate if resident exists
        if apt.resident and apt.appt_date:
            active_statuses = [Appointment.STATUS_PENDING, Appointment.STATUS_APPROVED]
            dup_qs = Appointment.objects.filter(
                resident=apt.resident,
                appt_date=apt.appt_date,
                category=apt.category,
                status__in=active_statuses
            ).exclude(id=apt.id)
            if apt.category == Appointment.CATEGORY_DOCUMENT:
                dup_qs = dup_qs.filter(document_type=apt.document_type)
            elif apt.category == Appointment.CATEGORY_HEALTHCARE:
                dup_qs = dup_qs.filter(healthcare_service=apt.healthcare_service)

            if dup_qs.exists():
                raise ValueError("You already have an active appointment request for this service on this date.")

        # Check capacity if healthcare
        if apt.category == Appointment.CATEGORY_HEALTHCARE and apt.appt_date:
            svc = apt.healthcare_service
            if svc:
                sched = HealthSchedule.objects.filter(
                    health_service=svc,
                    service_date=apt.appt_date,
                    time_window=apt.time_window
                ).first()
                if sched:
                    booked_count = Appointment.objects.filter(
                        healthcare_service=svc,
                        appt_date=apt.appt_date,
                        time_window=apt.time_window,
                        status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_APPROVED]
                    ).exclude(id=apt.id).count()
                    if booked_count >= sched.capacity:
                        raise ValueError(f"No available slots for {svc.name} on this date and time window (capacity full).")

        if 'purpose' in data and data['purpose']:
            apt.purpose = data['purpose']
        if 'admin_notes' in data and data['admin_notes'] is not None:
            apt.admin_notes = data['admin_notes']

        # Edit must not change status directly
        apt.save()

        log_activity(
            actor=actor,
            action='update',
            action_type='Appointment',
            target_id=str(apt.id),
            target_name=apt.get_service_title(),
            details=f"Updated appointment details for {apt.reference_no}"
        )
        return apt

