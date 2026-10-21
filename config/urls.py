from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.generic.base import RedirectView

from apps.communications import views as comm_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/images/barangay_logo.png', permanent=False)),
    # Root only Django Admin
    path('admin/', admin.site.urls),

    # Module 0: Landing and Public Booking
    path('', comm_views.landing_view, name='landing'),
    path('landing/', comm_views.landing_view, name='landing_page'),

    # Module 1: Accounts and Login
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('system/', lambda request: redirect('/accounts/system/?' + request.META.get('QUERY_STRING', ''))),
    path('dashboard/', lambda request: redirect('home')),

    # Module 2: Home
    path('feed/', comm_views.feed_view, name='feed'),
    path('home/', comm_views.feed_view, name='home'),
    path('home/', include('apps.communications.urls', namespace='communications')),

    # Module 3: Announcements
    path('announcements/', lambda request: redirect('communications:announcements_list'), name='announcements_hub'),

    # Module 4: Emergency
    path('emergency/', lambda request: redirect('communications:emergency_list'), name='emergency_hub'),

    # Module 5 & 14: Messages & Notifications
    path('chat/', include('apps.chat.urls', namespace='chat')),
    path('messages/', lambda request: redirect('chat:inbox'), name='messages_hub'),

    # Module 6, 8, 9: Appointments, Health Center, Documents
    path('appointments/', include('apps.appointments.urls', namespace='appointments')),
    path('communications/<path:subpath>', lambda request, subpath: redirect(f'/home/{subpath}')),
    path('communications/', lambda request: redirect('home')),

    # Directory (Officers and Department Directory)
    path('directory/', lambda request: redirect('accounts:departments_directory'), name='directory_hub'),

    # Inventory and Asset Tracking
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),

    # Financial Management
    path('financial-management/', include('apps.finance.urls', namespace='finance')),
    path('finance/', lambda request: redirect('finance:financial_management'), name='finance_hub'),
    # Blotter (Katarungang Pambarangay)
    path('blotter/', include('apps.blotter.urls', namespace='blotter')),

    # Module 11: Statistics (Consolidated Overview & Export)
    path('statistics/', include('apps.statistics.urls', namespace='statistics')),
    path('stats_overview/', lambda request: redirect('statistics:overview'), name='stats_overview'),

    # Module 12: History & Email Log
    path('history/', include('apps.history.urls', namespace='history')),
    path('history_overview/', lambda request: redirect('history:overview'), name='history_overview'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
