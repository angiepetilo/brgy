from django.urls import path
from apps.inventory import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_view, name='inventory'),
]
