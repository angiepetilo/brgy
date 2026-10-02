from django.urls import path
from apps.finance import views

app_name = 'finance'

urlpatterns = [
    path('', views.finance_overview_view, name='overview'),
    path('assets/new/', views.asset_create_view, name='asset_create'),
    path('assets/<int:pk>/edit/', views.asset_edit_view, name='asset_edit'),
]
