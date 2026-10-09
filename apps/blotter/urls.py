from django.urls import path

from apps.blotter import api, views

app_name = 'blotter'

urlpatterns = [
    path('', views.case_list, name='case_list'),
    path('new/', views.case_create, name='case_create'),
    path('<int:pk>/', views.case_detail, name='case_detail'),
    path('<int:pk>/edit/', views.case_edit, name='case_edit'),
    path('<int:pk>/transition/', views.case_transition, name='case_transition'),
    path('<int:pk>/hearings/add/', views.hearing_add, name='hearing_add'),
    path('<int:pk>/delete/', views.case_delete, name='case_delete'),
    path('<int:pk>/print/', views.case_print, name='case_print'),
    # JSON API (blotter.view; create needs blotter.create)
    path('api/cases/', api.api_list, name='api_list'),
    path('api/cases/create/', api.api_create, name='api_create'),
    path('api/cases/<int:pk>/', api.api_detail, name='api_detail'),
    path('api/cases/<int:pk>/transition/', api.api_transition, name='api_transition'),
]
