"""
JSON-or-HTML helpers for error responses.

API callers (fetch/XHR) must get a JSON body with the right status code, not
a login page with HTTP 200 after a redirect, or the browser shows a JSON parse
error instead of a useful message.
"""
from urllib.parse import quote

from django.http import JsonResponse


def wants_json(request):
    """True for API paths, JSON Accept headers and XMLHttpRequest calls."""
    if '/api/' in request.path:
        return True
    if 'application/json' in request.headers.get('Accept', ''):
        return True
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def login_url_for(request):
    """Login URL that returns to the current path afterwards."""
    return f"/accounts/login/?next={quote(request.get_full_path())}"


def json_error(status, message, **extra):
    """JsonResponse {"error": message, **extra} with the given status and no caching."""
    response = JsonResponse({'error': message, **extra}, status=status)
    response['Cache-Control'] = 'no-store'
    return response


def json_login_required(request, message='Please log in to continue. If you were logged in, your session expired.'):
    """401 JSON telling the client to log in again."""
    return json_error(401, message, requires_login=True, login_url=login_url_for(request))


def json_forbidden(message='You do not have permission to perform this action.'):
    """403 JSON."""
    return json_error(403, message)


GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again or contact the Barangay Office.'


def public_error_message(exc):
    """
    Message safe to show the user for ``exc``, or None.

    Only ValueError, ValidationError and PermissionDenied carry messages meant
    for users (services raise them on purpose). Anything else may leak
    internals (SQL, paths, secrets): callers log it with logger.exception and
    show GENERIC_ERROR_MESSAGE instead.
    """
    from django.core.exceptions import PermissionDenied, ValidationError

    if isinstance(exc, ValidationError):
        return ' '.join(exc.messages)
    if isinstance(exc, (ValueError, PermissionDenied)):
        return str(exc) or GENERIC_ERROR_MESSAGE
    return None
