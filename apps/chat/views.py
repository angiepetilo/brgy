import os
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse, FileResponse, Http404
from django.core.exceptions import PermissionDenied
from django.contrib import messages

from apps.chat.models import Message, Notification, ChatThread
from apps.chat.services import (
    create_direct_thread_service,
    create_concern_thread_service,
    send_thread_message_service,
    update_concern_status_service,
    mark_concern_seen_service,
)

from apps.core.ratelimit import ratelimit
User = get_user_model()


def get_officer_position_display(user):
    """Returns official position title for an officer."""
    if hasattr(user, 'officer_roles') and user.officer_roles.exists():
        return user.officer_roles.first().position or user.officer_roles.first().get_position_display()
    if hasattr(user, 'staff_assignments') and user.staff_assignments.exists():
        assignment = user.staff_assignments.select_related('officer').first()
        if assignment and assignment.officer:
            return assignment.officer.position or assignment.officer.get_position_display()
    if user.role == User.ROLE_KAPITAN:
        return 'Punong Barangay'
    if user.role == User.ROLE_ADMIN:
        return 'Barangay Administrator'
    return user.get_role_display()


def get_chat_contacts(user):
    """
    Returns list of contacts / threads for inbox sidebar.
    """
    # 1. Existing direct message contacts
    sent_to_ids = Message.objects.filter(sender=user).values_list('recipient_id', flat=True)
    received_from_ids = Message.objects.filter(recipient=user).values_list('sender_id', flat=True)
    chatted_user_ids = set([uid for uid in list(sent_to_ids) + list(received_from_ids) if uid])

    if user.is_admin_user or user.is_kapitan_user or user.is_staff:
        all_potential = User.objects.exclude(id=user.id).distinct()
    else:
        all_potential = User.objects.filter(
            Q(id__in=chatted_user_ids) | Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
        ).exclude(id=user.id).distinct()

    contacts = []
    for contact_user in all_potential:
        last_msg = Message.objects.filter(
            (Q(sender=user, recipient=contact_user) | Q(sender=contact_user, recipient=user))
        ).order_by('-created_at').first()

        unread_count = Message.objects.filter(
            sender=contact_user, recipient=user, is_read=False
        ).count()

        is_online = (contact_user.duty_status == 'on_duty') or getattr(contact_user, 'is_active', False)

        contacts.append({
            'user': contact_user,
            'last_message': last_msg,
            'unread_count': unread_count,
            'is_online': is_online,
        })

    # Sort contacts: messages first, then unread first, then latest activity
    contacts.sort(
        key=lambda c: (
            1 if c['last_message'] else 0,
            c['unread_count'] > 0,
            c['last_message'].created_at if c['last_message'] else c['user'].date_joined
        ),
        reverse=True
    )
    return contacts


@login_required
def inbox_view(request):
    user = request.user
    contacts = get_chat_contacts(user)

    # Active officers for "Message an officer" list (name and position only)
    active_officers_qs = User.objects.filter(
        status=User.STATUS_ACTIVE,
        is_approved=True
    ).filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('role', 'last_name')

    officers = [
        {
            'id': off.id,
            'name': off.get_full_name() or off.username,
            'username': off.username,
            'position': get_officer_position_display(off),
            'get_role_display': get_officer_position_display(off),
            'get_full_name': off.get_full_name() or off.username,
            'initials': off.initials,
            'avatar': off.avatar,
        }
        for off in active_officers_qs
    ]

    # Concerns list for current user
    if user.role == User.ROLE_RESIDENT:
        concerns = ChatThread.objects.filter(
            thread_type=ChatThread.THREAD_CONCERN,
            initiator=user
        ).order_by('-updated_at')
    elif user.role == User.ROLE_ADMIN or user.is_superuser:
        concerns = ChatThread.objects.filter(
            thread_type=ChatThread.THREAD_CONCERN
        ).order_by('-updated_at')
    else:
        concerns = ChatThread.objects.filter(
            thread_type=ChatThread.THREAD_CONCERN,
            assigned_handler=user
        ).order_by('-updated_at')

    context = {
        'contacts': contacts,
        'officers': officers,
        'concerns': concerns,
        'other_user': None,
        'messages_history': None,
        'is_admin': user.is_admin_user or user.is_kapitan_user,
    }
    return render(request, 'chat/inbox.html', context)


