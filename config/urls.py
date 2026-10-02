from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.blotter import views as blotter_views
from apps.communications import views as comm_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', comm_views.landing_view, name='landing'),
    path('landing/', comm_views.landing_view, name='landing_page'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', lambda request: redirect('accounts:dashboard')),
    path('feed/', comm_views.feed_view, name='feed'),
    path('records/', blotter_views.records_hub_view, name='records_hub'),
    path('appointments/', include('apps.appointments.urls', namespace='appointments')),
    path('communications/', include('apps.communications.urls', namespace='communications')),
    path('announcements/', lambda request: redirect('communications:announcements_list'), name='announcements_hub'),
    path('emergency/', lambda request: redirect('communications:emergency_list'), name='emergency_hub'),
    path('chat/', include('apps.chat.urls', namespace='chat')),
    path('messages/', lambda request: redirect('chat:inbox'), name='messages_hub'),
    path('blotter/', include('apps.blotter.urls', namespace='blotter')),
    path('finance/', include('apps.finance.urls', namespace='finance')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
