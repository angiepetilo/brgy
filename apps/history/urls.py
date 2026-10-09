from django.urls import path
from apps.history import views

app_name = 'history'

urlpatterns = [
    path('', views.history_overview, name='overview'),
    path('emails/<int:email_id>/resend/', views.resend_failed_email_view, name='resend_email'),
    path('emails/<int:email_id>/resend-failed/', views.resend_failed_email_view, name='resend_failed_email'),
]
