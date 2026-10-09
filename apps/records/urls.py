from django.urls import path
from apps.records import views

app_name = 'records'

urlpatterns = [
    path('', views.records_hub_view, name='hub'),
    path('documents/<int:pk>/print/', views.print_document_view, name='print_document'),
    path('health/<int:pk>/print/', views.print_health_record_view, name='print_health'),
]
