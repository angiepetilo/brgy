"""
Views for the System Module (PART G).
Accessible exclusively by administrators and superusers (admin-only by default).

Views stay thin: reads come from ``selectors``, writes from ``system_services``.
Error policy (see ``_run_service``): a ``ValueError``/validation error shows its own
message, a missing object shows a "no longer exists" message, ``PermissionDenied`` is
re-raised, and anything else is logged with ``logger.exception`` and shown as a generic
message so internals never reach the browser.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import JsonResponse
from django.urls import reverse
from urllib.parse import urlencode

from apps.accounts.permissions import require_perm, check_user_perm
from apps.accounts import selectors, system_services
from apps.accounts.system_utils import with_unchecked_checkboxes
from apps.core.http import wants_json

logger = logging.getLogger(__name__)

GENERIC_ERROR = "Something went wrong. Please try again."
MISSING_ERROR = "That item no longer exists. Refresh the page and try again."

# Checkboxes each form renders. A browser does not post an unchecked box, so the view
# treats "not posted" as unchecked (see system_utils for the create/update rule).
POST_CATEGORY_CHECKBOXES = ('expires', 'notify_on_post', 'is_active')
DOCUMENT_TYPE_CHECKBOXES = ('is_active',)
HEALTH_SERVICE_CHECKBOXES = ('is_active', 'is_free')
CONCERN_CATEGORY_CHECKBOXES = ('is_active',)


SYSTEM_ACTIONS = (
    'edit', 'manage_categories', 'manage_documents', 'manage_health_services',
    'manage_concerns', 'manage_staff', 'preview_emails',
)


def _settings_redirect(tab, subtab=None):
    """Redirect to the System Settings page using the canonical tab/subtab names."""
    params = {'tab': tab}
    if subtab:
        params['subtab'] = subtab
    return redirect(f"{reverse('accounts:system_dashboard')}?{urlencode(params)}")


def _error_message(exc):
    """Message that is safe to show for an exception, or None if it is an internal error."""
    if isinstance(exc, ValidationError):
        return ' '.join(exc.messages)
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ObjectDoesNotExist):
        return MISSING_ERROR
    return None


def _run_service(request, fn, success_message, level='success'):
    """
    Run ``fn()`` and queue a flash message.
    ``success_message`` is a string or a callable receiving fn's result.
    """
    try:
        result = fn()
    except PermissionDenied:
        raise
    except Exception as exc:
        safe = _error_message(exc)
        if safe is None:
            logger.exception("System settings action failed: %s %s", request.method, request.path)
            safe = GENERIC_ERROR
        messages.error(request, safe)
        return None
    text = success_message(result) if callable(success_message) else success_message
    getattr(messages, level)(request, text)
    return result


def _json_error(exc, path):
    safe = _error_message(exc)
    if safe is None:
        logger.exception("System settings email template request failed: %s", path)
        safe = GENERIC_ERROR
    return JsonResponse({'error': safe}, status=400)


@require_perm('system', 'view')
def system_dashboard_view(request):
    """
    Unified System Administration Dashboard:
    - BarangayInfo
    - Post Categories
    - Document Types & Checklist Requirements
    - Health Care Services
    - Concern Categories & Routing Targets
    - Staff Accounts & Terms Ending in 30 Days
    - Email Template Previews
    Legacy tab names (documents, health_services, staff_accounts, concern_categories) are
    normalised to the canonical tab + subtab.
    """
    active_tab, active_subtab = selectors.normalize_system_tab(
        request.GET.get('tab'), request.GET.get('subtab')
    )
    context = selectors.system_dashboard_data()
    context.update({
        'active_tab': active_tab,
        'active_subtab': active_subtab,
        'email_templates_list': system_services.EMAIL_TEMPLATE_CATALOG,
        'ending_soon_ids': {u.id for u in context['terms_ending_soon']},
        # Edit controls are rendered only for actions the user may perform.
        'can': {
            **{action: check_user_perm(request.user, 'system', action) for action in SYSTEM_ACTIONS},
            'manage_schedule': check_user_perm(request.user, 'health_center', 'manage_schedule'),
            'edit_officers': check_user_perm(request.user, 'officers', 'edit'),
        },
    })
    return render(request, 'accounts/system/system_dashboard.html', context)


@require_perm('system', 'edit')
def update_barangay_info_view(request):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.update_barangay_info_service(
                request.user, request.POST, request.FILES.get('logo')
            ),
            "Barangay Information updated successfully.",
        )
    return _settings_redirect('barangay_info')


@require_perm('system', 'manage_categories')
def post_category_save_view(request, category_id=None):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.create_or_update_post_category_service(
                actor=request.user,
                data=with_unchecked_checkboxes(request.POST, POST_CATEGORY_CHECKBOXES),
                category_id=category_id,
            ),
            lambda cat: f"Post Category '{cat.name}' saved successfully.",
        )
    return _settings_redirect('post_categories')


@require_perm('system', 'manage_categories')
def post_category_delete_view(request, category_id):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.delete_post_category_service(request.user, category_id),
            "Post Category deleted successfully.",
        )
    return _settings_redirect('post_categories')


@require_perm('system', 'manage_documents')
def document_type_save_view(request, doc_id=None):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.create_or_update_document_type_service(
                actor=request.user,
                data=with_unchecked_checkboxes(request.POST, DOCUMENT_TYPE_CHECKBOXES),
                doc_id=doc_id,
            ),
            lambda doc: f"Document Type '{doc.name}' saved successfully.",
        )
    return _settings_redirect('document_health', 'documents')


@require_perm('system', 'manage_documents')
def document_type_delete_view(request, doc_id):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.delete_document_type_service(request.user, doc_id),
            "Document Type deleted successfully.",
        )
    return _settings_redirect('document_health', 'documents')


@require_perm('system', 'manage_health_services')
def health_service_save_view(request, svc_id=None):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.create_or_update_health_service_service(
                actor=request.user,
                data=with_unchecked_checkboxes(request.POST, HEALTH_SERVICE_CHECKBOXES),
                svc_id=svc_id,
            ),
            lambda svc: f"Health Care Service '{svc.name}' saved successfully.",
        )
    return _settings_redirect('document_health', 'health')


@require_perm('system', 'manage_health_services')
def health_service_delete_view(request, svc_id):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.delete_health_service_service(request.user, svc_id),
            "Health Care Service deleted successfully.",
        )
    return _settings_redirect('document_health', 'health')


@require_perm('system', 'manage_concerns')
def concern_category_save_view(request, cat_id=None):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.create_or_update_concern_category_service(
                actor=request.user,
                data=with_unchecked_checkboxes(request.POST, CONCERN_CATEGORY_CHECKBOXES),
                cat_id=cat_id,
            ),
            lambda cat: f"Concern Category '{cat.name}' saved successfully.",
        )
    return _settings_redirect('user_management', 'concerns')


@require_perm('system', 'manage_concerns')
def concern_category_delete_view(request, cat_id):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.delete_concern_category_service(request.user, cat_id),
            "Concern Category deleted successfully.",
        )
    return _settings_redirect('user_management', 'concerns')


@require_perm('system', 'manage_staff')
def staff_account_create_view(request):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.create_staff_account_service(request.user, request.POST),
            lambda user: (
                f"Staff account for {user.get_full_name() or user.username} ({user.email}) created! "
                "Temporary credentials were sent to their email."
            ),
        )
    return _settings_redirect('user_management', 'staff')


@require_perm('system', 'manage_staff')
def staff_account_disable_view(request, user_id):
    if request.method == 'POST':
        _run_service(
            request,
            lambda: system_services.disable_staff_account_service(request.user, user_id),
            lambda user: f"Staff account '{user.username}' has been disabled.",
            level='warning',
        )
    return _settings_redirect('user_management', 'staff')


@require_perm('system', 'preview_emails')
def email_template_preview_api_view(request, template_name):
    """
    Returns read-only preview of requested email template in JSON format for the preview modal.
    """
    try:
        return JsonResponse(system_services.render_email_template_preview(template_name))
    except PermissionDenied:
        raise
    except Exception as exc:
        return _json_error(exc, request.path)


@require_perm('system', 'preview_emails')
def email_template_edit_view(request, template_name):
    """
    GET: Returns raw template source for the edit modal.
    POST: Saves updated template subject and body.
    """
    if request.method == 'POST':
        # Templates are Django template code: saving needs system.edit, not just preview.
        if not check_user_perm(request.user, 'system', 'edit'):
            raise PermissionDenied
        content = request.POST.get('content', '')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        if template_name in system_services.EMAIL_TEMPLATES_WITHOUT_SUBJECT:
            # Their subject lives in a separate file; never write a 'Subject:' line into the body.
            subject = ''
        if not content and subject:
            content = f"Subject: {subject}\n\n{body}\n"
        elif not content and body:
            content = f"{body}\n"

        try:
            system_services.update_email_template_service(request.user, template_name, content)
        except PermissionDenied:
            raise
        except Exception as exc:
            if wants_json(request):
                return _json_error(exc, request.path)
            safe = _error_message(exc)
            if safe is None:
                logger.exception("System settings email template save failed: %s", request.path)
                safe = GENERIC_ERROR
            messages.error(request, safe)
        else:
            if wants_json(request):
                return JsonResponse({'status': 'success', 'message': 'Email template updated successfully.'})
            messages.success(request, f"Email template '{template_name}' updated successfully.")
        return _settings_redirect('email_templates')

    try:
        return JsonResponse(system_services.get_email_template_source(template_name))
    except PermissionDenied:
        raise
    except Exception as exc:
        return _json_error(exc, request.path)
