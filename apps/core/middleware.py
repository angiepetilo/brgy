"""Shared middleware."""
from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.core.http import json_forbidden, wants_json


def build_csp(directives):
    """'default-src 'self'; script-src 'self'; ...' from a {directive: [sources]} dict."""
    return '; '.join(
        f"{name} {' '.join(sources)}".strip() for name, sources in directives.items()
    )


class SecurityHeadersMiddleware:
    """
    Adds Content-Security-Policy (or -Report-Only when settings.CSP_REPORT_ONLY)
    and Permissions-Policy to every response. Cross-Origin-Opener-Policy comes
    from Django's SecurityMiddleware (SECURE_CROSS_ORIGIN_OPENER_POLICY).
    A view may set its own CSP header; it is then left untouched.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = build_csp(settings.CSP_DIRECTIVES)
        self.header = (
            'Content-Security-Policy-Report-Only' if settings.CSP_REPORT_ONLY
            else 'Content-Security-Policy'
        )
        self.permissions_policy = settings.PERMISSIONS_POLICY

    def __call__(self, request):
        response = self.get_response(request)
        if 'Content-Security-Policy' not in response and 'Content-Security-Policy-Report-Only' not in response:
            response[self.header] = self.policy
        response.setdefault('Permissions-Policy', self.permissions_policy)
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        return response


class JsonExceptionMiddleware:
    """
    Turns PermissionDenied raised in a view into 403 JSON when the caller wants
    JSON (see apps.core.http.wants_json). HTML requests keep Django's normal
    403 handling.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied) and wants_json(request):
            return json_forbidden(str(exception) or 'You do not have permission to perform this action.')
        return None
