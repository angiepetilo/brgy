import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from apps.accounts.permissions import admin_only
from apps.accounts.models import User
from apps.history.models import ActivityLog, EmailLog


@admin_only
def history_overview(request):
    """
    Module 12: History & Email Log (Administrator Only, Read-Only).
    Provides dual-tabbed audit logging of all system actions:
    Tab 1: Activity & Audit Trail (filter by user, action, module/action_type, date)
    Tab 2: Email Dispatch Log (filter by status, date, and resend failed non-secret emails)
    """
    active_tab = request.GET.get('tab', 'activity')
    q = request.GET.get('q', '').strip()
    action_filter = request.GET.get('action', '').strip()
    module_filter = request.GET.get('module', '').strip()
    user_filter = request.GET.get('user', '').strip()
    date_filter = request.GET.get('date', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Activity Log Query
    activity_qs = ActivityLog.objects.select_related('actor').all()

    if q and active_tab == 'activity':
        activity_qs = activity_qs.filter(
            Q(target_name__icontains=q) |
            Q(target_id__icontains=q) |
            Q(details__icontains=q) |
            Q(actor__first_name__icontains=q) |
            Q(actor__last_name__icontains=q) |
            Q(actor__username__icontains=q) |
            Q(ip_address__icontains=q)
        )

    if action_filter and active_tab == 'activity':
        activity_qs = activity_qs.filter(action=action_filter)

    if module_filter and active_tab == 'activity':
        activity_qs = activity_qs.filter(action_type__iexact=module_filter)

    if user_filter and active_tab == 'activity':
        if user_filter.isdigit():
            activity_qs = activity_qs.filter(actor_id=int(user_filter))
        else:
            activity_qs = activity_qs.filter(actor__username__iexact=user_filter)

    if date_filter and active_tab == 'activity':
        try:
            parsed_date = datetime.date.fromisoformat(date_filter)
            activity_qs = activity_qs.filter(created_at__date=parsed_date)
        except ValueError:
            pass

    activity_paginator = Paginator(activity_qs, 20)
    activity_page = activity_paginator.get_page(request.GET.get('page') if active_tab == 'activity' else 1)

    # Email Log Query
    email_qs = EmailLog.objects.all()

    if q and active_tab == 'emails':
        email_qs = email_qs.filter(
            Q(recipient__icontains=q) |
            Q(recipient_name__icontains=q) |
            Q(subject__icontains=q) |
            Q(error_message__icontains=q)
        )

    if status_filter and active_tab == 'emails':
        email_qs = email_qs.filter(status=status_filter)

    if date_filter and active_tab == 'emails':
        try:
            parsed_date = datetime.date.fromisoformat(date_filter)
            email_qs = email_qs.filter(created_at__date=parsed_date)
        except ValueError:
            pass

    email_paginator = Paginator(email_qs, 20)
    email_page = email_paginator.get_page(request.GET.get('page') if active_tab == 'emails' else 1)

    # Distinct modules/action_types and users for dropdown filters
    action_types = ActivityLog.objects.values_list('action_type', flat=True).distinct().order_by('action_type')
    action_types = [t for t in action_types if t]

    staff_and_admins = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_KAPITAN]) | Q(is_superuser=True)
    ).distinct().order_by('first_name', 'last_name')

    # Aggregates
    total_activities = ActivityLog.objects.count()
    approved_count = ActivityLog.objects.filter(action=ActivityLog.ACTION_APPROVE).count()
    rejected_count = ActivityLog.objects.filter(action=ActivityLog.ACTION_REJECT).count()
    completed_count = ActivityLog.objects.filter(action=ActivityLog.ACTION_COMPLETE).count()
    noshow_count = ActivityLog.objects.filter(action=ActivityLog.ACTION_NO_SHOW).count()

    total_emails = EmailLog.objects.count()
    emails_sent = EmailLog.objects.filter(status=EmailLog.STATUS_SENT).count()
    emails_failed = EmailLog.objects.filter(status=EmailLog.STATUS_FAILED).count()
    emails_queued = EmailLog.objects.filter(status=EmailLog.STATUS_QUEUED).count()

    context = {
        'active_tab': active_tab,
        'q': q,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'user_filter': user_filter,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'activity_page': activity_page,
        'email_page': email_page,
        'action_types': action_types,
        'staff_and_admins': staff_and_admins,
        # Stats
        'total_activities': total_activities,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'completed_count': completed_count,
        'noshow_count': noshow_count,
        'total_emails': total_emails,
        'emails_sent': emails_sent,
        'emails_failed': emails_failed,
        'emails_queued': emails_queued,
    }
    return render(request, 'history/overview.html', context)


@admin_only
def resend_failed_email_view(request, email_id):
    """
    Allows admin to retry any failed non-secret email.
    """
    if request.method == 'POST':
        email_obj = get_object_or_404(EmailLog, id=email_id)
        if email_obj.is_secret:
            messages.error(request, "Credentials emails cannot be resent from the outbox. Please use 'Resend temporary password' from the resident's record.")
        elif email_obj.status == EmailLog.STATUS_FAILED:
            email_obj.status = EmailLog.STATUS_QUEUED
            email_obj.attempts = 0
            email_obj.error_message = ''
            email_obj.save(update_fields=['status', 'attempts', 'error_message'])
            messages.success(request, f"Email to {email_obj.recipient} re-queued for delivery.")
        else:
            messages.info(request, f"Email is currently in status '{email_obj.get_status_display()}'.")
    return redirect(f"{reverse('history:overview')}?tab=emails")
