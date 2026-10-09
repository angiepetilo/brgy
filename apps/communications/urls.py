from django.urls import path
from apps.communications import views

app_name = 'communications'

urlpatterns = [
    path('', views.feed_view, name='home'),
    path('', views.feed_view, name='feed'),
    path('announcements/', views.announcements_list_view, name='announcements_list'),
    path('emergency/', views.emergency_list_view, name='emergency_list'),
    path('manage/history/', views.manage_history_posts_view, name='manage_history'),
    path('announcements/<int:pk>/', views.announcement_detail_view, name='announcement_detail'),
    path('announcements/new/', views.create_announcement_view, name='create_announcement'),
    path('announcements/create/', views.create_announcement_view, name='create_announcement_alias'),
    path('announcements/<int:pk>/edit/', views.edit_announcement_view, name='edit_announcement'),
    path('announcements/<int:pk>/delete/', views.delete_announcement_view, name='delete_announcement'),
    path('announcements/<int:pk>/toggle-pin/', views.toggle_pin_announcement_view, name='toggle_pin_announcement'),
    path('announcements/<int:pk>/extend/', views.extend_announcement_view, name='extend_announcement'),
    path('announcements/<int:pk>/mark-done/', views.mark_done_announcement_view, name='mark_done_announcement'),
    path('announcements/<int:pk>/reopen/', views.reopen_announcement_view, name='reopen_announcement'),
    path('posts/<int:post_id>/react/', views.react_post_view, name='react_post'),
    path('posts/<int:post_id>/comment/', views.comment_post_view, name='comment_post'),
]
