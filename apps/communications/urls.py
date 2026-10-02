from django.urls import path
from apps.communications import views

app_name = 'communications'

urlpatterns = [
    path('', views.feed_view, name='feed'),
    path('announcements/', views.announcements_list_view, name='announcements_list'),
    path('emergency/', views.emergency_list_view, name='emergency_list'),
    path('announcements/<int:pk>/', views.announcement_detail_view, name='announcement_detail'),
    path('announcements/new/', views.create_announcement_view, name='create_announcement'),
    path('announcements/<int:pk>/edit/', views.edit_announcement_view, name='edit_announcement'),
    path('announcements/<int:pk>/delete/', views.delete_announcement_view, name='delete_announcement'),
    path('posts/<int:post_id>/react/', views.react_post_view, name='react_post'),
    path('posts/<int:post_id>/comment/', views.comment_post_view, name='comment_post'),
    path('kapitan/tracker/', views.kapitan_tracker_view, name='kapitan_tracker'),
    path('transparency/', views.transparency_portal_view, name='transparency'),
    path('transparency/new/', views.legislative_create_view, name='legislative_create'),
]
