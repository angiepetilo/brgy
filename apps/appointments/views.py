from datetime import date, timedelta
import json
import logging
import mimetypes
import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User, StaffAssignment
from apps.accounts.selectors import get_contact_number
from apps.accounts.permissions import (
    require_perm,
    check_user_perm,
    check_staff_appointment_scope,
    can_manage_service_area,
    resident_forbidden,
    admin_only,
)
from apps.appointments.models import Appointment, HealthCareService, IssuedDocumentLog, DocumentType, HealthSchedule
from apps.appointments.forms import AppointmentCreateForm, AppointmentStatusUpdateForm, HealthCareServiceForm
from apps.appointments.email_validator import validate_email_address
from apps.appointments import selectors as appointment_selectors
from apps.appointments.services import (
    book_appointment_service,
    resolve_document_type,
    approve_appointment_service,
    reject_appointment_service,
    complete_appointment_service,
    noshow_appointment_service,
    mark_no_show_service,
    update_appointment_service,
    send_appointment_status_email,
)
from apps.history.utils import log_activity, log_email
from apps.chat.models import Notification
from apps.core.http import GENERIC_ERROR_MESSAGE, json_login_required, public_error_message
from apps.core.ratelimit import ratelimit
from apps.core.validators import validate_ph_mobile

logger = logging.getLogger(__name__)


