from django.contrib import admin
from apps.history.models import ActivityLog, EmailLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'action_type', 'target_name', 'target_id')
    list_filter = ('action', 'action_type', 'created_at')
    search_fields = ('target_name', 'target_id', 'details', 'actor__username', 'actor__first_name', 'actor__last_name')
    readonly_fields = ('created_at', 'actor', 'action', 'action_type', 'target_id', 'target_name', 'details')


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'recipient', 'subject', 'email_type', 'status')
    list_filter = ('status', 'email_type', 'created_at')
    search_fields = ('recipient', 'recipient_name', 'subject', 'error_message')
    readonly_fields = ('created_at', 'recipient', 'recipient_name', 'subject', 'email_type', 'status', 'error_message')
