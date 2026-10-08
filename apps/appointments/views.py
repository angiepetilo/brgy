from datetime import date, timedelta
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User
from apps.appointments.models import Appointment, HealthCareService, IssuedDocumentLog, DocumentType
from apps.appointments.forms import AppointmentCreateForm, AppointmentStatusUpdateForm, HealthCareServiceForm
from apps.appointments.email_validator import validate_email_address
from apps.chat.models import Notification


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
            doc_type = custom_doc_name or "Custom Document"
            # Persist custom document type in catalog
            DocumentType.objects.get_or_create(
                name=doc_type,
                defaults={'requirements_needed': reqs, 'is_active': True}
            )
        elif not doc_type:
            doc_type = Appointment.DOC_CLEARANCE

        officer_id = request.POST.get('officer_in_charge')
        officer = User.objects.filter(id=officer_id).first() if officer_id else None
        officer_name = officer.get_full_name() if officer else "Barangay Administration"

        Appointment.objects.create(
            resident=user if user.role == User.ROLE_RESIDENT else None,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=doc_type,
            purpose=f"Requirements: {reqs}. Submitted to: {officer_name}",
            preferred_date=timezone.now().date(),
            preferred_time_slot=Appointment.TIME_SLOT_MORNING,
            status=Appointment.STATUS_SUBMITTED,
            applicant_first_name=user.first_name,
            applicant_last_name=user.last_name,
            applicant_email=user.email,
            applicant_phone=user.phone_number,
        )
        messages.success(request, f"Document request for '{doc_type}' submitted to {officer_name} successfully!")
        return redirect(f"{reverse('appointments:list')}?tab=documents")

    if user.is_admin_user or user.is_kapitan_user:
        base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'processed_by').all()
    else:
        base_queryset = Appointment.objects.select_related('resident', 'healthcare_service', 'processed_by').filter(
            Q(resident=user) | Q(applicant_email__iexact=user.email)
        )

    queryset = base_queryset
    today = timezone.now().date()

    # Date filter: Today, Yesterday, Tomorrow
    if date_filter == 'today':
        queryset = queryset.filter(preferred_date=today)
    elif date_filter == 'yesterday':
        queryset = queryset.filter(preferred_date=today - timedelta(days=1))
    elif date_filter == 'tomorrow':
        queryset = queryset.filter(preferred_date=today + timedelta(days=1))

    # Status filter
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    # Service filter
    if service_filter:
        if service_filter.startswith('doc_'):
            queryset = queryset.filter(category=Appointment.CATEGORY_DOCUMENT, document_type=service_filter[4:])
        elif service_filter.startswith('health_'):
            queryset = queryset.filter(category=Appointment.CATEGORY_HEALTHCARE, healthcare_service_id=service_filter[7:])
        elif service_filter in dict(Appointment.DOCUMENT_CHOICES):
            queryset = queryset.filter(document_type=service_filter)
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

    # Admin phone number lookup
    admin_user = User.objects.filter(role=User.ROLE_ADMIN).first() or User.objects.filter(is_superuser=True).first()
    admin_phone = admin_user.phone_number if (admin_user and admin_user.phone_number) else '0917-111-2222'

    # Statistics for dashboard summary cards
    today_count = base_queryset.filter(preferred_date=today).count()
    pending_count = base_queryset.filter(status=Appointment.STATUS_SUBMITTED).count()
    approved_count = base_queryset.filter(status=Appointment.STATUS_APPROVED_SCHEDULED).count()
    completed_count = base_queryset.filter(status=Appointment.STATUS_COMPLETED).count()

    active_health_services = HealthCareService.objects.filter(is_active=True)

    events_data = []
    for apt in base_queryset:
        start_time = "08:30:00" if apt.preferred_time_slot == Appointment.TIME_SLOT_MORNING else "13:00:00"
        end_time = "11:30:00" if apt.preferred_time_slot == Appointment.TIME_SLOT_MORNING else "16:30:00"
        title = f"{apt.get_service_title()} - {apt.get_applicant_name()}"
        color = "#2563EB"
        if apt.status == Appointment.STATUS_COMPLETED:
            color = "#16A34A"
        elif apt.status == Appointment.STATUS_REJECTED:
            color = "#DC2626"
        elif apt.status == Appointment.STATUS_UNDER_REVIEW:
            color = "#D97706"
        elif apt.status == Appointment.STATUS_APPROVED_SCHEDULED:
            color = "#0284C7"
        elif apt.status == Appointment.STATUS_READY_FOR_PICKUP:
            color = "#7C3AED"

        events_data.append({
            "id": apt.id,
            "title": title,
            "start": f"{apt.preferred_date.isoformat()}T{start_time}",
            "end": f"{apt.preferred_date.isoformat()}T{end_time}",
            "url": f"/appointments/{apt.id}/",
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {
                "status": apt.get_status_display(),
                "slot": apt.get_preferred_time_slot_display(),
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
    date_appointments = Appointment.objects.filter(preferred_date=today)
    morning_count = date_appointments.filter(preferred_time_slot=Appointment.TIME_SLOT_MORNING).count()
    afternoon_count = date_appointments.filter(preferred_time_slot=Appointment.TIME_SLOT_AFTERNOON).count()
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
        'doc_choices': Appointment.DOCUMENT_CHOICES,
        'document_types': DocumentType.objects.filter(is_active=True).order_by('name'),
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
        'calendar_events_json': json.dumps(events_data),
    }
    return render(request, 'appointments/appointment_list.html', context)


def api_validate_email_view(request):
    """
    Validates email format, domain existence, disposable status, and Abstract API status.
    """
    email = request.GET.get('email', '').strip()
    if not email:
        return JsonResponse({'valid': False, 'message': 'Email address is required.'}, status=400)
    is_valid, message, details = validate_email_address(email)
    return JsonResponse({'valid': is_valid, 'message': message, 'details': details})


def public_appointment_book_view(request):
    """
    Public modern popup modal booking endpoint.
    Handles booking submissions from landing page and appointment module.
    Validates required fields: First Name, Last Name, Middle Name, Age, Address, Email (Abstract API), Phone (11 digits).
    Dispatches confirmation email and returns JSON response with admin contact info.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST method required.'}, status=405)

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    middle_name = request.POST.get('middle_name', '').strip()
    age_str = request.POST.get('age', '').strip()
    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone_number', '').strip()
    category = request.POST.get('category', Appointment.CATEGORY_DOCUMENT).strip()
    document_type = request.POST.get('document_type', Appointment.DOC_CLEARANCE).strip()
    healthcare_service_id = request.POST.get('healthcare_service', '').strip()
    preferred_date_str = request.POST.get('preferred_date', '').strip()
    preferred_time_slot = request.POST.get('preferred_time_slot', Appointment.TIME_SLOT_MORNING).strip()
    purpose = request.POST.get('purpose', '').strip()

    # Validation: required fields
    errors = {}
    if not first_name:
        errors['first_name'] = 'First Name is required.'
    if not last_name:
        errors['last_name'] = 'Last Name is required.'
    if not middle_name:
        errors['middle_name'] = 'Middle Name is required.'

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

    # Phone validation: strictly 11 digits
    clean_phone = re.sub(r'[^0-9]', '', phone)
    if not clean_phone:
        errors['phone_number'] = 'Phone number is required.'
    elif len(clean_phone) != 11:
        errors['phone_number'] = f'Phone number must be exactly 11 digits (e.g. 09171234567). Current digits: {len(clean_phone)}.'
    elif not clean_phone.startswith('09'):
        errors['phone_number'] = 'Mobile number must start with 09 (e.g. 09XXXXXXXXX).'

    # Email validation via Abstract API validator
    if not email:
        errors['email'] = 'Email address is required.'
    else:
        is_email_valid, email_msg, _ = validate_email_address(email)
        if not is_email_valid:
            errors['email'] = email_msg

    # Preferred date validation
    if not preferred_date_str:
        errors['preferred_date'] = 'Please select an appointment date.'
    else:
        try:
            pref_date = date.fromisoformat(preferred_date_str)
            if pref_date < timezone.now().date():
                errors['preferred_date'] = 'Appointment date cannot be in the past.'
        except Exception:
            errors['preferred_date'] = 'Invalid date format.'

    if not purpose:
        errors['purpose'] = 'Purpose of appointment or consultation notes are required.'

    # Category and subservice validation
    healthcare_service = None
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
        valid_doc_types = [code for code, _ in Appointment.DOCUMENT_CHOICES]
        if document_type not in valid_doc_types:
            document_type = Appointment.DOC_CLEARANCE

    if errors:
        return JsonResponse({'status': 'error', 'errors': errors, 'message': 'Please correct the highlighted fields.'}, status=400)

    # Resident user linking:
    # Resident registrations go to Resident Module (/accounts/signup/).
    # Appointments go to Appointment Module (/appointments/).
    # If authenticated, link to current user; if matching an existing resident account, link to it.
    # Otherwise, keep resident as None and retain applicant details directly on the Appointment model.
    resident = None
    if request.user.is_authenticated:
        resident = request.user
    else:
        existing_user = User.objects.filter(email__iexact=email).first() or User.objects.filter(phone_number=clean_phone).first()
        if existing_user:
            resident = existing_user

    # Create Appointment
    appointment = Appointment.objects.create(
        resident=resident,
        applicant_first_name=first_name,
        applicant_middle_name=middle_name,
        applicant_last_name=last_name,
        applicant_age=int(age_str),
        applicant_address=address,
        applicant_email=email,
        applicant_phone=clean_phone,
        category=category,
        document_type=document_type if category == Appointment.CATEGORY_DOCUMENT else '',
        healthcare_service=healthcare_service if category == Appointment.CATEGORY_HEALTHCARE else None,
        preferred_date=date.fromisoformat(preferred_date_str),
        preferred_time_slot=preferred_time_slot,
        purpose=purpose,
        supporting_id=request.FILES.get('supporting_id'),
        status=Appointment.STATUS_SUBMITTED
    )

    # Admin phone lookup
    admin_user = User.objects.filter(role=User.ROLE_ADMIN).first() or User.objects.filter(is_superuser=True).first()
    admin_phone = admin_user.phone_number if (admin_user and admin_user.phone_number) else '0917-111-2222'

    # Send confirmation email to applicant
    email_subject = f"Appointment Request Submitted: {appointment.get_service_title()} [Ref #APT-{appointment.id:04d}]"
    email_body = (
        f"Dear {first_name} {last_name},\n\n"
        f"Thank you for submitting your appointment request with Barangay e-Portal.\n\n"
        f"Request Summary:\n"
        f"• Reference Number: #APT-{appointment.id:04d}\n"
        f"• Service: {appointment.get_service_title()}\n"
        f"• Scheduled Date: {appointment.preferred_date.strftime('%B %d, %Y')}\n"
        f"• Time Window: {appointment.get_preferred_time_slot_display()}\n\n"
        f"Wait for the email sent for approved your appointment date. We will notify via email please keep track on you email.\n\n"
        f"Thank you if you have any question please contact {admin_phone}.\n\n"
        f"Barangay Administration"
    )
    send_mail(email_subject, email_body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)

    return JsonResponse({
        'status': 'ok',
        'ref_number': f"#APT-{appointment.id:04d}",
        'appointment_id': appointment.id,
        'service_title': appointment.get_service_title(),
        'scheduled_date': appointment.preferred_date.strftime('%B %d, %Y'),
        'time_slot': appointment.get_preferred_time_slot_display(),
        'applicant_name': appointment.get_applicant_name(),
        'applicant_email': email,
        'applicant_phone': clean_phone,
        'admin_phone': admin_phone,
        'message': f"Wait for the email sent for approved your appointment date. We will notify via email please keep track on you email. Thank you if you have any question please contact {admin_phone}."
    })


def appointment_create_view(request):
    """Fallback traditional full-page appointment form view."""
    if not request.user.is_authenticated:
        return redirect('accounts:signup')
    initial_data = {}
    doc_preset = request.GET.get('doc')
    if doc_preset in dict(Appointment.DOCUMENT_CHOICES):
        initial_data['document_type'] = doc_preset
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
        initial_data['preferred_date'] = date_preset
    slot_preset = request.GET.get('slot')
    if slot_preset in dict(Appointment.TIME_SLOT_CHOICES):
        initial_data['preferred_time_slot'] = slot_preset

    if request.method == 'POST':
        form = AppointmentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.resident = request.user
            appointment.status = Appointment.STATUS_SUBMITTED
            appointment.save()

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


@login_required
def healthcare_service_list_view(request):
    if not (request.user.is_admin_user or request.user.is_kapitan_user):
        messages.error(request, "Permission denied. Admin privileges required.")
        return redirect('accounts:dashboard')

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


@login_required
def healthcare_service_update_view(request, pk):
    if not (request.user.is_admin_user or request.user.is_kapitan_user):
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')

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


@login_required
def healthcare_service_delete_view(request, pk):
    if not (request.user.is_admin_user or request.user.is_kapitan_user):
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')

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


def api_services_view(request):
    health_services = list(HealthCareService.objects.filter(is_active=True).values('id', 'name', 'description'))
    documents = [
        {'id': code, 'name': label} for code, label in Appointment.DOCUMENT_CHOICES
    ]
    return JsonResponse({
        'status': 'ok',
        'health_services': health_services,
        'documents': documents
    })


@login_required
def appointment_edit_view(request, pk):
    user = request.user
    if not (user.is_admin_user or user.is_kapitan_user):
        messages.error(request, "Permission denied. Admin privileges required.")
        return redirect('appointments:list')

    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        preferred_date = request.POST.get('preferred_date')
        preferred_time_slot = request.POST.get('preferred_time_slot')
        status = request.POST.get('status')
        purpose = request.POST.get('purpose')
        admin_notes = request.POST.get('admin_notes', '')

        if preferred_date:
            appointment.preferred_date = preferred_date
        if preferred_time_slot:
            appointment.preferred_time_slot = preferred_time_slot
        if status:
            appointment.status = status
            appointment.processed_by = user
        if purpose is not None:
            appointment.purpose = purpose
        appointment.admin_notes = admin_notes
        appointment.save()

        messages.success(request, f"Appointment record APT-{appointment.id:04d} updated successfully.")
        return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:list'))

    return redirect('appointments:detail', pk=pk)


@login_required
def appointment_delete_view(request, pk):
    user = request.user
    if not (user.is_admin_user or user.is_kapitan_user):
        messages.error(request, "Permission denied. Admin privileges required.")
        return redirect('appointments:list')

    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        apt_ref = f"APT-{appointment.id:04d}"
        appointment.delete()
        messages.success(request, f"Appointment {apt_ref} has been deleted successfully.")
        return redirect(request.META.get('HTTP_REFERER') or reverse('appointments:list'))

    messages.warning(request, "Invalid request method for deleting appointment.")
    return redirect('appointments:list')


@login_required
def appointment_detail_view(request, pk):
    user = request.user
    if user.is_admin_user or user.is_kapitan_user:
        appointment = get_object_or_404(Appointment.objects.select_related('resident', 'processed_by'), pk=pk)
    else:
        appointment = get_object_or_404(Appointment.objects.select_related('resident', 'processed_by'), pk=pk, resident=user)

    admin_user = User.objects.filter(role=User.ROLE_ADMIN).first() or User.objects.filter(is_superuser=True).first()
    admin_phone = admin_user.phone_number if (admin_user and admin_user.phone_number) else '0917-111-2222'

    status_form = None
    if user.is_admin_user:
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

                # Send email notification to applicant
                target_email = updated_apt.get_applicant_email()
                if target_email:
                    email_subj = f"Appointment Update: {status_display} [{updated_apt.get_service_title()}]"
                    email_body = (
                        f"Dear {updated_apt.get_applicant_name()},\n\n"
                        f"Your appointment request for '{updated_apt.get_service_title()}' on "
                        f"{updated_apt.preferred_date.strftime('%B %d, %Y')} ({updated_apt.get_preferred_time_slot_display()}) "
                        f"has been updated to: {status_display.upper()}.\n\n"
                    )
                    if updated_apt.admin_notes:
                        email_body += f"Administrative Remarks / Instructions:\n{updated_apt.admin_notes}\n\n"

                    if updated_apt.status == Appointment.STATUS_APPROVED_SCHEDULED:
                        email_body += (
                            f"Your appointment date has been officially APPROVED! Please visit the Barangay Hall on your scheduled slot.\n\n"
                        )
                    elif updated_apt.status == Appointment.STATUS_READY_FOR_PICKUP:
                        email_body += (
                            f"Your requested document is printed and ready for pickup at the Barangay Records Office.\n\n"
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

    status_order = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved_scheduled', 'Approved / Scheduled'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('completed', 'Completed'),
    ]

    context = {
        'appointment': appointment,
        'status_form': status_form,
        'status_order': status_order,
        'admin_phone': admin_phone,
    }
    return render(request, 'appointments/appointment_detail.html', context)


def appointment_verify_view(request, control_number):
    log = IssuedDocumentLog.objects.select_related('appointment', 'issued_to', 'issued_by').filter(
        control_number=control_number
    ).first()
    return render(request, 'appointments/verify.html', {'log': log, 'control_number': control_number})
