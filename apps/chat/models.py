from django.db import models
from django.conf import settings


class Message(models.Model):
    """
    Direct messaging between residents and barangay staff / administrators.
    """
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    content = models.TextField()
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
        return f"{self.sender.username} -> {self.recipient.username}: {self.content[:30]}"


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
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
