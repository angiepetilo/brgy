import os
import uuid
import datetime
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.chat.models import ChatThread, Message, Notification, ConcernCategory
from apps.accounts.models import StaffAssignment, Officer
from apps.history.models import ActivityLog
from apps.history.utils import log_activity

User = get_user_model()

MAX_MESSAGE_LENGTH = 2000
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_ATTACHMENT_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf']
FORBIDDEN_EXTENSIONS = ['.exe', '.bat', '.sh', '.php', '.py', '.js', '.vbs', '.msi', '.bin', '.cmd', '.svg', '.html', '.htm']


def create_notification(recipient, title, message, url='', action_type=''):
    """
    Unified creation function for in-app user notifications.
    Creates Notification model instance and broadcasts real-time updates via WebSockets/Channels if available.
    """
    if not recipient:
        return None

    action_type = action_type or 'general'
    url = url or ''

    if action_type in ['concern', 'message', 'chat']:
        notif_type = Notification.TYPE_CHAT
    elif action_type in ['appointment']:
        notif_type = Notification.TYPE_APPOINTMENT
    elif action_type in ['approval', 'registration']:
        notif_type = Notification.TYPE_APPROVAL
    elif action_type in ['status']:
        notif_type = Notification.TYPE_STATUS
    elif action_type in ['announcement', 'emergency', 'post']:
        notif_type = Notification.TYPE_ANNOUNCEMENT
    else:
        notif_type = action_type if action_type in dict(Notification.TYPE_CHOICES) else Notification.TYPE_CHAT

    notif = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        url=url,
        link_url=url,
        action_type=action_type,
        notification_type=notif_type,
        is_read=False,
    )

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{recipient.id}",
                {
                    'type': 'notification.message',
                    'data': {
                        'id': notif.id,
                        'title': notif.title,
                        'message': notif.message,
                        'url': notif.url,
                        'action_type': notif.action_type,
                        'created_at': notif.created_at.strftime('%b %d, %H:%M'),
                    }
                }
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("WebSocket notification broadcast failed (channel layer unavailable): %s", exc)

    return notif


def validate_chat_attachment(file_obj):
    """
    Validates file size (max 10MB), allowlist (jpg, png, pdf),
    checks real content type, blocks SVG/HTML.
    """
    if not file_obj:
        return
    if file_obj.size > MAX_ATTACHMENT_SIZE:
        raise ValueError("Attachment size cannot exceed 10MB.")

    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext in FORBIDDEN_EXTENSIONS:
        raise ValueError(f"File format '{ext}' is forbidden for security reasons.")
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValueError(f"File format '{ext}' is not allowed. Allowed formats: JPG, PNG, PDF.")

    file_obj.seek(0)
    initial_bytes = file_obj.read(1024)
    file_obj.seek(0)

    # Security check: never allow HTML or SVG
    lower_bytes = initial_bytes.lower()
    if b'<svg' in lower_bytes or b'<html' in lower_bytes or b'<!doctype' in lower_bytes or b'<script' in lower_bytes:
        raise ValueError("Malicious file content detected.")

    if ext in ['.jpg', '.jpeg', '.png']:
        try:
            from PIL import Image
            img = Image.open(file_obj)
            img.verify()
            if img.format not in ['JPEG', 'PNG']:
                raise ValueError("Real image format does not match file extension.")
            file_obj.seek(0)
        except Exception:
            raise ValueError("Corrupted or invalid image file content.")
    elif ext == '.pdf':
        if not initial_bytes.startswith(b'%PDF-'):
            raise ValueError("Invalid PDF file header.")


