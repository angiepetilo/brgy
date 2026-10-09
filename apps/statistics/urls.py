from django.urls import path
from apps.statistics import api, views

app_name = 'statistics'

urlpatterns = [
    path('', views.stats_overview, name='overview'),
    path('export/excel/', views.stats_export_excel, name='export_excel'),
    path('export/pdf/', views.stats_export_pdf, name='export_pdf'),
    # JSON API (statistics.view). Filters: date_from, date_to, purok.
    path('api/summary/', api.summary, name='api_summary'),
    path('api/demographics/', api.demographics, name='api_demographics'),
    path('api/purok-density/', api.purok_density, name='api_purok_density'),
    path('api/appointments/', api.appointments, name='api_appointments'),
    path('api/revenue/', api.revenue, name='api_revenue'),
    path('api/blotter/', api.blotter, name='api_blotter'),
]
