from django.urls import path
from apps.accounts import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('pending/', views.pending_approval_view, name='pending_approval'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('approvals/', views.approval_list_view, name='approval_list'),
    path('approvals/<int:user_id>/approve/', views.approve_resident_view, name='approve_resident'),
    path('approvals/<int:user_id>/reject/', views.reject_resident_view, name='reject_resident'),
    path('approvals/<int:user_id>/reevaluate/', views.reevaluate_resident_view, name='reevaluate_resident'),
    path('residents/', views.residents_tabbed_view, name='residents_tabbed'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/avatar/remove/', views.remove_avatar_view, name='remove_avatar'),
    path('settings/', views.settings_view, name='settings'),
    path('rbi/', views.rbi_directory_view, name='rbi_directory'),
]