@login_required
@ratelimit(key='user', rate='chat_send')
def chat_room_view(request, user_id):
    """
    Direct 1-on-1 private messaging room between request.user and other_user:
    - Direct messages only between the two participants.
    """
    user = request.user
    other_user = get_object_or_404(User, id=user_id)

    if user.id == other_user.id:
        return redirect('chat:inbox')

    contacts = get_chat_contacts(user)

    active_officers_qs = User.objects.filter(
        status=User.STATUS_ACTIVE,
        is_approved=True
    ).filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('role', 'last_name')

    officers = [
        {
            'id': off.id,
            'name': off.get_full_name() or off.username,
            'username': off.username,
            'position': get_officer_position_display(off),
            'get_role_display': get_officer_position_display(off),
            'get_full_name': off.get_full_name() or off.username,
            'initials': off.initials,
            'avatar': off.avatar,
        }
        for off in active_officers_qs
    ]

    # Handle sending a new message
    if request.method == 'POST':
        content = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        try:
            create_direct_thread_service(
                sender=user,
                recipient=other_user,
                raw_content=content,
                attachment_file=attachment,
                request=request
            )
            return redirect('chat:room', user_id=other_user.id)
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))

    # Fetch chat history between user and other_user
    messages_history = Message.objects.filter(
        (Q(sender=user, recipient=other_user) | Q(sender=other_user, recipient=user))
    ).order_by('created_at')

    # Mark incoming messages as read
    Message.objects.filter(sender=other_user, recipient=user, is_read=False).update(is_read=True)

    # Mark related chat notifications as read
    Notification.objects.filter(
        recipient=user, sender=other_user, notification_type=Notification.TYPE_CHAT, is_read=False
    ).update(is_read=True)

    context = {
        'contacts': contacts,
        'officers': officers,
        'other_user': other_user,
        'messages_history': messages_history,
        'active_chat': {'user': other_user},
        'messages': messages_history,
        'is_admin': user.is_admin_user or user.is_kapitan_user,
    }
    return render(request, 'chat/inbox.html', context)


@login_required
def submit_concern_view(request):
    """
    Submit a resident concern/ticket:
    - Rate limit enforced (max 3/hour per resident).
    - Routed to handler by category and StaffAssignment; falls back to admin.
    """
    if request.method == 'POST':
        try:
            thread = create_concern_thread_service(
                resident=request.user,
                data=request.POST,
                attachment_file=request.FILES.get('attachment'),
                request=request
            )
            messages.success(request, f"Your concern #{thread.id} has been submitted to barangay administration.")
            return redirect('chat:concern_detail', concern_id=thread.id)
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))
            return redirect('chat:inbox')

    return render(request, 'chat/concern_form.html', {
        'categories': ChatThread.CATEGORY_CHOICES,
    })


@login_required
@ratelimit(key='user', rate='chat_send')
def concern_detail_view(request, concern_id):
    """
    View and reply to a concern thread:
    - Only participants, assigned handler, and admin can read.
    - Automatically marks 'seen' when handler/admin first opens it.
    - Handles replies via send_thread_message_service.
    """
    thread = get_object_or_404(ChatThread, id=concern_id, thread_type=ChatThread.THREAD_CONCERN)

    if not thread.can_read(request.user):
        raise PermissionDenied("You do not have permission to view this concern thread.")

    # Auto "seen" transition when handler/admin views it
    mark_concern_seen_service(thread, request.user)

    if request.method == 'POST':
        content = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        try:
            send_thread_message_service(
                thread=thread,
                sender=request.user,
                raw_content=content,
                attachment_file=attachment,
                request=request
            )
            messages.success(request, "Message sent.")
            return redirect('chat:concern_detail', concern_id=thread.id)
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))

    thread_messages = thread.messages.all().order_by('created_at')

    # Mark incoming messages as read
    thread.messages.filter(recipient=request.user, is_read=False).update(is_read=True)

    active_handlers = User.objects.filter(
        status=User.STATUS_ACTIVE,
        is_active=True
    ).filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('last_name')

    return render(request, 'chat/concern_detail.html', {
        'concern': thread,
        'thread': thread,
        'messages': thread_messages,
        'can_update_status': thread.can_update_status(request.user),
        'status_choices': ChatThread.STATUS_CHOICES,
        'active_handlers': active_handlers,
    })


