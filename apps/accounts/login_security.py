"""
Login brute-force protection.

Failures are counted from django.contrib.auth's ``user_login_failed`` signal,
so every failed authenticate() call counts, whatever the HTTP status of the
response. Three independent counters share one window (LOGIN_LOCKOUT_SECONDS):

- username + IP      -> LOGIN_FAILURE_LIMIT       (default 5)
- IP, any username   -> LOGIN_IP_FAILURE_LIMIT    (default 20)
- username, any IP   -> LOGIN_USER_FAILURE_LIMIT  (default 10)

Reaching a limit sets a lock key for LOGIN_LOCKOUT_SECONDS. The identifier is
the submitted login string (stripped, lowercased) and is sha256-hashed inside
cache keys so emails are never stored as key names. A successful login clears
only the username + IP counter.
"""
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache

from apps.core.net import get_client_ip

logger = logging.getLogger('apps.security.login')


def normalize_identifier(raw):
    return (raw or '').strip().lower()


def _h(identifier):
    return hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:40]


def _window():
    return int(getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900))


def _scopes(identifier, ip):
    """(name, counter key, limit) for each counter that applies."""
    scopes = []
    if identifier:
        hid = _h(identifier)
        scopes.append(('user_ip', f'lf:u_ip:{hid}:{ip}', int(getattr(settings, 'LOGIN_FAILURE_LIMIT', 5))))
        scopes.append(('user', f'lf:u:{hid}', int(getattr(settings, 'LOGIN_USER_FAILURE_LIMIT', 10))))
    scopes.append(('ip', f'lf:ip:{ip}', int(getattr(settings, 'LOGIN_IP_FAILURE_LIMIT', 20))))
    return scopes


def _lock_key(counter_key):
    return f'{counter_key}:lock'


def _incr(key, timeout):
    cache.add(key, 0, timeout=timeout)
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, timeout=timeout)
        return 1


def record_failure(identifier, ip):
    """Count one failed login; set lock keys for every limit reached."""
    identifier = normalize_identifier(identifier)
    window = _window()
    for scope, key, limit in _scopes(identifier, ip):
        count = _incr(key, window)
        if count >= limit and not cache.get(_lock_key(key)):
            cache.set(_lock_key(key), time.time() + window, timeout=window)
            # Never log the password; the identifier is hashed.
            logger.warning(
                'Login lockout (%s): %d failed attempts, ip=%s, identifier_hash=%s, locked for %ds',
                scope, count, ip, _h(identifier) if identifier else '-', window,
            )


def lock_remaining(identifier, ip):
    """Seconds until every active lock for this identifier/IP expires (0 = not locked)."""
    identifier = normalize_identifier(identifier)
    now = time.time()
    remaining = 0
    for _scope, key, _limit in _scopes(identifier, ip):
        until = cache.get(_lock_key(key))
        if until:
            remaining = max(remaining, int(until - now) + 1)
    return remaining


def clear(identifier, ip):
    """Clear the username + IP counter and its lock (after a successful login)."""
    identifier = normalize_identifier(identifier)
    if not identifier:
        return
    key = f'lf:u_ip:{_h(identifier)}:{ip}'
    cache.delete_many([key, _lock_key(key)])


# ---------------------------------------------------------------------------
# Signal receivers (connected in AccountsConfig.ready)
# ---------------------------------------------------------------------------
def on_login_failed(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    # Count under the string the user typed (username or email), the same key
    # the middleware pre-check reads; fall back to the credentials passed in.
    submitted = request.POST.get('username', '') if request.method == 'POST' else ''
    record_failure(submitted or credentials.get('username', ''), get_client_ip(request))


def on_logged_in(sender, request, user, **kwargs):
    if request is None:
        return
    ip = get_client_ip(request)
    submitted = request.POST.get('username', '') if request.method == 'POST' else ''
    for ident in {submitted, user.get_username(), getattr(user, 'email', '') or ''}:
        clear(ident, ip)
