from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

import secrets
import string
import logging
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail

from apps.accounts.models import User, Household
from apps.accounts.forms import ResidentRegistrationForm, UserLoginForm, ProfileUpdateForm, SettingsForm, PersonalInfoForm, DutyStatusForm
from apps.appointments.models import Appointment
from apps.communications.models import Announcement, KapitanStatus
from apps.chat.models import Notification

logger = logging.getLogger(__name__)


def generate_random_password(length=8):
    """Generates a secure, user-friendly randomized password (e.g. Brgy-X7k2M9p4)."""
    chars = string.ascii_letters + string.digits
    rand_suffix = ''.join(secrets.choice(chars) for _ in range(length))
    return f"Brgy-{rand_suffix}"


def send_approval_credentials_email(request, resident, password):
    """Sends notification email to approved resident with their login credentials."""
    if not resident.email:
        return False, "No email address registered for this resident."

    login_url = request.build_absolute_uri(reverse('accounts:login'))
    subject = "🏛️ Your Barangay e-Portal Account Has Been Approved!"
    message = f"""Mabuhay, {resident.get_full_name() or resident.username}!

We are pleased to inform you that your Barangay Resident account has been officially verified and APPROVED by the Barangay Administrator.

Your Account Login Credentials:
─────────────────────────────────────────────
• Username: {resident.username}
• Registered Email: {resident.email}
• Temporary Password: {password}
─────────────────────────────────────────────

You can sign in immediately at:
{login_url}

For your account security, please change your password after logging in.

Thank you,
Barangay Hall Administration
Barangay e-Portal Digital Services
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[resident.email],
            fail_silently=False,
        )
        return True, "Email sent successfully."
    except Exception as exc:
        logger.error(f"Failed to send approval email to {resident.email}: {exc}")
        return False, str(exc)


def is_admin(user):
    return user.is_authenticated and (user.role == User.ROLE_ADMIN or user.is_staff or user.is_superuser)


def is_kapitan_or_admin(user):
    return user.is_authenticated and (user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or user.is_staff)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = ResidentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            return render(request, 'accounts/signup.html', {
                'form': ResidentRegistrationForm(),
                'registration_submitted': True,
                'registered_user': user,
            })
    else:
        form = ResidentRegistrationForm()

    return render(request, 'accounts/signup.html', {
        'form': form,
        'registration_submitted': False,
    })


def login_view(request):
    if request.user.is_authenticated:
        if request.user.role == User.ROLE_RESIDENT and not request.user.is_approved:
            return redirect('accounts:pending_approval')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            if user.role == User.ROLE_RESIDENT and not user.is_approved:
                return redirect('accounts:pending_approval')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


@login_required
def pending_approval_view(request):
    """
    Dedicated screen for unapproved residents.
    Enforced by ApprovalGateMiddleware.
    """
    return render(request, 'accounts/pending_approval.html', {'user': request.user})


@login_required
def dashboard_view(request):
    user = request.user

    # Fetch latest Kapitan status
    kapitan_status = KapitanStatus.objects.order_by('-updated_at').first()

    if user.is_admin_user:
        # Admin metrics
        pending_appointments = Appointment.objects.filter(status=Appointment.STATUS_SUBMITTED).count()
        total_appointments = Appointment.objects.count()
        pending_verifications = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=False, rejection_reason__isnull=True).count()
        total_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True).count()

        recent_appointments = Appointment.objects.select_related('resident').order_by('-created_at')[:8]
        pending_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=False, rejection_reason__isnull=True)[:5]
        latest_announcements = Announcement.objects.order_by('-created_at')[:4]

        context = {
            'role': 'admin',
            'pending_appointments': pending_appointments,
            'total_appointments': total_appointments,
            'pending_verifications': pending_verifications,
            'total_residents': total_residents,
            'recent_appointments': recent_appointments,
            'pending_residents': pending_residents,
            'latest_announcements': latest_announcements,
            'kapitan_status': kapitan_status,
        }
        return render(request, 'accounts/dashboard_admin.html', context)

    elif user.is_kapitan_user:
        total_appointments = Appointment.objects.count()
        active_announcements = Announcement.objects.count()
        latest_announcements = Announcement.objects.order_by('-created_at')[:5]
        recent_appointments = Appointment.objects.select_related('resident').order_by('-created_at')[:6]

        context = {
            'role': 'kapitan',
            'kapitan_status': kapitan_status,
            'total_appointments': total_appointments,
            'active_announcements': active_announcements,
            'latest_announcements': latest_announcements,
            'recent_appointments': recent_appointments,
        }
        return render(request, 'accounts/dashboard_kapitan.html', context)

    else:
        # Resident view
        user_appointments = Appointment.objects.filter(resident=user).order_by('-created_at')
        active_appointments = user_appointments.exclude(status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_REJECTED])
        completed_appointments = user_appointments.filter(status=Appointment.STATUS_COMPLETED)
        latest_announcements = Announcement.objects.order_by('-created_at')[:5]

        context = {
            'role': 'resident',
            'user_appointments': user_appointments[:5],
            'active_count': active_appointments.count(),
            'completed_count': completed_appointments.count(),
            'latest_announcements': latest_announcements,
            'kapitan_status': kapitan_status,
        }
        return render(request, 'accounts/dashboard_resident.html', context)


@login_required
@user_passes_test(is_admin)
def approval_list_view(request):
    """
    Approval dashboard for admins to inspect resident registrations and ID proofs.
    """
    pending_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=False).order_by('-date_joined')
    return render(request, 'accounts/approval_list.html', {'pending_residents': pending_residents})


@login_required
@user_passes_test(is_admin)
def approve_resident_view(request, user_id):
    if request.method == 'POST':
        resident = get_object_or_404(User, id=user_id, role=User.ROLE_RESIDENT)
        
        # Generate unique randomized password for resident login
        random_password = generate_random_password(8)
        resident.set_password(random_password)
        resident.is_approved = True
        resident.rejection_reason = None
        resident.verified_at = timezone.now()
        resident.verified_by = request.user
        resident.save()

        # Send official email with randomized password
        email_sent, email_msg = send_approval_credentials_email(request, resident, random_password)

        # Create persistent notification
        Notification.objects.create(
            recipient=resident,
            sender=request.user,
            title="Account Verified & Approved!",
            message="Your Barangay Resident account has been verified and approved. You now have full access to services.",
            notification_type=Notification.TYPE_APPROVAL,
            link_url="/dashboard/"
        )

        # Broadcast via WebSockets to resident's personal channel
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{resident.id}",
            {
                "type": "send_notification",
                "title": "Account Approved!",
                "message": "Your registration has been approved. You now have full access to barangay services.",
                "notification_type": "approval",
                "link_url": "/dashboard/",
            }
        )

        if email_sent:
            messages.success(
                request,
                f"Resident {resident.get_full_name() or resident.username} approved! "
                f"Login credentials and temporary password [{random_password}] were sent to {resident.email}."
            )
        else:
            messages.warning(
                request,
                f"Resident {resident.get_full_name() or resident.username} approved! "
                f"Generated Password: [{random_password}]. "
                f"(Email delivery note: {email_msg})"
            )
    return redirect('accounts:approval_list')


@login_required
@user_passes_test(is_admin)
def reject_resident_view(request, user_id):
    if request.method == 'POST':
        resident = get_object_or_404(User, id=user_id, role=User.ROLE_RESIDENT)
        reason = request.POST.get('rejection_reason', 'ID proof is unclear or invalid. Please re-register or contact the barangay hall.')
        resident.is_approved = False
        resident.rejection_reason = reason
        resident.save()

        # Create persistent notification
        Notification.objects.create(
            recipient=resident,
            sender=request.user,
            title="Account Verification Declined",
            message=f"Reason: {reason}",
            notification_type=Notification.TYPE_APPROVAL,
            link_url="/accounts/pending/"
        )

        # Broadcast via WebSockets
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{resident.id}",
            {
                "type": "send_notification",
                "title": "Verification Declined",
                "message": f"Reason: {reason}",
                "notification_type": "approval",
                "link_url": "/accounts/pending/",
            }
        )

        messages.warning(request, f"Resident {resident.username} application was rejected.")
    return redirect('accounts:approval_list')


@login_required
@user_passes_test(is_admin)
def rbi_directory_view(request):
    """
    Registry of Barangay Inhabitants (RBI) & Household Demographics Directory.
    Admin-only searchable, paginated table of residents filterable by Purok, Senior Citizens, PWDs, 4Ps, and Households.
    """
    purok_filter = request.GET.get('purok', '')
    is_senior = request.GET.get('is_senior', '')
    is_pwd = request.GET.get('is_pwd', '')
    is_4ps = request.GET.get('is_4ps', '')
    household_filter = request.GET.get('household', '')
    search_query = request.GET.get('q', '').strip()

    queryset = User.objects.filter(role=User.ROLE_RESIDENT).select_related('household').order_by('last_name', 'first_name')

    if purok_filter:
        if purok_filter.isdigit():
            queryset = queryset.filter(purok_id=int(purok_filter))
        else:
            queryset = queryset.filter(purok__name=purok_filter)
    if is_senior == '1':
        queryset = queryset.filter(is_senior=True)
    if is_pwd == '1':
        queryset = queryset.filter(is_pwd=True)
    if is_4ps == '1':
        queryset = queryset.filter(is_4ps=True)
    if household_filter:
        queryset = queryset.filter(household__household_number=household_filter)
    if search_query:
        queryset = queryset.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(occupation__icontains=search_query)
        )

    # Demographics KPI aggregates
    total_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True).count()
    total_households = Household.objects.count()
    total_seniors = User.objects.filter(role=User.ROLE_RESIDENT, is_senior=True).count()
    total_pwd = User.objects.filter(role=User.ROLE_RESIDENT, is_pwd=True).count()
    total_4ps = User.objects.filter(role=User.ROLE_RESIDENT, is_4ps=True).count()

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'purok_filter': purok_filter,
        'is_senior': is_senior,
        'is_pwd': is_pwd,
        'is_4ps': is_4ps,
        'household_filter': household_filter,
        'search_query': search_query,
        'purok_choices': User.PUROK_CHOICES,
        'total_residents': total_residents,
        'total_households': total_households,
        'total_seniors': total_seniors,
        'total_pwd': total_pwd,
        'total_4ps': total_4ps,
    }
    return render(request, 'accounts/rbi_directory.html', context)


@login_required
@user_passes_test(is_kapitan_or_admin)
def residents_tabbed_view(request):
    """
    Residents Management Module (/accounts/residents/)
    Tri-Tab Interface (Admin/Staff Only):
    PENDING - Unapproved registrations; inline action buttons to VIEW PROOF, APPROVE, or REJECT.
    APPROVED - Searchable RBI directory of verified residents with edit capabilities.
    REJECTED - List of declined registration attempts with logged rejection reasons and option to re-evaluate.
    """
    active_tab = request.GET.get('tab', 'pending')
    if active_tab not in ['pending', 'approved', 'rejected']:
        active_tab = 'pending'

    # Base querysets
    pending_qs = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=False).exclude(rejection_reason__gt='').order_by('-date_joined')
    approved_qs = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True).select_related('household').order_by('last_name', 'first_name')
    rejected_qs = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=False, rejection_reason__gt='').order_by('-date_joined')

    # Counts
    pending_count = pending_qs.count()
    approved_count = approved_qs.count()
    rejected_count = rejected_qs.count()

    # Search / Filters
    search_query = request.GET.get('q', '').strip()
    purok_filter = request.GET.get('purok', '')

    if search_query:
        query_filter = (
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
        if active_tab == 'pending':
            pending_qs = pending_qs.filter(query_filter)
        elif active_tab == 'approved':
            approved_qs = approved_qs.filter(query_filter)
        elif active_tab == 'rejected':
            rejected_qs = rejected_qs.filter(query_filter)

    if purok_filter and active_tab == 'approved':
        if purok_filter.isdigit():
            approved_qs = approved_qs.filter(purok_id=int(purok_filter))
        else:
            approved_qs = approved_qs.filter(purok__name=purok_filter)

    # Pagination for approved
    paginator = Paginator(approved_qs, 15)
    page_number = request.GET.get('page')
    approved_page = paginator.get_page(page_number)

    main_tab = request.GET.get('main_tab', 'residents')
    if main_tab not in ['residents', 'rbi']:
        main_tab = 'residents'

    context = {
        'main_tab': main_tab,
        'active_tab': active_tab,
        'pending_residents': pending_qs,
        'approved_page': approved_page,
        'rejected_residents': rejected_qs,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'search_query': search_query,
        'purok_filter': purok_filter,
        'purok_choices': User.PUROK_CHOICES,
    }
    return render(request, 'accounts/residents_tabbed.html', context)


@login_required
@user_passes_test(is_admin)
def reevaluate_resident_view(request, user_id):
    resident = get_object_or_404(User, id=user_id, role=User.ROLE_RESIDENT)
    if request.method == 'POST':
        action = request.POST.get('action', 'approve')
        if action == 'approve':
            random_password = generate_random_password(8)
            resident.set_password(random_password)
            resident.is_approved = True
            resident.rejection_reason = ''
            resident.save()

            email_sent, email_msg = send_approval_credentials_email(request, resident, random_password)

            # Create notification
            Notification.objects.create(
                recipient=resident,
                sender=request.user,
                title="Account Re-evaluated & Approved!",
                message="Your resident account registration was re-evaluated and officially approved.",
                notification_type=Notification.TYPE_APPROVAL,
                link_url="/dashboard/"
            )

            if email_sent:
                messages.success(
                    request,
                    f"Resident {resident.get_full_name() or resident.username} has been re-evaluated and approved! "
                    f"Login credentials with temporary password [{random_password}] were sent to {resident.email}."
                )
            else:
                messages.warning(
                    request,
                    f"Resident {resident.get_full_name() or resident.username} approved! "
                    f"Generated Password: [{random_password}]. "
                    f"(Email delivery note: {email_msg})"
                )
        else:
            # Revert to pending
            resident.rejection_reason = ''
            resident.is_approved = False
            resident.save()
            messages.info(request, f"Resident {resident.username} returned to pending verification.")
    return redirect('/accounts/residents/?tab=rejected')


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile and status message have been updated successfully.")
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=user)

    context = {
        'form': form,
        'user_obj': user,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def remove_avatar_view(request):
    user = request.user
    if request.method == 'POST':
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
            messages.success(request, "Profile avatar removed. Reverted to initial text badge.")
    return redirect('accounts:profile')


@login_required
def settings_view(request):
    user = request.user
    active_tab = request.GET.get('tab', 'personal')

    personal_form = PersonalInfoForm(instance=user)
    duty_form = DutyStatusForm(instance=user)
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'change_password':
            active_tab = 'security'
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user_updated = password_form.save()
                update_session_auth_hash(request, user_updated)
                messages.success(request, "Your password has been changed successfully.")
                return redirect(f"{reverse('accounts:settings')}?tab=security")
            else:
                messages.error(request, "Please correct the password errors below.")

        elif action == 'set_duty_status':
            active_tab = 'duty'
            duty_form = DutyStatusForm(request.POST, instance=user)
            if duty_form.is_valid():
                duty_form.save()
                messages.success(request, f"Duty status updated to: {user.get_duty_status_display()}.")
                return redirect(f"{reverse('accounts:settings')}?tab=duty")
            else:
                messages.error(request, "Please correct the errors in the duty status form.")

        else:
            # Default / personal_info
            active_tab = 'personal'
            personal_form = PersonalInfoForm(request.POST, instance=user)
            if personal_form.is_valid():
                personal_form.save()
                messages.success(request, "Personal information updated successfully.")
                return redirect(f"{reverse('accounts:settings')}?tab=personal")
            else:
                messages.error(request, "Please correct the errors in your personal information.")

    context = {
        'form': personal_form,  # For backward compatibility if anything reads form
        'personal_form': personal_form,
        'duty_form': duty_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'user_obj': user,
        'is_superuser': user.is_superuser or user.is_staff,
    }
    return render(request, 'accounts/settings.html', context)


