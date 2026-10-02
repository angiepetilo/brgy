from django.urls import path
from apps.chat import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('<int:user_id>/', views.chat_room_view, name='room'),
    path('notifications/', views.notifications_list_view, name='notifications_list'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_api, name='mark_notification_read'),
]
