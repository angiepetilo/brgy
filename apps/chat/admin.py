from django.contrib import admin
from apps.chat.models import Message, Notification


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'content', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'recipient__username', 'content')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('recipient__username', 'title', 'message')