@login_required
def appointment_list_view(request):
    """
    Unified Appointment Management Module with 3 Tabs:
    1. Appointment Tab (all appointments, modern search, date filter: today/yesterday/tomorrow, status, service dropdowns)
    2. Documents Request Tab (clearances, stepper flow, and document requests)
    3. Health Services Tab (health center services catalog and appointments)
    """
    user = request.user
    active_tab = request.GET.get('tab', 'appointments')
    if active_tab == 'requests':
        active_tab = 'documents'
    elif active_tab not in ['appointments', 'documents', 'health_services', 'schedule']:
        active_tab = 'appointments'

    status_filter = request.GET.get('status', '').strip()
    service_filter = request.GET.get('service', '').strip()
    date_filter = request.GET.get('date_filter', '').strip()
    search_query = request.GET.get('q', '').strip()

    if request.method == 'POST' and 'create_health_service' in request.POST:
        svc_name = request.POST.get('name', '').strip()
        svc_date = request.POST.get('service_date', '').strip()
        svc_time = request.POST.get('service_time', '').strip()
        svc_desc = request.POST.get('description', '').strip()
        if svc_name:
            HealthCareService.objects.create(
                name=svc_name,
                available_date=svc_date,
                available_time=svc_time,
                description=svc_desc,
                is_active=True
            )
            messages.success(request, f"New Health Service '{svc_name}' created successfully!")
            return redirect(f"{reverse('appointments:list')}?tab=health_services")

    if request.method == 'POST' and 'create_document_request' in request.POST:
        custom_doc_name = request.POST.get('custom_document_name', '').strip()
        doc_type = request.POST.get('document_type', '').strip()
        reqs = request.POST.get('requirements_needed', '').strip()

        if custom_doc_name or doc_type == '__custom__':
            doc_type_name = custom_doc_name or "Custom Document"
            # Persist custom document type in catalog
            document_type_obj, _ = DocumentType.objects.get_or_create(
                name=doc_type_name,
                defaults={'requirements_needed': reqs, 'is_active': True}
            )
        else:
            try:
                document_type_obj = resolve_document_type(doc_type)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect(f"{reverse('appointments:list')}?tab=documents")
            if document_type_obj is None:
                messages.error(request, "No active document types are configured.")
                return redirect(f"{reverse('appointments:list')}?tab=documents")
            doc_type_name = document_type_obj.name

        officer_id = request.POST.get('officer_in_charge')
        officer = User.objects.filter(id=officer_id).first() if officer_id else None
        officer_name = officer.get_full_name() if officer else "Barangay Administration"

        Appointment.objects.create(
            resident=user if user.role == User.ROLE_RESIDENT else None,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=document_type_obj,
            purpose=f"Requirements: {reqs}. Submitted to: {officer_name}",
            appt_date=timezone.localdate(),
            time_window=Appointment.TIME_SLOT_MORNING,
            fee_at_booking=document_type_obj.fee,
            status=Appointment.STATUS_PENDING,
            applicant_first_name=user.first_name,
            applicant_last_name=user.last_name,
            applicant_email=user.email,
            applicant_phone=user.phone_number,
        )
        messages.success(request, f"Document request for '{doc_type_name}' submitted to {officer_name} successfully!")
        return redirect(f"{reverse('appointments:list')}?tab=documents")

    if user.is_admin_user or user.is_kapitan_user or user.is_superuser:
        base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'document_type', 'processed_by').all()
    elif user.is_staff_user or user.is_staff:
        assignments = StaffAssignment.objects.filter(user=user)
        if not assignments.exists():
            base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'document_type', 'processed_by').all()
        else:
            service_areas = [a.scope_value.strip().lower() for a in assignments.filter(scope_type=StaffAssignment.SCOPE_SERVICE_AREA)]
            puroks = [a.scope_value.strip() for a in assignments.filter(scope_type=StaffAssignment.SCOPE_PUROK)]

            q_scope = Q()
            if any('doc' in sa for sa in service_areas) or 'all' in service_areas or 'general' in service_areas:
                q_scope |= Q(category=Appointment.CATEGORY_DOCUMENT)
            if any('health' in sa for sa in service_areas) or 'all' in service_areas or 'general' in service_areas:
                q_scope |= Q(category=Appointment.CATEGORY_HEALTHCARE)
            if puroks:
                q_scope |= (
                    Q(resident__resident_profile__purok__name__in=puroks) |
                    Q(resident__purok__name__in=puroks)
                )
            base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'document_type', 'processed_by').filter(q_scope) if q_scope else Appointment.objects.select_related('resident', 'healthcare_service', 'document_type', 'processed_by').all()
    elif user.role == User.ROLE_RESIDENT:
        q_res = Q(resident=user)
        if user.email:
            q_res |= Q(applicant_email__iexact=user.email)
        base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'document_type', 'processed_by').filter(q_res)
    else:
        base_queryset = Appointment.objects.none()

    queryset = base_queryset
    today = timezone.localdate()

    # Date filter: Today, Yesterday, Tomorrow
    if date_filter == 'today':
        queryset = queryset.filter(appt_date=today)
    elif date_filter == 'yesterday':
        queryset = queryset.filter(appt_date=today - timedelta(days=1))
    elif date_filter == 'tomorrow':
        queryset = queryset.filter(appt_date=today + timedelta(days=1))

    # Status filter
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    # Service filter
    if service_filter:
        if service_filter.startswith('doc_'):
            doc_key = service_filter[4:]
            if doc_key.isdigit():
                doc_q = Q(document_type_id=int(doc_key))
            else:
                doc_q = Q(document_type__code__iexact=doc_key)
            queryset = queryset.filter(doc_q, category=Appointment.CATEGORY_DOCUMENT)
        elif service_filter.startswith('health_'):
            queryset = queryset.filter(category=Appointment.CATEGORY_HEALTHCARE, healthcare_service_id=service_filter[7:])
        elif service_filter == 'document':
            queryset = queryset.filter(category=Appointment.CATEGORY_DOCUMENT)
        elif service_filter == 'healthcare':
            queryset = queryset.filter(category=Appointment.CATEGORY_HEALTHCARE)

    # Search filter across REF #, applicant, purpose
    if search_query:
        clean_id = search_query.lstrip('#').replace('APT-', '').replace('apt-', '')
        id_q = Q(id=int(clean_id)) if clean_id.isdigit() else Q()
        queryset = queryset.filter(
            id_q |
            Q(applicant_first_name__icontains=search_query) |
            Q(applicant_last_name__icontains=search_query) |
            Q(applicant_email__icontains=search_query) |
            Q(applicant_phone__icontains=search_query) |
            Q(resident__first_name__icontains=search_query) |
            Q(resident__last_name__icontains=search_query) |
            Q(resident__username__icontains=search_query) |
            Q(purpose__icontains=search_query)
        )

    # Tab 2: Document requests specifically
    doc_queryset = base_queryset.filter(category=Appointment.CATEGORY_DOCUMENT)
    if status_filter and active_tab == 'documents':
        doc_queryset = doc_queryset.filter(status=status_filter)
    if search_query and active_tab == 'documents':
        doc_queryset = doc_queryset.filter(
            Q(applicant_first_name__icontains=search_query) |
            Q(applicant_last_name__icontains=search_query) |
            Q(resident__first_name__icontains=search_query) |
            Q(resident__last_name__icontains=search_query) |
            Q(purpose__icontains=search_query)
        )

    # Tab 3: Health services
    health_services_list = HealthCareService.objects.all().order_by('-is_active', 'name')
    health_appointments = base_queryset.filter(category=Appointment.CATEGORY_HEALTHCARE)
    if status_filter and active_tab == 'health_services':
        health_appointments = health_appointments.filter(status=status_filter)
    if search_query and active_tab == 'health_services':
        health_appointments = health_appointments.filter(
            Q(applicant_first_name__icontains=search_query) |
            Q(applicant_last_name__icontains=search_query) |
            Q(resident__first_name__icontains=search_query) |
            Q(resident__last_name__icontains=search_query) |
            Q(purpose__icontains=search_query)
        )

    # Official contact number (Barangay Info, then settings)
    admin_phone = get_contact_number()

    # Statistics for dashboard summary cards
    today_count = base_queryset.filter(appt_date=today).count()
    pending_count = base_queryset.filter(status=Appointment.STATUS_PENDING).count()
    approved_count = base_queryset.filter(status=Appointment.STATUS_APPROVED).count()
    completed_count = base_queryset.filter(status=Appointment.STATUS_COMPLETED).count()

    active_health_services = HealthCareService.objects.filter(is_active=True)

    events_data = []
    for apt in base_queryset:
        start_time = "08:30:00" if apt.time_window == Appointment.TIME_SLOT_MORNING else "13:00:00"
        end_time = "11:30:00" if apt.time_window == Appointment.TIME_SLOT_MORNING else "16:30:00"
        title = f"{apt.get_service_title()} - {apt.get_applicant_name()}"
        color = "#2563EB"
        if apt.status == Appointment.STATUS_COMPLETED:
            color = "#16A34A"
        elif apt.status == Appointment.STATUS_REJECTED:
            color = "#DC2626"
        elif apt.status == Appointment.STATUS_PENDING:
            color = "#D97706"
        elif apt.status == Appointment.STATUS_APPROVED:
            color = "#0284C7"

        events_data.append({
            "id": apt.id,
            "title": title,
            "start": f"{apt.appt_date.isoformat()}T{start_time}",
            "end": f"{apt.appt_date.isoformat()}T{end_time}",
            "url": f"/appointments/{apt.id}/",
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {
                "status": apt.get_status_display(),
                "slot": apt.get_time_window_display(),
                "resident": apt.get_applicant_name(),
                "service": apt.get_service_title(),
            }
        })

    # Standard hourly slots for capacity view
    hourly_slots_def = [
        {"slot_id": "08:00-09:00", "time_slot": "morning", "label": "08:00 AM - 09:00 AM", "capacity": 10},
        {"slot_id": "09:00-10:00", "time_slot": "morning", "label": "09:00 AM - 10:00 AM", "capacity": 10},
        {"slot_id": "10:00-11:00", "time_slot": "morning", "label": "10:00 AM - 11:00 AM", "capacity": 10},
        {"slot_id": "11:00-12:00", "time_slot": "morning", "label": "11:00 AM - 12:00 PM", "capacity": 10},
        {"slot_id": "13:00-14:00", "time_slot": "afternoon", "label": "01:00 PM - 02:00 PM", "capacity": 10},
        {"slot_id": "14:00-15:00", "time_slot": "afternoon", "label": "02:00 PM - 03:00 PM", "capacity": 10},
        {"slot_id": "15:00-16:00", "time_slot": "afternoon", "label": "03:00 PM - 04:00 PM", "capacity": 10},
        {"slot_id": "16:00-17:00", "time_slot": "afternoon", "label": "04:00 PM - 05:00 PM", "capacity": 10},
    ]
    date_appointments = Appointment.objects.filter(appt_date=today)
    morning_count = date_appointments.filter(time_window=Appointment.TIME_SLOT_MORNING).count()
    afternoon_count = date_appointments.filter(time_window=Appointment.TIME_SLOT_AFTERNOON).count()
    hourly_slots = []
    for slot in hourly_slots_def:
        current_booked = (morning_count // 4) if slot["time_slot"] == "morning" else (afternoon_count // 4)
        hourly_slots.append({
            "slot_id": slot["slot_id"],
            "time_slot": slot["time_slot"],
            "label": slot["label"],
            "capacity": slot["capacity"],
            "booked": min(current_booked, slot["capacity"]),
            "available": max(0, slot["capacity"] - current_booked),
            "is_full": current_booked >= slot["capacity"],
        })
    calendar_days = [today + timedelta(days=i) for i in range(7)]

    context = {
        'active_tab': active_tab,
        'appointments': queryset,
        'doc_appointments': doc_queryset,
        'health_appointments': health_appointments,
        'health_services_list': health_services_list,
        'active_health_services': active_health_services,
        'status_filter': status_filter,
        'service_filter': service_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'status_choices': Appointment.STATUS_CHOICES,
        'document_types': DocumentType.objects.filter(is_active=True).order_by('order', 'name'),
        'admin_phone': admin_phone,
        'today': today,
        'selected_date': today,
        'hourly_slots': hourly_slots,
        'calendar_days': calendar_days,
        'officers': User.objects.filter(
            Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
        ).distinct().order_by('role', 'last_name'),
        'total_count': queryset.count(),
        'today_count': today_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'completed_count': completed_count,
        'can_approve': check_user_perm(user, 'appointments', 'approve'),
        'calendar_events_json': json.dumps(events_data),
    }
    return render(request, 'appointments/appointment_list.html', context)


@ratelimit(key='user', rate='email_validation', methods=('GET', 'POST'))
def api_validate_email_view(request):
    """
    Validates email format, domain existence, disposable status, and Abstract API status.
    Logged-in users only: the external Abstract API is never called for anonymous requests.
    """
    if not request.user.is_authenticated:
        return json_login_required(request)
    email = request.GET.get('email', '').strip()
    if not email:
        return JsonResponse({'valid': False, 'message': 'Email address is required.'}, status=400)
    is_valid, message, details = validate_email_address(email)
    return JsonResponse({'valid': is_valid, 'message': message, 'details': details})


@ratelimit(key='user', rate='public_booking')
def public_appointment_book_view(request):
    """
    Public modern popup modal booking endpoint.
    Handles booking submissions from landing page and appointment module.
    Validates required fields: First Name, Last Name, Middle Name, Age, Address, Email (Abstract API), Phone (11 digits).
    Dispatches confirmation email and returns JSON response with admin contact info.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST method required.'}, status=405)

    # Authentication first: never call the external email API for anonymous users.
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error',
            'requires_login': True,
            'login_url': '/accounts/login/?next=/#bookAppointmentModal',
            'message': 'Please log in or register before booking an appointment.'
        }, status=401)

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    middle_name = request.POST.get('middle_name', '').strip()
    age_str = request.POST.get('age', '').strip()
    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone_number', '').strip()
    category = request.POST.get('category', Appointment.CATEGORY_DOCUMENT).strip()
    document_type_value = request.POST.get('document_type', '').strip()
    healthcare_service_id = request.POST.get('healthcare_service', '').strip()
    appt_date_str = request.POST.get('appt_date', '').strip()
    time_window = request.POST.get('time_window', Appointment.TIME_SLOT_MORNING).strip()
    purpose = request.POST.get('purpose', '').strip()

    # Validation: required fields
    errors = {}
    if not first_name:
        errors['first_name'] = 'First Name is required.'
    if not last_name:
        errors['last_name'] = 'Last Name is required.'
    # Middle name is optional per specification

    if not age_str:
        errors['age'] = 'Age is required.'
    else:
        try:
            age = int(age_str)
            if age < 1 or age > 125:
                errors['age'] = 'Please enter a valid age.'
        except ValueError:
            errors['age'] = 'Age must be a valid number.'

    if not address:
        errors['address'] = 'Residential address is required.'

    # Phone validation: exactly 11 digits, 09XXXXXXXXX (no dashes or spaces)
    if not phone:
        errors['phone_number'] = 'Phone number is required.'
    else:
        try:
            validate_ph_mobile(phone)
        except ValidationError as exc:
            errors['phone_number'] = exc.messages[0]

    # Email validation via Abstract API validator
    if not email:
        errors['email'] = 'Email address is required.'
    else:
        is_email_valid, email_msg, _ = validate_email_address(email)
        if not is_email_valid:
            errors['email'] = email_msg

    # Appointment date and time window validation
    if not appt_date_str:
        errors['appt_date'] = 'Please select an appointment date.'
    else:
        try:
            pref_date = date.fromisoformat(appt_date_str)
            if pref_date < timezone.localdate():
                errors['appt_date'] = 'Appointment date cannot be in the past.'
        except Exception:
            errors['appt_date'] = 'Invalid date format.'
    if time_window not in dict(Appointment.TIME_SLOT_CHOICES):
        errors['time_window'] = 'Please select a valid time window.'

    if category == Appointment.CATEGORY_HEALTHCARE:
        if not purpose:
            purpose = 'Health Service Consultation'
    else:
        if not purpose:
            errors['purpose'] = 'Purpose of appointment or consultation notes are required.'

    # Category and subservice validation
    healthcare_service = None
    document_type = None
    if category == Appointment.CATEGORY_HEALTHCARE:
        if not healthcare_service_id:
            errors['healthcare_service'] = 'Please select a health care service.'
        else:
            try:
                healthcare_service = HealthCareService.objects.get(id=healthcare_service_id, is_active=True)
            except HealthCareService.DoesNotExist:
                errors['healthcare_service'] = 'Selected health care service is not active or available.'
    else:
        category = Appointment.CATEGORY_DOCUMENT
        try:
            document_type = resolve_document_type(document_type_value)
        except ValueError as exc:
            document_type = None
            errors['document_type'] = str(exc)
        else:
            if document_type is None:
                errors['document_type'] = 'No document types are currently available.'

    if errors:
        return JsonResponse({'status': 'error', 'errors': errors, 'message': 'Please correct the highlighted fields.'}, status=400)

    try:
        data = request.POST.copy()
        data['category'] = category
        data['document_type'] = document_type.pk if document_type else ''
        data['healthcare_service'] = healthcare_service_id
        data['appt_date'] = appt_date_str
        data['time_window'] = time_window
        data['purpose'] = purpose
        data['address'] = address
        data['age'] = age_str
        appointment = book_appointment_service(request.user, data)
    except (ValueError, PermissionDenied) as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    # Official contact number (Barangay Info, then settings)
    admin_phone = get_contact_number()

    return JsonResponse({
        'status': 'ok',
        'ref_number': appointment.reference_no,
        'appointment_id': appointment.id,
        'service_title': appointment.get_service_title(),
        'scheduled_date': appointment.appt_date.strftime('%B %d, %Y'),
        'time_slot': appointment.get_time_window_display(),
        'applicant_name': appointment.get_applicant_name(),
        'applicant_email': appointment.get_applicant_email(),
        'applicant_phone': appointment.get_applicant_phone(),
        'admin_phone': admin_phone,
        'message': f"Wait for the email sent for approved your appointment date. We will notify via email please keep track on you email. Thank you if you have any question please contact {admin_phone}."
    })


def appointment_create_view(request):
    """Fallback traditional full-page appointment form view."""
    if not request.user.is_authenticated:
        return redirect('accounts:signup')
    initial_data = {}
    doc_preset = request.GET.get('doc', '').strip()
    if doc_preset:
        try:
            preset_type = resolve_document_type(doc_preset)
        except ValueError:
            preset_type = None
        if preset_type is not None:
            initial_data['document_type'] = preset_type.pk
            initial_data['category'] = Appointment.CATEGORY_DOCUMENT

    cat_preset = request.GET.get('cat')
    if cat_preset in [Appointment.CATEGORY_DOCUMENT, Appointment.CATEGORY_HEALTHCARE]:
        initial_data['category'] = cat_preset

    service_id = request.GET.get('service_id')
    if service_id:
        initial_data['healthcare_service'] = service_id
        initial_data['category'] = Appointment.CATEGORY_HEALTHCARE

    date_preset = request.GET.get('date')
    if date_preset:
        initial_data['appt_date'] = date_preset
    slot_preset = request.GET.get('slot')
    if slot_preset in dict(Appointment.TIME_SLOT_CHOICES):
        initial_data['time_window'] = slot_preset

    if request.method == 'POST':
        form = AppointmentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            booking_data = form.cleaned_data.copy()
            if request.FILES.get('supporting_id'):
                booking_data['supporting_id'] = request.FILES.get('supporting_id')
            try:
                appointment = book_appointment_service(request.user, booking_data, request=request)
            except Exception as e:
                message = public_error_message(e)
                if message is None:
                    logger.exception('Appointment booking failed for user %s', request.user.pk)
                    message = GENERIC_ERROR_MESSAGE
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': message}, status=400)
                messages.error(request, message)
                return render(request, 'appointments/appointment_form.html', {
                    'form': form,
                    'healthcare_services': HealthCareService.objects.filter(is_active=True),
                })

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'appointment_id': appointment.id,
                    'service': appointment.get_service_title(),
                    'message': f"Your appointment request for {appointment.get_service_title()} has been booked successfully!",
                    'redirect_url': f"/appointments/{appointment.id}/"
                })

            messages.success(request, f"Your request for {appointment.get_service_title()} has been submitted successfully!")
            return redirect('appointments:detail', pk=appointment.id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    else:
        form = AppointmentCreateForm(initial=initial_data)

    return render(request, 'appointments/appointment_form.html', {
        'form': form,
        'healthcare_services': HealthCareService.objects.filter(is_active=True),
    })


@require_perm('appointments', 'manage_services')
def healthcare_service_list_view(request):
    services = HealthCareService.objects.all().order_by('-is_active', 'name')
    form = HealthCareServiceForm()

    if request.method == 'POST' and 'create_service' in request.POST:
        form = HealthCareServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Health Care Service '{service.name}' created successfully!")
            return redirect('appointments:service_list')

    return render(request, 'appointments/healthcare_services.html', {
        'services': services,
        'form': form,
    })


@require_perm('appointments', 'manage_services')
def healthcare_service_update_view(request, pk):
    service = get_object_or_404(HealthCareService, pk=pk)
    if request.method == 'POST':
        form = HealthCareServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Health Care Service '{service.name}' updated successfully.")
            referer = request.META.get('HTTP_REFERER')
            if referer and 'appointments/services' not in referer:
                return redirect(referer)
            return redirect('appointments:service_list')
    else:
        form = HealthCareServiceForm(instance=service)

    return render(request, 'appointments/healthcare_service_form.html', {
        'form': form,
        'service': service,
        'title': f"Edit Health Service: {service.name}",
    })


@require_perm('appointments', 'manage_services')
def healthcare_service_delete_view(request, pk):
    service = get_object_or_404(HealthCareService, pk=pk)
    if request.method == 'POST':
        svc_name = service.name
        service.delete()
        messages.success(request, f"Health Care Service '{svc_name}' deleted successfully.")
        referer = request.META.get('HTTP_REFERER')
        if referer and 'appointments/services' not in referer:
            return redirect(referer)
        return redirect('appointments:service_list')

    return render(request, 'appointments/healthcare_service_confirm_delete.html', {
        'service': service,
    })


@login_required
def health_schedule_resident_view(request):
    """
    Read-only Health Schedule page for residents.
    Requires login and an active account (not public).
    Displays free active services only, upcoming schedule dates, time windows, and remaining slots.
    """
    if request.user.status != User.STATUS_ACTIVE:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only active accounts may view the health schedule.")

    today = timezone.localdate()
    schedules = HealthSchedule.objects.filter(
        health_service__is_active=True,
        health_service__is_free=True,
        service_date__gte=today
    ).select_related('health_service').order_by('service_date', 'time_window')

    schedule_data = []
    active_statuses = [
        Appointment.STATUS_PENDING,
        Appointment.STATUS_APPROVED,
    ]
    for s in schedules:
        booked = Appointment.objects.filter(
            healthcare_service=s.health_service,
            appt_date=s.service_date,
            time_window=s.time_window,
            status__in=active_statuses
        ).count()
        remaining = max(0, s.capacity - booked)
        schedule_data.append({
            'schedule': s,
            'service_name': s.health_service.name,
            'description': s.health_service.description,
            'date': s.service_date,
            'time_window_display': s.get_time_window_display(),
            'capacity': s.capacity,
            'booked': booked,
            'remaining_slots': remaining,
            'is_available': remaining > 0,
        })

    return render(request, 'appointments/health_schedule.html', {
        'schedules': schedule_data,
        'title': 'Health Center Schedule & Slot Availability',
    })


@require_perm('health_center', 'manage_schedule')
def health_schedule_manage_view(request):
    """
    Staff management for Health Center Schedules.
    Protected with permission and service-area scope check ('Health').
    """
    if not can_manage_service_area(request.user, 'Health'):
        raise PermissionDenied("You do not have jurisdiction over Health Center service schedules.")

    today = timezone.localdate()
    if request.method == 'POST' and 'create_schedule' in request.POST:
        svc_id = request.POST.get('health_service_id')
        svc_date_str = request.POST.get('service_date')
        time_win = request.POST.get('time_window', 'morning')
        cap_str = request.POST.get('capacity', '20')

        if svc_id and svc_date_str:
            svc = get_object_or_404(HealthCareService, id=svc_id)
            svc_date = date.fromisoformat(svc_date_str)
            cap = int(cap_str) if cap_str.isdigit() else 20
            HealthSchedule.objects.update_or_create(
                health_service=svc,
                service_date=svc_date,
                time_window=time_win,
                defaults={'capacity': cap}
            )
            messages.success(request, f"Schedule for {svc.name} on {svc_date} ({time_win}) saved.")
            return redirect('appointments:schedule_manage')

    schedules = HealthSchedule.objects.filter(
        service_date__gte=today
    ).select_related('health_service').order_by('service_date', 'time_window')
    health_services = HealthCareService.objects.filter(is_active=True)

    return render(request, 'appointments/health_schedule_manage.html', {
        'schedules': schedules,
        'health_services': health_services,
    })


@require_perm('health_center', 'manage_schedule')
def health_schedule_edit_view(request, pk):
    """
    Staff edit for a specific HealthSchedule slot.
    Protected with permission and service-area scope check ('Health').
    """
    if not can_manage_service_area(request.user, 'Health'):
        raise PermissionDenied("You do not have jurisdiction over Health Center service schedules.")

    schedule = get_object_or_404(HealthSchedule, pk=pk)
    if request.method == 'POST':
        cap_str = request.POST.get('capacity', str(schedule.capacity))
        if cap_str.isdigit():
            schedule.capacity = int(cap_str)
            schedule.save()
            messages.success(request, f"Schedule updated for {schedule.health_service.name}.")
            return redirect('appointments:schedule_manage')

    return render(request, 'appointments/health_schedule_form.html', {
        'schedule': schedule,
    })


@require_perm('health_center', 'manage_schedule')
def health_schedule_delete_view(request, pk):
    """
    Staff delete for a specific HealthSchedule slot.
    Protected with permission and service-area scope check ('Health').
    """
    if not can_manage_service_area(request.user, 'Health'):
        raise PermissionDenied("You do not have jurisdiction over Health Center service schedules.")

    schedule = get_object_or_404(HealthSchedule, pk=pk)
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, "Schedule slot removed successfully.")
        return redirect('appointments:schedule_manage')

    return render(request, 'appointments/health_schedule_confirm_delete.html', {
        'schedule': schedule,
    })


def api_services_view(request):
    """
    Load services for category, date and window:
    GET /appointments/api/services/?category=&date=&window=
    Reads health_schedule + health_service (only free, with capacity) or document_type.
    """
    category = request.GET.get('category', '').strip()
    date_str = request.GET.get('date', '').strip()
    window = request.GET.get('window', '').strip()

    parsed_date = None
    if date_str:
        try:
            parsed_date = date.fromisoformat(date_str)
        except ValueError:
            parsed_date = None

    # Filter only active and free health services
    health_services_qs = HealthCareService.objects.filter(is_active=True, is_free=True)
    unique_health_services = []
    seen_names = set()

    for svc in health_services_qs:
        clean_name = svc.name.strip()
        if clean_name.lower() in seen_names:
            continue
        seen_names.add(clean_name.lower())

        # Check capacity if date is provided
        has_capacity = True
        capacity = 25
        if parsed_date:
            sched = svc.schedules.filter(service_date=parsed_date).first()
            if not sched:
                sched = svc.schedules.filter(service_date__isnull=True).first()
            if sched:
                capacity = sched.capacity

            booked_qs = Appointment.objects.filter(
                healthcare_service=svc,
                appt_date=parsed_date,
                status__in=[
                    Appointment.STATUS_PENDING,
                    Appointment.STATUS_APPROVED,
                ]
            )
            if window in ['morning', 'afternoon']:
                booked_qs = booked_qs.filter(time_window=window)

            if booked_qs.count() >= capacity:
                has_capacity = False

        if has_capacity:
            unique_health_services.append({
                'id': svc.id,
                'name': svc.name,
                'display_name': f"{svc.name} (Free)",
                'is_free': True,
                'description': svc.description or '',
                'available_date': svc.available_date or 'Everyday',
                'available_time': svc.available_time or '8:00 AM - 5:00 PM',
            })

    documents = [
        {
            'id': dt.id,
            'code': dt.code,
            'name': dt.name,
            'price': float(dt.fee),
            'requirements': dt.requirements_needed,
        }
        for dt in DocumentType.objects.filter(is_active=True).order_by('order', 'name')
    ]
    return JsonResponse({
        'status': 'ok',
        'category': category,
        'date': date_str,
        'window': window,
        'health_services': unique_health_services,
        'documents': documents
    })


def api_slots_view(request):
    """
    Check slot: GET /appointments/api/slots/?date=&window=
    Counts approved/pending rows in appointment against capacity.
    Applies weekend, past-date, and 60-day rules, returning counts only.
    """
    date_str = request.GET.get('date', '').strip()
    window = request.GET.get('window', 'morning').strip()
    service_id = request.GET.get('service_id', '').strip()

    if not date_str:
        return JsonResponse({'error': 'Date is required.'}, status=400)

    try:
        pref_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format.'}, status=400)

    today = timezone.localdate()
    if pref_date < today:
        return JsonResponse({
            'error': 'Appointment date cannot be in the past.',
            'capacity': 0,
            'booked': 0,
            'available_slots': 0,
            'is_available': False
        }, status=400)

    if pref_date > today + timedelta(days=60):
        return JsonResponse({
            'error': 'Appointment date cannot be more than 60 days in advance.',
            'capacity': 0,
            'booked': 0,
            'available_slots': 0,
            'is_available': False
        }, status=400)

    if pref_date.weekday() in (5, 6):
        return JsonResponse({
            'error': 'Appointments are only available on weekdays (Monday to Friday).',
            'capacity': 0,
            'booked': 0,
            'available_slots': 0,
            'is_available': False
        }, status=400)

    total_capacity = 30
    booked_qs = Appointment.objects.filter(
        appt_date=pref_date,
        status__in=[
            Appointment.STATUS_PENDING,
            Appointment.STATUS_APPROVED,
        ]
    )
    if window in ['morning', 'afternoon']:
        booked_qs = booked_qs.filter(time_window=window)

    if service_id and service_id.isdigit():
        booked_qs = booked_qs.filter(healthcare_service_id=int(service_id))
        sched = HealthSchedule.objects.filter(health_service_id=int(service_id), service_date=pref_date, time_window=window).first()
        if sched:
            total_capacity = sched.capacity

    booked_count = booked_qs.count()
    remaining_slots = max(0, total_capacity - booked_count)

    # Return counts only
    return JsonResponse({
        'capacity': total_capacity,
        'booked': booked_count,
        'available_slots': remaining_slots,
        'is_available': (remaining_slots > 0)
    })


@require_perm('appointments', 'approve')
def appointment_approve_view(request, pk):
    """POST /appointments/<id>/approve/ -> services.approve_appointment_service()"""
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        approve_appointment_service(appointment, request.user, request)
        messages.success(request, f"Appointment {appointment.reference_no} approved successfully and notification sent.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:detail', kwargs={'pk': pk}))


@require_perm('appointments', 'reject')
def appointment_reject_view(request, pk):
    """POST /appointments/<id>/reject/ (reason required) -> services.reject_appointment_service()"""
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', '').strip() or request.POST.get('admin_notes', '').strip()
        if not reason:
            reason = "Document requirements incomplete or invalid schedule."
        reject_appointment_service(appointment, request.user, reason, request)
        messages.warning(request, f"Appointment {appointment.reference_no} was rejected. Reason: {reason}")
    return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:detail', kwargs={'pk': pk}))


@require_perm('appointments', 'complete')
def appointment_complete_view(request, pk):
    """POST /appointments/<id>/complete/ -> sets completed, creates record, sends Email 5"""
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        complete_appointment_service(appointment, request.user, request)
        messages.success(request, f"Appointment {appointment.reference_no} marked as completed.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:detail', kwargs={'pk': pk}))


@require_perm('appointments', 'no_show')
def appointment_noshow_view(request, pk):
    """POST /appointments/<id>/noshow/ -> noshow_appointment_service()"""
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        noshow_appointment_service(appointment, request.user, request)
        messages.info(request, f"Appointment {appointment.reference_no} marked as No-Show.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:detail', kwargs={'pk': pk}))


@resident_forbidden
def appointment_edit_view(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        try:
            update_appointment_service(appointment, request.user, request.POST, request=request)
            messages.success(request, f"Appointment record {appointment.reference_no or f'APT-{appointment.id:04d}'} updated successfully.")
        except Exception as e:
            message = public_error_message(e)
            if message is None:
                logger.exception('Appointment %s update failed', appointment.pk)
                message = GENERIC_ERROR_MESSAGE
            messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:list'))

    return redirect('appointments:detail', pk=pk)


@login_required
def appointment_delete_view(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    user = request.user
    can_delete = False
    if user.is_admin_user or user.is_staff_user or getattr(user, 'is_superuser', False):
        can_delete = True
    elif hasattr(user, 'resident_profile') and appointment.resident == user.resident_profile:
        can_delete = True

    if not can_delete:
        messages.error(request, "You do not have permission to delete this appointment.")
        return redirect('appointments:list')

    if request.method == 'POST':
        apt_ref = appointment.reference_no or f"APT-{appointment.id:04d}"
        appointment.delete()
        messages.success(request, f"Appointment {apt_ref} has been deleted successfully.")
        return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:list'))

    messages.warning(request, "Invalid request method for deleting appointment.")
    return redirect('appointments:list')


@login_required
def appointment_detail_view(request, pk):
    user = request.user
    appointment = appointment_selectors.get_viewable_appointment(user, pk)

    admin_phone = get_contact_number()

    status_form = None
    if user.is_admin_user or user.is_staff_user:
        if request.method == 'POST' and 'update_status' in request.POST:
            status_form = AppointmentStatusUpdateForm(request.POST, instance=appointment)
            if status_form.is_valid():
                updated_apt = status_form.save(commit=False)
                updated_apt.processed_by = user
                updated_apt.save()

                status_display = updated_apt.get_status_display()
                notif_msg = f"Your request for {updated_apt.get_service_title()} is now: {status_display}."
                if updated_apt.admin_notes:
                    notif_msg += f" Note: {updated_apt.admin_notes}"

                # Send in-app notification if resident user linked
                if updated_apt.resident:
                    Notification.objects.create(
                        recipient=updated_apt.resident,
                        sender=user,
                        title=f"Appointment Status: {status_display}",
                        message=notif_msg,
                        notification_type=Notification.TYPE_APPOINTMENT,
                        link_url=f"/appointments/{updated_apt.id}/"
                    )

                    try:
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            f"user_{updated_apt.resident.id}",
                            {
                                "type": "send_notification",
                                "title": f"Document Update: {status_display}",
                                "message": notif_msg,
                                "notification_type": "appointment",
                                "link_url": f"/appointments/{updated_apt.id}/",
                            }
                        )
                    except Exception:
                        pass

                # Send email notification to applicant
                target_email = updated_apt.get_applicant_email()
                if target_email:
                    email_subj = f"Appointment Update: {status_display} [{updated_apt.get_service_title()}]"
                    email_body = (
                        f"Dear {updated_apt.get_applicant_name()},\n\n"
                        f"Your appointment request for '{updated_apt.get_service_title()}' on "
                        f"{updated_apt.appt_date.strftime('%B %d, %Y')} ({updated_apt.get_time_window_display()}) "
                        f"has been updated to: {status_display.upper()}.\n\n"
                    )
                    if updated_apt.admin_notes:
                        email_body += f"Administrative Remarks / Instructions:\n{updated_apt.admin_notes}\n\n"

                    if updated_apt.status == Appointment.STATUS_APPROVED:
                        email_body += (
                            f"Your appointment date has been officially APPROVED! Please visit the Barangay Hall on your scheduled slot.\n\n"
                        )

                    email_body += (
                        f"Thank you if you have any question please contact {admin_phone}.\n\n"
                        f"Barangay Administration"
                    )
                    send_mail(email_subj, email_body, settings.DEFAULT_FROM_EMAIL, [target_email], fail_silently=True)

                messages.success(request, f"Appointment status updated to '{status_display}' and notification sent.")
                return redirect('appointments:detail', pk=appointment.id)
        else:
            status_form = AppointmentStatusUpdateForm(instance=appointment)

    context = {
        'appointment': appointment,
        'status_form': status_form,
        'status_steps': appointment_selectors.status_steps(appointment),
        'allowed_actions': appointment_selectors.allowed_actions(appointment, user),
        'admin_phone': admin_phone,
    }
    return render(request, 'appointments/appointment_detail.html', context)


@login_required
def appointment_supporting_id_view(request, pk):
    """
    GET /appointments/<id>/supporting-id/ streams the private supporting document.
    Same access rule as the detail page (owner resident, admin/kapitan, in-scope staff).
    """
    appointment = appointment_selectors.get_viewable_appointment(request.user, pk, strict_scope=True)
    if not appointment.supporting_id:
        raise Http404("No supporting document was uploaded for this appointment.")
    try:
        handle = appointment.supporting_id.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404("Supporting document file not found.")
    name = appointment.supporting_id.name
    content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    response = FileResponse(handle, content_type=content_type, as_attachment=False,
                            filename=os.path.basename(name))
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    log_activity(
        actor=request.user,
        action='view',
        action_type='AppointmentSupportingID',
        target_id=str(appointment.pk),
        target_name=appointment.reference_no or f'APT-{appointment.pk:04d}',
        details=f"Supporting document of appointment {appointment.pk} viewed by {request.user.username}.",
        request=request,
    )
    return response