def check_staff_resident_scope(staff_user, resident_user):
    """
    Staff may start a direct message only with residents in their scope:
    - Admin/Kapitan/Superuser: unconditional scope.
    - Staff with SCOPE_PUROK: resident must belong to that purok.
    - Staff with SCOPE_SERVICE_AREA: general/all or matching assigned resident.
    """
    if staff_user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or staff_user.is_superuser:
        return True

    assignments = staff_user.staff_assignments.all()
    if not assignments.exists():
        return False

    purok_name = ''
    if hasattr(resident_user, 'resident_profile') and resident_user.resident_profile and resident_user.resident_profile.purok:
        purok_name = resident_user.resident_profile.purok.name
    elif hasattr(resident_user, 'purok') and resident_user.purok:
        purok_name = resident_user.purok.name if hasattr(resident_user.purok, 'name') else str(resident_user.purok)

    for a in assignments:
        if a.scope_type == StaffAssignment.SCOPE_PUROK:
            if a.scope_value.strip().lower() in [purok_name.strip().lower(), 'all']:
                return True
        elif a.scope_type == StaffAssignment.SCOPE_SERVICE_AREA:
            val = a.scope_value.strip().lower()
            if val in ['all', 'general', 'punong barangay']:
                return True
            if hasattr(resident_user, 'resident_profile') and resident_user.resident_profile:
                if resident_user.resident_profile.assigned_officer_id == a.officer_id:
                    return True
    return False


