from django.urls import path
from apps.chat import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('<int:user_id>/', views.chat_room_view, name='room'),
    path('concern/new/', views.submit_concern_view, name='submit_concern'),
    path('concern/<int:concern_id>/', views.concern_detail_view, name='concern_detail'),
    path('concern/<int:concern_id>/status/', views.update_concern_status_view, name='update_concern_status'),
    path('concern/<int:concern_id>/reassign/', views.reassign_concern_view, name='reassign_concern'),
    path('messages/<int:message_id>/attachment/', views.serve_chat_attachment_view, name='serve_attachment'),
    path('notifications/', views.notifications_list_view, name='notifications_list'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read_view, name='mark_all_read'),
    path('notifications/unread-count/', views.unread_notifications_count_api, name='unread_notifications_count'),
    path('notifications/<int:notif_id>/open/', views.open_notification_view, name='open_notification'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_api, name='mark_notification_read'),
]