@login_required
def update_concern_status_view(request, concern_id):
    """
    Updates status of a concern:
    - Only handler or admin.
    - Invalid jumps refused.
    """
    thread = get_object_or_404(ChatThread, id=concern_id, thread_type=ChatThread.THREAD_CONCERN)

    if not thread.can_update_status(request.user):
        raise PermissionDenied("You do not have permission to update the status of this concern.")

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip().lower()
        try:
            update_concern_status_service(thread, request.user, new_status, request=request)
            messages.success(request, f"Concern status updated to '{thread.get_status_display()}'.")
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('chat:concern_detail', concern_id=thread.id)


@login_required
def reassign_concern_view(request, concern_id):
    """
    Reassigns a concern:
    - Admin or current handler reassigns to new handler.
    - Resident requests reassignment to admin.
    """
    thread = get_object_or_404(ChatThread, id=concern_id, thread_type=ChatThread.THREAD_CONCERN)

    if request.method == 'POST':
        action = request.POST.get('action', 'reassign')
        if action == 'resident_escalate':
            try:
                from apps.chat.services import resident_request_reassignment_service
                resident_request_reassignment_service(thread, request.user, request=request)
                messages.success(request, "Your concern has been escalated and reassigned to Barangay Administration.")
            except (ValueError, PermissionDenied) as e:
                messages.error(request, str(e))
        else:
            new_handler_id = request.POST.get('handler_id')
            new_handler = get_object_or_404(User, id=new_handler_id)
            try:
                from apps.chat.services import reassign_concern_service
                reassign_concern_service(thread, request.user, new_handler, request=request)
                messages.success(request, f"Concern #{thread.id} has been reassigned to {new_handler.get_full_name() or new_handler.username}.")
            except (ValueError, PermissionDenied) as e:
                messages.error(request, str(e))

    return redirect('chat:concern_detail', concern_id=thread.id)


@login_required
def serve_chat_attachment_view(request, message_id):
    """
    Serves private chat and concern attachments through permission-checked view:
    - Direct message: only sender or recipient.
    - Concern: only initiator, assigned handler, or admin.
    - Always Content-Disposition: attachment
    - X-Content-Type-Options: nosniff
    - Never inline SVG/HTML
    """
    msg = get_object_or_404(Message, id=message_id)
    if not msg.attachment:
        raise Http404("Attachment not found.")

    # Permission check
    if msg.thread:
        if not msg.thread.can_read(request.user):
            raise PermissionDenied("You do not have permission to access this attachment.")
    else:
        if request.user.id not in [msg.sender_id, msg.recipient_id]:
            raise PermissionDenied("You do not have permission to access this attachment.")

    filename = msg.attachment_filename or os.path.basename(msg.attachment.name)
    ext = os.path.splitext(filename)[1].lower()

    if ext in ['.svg', '.html', '.htm'] or 'svg' in (msg.attachment_mime or '') or 'html' in (msg.attachment_mime or ''):
        raise PermissionDenied("Serving HTML or SVG attachments is prohibited.")

    content_type = msg.attachment_mime or 'application/octet-stream'
    response = FileResponse(msg.attachment.open('rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def notifications_list_view(request):
    """
    Paginated notification center.
    Residents only see their own notifications.
    Staff only see their own notifications.
    """
    notifs_qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    paginator = Paginator(notifs_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'chat/notifications_list.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
    })


@login_required
def mark_all_notifications_read_view(request):
    """
    Marks all notifications for request.user as read.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'ok'})
    messages.success(request, "All notifications marked as read.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('chat:notifications_list'))


@login_required
def open_notification_view(request, notif_id):
    """
    Marks a notification as read and redirects to target URL if authorized.
    Isolated per user: users can only open their own notifications.
    Residents cannot open staff/admin targets.
    """
    notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read'])

    target_url = notif.url or notif.link_url or reverse('chat:notifications_list')

    # Guard: check if resident is trying to open a restricted staff/admin area
    restricted_staff_prefixes = ['/accounts/system/', '/system/', '/history/', '/records/', '/statistics/']
    is_resident = request.user.role == User.ROLE_RESIDENT
    if is_resident and any(target_url.startswith(prefix) for prefix in restricted_staff_prefixes):
        messages.error(request, "You do not have permission to view that administrative page.")
        return redirect('home')

    return redirect(target_url)


@login_required
def unread_notifications_count_api(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})


@login_required
def mark_notification_read_api(request, notif_id):
    if request.method == 'POST':
        notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'invalid method'}, status=400)