def route_concern_handler(category, purok=None):
    """
    Routes a concern to the appropriate active staff member based on category and StaffAssignment.
    Falls back to admin if no assigned staff member is found or active.
    """
    cat_lower = (category or '').strip().lower()

    keyword_map = {
        'health': ['health'],
        'peace_and_order': ['peace and order', 'tanod', 'security', 'peace'],
        'education': ['education', 'youth', 'scholarship'],
        'infrastructure': ['infrastructure', 'public works', 'eng'],
        'general': ['general', 'secretary'],
    }
    keywords = keyword_map.get(cat_lower, [cat_lower])

    for kw in keywords:
        assignment = StaffAssignment.objects.filter(
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value__icontains=kw,
            user__status=User.STATUS_ACTIVE,
            user__is_active=True
        ).select_related('user').first()
        if assignment and assignment.user:
            return assignment.user

    for kw in keywords:
        officer = Officer.objects.filter(
            committee__icontains=kw,
            user__status=User.STATUS_ACTIVE,
            user__is_active=True
        ).select_related('user').first()
        if officer and officer.user:
            return officer.user

    admin_user = User.objects.filter(
        role=User.ROLE_ADMIN,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first() or User.objects.filter(
        is_superuser=True,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first()
    return admin_user


def create_concern_thread_service(resident, data, attachment_file=None, request=None):
    """
    Submits a new resident concern / ticket:
    - Rate limit: max 3 concerns per resident per hour.
    - Message length cap: 2000 chars.
    - Stores raw text (no HTML escaping; relies on template auto-escape).
    - Routes to handler by category and StaffAssignment; falls back to admin.
    - Status initialized to 'submitted'.
    - Attachment stored privately.
    - In-app notification to handler (no email).
    - Logs ActivityLog.
    """
    if not resident.is_authenticated:
        raise PermissionDenied("Authentication required to submit a concern.")

    # Rate limit check: max 3 concerns per hour per resident
    one_hour_ago = timezone.now() - datetime.timedelta(hours=1)
    recent_count = ChatThread.objects.filter(
        initiator=resident,
        thread_type=ChatThread.THREAD_CONCERN,
        created_at__gte=one_hour_ago
    ).count()
    if recent_count >= 3:
        raise PermissionDenied("Rate limit exceeded: You may only submit 3 concerns per hour. Please try again later.")

    raw_content = data.get('content', '').strip()
    if not raw_content:
        raise ValueError("Concern description/content is required.")
    if len(raw_content) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message content exceeds maximum allowed length of {MAX_MESSAGE_LENGTH} characters.")

    # Store raw text; template auto-escape protects output
    content = raw_content
    title = data.get('title', '').strip() or f"Concern regarding {data.get('category', 'Community')}"
    category = data.get('category', ChatThread.CATEGORY_GENERAL)

    if attachment_file:
        validate_chat_attachment(attachment_file)

    handler = route_concern_handler(category)

    with transaction.atomic():
        thread = ChatThread.objects.create(
            thread_type=ChatThread.THREAD_CONCERN,
            status=ChatThread.STATUS_SUBMITTED,
            category=category,
            title=title,
            initiator=resident,
            assigned_handler=handler
        )
        thread.participants.add(resident)
        if handler:
            thread.participants.add(handler)

        msg = Message.objects.create(
            thread=thread,
            sender=resident,
            recipient=handler,
            content=content,
            attachment=attachment_file,
            attachment_filename=attachment_file.name if attachment_file else '',
            attachment_size=attachment_file.size if attachment_file else 0,
            attachment_mime=getattr(attachment_file, 'content_type', '') if attachment_file else ''
        )

        if handler:
            create_notification(
                recipient=handler,
                title=f"Concern #{thread.id} Assigned to You",
                message=f"New resident concern: '{title}'. Assigned to you.",
                url=f"/chat/concern/{thread.id}/",
                action_type="concern"
            )

        log_activity(
            actor=resident,
            action='create',
            action_type='Concern',
            target_id=str(thread.id),
            target_name=title,
            details=f"Resident submitted concern #{thread.id} in {category} (Assigned to {handler.username if handler else 'Admin'})"
        )
    return thread


def create_direct_thread_service(sender, recipient, raw_content, attachment_file=None, request=None):
    """
    Creates or retrieves a direct 1-on-1 message thread:
    - Residents may message ONLY active officers (never residents or disabled accounts).
    - Staff may start a direct message ONLY with residents in their scope.
    - Rate limit: max 15 messages/hour to officers.
    - Raw text stored.
    """
    if not sender.is_authenticated:
        raise PermissionDenied("Authentication required to send messages.")
    if sender.id == recipient.id:
        raise ValueError("Cannot initiate a direct chat with yourself.")

    # Minors cannot be messaged
    if hasattr(recipient, 'resident_profile') and recipient.resident_profile:
        if recipient.resident_profile.age is not None and recipient.resident_profile.age < 18:
            raise PermissionDenied("Minors cannot be messaged.")
    elif hasattr(recipient, 'date_of_birth') and recipient.date_of_birth:
        today = timezone.now().date()
        dob = recipient.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise PermissionDenied("Minors cannot be messaged.")

    # 1. Residents messaging restrictions
    if sender.role == User.ROLE_RESIDENT:
        if recipient.role == User.ROLE_RESIDENT:
            raise PermissionDenied("Residents may only message barangay officers, not other residents.")
        if recipient.status != User.STATUS_ACTIVE or not recipient.is_active:
            raise PermissionDenied("Cannot message an inactive or disabled account.")
        is_officer = (
            recipient.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or
            (recipient.role == User.ROLE_STAFF and recipient.is_staff) or
            recipient.is_superuser
        )
        if not is_officer:
            raise PermissionDenied("Residents may only message active barangay officers.")

        # Rate limit on DMs to officers
        one_hour_ago = timezone.now() - datetime.timedelta(hours=1)
        dm_count = Message.objects.filter(
            sender=sender,
            recipient=recipient,
            created_at__gte=one_hour_ago
        ).count()
        if dm_count >= 15:
            raise PermissionDenied("Rate limit exceeded for messaging this officer. Please try again later.")

    # 2. Staff messaging restrictions
    if sender.role == User.ROLE_STAFF and not sender.is_superuser:
        if recipient.role == User.ROLE_RESIDENT:
            if not check_staff_resident_scope(sender, recipient):
                raise PermissionDenied("Staff may only start a direct message with residents within their assigned scope.")

    raw_content = raw_content.strip()
    if not raw_content and not attachment_file:
        raise ValueError("Message content or attachment is required.")
    if len(raw_content) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message content exceeds maximum allowed length of {MAX_MESSAGE_LENGTH} characters.")

    content = raw_content

    if attachment_file:
        validate_chat_attachment(attachment_file)

    with transaction.atomic():
        thread = ChatThread.objects.filter(
            thread_type=ChatThread.THREAD_DIRECT
        ).filter(
            (Q(initiator=sender, direct_recipient=recipient) | Q(initiator=recipient, direct_recipient=sender))
        ).first()

        if not thread:
            thread = ChatThread.objects.create(
                thread_type=ChatThread.THREAD_DIRECT,
                initiator=sender,
                direct_recipient=recipient
            )
            thread.participants.add(sender, recipient)

        msg = Message.objects.create(
            thread=thread,
            sender=sender,
            recipient=recipient,
            content=content,
            attachment=attachment_file,
            attachment_filename=attachment_file.name if attachment_file else '',
            attachment_size=attachment_file.size if attachment_file else 0,
            attachment_mime=getattr(attachment_file, 'content_type', '') if attachment_file else ''
        )

        thread.save(update_fields=['updated_at'])

        sender_display = sender.get_full_name() or sender.username
        create_notification(
            recipient=recipient,
            title=f"New message from {sender_display}",
            message=content[:100],
            url=f"/chat/{sender.id}/",
            action_type="chat"
        )

    return msg


def send_thread_message_service(thread, sender, raw_content, attachment_file=None, request=None):
    """
    Sends a message within an existing thread (concern or direct):
    - Rate limit: max 20 messages per thread per 10 mins.
    - A resident message on a resolved concern reopens it (in_progress) and notifies the handler.
    - Raw text stored.
    """
    if not sender.is_authenticated:
        raise PermissionDenied("Authentication required to send a message.")

    if not thread.can_read(sender):
        raise PermissionDenied("You are not authorized to view or reply to this conversation.")

    # Rate limit check per thread
    ten_mins_ago = timezone.now() - datetime.timedelta(minutes=10)
    recent_thread_msgs = thread.messages.filter(
        sender=sender,
        created_at__gte=ten_mins_ago
    ).count()
    if recent_thread_msgs >= 20:
        raise PermissionDenied("You are sending messages too quickly in this thread. Please wait a few moments.")

    raw_content = raw_content.strip()
    if not raw_content and not attachment_file:
        raise ValueError("Message content or attachment is required.")
    if len(raw_content) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message content exceeds maximum allowed length of {MAX_MESSAGE_LENGTH} characters.")

    content = raw_content

    if attachment_file:
        validate_chat_attachment(attachment_file)

    # Determine recipient
    if thread.thread_type == ChatThread.THREAD_DIRECT:
        recipient = thread.direct_recipient if sender.id == thread.initiator_id else thread.initiator
    else:
        if sender.id == thread.initiator_id:
            recipient = thread.assigned_handler
        else:
            recipient = thread.initiator

    with transaction.atomic():
        msg = Message.objects.create(
            thread=thread,
            sender=sender,
            recipient=recipient,
            content=content,
            attachment=attachment_file,
            attachment_filename=attachment_file.name if attachment_file else '',
            attachment_size=attachment_file.size if attachment_file else 0,
            attachment_mime=getattr(attachment_file, 'content_type', '') if attachment_file else ''
        )

        was_reopened = False
        # Auto-transitions for concerns:
        if thread.thread_type == ChatThread.THREAD_CONCERN:
            # 1. If handler replies to submitted/seen concern -> in_progress
            if thread.status in [ChatThread.STATUS_SUBMITTED, ChatThread.STATUS_SEEN] and sender.id != thread.initiator_id:
                thread.status = ChatThread.STATUS_IN_PROGRESS

            # 2. Resident reply on a resolved concern reopens it (in_progress) and notifies the handler
            elif thread.status == ChatThread.STATUS_RESOLVED and sender.id == thread.initiator_id:
                thread.status = ChatThread.STATUS_IN_PROGRESS
                was_reopened = True
                log_activity(
                    actor=sender,
                    action='update',
                    action_type='Concern',
                    target_id=str(thread.id),
                    target_name=thread.title,
                    details=f"Concern #{thread.id} automatically reopened to 'in_progress' by resident reply"
                )

            thread.save(update_fields=['status', 'updated_at'])
        else:
            thread.save(update_fields=['updated_at'])

        if recipient:
            sender_display = sender.get_full_name() or sender.username
            if was_reopened:
                notif_title = f"Concern #{thread.id} Reopened by {sender_display}"
                notif_msg = f"Resident {sender_display} replied to resolved concern #{thread.id}, reopening it: {content[:80]}"
            else:
                notif_title = f"New reply from {sender_display}"
                notif_msg = content[:100]

            target_url = f"/chat/concern/{thread.id}/" if thread.thread_type == ChatThread.THREAD_CONCERN else f"/chat/{sender.id}/"
            action_type = "concern" if thread.thread_type == ChatThread.THREAD_CONCERN else "chat"
            create_notification(
                recipient=recipient,
                title=notif_title,
                message=notif_msg,
                url=target_url,
                action_type=action_type
            )

    return msg


def update_concern_status_service(thread, actor, new_status, request=None):
    """
    Updates concern status:
    - Only handler or admin can update status.
    - Valid transitions enforced.
    - Records ActivityLog.
    """
    if thread.thread_type != ChatThread.THREAD_CONCERN:
        raise ValueError("Cannot update status on a direct message thread.")

    if not thread.can_update_status(actor):
        raise PermissionDenied("Only the assigned handler or an administrator can update concern status.")

    current_status = thread.status
    if current_status == new_status:
        return thread

    allowed_transitions = {
        ChatThread.STATUS_SUBMITTED: [ChatThread.STATUS_SEEN, ChatThread.STATUS_IN_PROGRESS],
        ChatThread.STATUS_SEEN: [ChatThread.STATUS_IN_PROGRESS, ChatThread.STATUS_RESOLVED],
        ChatThread.STATUS_IN_PROGRESS: [ChatThread.STATUS_RESOLVED],
        ChatThread.STATUS_RESOLVED: [ChatThread.STATUS_IN_PROGRESS],
    }

    valid_next = allowed_transitions.get(current_status, [])
    if new_status not in valid_next:
        raise ValueError(
            f"Invalid status jump from '{current_status}' to '{new_status}'. "
            f"Allowed transitions from '{current_status}': {', '.join(valid_next)}."
        )

    with transaction.atomic():
        thread.status = new_status
        thread.save(update_fields=['status', 'updated_at'])

        create_notification(
            recipient=thread.initiator,
            title=f"Concern Status: {thread.get_status_display()}",
            message=f"Your concern #{thread.id} ('{thread.title}') has been marked as '{thread.get_status_display()}'.",
            url=f"/chat/concern/{thread.id}/",
            action_type="concern"
        )

        log_activity(
            actor=actor,
            action='update',
            action_type='Concern',
            target_id=str(thread.id),
            target_name=thread.title,
            details=f"Concern #{thread.id} status transitioned from '{current_status}' to '{new_status}' by {actor.username}"
        )

    return thread


def mark_concern_seen_service(thread, actor):
    """
    Automatically sets concern status to 'seen' when handler or admin first views it.
    """
    if thread.thread_type != ChatThread.THREAD_CONCERN:
        return thread

    if thread.status == ChatThread.STATUS_SUBMITTED:
        if thread.can_update_status(actor) and actor.id != thread.initiator_id:
            with transaction.atomic():
                thread.status = ChatThread.STATUS_SEEN
                thread.save(update_fields=['status', 'updated_at'])
                log_activity(
                    actor=actor,
                    action='update',
                    action_type='Concern',
                    target_id=str(thread.id),
                    target_name=thread.title,
                    details=f"Concern #{thread.id} automatically marked as seen by {actor.username}"
                )
    return thread


def reassign_concern_service(thread, actor, new_handler, request=None):
    """
    Reassigns a concern to another handler:
    - Allowed only by Admin or current assigned handler.
    - Logged in ActivityLog.
    """
    if thread.thread_type != ChatThread.THREAD_CONCERN:
        raise ValueError("Only concerns can be reassigned.")

    is_admin = actor.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or actor.is_superuser
    is_handler = bool(thread.assigned_handler_id and actor.id == thread.assigned_handler_id)

    if not (is_admin or is_handler):
        raise PermissionDenied("Only the current handler or an administrator can reassign this concern.")

    if not new_handler or new_handler.status != User.STATUS_ACTIVE:
        raise ValueError("Target handler must be an active staff member or administrator.")

    old_handler = thread.assigned_handler
    with transaction.atomic():
        thread.assigned_handler = new_handler
        thread.participants.add(new_handler)
        thread.save(update_fields=['assigned_handler', 'updated_at'])

        old_name = old_handler.get_full_name() if old_handler else 'None'
        new_name = new_handler.get_full_name() or new_handler.username
        log_activity(
            actor=actor,
            action='update',
            action_type='Concern',
            target_id=str(thread.id),
            target_name=thread.title,
            details=f"Concern #{thread.id} reassigned from {old_name} to {new_name} by {actor.username}"
        )

        # Resident receives notification for concern reassigned
        create_notification(
            recipient=thread.initiator,
            title="Concern Reassigned",
            message=f"Your concern #{thread.id} ('{thread.title}') has been reassigned to {new_name}.",
            url=f"/chat/concern/{thread.id}/",
            action_type="concern"
        )

        create_notification(
            recipient=new_handler,
            title=f"Concern #{thread.id} Assigned to You",
            message=f"Concern #{thread.id} ('{thread.title}') has been assigned to you.",
            url=f"/chat/concern/{thread.id}/",
            action_type="concern"
        )
    return thread


def resident_request_reassignment_service(thread, resident, request=None):
    """
    Resident initiator requests concern reassignment to Admin:
    - Moves concern to the active Admin.
    - Logged in ActivityLog.
    """
    if thread.thread_type != ChatThread.THREAD_CONCERN:
        raise ValueError("Only concerns can be reassigned.")

    if resident.id != thread.initiator_id:
        raise PermissionDenied("Only the resident who submitted this concern can request reassignment.")

    admin_user = User.objects.filter(
        role=User.ROLE_ADMIN,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first() or User.objects.filter(
        is_superuser=True,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first()

    if not admin_user:
        raise ValueError("No active administrator available to take reassignment.")

    old_handler = thread.assigned_handler
    with transaction.atomic():
        thread.assigned_handler = admin_user
        thread.participants.add(admin_user)
        thread.save(update_fields=['assigned_handler', 'updated_at'])

        old_name = old_handler.get_full_name() if old_handler else 'None'
        log_activity(
            actor=resident,
            action='update',
            action_type='Concern',
            target_id=str(thread.id),
            target_name=thread.title,
            details=f"Resident {resident.username} requested reassignment of Concern #{thread.id} from {old_name} to Admin"
        )

        create_notification(
            recipient=admin_user,
            title=f"Concern #{thread.id} Reassignment Requested",
            message=f"Resident {resident.get_full_name()} requested escalation/reassignment of concern #{thread.id} to Admin.",
            url=f"/chat/concern/{thread.id}/",
            action_type="concern"
        )
    return thread


def reassign_staff_open_concerns(staff_user, actor=None):
    """
    When a staff account is disabled, all their open concerns are reassigned to admin.
    """
    admin_user = User.objects.filter(
        role=User.ROLE_ADMIN,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first() or User.objects.filter(
        is_superuser=True,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first()

    if not admin_user:
        return 0

    open_concerns = ChatThread.objects.filter(
        thread_type=ChatThread.THREAD_CONCERN,
        assigned_handler=staff_user
    ).exclude(status=ChatThread.STATUS_RESOLVED)

    count = 0
    with transaction.atomic():
        for concern in open_concerns:
            concern.assigned_handler = admin_user
            concern.participants.add(admin_user)
            concern.save(update_fields=['assigned_handler', 'updated_at'])
            count += 1

        if count > 0:
            log_activity(
                actor=actor or admin_user,
                action='update',
                action_type='Concern',
                details=f"Reassigned {count} open concern(s) from disabled staff {staff_user.username} to admin {admin_user.username}"
            )
    return count


@receiver(post_delete, sender=StaffAssignment)
def on_staff_assignment_deleted(sender, instance, **kwargs):
    """
    Move concerns to the admin queue when a staff assignment is removed.
    """
    user = instance.user
    if not user:
        return

    admin_user = User.objects.filter(
        role=User.ROLE_ADMIN,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first() or User.objects.filter(
        is_superuser=True,
        status=User.STATUS_ACTIVE,
        is_active=True
    ).first()

    if not admin_user:
        return

    # Check if user has any remaining assignments
    remaining = StaffAssignment.objects.filter(user=user).exists()
    if not remaining:
        # Move all open concerns to admin queue
        open_concerns = ChatThread.objects.filter(
            thread_type=ChatThread.THREAD_CONCERN,
            assigned_handler=user
        ).exclude(status=ChatThread.STATUS_RESOLVED)

        for concern in open_concerns:
            concern.assigned_handler = admin_user
            concern.participants.add(admin_user)
            concern.save(update_fields=['assigned_handler', 'updated_at'])
            log_activity(
                actor=admin_user,
                action='update',
                action_type='Concern',
                target_id=str(concern.id),
                target_name=concern.title,
                details=f"Concern #{concern.id} moved to admin queue due to removal of all staff assignments for {user.username}"
            )
