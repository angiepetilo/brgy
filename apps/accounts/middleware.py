"""
Middleware for the accounts app.

ApprovalGateMiddleware   — enforces login, active-account, and force-password-change gates
LoginThrottleMiddleware  — rate-limits failed login attempts (5 failures → 15-min lockout per account+IP)
SessionIdleTimeoutMiddleware — logs out sessions idle for longer than SESSION_IDLE_TIMEOUT seconds
"""

import logging
import time
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import User
from apps.core.http import json_login_required, wants_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ApprovalGateMiddleware
# ---------------------------------------------------------------------------
class ApprovalGateMiddleware:
    """
    Enforces Access & Permission Rules:
    1. Landing page stays public ('/' and '/landing/'). Everything else requires login and status = active.
    2. Sensitive media (id_photos/) is NEVER public.
    3. If must_change_password is True, redirect every request to the change-password page until done.
    4. Non-active users are logged out and redirected to login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Sensitive media is NEVER public. Appointment supporting documents are
        # streamed only by appointments:supporting_id, so /media/appointments/
        # (legacy public copies) is denied to everyone.
        if path.startswith('/media/appointments/'):
            if not request.user.is_authenticated:
                return redirect(f"/accounts/login/?next={path}")
            raise PermissionDenied("Supporting documents are only available from the appointment page.")
        # ID photos / legacy ID proofs: staff only (residents use accounts:serve_id_photo).
        if path.startswith(('/media/id_photos/', '/media/id_proofs/')):
            if not request.user.is_authenticated:
                return redirect(f"/accounts/login/?next={path}")
            if not (request.user.role in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_KAPITAN]
                    or request.user.is_staff or request.user.is_superuser):
                raise PermissionDenied("Direct access to ID photo files is restricted.")

        # Completely public paths accessible without login
        public_exact = ['/', '/landing/']
        public_prefixes = [
            '/static/',
            '/media/avatars/',
            '/media/announcements/',
            '/media/attachments/',
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/logout/',
            '/accounts/password-reset/',
        ]

        is_public = (
            path in public_exact or
            any(path.startswith(prefix) for prefix in public_prefixes)
        )

        if not request.user.is_authenticated:
            if not is_public:
                if wants_json(request):
                    return json_login_required(request)
                return redirect(f"/accounts/login/?next={path}")
            return self.get_response(request)

        # Authenticated user checks
        user = request.user

        # Status Check: Must be active to access the portal
        if user.status != User.STATUS_ACTIVE:
            logout(request)
            if wants_json(request) and not is_public:
                return json_login_required(request, 'Your account is not active. Please log in again.')
            return redirect('/accounts/login/')

        # Session idle timeout
        idle_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', None)
        if idle_timeout:
            last_active = request.session.get('_last_active')
            now = int(time.time())
            if last_active and (now - last_active) > idle_timeout:
                logout(request)
                if wants_json(request):
                    return json_login_required(request)
                from django.contrib import messages
                messages.info(request, "Your session expired due to inactivity. Please log in again.")
                return redirect('/accounts/login/')
            request.session['_last_active'] = now

        # Force Password Change Check
        if user.must_change_password:
            exempt_for_password_change = [
                '/accounts/change-password/',
                '/accounts/logout/',
                '/static/',
            ]
            if not any(path.startswith(p) for p in exempt_for_password_change):
                return redirect('accounts:change_password')
        else:
            # If user does not need to change password but attempts to visit change-password page
            if path == '/accounts/change-password/':
                return redirect('home')

        return self.get_response(request)


# ---------------------------------------------------------------------------
# LoginThrottleMiddleware
# ---------------------------------------------------------------------------
class LoginThrottleMiddleware:
    """
    Pre-check for login POSTs. Failures are counted by the user_login_failed
    signal (apps.accounts.login_security); this middleware only refuses a login
    POST while any lock (username+IP, IP, or username) is active, with HTTP 429,
    a Retry-After header and the same generic message for every account.
    """

    LOGIN_PATH = '/accounts/login/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.LOGIN_PATH and request.method == 'POST':
            from apps.accounts import login_security
            from apps.core.net import get_client_ip

            remaining = login_security.lock_remaining(
                request.POST.get('username', ''), get_client_ip(request),
            )
            if remaining:
                from django.shortcuts import render
                from apps.accounts.forms import UserLoginForm

                minutes = max(1, -(-remaining // 60))  # ceil
                response = render(
                    request,
                    'accounts/login.html',
                    {
                        'form': UserLoginForm(request),
                        'throttled': True,
                        'lockout_minutes': minutes,
                    },
                    status=429,
                )
                response['Retry-After'] = str(remaining)
                return response

        return self.get_response(request)
