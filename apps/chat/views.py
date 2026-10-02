from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q, Max
from django.http import JsonResponse
from apps.chat.models import Message, Notification

User = get_user_model()


def get_chat_contacts(user):
    sent_to_ids = Message.objects.filter(sender=user).values_list('recipient_id', flat=True)
    received_from_ids = Message.objects.filter(recipient=user).values_list('sender_id', flat=True)
    chatted_user_ids = set(list(sent_to_ids) + list(received_from_ids))

    if user.is_admin_user or user.is_kapitan_user or user.is_staff:
        # Admins & Staff see all users with chat history or verified residents & officers
        all_potential = User.objects.exclude(id=user.id).distinct()
    else:
        # Residents see who they have chatted with + officers
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

    # Sort contacts: contacts with messages first, then unread first, then latest activity
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

    all_officers = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('role', 'last_name')

    context = {
        'contacts': contacts,
        'officers': all_officers,
        'other_user': None,
        'messages_history': None,
        'is_admin': user.is_admin_user or user.is_kapitan_user,
    }
    return render(request, 'chat/inbox.html', context)


@login_required
def chat_room_view(request, user_id):
    user = request.user
    other_user = get_object_or_404(User, id=user_id)
    contacts = get_chat_contacts(user)

    all_officers = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('role', 'last_name')

    # Fetch chat history between user and other_user
    messages_history = Message.objects.filter(
        (Q(sender=user, recipient=other_user) | Q(sender=other_user, recipient=user))
    ).order_by('created_at')

    # Mark incoming messages as read
    Message.objects.filter(sender=other_user, recipient=user, is_read=False).update(is_read=True)

    # Also mark related chat notifications as read
    Notification.objects.filter(
        recipient=user, sender=other_user, notification_type=Notification.TYPE_CHAT, is_read=False
    ).update(is_read=True)

    context = {
        'contacts': contacts,
        'officers': all_officers,
        'other_user': other_user,
        'messages_history': messages_history,
        'active_chat': {'user': other_user},
        'messages': messages_history,
        'is_admin': user.is_admin_user or user.is_kapitan_user,
    }
    return render(request, 'chat/inbox.html', context)


@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    # Mark all as read when visiting notification center
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)

    return render(request, 'chat/notifications_list.html', {'notifications': notifications})


@login_required
def mark_notification_read_api(request, notif_id):
    if request.method == 'POST':
        notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)
        notif.is_read = True
        notif.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'invalid method'}, status=400)
