from django.urls import path
from django.contrib.auth import views as auth_views
from apps.accounts import views, system_views
from apps.core.ratelimit import ratelimit

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('pending/', views.pending_approval_view, name='pending_approval'),
    path('id-photo/<int:resident_id>/', views.serve_id_photo_view, name='serve_id_photo'),
    path('residents/', views.residents_tabbed_view, name='residents_tabbed'),
    path('residents/<int:user_id>/edit/', views.resident_edit_view, name='resident_edit'),
    path('residents/<int:user_id>/delete/', views.resident_delete_view, name='resident_delete'),
    path('residents/<int:user_id>/approve/', views.approve_resident_view, name='resident_approve_direct'),
    path('residents/<int:user_id>/reject/', views.reject_resident_view, name='resident_reject_direct'),
    path('residents/<int:user_id>/resend-temp-password/', views.resend_temp_password_view, name='resend_temp_password'),
    path('residents/register/', views.staff_register_resident_view, name='staff_register_resident'),
    path('residents/<int:resident_id>/needs/', views.update_resident_needs_view, name='update_resident_needs'),
    path('residents/assign/', views.assign_resident_officer_view, name='assign_resident_officer'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('officers/permissions/', views.officers_permissions_view, name='officers_permissions'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/avatar/remove/', views.remove_avatar_view, name='remove_avatar'),

    # Password reset (Django built-in; generic response regardless of email existence)
    path(
        'password-reset/',
        ratelimit(key='ip', rate='password_reset')(auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='emails/password_reset_email.txt',
            subject_template_name='emails/password_reset_subject.txt',
            success_url='/accounts/password-reset/done/',
            extra_context={'title': 'Reset Your Password'},
        )),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url='/accounts/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # System Module (Part G - Admin Only)
    path('system/', system_views.system_dashboard_view, name='system_dashboard'),
    path('system/barangay-info/update/', system_views.update_barangay_info_view, name='system_barangay_info_update'),
    path('system/categories/create/', system_views.post_category_save_view, name='system_post_category_create'),
    path('system/categories/<int:category_id>/edit/', system_views.post_category_save_view, name='system_post_category_edit'),
    path('system/categories/<int:category_id>/delete/', system_views.post_category_delete_view, name='system_post_category_delete'),
    path('system/documents/create/', system_views.document_type_save_view, name='system_document_type_create'),
    path('system/documents/<int:doc_id>/edit/', system_views.document_type_save_view, name='system_document_type_edit'),
    path('system/documents/<int:doc_id>/delete/', system_views.document_type_delete_view, name='system_document_type_delete'),
    path('system/health-services/create/', system_views.health_service_save_view, name='system_health_service_create'),
    path('system/health-services/<int:svc_id>/edit/', system_views.health_service_save_view, name='system_health_service_edit'),
    path('system/health-services/<int:svc_id>/delete/', system_views.health_service_delete_view, name='system_health_service_delete'),
    path('system/concerns/create/', system_views.concern_category_save_view, name='system_concern_category_create'),
    path('system/concerns/<int:cat_id>/edit/', system_views.concern_category_save_view, name='system_concern_category_edit'),
    path('system/concerns/<int:cat_id>/delete/', system_views.concern_category_delete_view, name='system_concern_category_delete'),
    path('system/staff/create/', system_views.staff_account_create_view, name='system_staff_account_create'),
    path('system/staff/<int:user_id>/disable/', system_views.staff_account_disable_view, name='system_staff_account_disable'),
    path('system/emails/<str:template_name>/preview/', system_views.email_template_preview_api_view, name='system_email_preview'),
    path('system/emails/<str:template_name>/edit/', system_views.email_template_edit_view, name='system_email_edit'),
]
