from django.urls import path
from apps.appointments import views

app_name = 'appointments'

urlpatterns = [
    path('', views.appointment_list_view, name='list'),
    path('new/', views.appointment_create_view, name='create'),
    path('<int:pk>/', views.appointment_detail_view, name='detail'),
    path('verify/<str:control_number>/', views.appointment_verify_view, name='verify'),
    path('services/', views.healthcare_service_list_view, name='service_list'),
    path('services/<int:pk>/edit/', views.healthcare_service_update_view, name='service_update'),
    path('services/<int:pk>/delete/', views.healthcare_service_delete_view, name='service_delete'),
    path('api/services/', views.api_services_view, name='api_services'),
    path('api/validate-email/', views.api_validate_email_view, name='api_validate_email'),
    path('api/public-book/', views.public_appointment_book_view, name='api_public_book'),
]
