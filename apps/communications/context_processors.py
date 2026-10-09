def global_barangay_context(request):
    """
    Supplies global context for header badge counters, Kapitan status indicator,
    slide-over drawer items, and role helpers across all rendered templates.
    """
    from django.utils.functional import SimpleLazyObject
    from apps.accounts.selectors import get_contact_number

    context = {
        # Lazy: only queries BarangayInfo when a template actually prints it.
        'barangay_contact': SimpleLazyObject(get_contact_number),
        'current_kapitan_status': None,
        'unread_notifications_count': 0,
        'unread_messages_count': 0,
        'pending_approvals_count': 0,
        'pending_tasks_count': 0,
        'drawer_unread_count': 0,
        'recent_notifications': [],
        'pending_tasks_list': [],
        # 4 Unique Real-Time Stat Cards (User.id level aggregations)
        'stat_pending_docs_count': 0,
        'stat_pending_residents_count': 0,
        'stat_total_residents_count': 0,
        'stat_handled_requests_count': 0,
        # Staff Duty Roster
        'duty_officers_roster': [],
        'staff_members': [],
    }

    if not request.user.is_authenticated:
        return context


    # Unread notifications & unread messages for current user
    try:
        from apps.chat.models import Notification, Message
        from django.utils import timezone
        import datetime
        now = timezone.now()
        day_ago = now - datetime.timedelta(hours=24)

        all_notifs = list(Notification.objects.filter(recipient=request.user).select_related('sender').order_by('-created_at')[:25])
        unread_notifs = [n for n in all_notifs if not n.is_read]
        context['unread_notifications_count'] = len(unread_notifs)
        context['recent_notifications'] = unread_notifs[:5]
        context['all_notifications'] = all_notifs
        context['new_notifications'] = [n for n in all_notifs if n.created_at >= day_ago or not n.is_read][:10]
        context['earlier_notifications'] = [n for n in all_notifs if n.created_at < day_ago and n.is_read][:15]

        # Recent chat previews
        from django.db.models import Q
        raw_msgs = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).select_related('sender', 'recipient').order_by('-created_at')[:30]

        conversations = {}
        for m in raw_msgs:
            other = m.recipient if m.sender == request.user else m.sender
            if other and other.id not in conversations:
                conversations[other.id] = {
                    'user': other,
                    'last_message': m.content,
                    'created_at': m.created_at,
                    'is_unread': (m.recipient == request.user and not m.is_read),
                    'is_mine': (m.sender == request.user),
                }

        context['recent_conversations'] = list(conversations.values())[:10]
        context['unread_messages_count'] = Message.objects.filter(recipient=request.user, is_read=False).count()
    except Exception:
        pass

    # 4 Unique Real-Time Stat Cards from Central get_dashboard_metrics
    try:
        from apps.accounts.services import get_dashboard_metrics
        from apps.appointments.models import Appointment

        metrics = get_dashboard_metrics(request.user)
        context['dashboard_metrics'] = metrics
        context['stat_total_residents_count'] = metrics['registered_residents_count']
        context['stat_portal_accounts_count'] = metrics['portal_accounts_count']
        context['stat_needs_attention_count'] = metrics['needs_attention_count']
        context['stat_pending_residents_count'] = metrics['pending_registrations_count']
        context['pending_approvals_count'] = metrics['pending_registrations_count']
        context['stat_pending_docs_count'] = Appointment.objects.filter(
            status=Appointment.STATUS_PENDING
        ).count()
        context['stat_handled_requests_count'] = Appointment.objects.filter(
            status=Appointment.STATUS_COMPLETED
        ).count()

        # Staff Duty Roster for Right Panel
        roster_users = User.objects.filter(
            Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
        ).distinct().order_by('role', 'last_name')
        context['duty_officers_roster'] = roster_users
        context['staff_members'] = roster_users
    except Exception:
        pass

    # Count pending approvals & document tasks for admin/staff
    is_staff_admin = (request.user.role in ['admin', 'kapitan'] or request.user.is_staff or request.user.is_superuser)
    tasks = []

    if is_staff_admin:
        try:
            from apps.accounts.models import User
            unapproved = User.objects.filter(
                role='resident', is_approved=False
            ).exclude(rejection_reason__gt='').order_by('-date_joined')
            context['pending_approvals_count'] = unapproved.count()
            for u in unapproved[:3]:
                tasks.append({
                    'title': f'Verify Resident: {u.get_full_name() or u.username}',
                    'subtitle': f'Registered on {u.date_joined.strftime("%b %d")}',
                    'url': '/accounts/residents/?tab=pending',
                    'badge': 'VERIFICATION',
                })
        except Exception:
            pass

        try:
            from apps.appointments.models import Appointment
            pending_docs = Appointment.objects.filter(
                status=Appointment.STATUS_PENDING
            ).select_related('resident', 'document_type', 'healthcare_service').order_by('-created_at')
            for doc in pending_docs[:3]:
                tasks.append({
                    'title': f'Approve {doc.get_service_title()}',
                    'subtitle': f'Req by {doc.resident.get_full_name() or doc.resident.username}',
                    'url': f'/appointments/{doc.id}/',
                    'badge': 'DOCUMENT',
                })
        except Exception:
            pass
    else:
        # Resident's own active document tasks
        try:
            from apps.appointments.models import Appointment
            active_docs = Appointment.objects.select_related('document_type', 'healthcare_service').filter(
                resident=request.user
            ).exclude(status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_REJECTED]).order_by('-created_at')
            for doc in active_docs[:3]:
                tasks.append({
                    'title': f'{doc.get_service_title()}',
                    'subtitle': f'Status: {doc.get_status_display()}',
                    'url': f'/appointments/{doc.id}/',
                    'badge': doc.get_status_display().upper(),
                })
        except Exception:
            pass

    context['pending_tasks_list'] = tasks
    context['pending_tasks_count'] = len(tasks)
    context['drawer_unread_count'] = context['unread_notifications_count'] + (context['pending_approvals_count'] if is_staff_admin else 0)

    return context


