from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_COMPLETE = 'complete'
    ACTION_NO_SHOW = 'no_show'
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'

    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approve'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_COMPLETE, 'Complete'),
        (ACTION_NO_SHOW, 'No-Show'),
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default=ACTION_APPROVE)
    action_type = models.CharField(max_length=100, help_text="e.g. Resident Registration, Appointment, Document Issuance")
    target_id = models.CharField(max_length=100, blank=True, default='')
    target_name = models.CharField(max_length=255, blank=True, default='')
    details = models.TextField(blank=True, default='', help_text="State of rejection, remarks, or notes")
    ip_address = models.CharField(max_length=45, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Activity & Audit Log'
        verbose_name_plural = 'Activity & Audit Logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['action_type']),
            models.Index(fields=['actor']),
        ]

    def __str__(self):
        actor_name = self.actor.get_full_name() or self.actor.username if self.actor else "System"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {actor_name} {self.get_action_display()} {self.action_type} #{self.target_id}"

    @property
    def badge_class(self):
        mapping = {
            self.ACTION_APPROVE: 'badge-success',
            self.ACTION_REJECT: 'badge-danger',
            self.ACTION_COMPLETE: 'badge-primary',
            self.ACTION_NO_SHOW: 'badge-warning',
            self.ACTION_CREATE: 'badge-info',
            self.ACTION_UPDATE: 'badge-secondary',
            self.ACTION_DELETE: 'badge-danger',
        }
        return mapping.get(self.action, 'badge-secondary')


class EmailLog(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    recipient = models.EmailField()
    recipient_name = models.CharField(max_length=255, blank=True, default='')
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='', help_text="Rendered email body. Never stores secret temporary passwords.")
    email_type = models.CharField(max_length=100, blank=True, default='')
    ref_table = models.CharField(max_length=100, blank=True, default='')
    ref_id = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    is_secret = models.BooleanField(default=False, help_text="True for credentials/passwords emails that must not be resent or stored.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Dispatch Log'
        verbose_name_plural = 'Email Dispatch Logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['recipient']),
            models.Index(fields=['email_type']),
        ]

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] To: {self.recipient} - {self.subject} ({self.status}, attempts={self.attempts})"
