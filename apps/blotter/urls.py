from django.urls import path
from apps.blotter import views

app_name = 'blotter'

urlpatterns = [
    path('', views.blotter_dashboard_view, name='dashboard'),
    path('new/', views.blotter_create_view, name='create'),
    path('<int:pk>/', views.blotter_detail_view, name='detail'),
]
