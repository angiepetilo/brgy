from django.urls import path
from apps.appointments import views

app_name = 'appointments'

urlpatterns = [
    path('', views.appointment_list_view, name='list'),
    path('new/', views.appointment_create_view, name='create'),
    path('<int:pk>/', views.appointment_detail_view, name='detail'),
    path('<int:pk>/edit/', views.appointment_edit_view, name='edit'),
    path('<int:pk>/delete/', views.appointment_delete_view, name='delete'),
    path('<int:pk>/approve/', views.appointment_approve_view, name='approve'),
    path('<int:pk>/reject/', views.appointment_reject_view, name='reject'),
    path('<int:pk>/complete/', views.appointment_complete_view, name='complete'),
    path('<int:pk>/noshow/', views.appointment_noshow_view, name='noshow'),
    path('<int:pk>/supporting-id/', views.appointment_supporting_id_view, name='supporting_id'),
    path('services/', views.healthcare_service_list_view, name='service_list'),
    path('services/<int:pk>/edit/', views.healthcare_service_update_view, name='service_update'),
    path('services/<int:pk>/delete/', views.healthcare_service_delete_view, name='service_delete'),
    path('schedule/', views.health_schedule_resident_view, name='health_schedule'),
    path('schedules/manage/', views.health_schedule_manage_view, name='schedule_manage'),
    path('schedules/manage/<int:pk>/edit/', views.health_schedule_edit_view, name='schedule_edit'),
    path('schedules/manage/<int:pk>/delete/', views.health_schedule_delete_view, name='schedule_delete'),
    path('api/services/', views.api_services_view, name='api_services'),
    path('api/slots/', views.api_slots_view, name='api_slots'),
    path('api/validate-email/', views.api_validate_email_view, name='api_validate_email'),
    path('api/public-book/', views.public_appointment_book_view, name='api_public_book'),
]
