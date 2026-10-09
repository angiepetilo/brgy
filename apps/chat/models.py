import os
import uuid
from django.db import models
from django.conf import settings


def chat_attachment_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"private_attachments/{uuid.uuid4().hex}{ext}"


class ConcernCategory(models.Model):
    """
    Admin-editable concern categories (will be built in Part G).
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    routing_target_type = models.CharField(
        max_length=20,
        choices=[('service_area', 'Service Area'), ('committee', 'Committee')],
        default='service_area'
    )
    routing_target_value = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Name of assigned service area or committee"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Concern Category'
        verbose_name_plural = 'Concern Categories'

    def __str__(self):
        return self.name


class ChatThread(models.Model):
    """
    Two thread types:
    1. concern: ticket/issue with status (submitted, seen, in_progress, resolved) and category.
    2. direct: direct message between two participants (no status).
    """
    THREAD_CONCERN = 'concern'
    THREAD_DIRECT = 'direct'
    THREAD_TYPE_CHOICES = [
        (THREAD_CONCERN, 'Resident Concern / Ticket'),
        (THREAD_DIRECT, 'Direct Message'),
    ]

    STATUS_SUBMITTED = 'submitted'
    STATUS_SEEN = 'seen'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_SEEN, 'Seen'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    CATEGORY_HEALTH = 'health'
    CATEGORY_PEACE_ORDER = 'peace_and_order'
    CATEGORY_EDUCATION = 'education'
    CATEGORY_INFRASTRUCTURE = 'infrastructure'
    CATEGORY_GENERAL = 'general'
    CATEGORY_CHOICES = [
        (CATEGORY_HEALTH, 'Health & Medical Services'),
        (CATEGORY_PEACE_ORDER, 'Peace, Order & Tanod'),
        (CATEGORY_EDUCATION, 'Education, Youth & Scholarship'),
        (CATEGORY_INFRASTRUCTURE, 'Infrastructure & Public Works'),
        (CATEGORY_GENERAL, 'General Community Concern'),
    ]

    thread_type = models.CharField(
        max_length=20,
        choices=THREAD_TYPE_CHOICES,
        default=THREAD_DIRECT,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="Status for concerns only. Null for direct messages."
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        blank=True,
        default='',
        db_index=True
    )
    title = models.CharField(max_length=255, blank=True, default='')

    # Thread participants & handlers
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='initiated_threads'
    )
    assigned_handler = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_concerns'
    )
    direct_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='direct_message_threads'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_threads',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Chat Thread / Concern'
        verbose_name_plural = 'Chat Threads / Concerns'

    def __str__(self):
        if self.thread_type == self.THREAD_CONCERN:
            return f"Concern #{self.id} [{self.get_status_display()}]: {self.title or self.category}"
        other = self.direct_recipient.username if self.direct_recipient else 'Unknown'
        return f"DM [{self.initiator.username} & {other}]"

    def is_participant(self, user):
        """Checks if a user is a direct participant in this thread."""
        if not user or not user.is_authenticated:
            return False
        if user.id == self.initiator_id:
            return True
        if self.direct_recipient_id and user.id == self.direct_recipient_id:
            return True
        if self.assigned_handler_id and user.id == self.assigned_handler_id:
            return True
        return self.participants.filter(id=user.id).exists()

    def can_read(self, user):
        """
        Only participants can read a thread; the assigned handler and admin can also read concerns;
        direct messages only the two participants.
        """
        if not user or not user.is_authenticated:
            return False
        if self.thread_type == self.THREAD_DIRECT:
            return user.id == self.initiator_id or user.id == self.direct_recipient_id
        # For concerns:
        if user.id == self.initiator_id:
            return True
        if self.assigned_handler_id and user.id == self.assigned_handler_id:
            return True
        if user.role == 'admin' or user.is_superuser:
            return True
        return False

    def can_update_status(self, user):
        """Only the handler or admin changes status of concerns."""
        if self.thread_type != self.THREAD_CONCERN:
            return False
        if not user or not user.is_authenticated:
            return False
        if user.role == 'admin' or user.is_superuser:
            return True
        if self.assigned_handler_id and user.id == self.assigned_handler_id:
            return True
        return False


class Message(models.Model):
    """
    Direct messaging and concern discussion messages.
    """
    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_messages'
    )
    content = models.TextField()
    attachment = models.FileField(
        upload_to=chat_attachment_upload_path,
        blank=True,
        null=True
    )
    attachment_filename = models.CharField(max_length=255, blank=True, default='')
    attachment_size = models.PositiveIntegerField(default=0)
    attachment_mime = models.CharField(max_length=100, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    @property
    def text(self):
        return self.content

    @property
    def timestamp(self):
        return self.created_at

    def __str__(self):
        recip_name = self.recipient.username if self.recipient else "Thread"
        return f"{self.sender.username} -> {recip_name}: {self.content[:30]}"


class Notification(models.Model):
    """
    Global notification records for real-time bell badges and toast popups.
    """
    TYPE_APPOINTMENT = 'appointment'
    TYPE_STATUS = 'status'
    TYPE_APPROVAL = 'approval'
    TYPE_CHAT = 'chat'
    TYPE_ANNOUNCEMENT = 'announcement'

    TYPE_CHOICES = [
        (TYPE_APPOINTMENT, 'Appointment Update'),
        (TYPE_STATUS, 'Kapitan Status'),
        (TYPE_APPROVAL, 'Account Verification'),
        (TYPE_CHAT, 'Direct Message'),
        (TYPE_ANNOUNCEMENT, 'New Announcement'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default=TYPE_APPOINTMENT
    )
    url = models.CharField(max_length=255, blank=True, default='')
    action_type = models.CharField(max_length=50, blank=True, default='')
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        if self.url and not self.link_url:
            self.link_url = self.url
        elif self.link_url and not self.url:
            self.url = self.link_url
        if self.action_type and not self.notification_type:
            self.notification_type = self.action_type
        elif self.notification_type and not self.action_type:
            self.action_type = self.notification_type
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
