"""
Cache-based fixed-window rate limiting.

    @ratelimit(key='ip', rate='password_reset')          # name in settings.RATE_LIMITS
    @ratelimit(key='user', rate='10/h', methods=('POST',))

``rate`` is either a name in settings.RATE_LIMITS or a literal "<count>/<period>"
where period is s, m, h or d with an optional multiplier ("15m"). The rate is
resolved on every request, so override_settings and env overrides apply.
``key='user'`` falls back to the client IP for anonymous requests.

Over the limit the view is not called: the response is 429 with Retry-After,
JSON when the caller wants JSON (apps.core.http.wants_json), otherwise 429.html.
Counters live in the default cache (Redis or the DatabaseCache table).
"""
import functools
import hashlib
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

from apps.core.http import json_error, wants_json
from apps.core.net import get_client_ip

_PERIODS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
_RATE_RE = re.compile(r'^\s*(\d+)\s*/\s*(\d*)\s*([smhd])\s*$')


def parse_rate(rate):
    """'5/15m' -> (5, 900). Raises ValueError for a malformed rate."""
    match = _RATE_RE.match(rate or '')
    if not match:
        raise ValueError(f'Invalid rate {rate!r}; expected e.g. "5/15m" or "20/h".')
    count, mult, unit = match.groups()
    return int(count), int(mult or 1) * _PERIODS[unit]


def resolve_rate(rate):
    limits = getattr(settings, 'RATE_LIMITS', {}) or {}
    return parse_rate(limits.get(rate, rate))


def _identity(request, key):
    if key == 'user' and getattr(request, 'user', None) is not None and request.user.is_authenticated:
        return f'u{request.user.pk}'
    return f'ip{get_client_ip(request)}'


def hit(scope, identity, limit, period):
    """
    Count one request in the current window. Returns seconds to wait (0 when allowed).
    """
    now = time.time()
    window_start = int(now // period) * period
    digest = hashlib.sha256(f'{scope}:{identity}'.encode()).hexdigest()[:40]
    cache_key = f'rl:{digest}:{window_start}'
    cache.add(cache_key, 0, timeout=period + 1)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=period + 1)
        count = 1
    if count > limit:
        return max(1, int(window_start + period - now) + 1)
    return 0


def too_many_requests(request, retry_after, message=None):
    minutes = max(1, -(-retry_after // 60))
    message = message or (
        f'Too many requests. Please wait {minutes} minute{"s" if minutes != 1 else ""} and try again.'
    )
    if wants_json(request):
        response = json_error(429, message, retry_after=retry_after)
    else:
        response = render(request, '429.html', {'message': message, 'retry_after': retry_after}, status=429)
    response['Retry-After'] = str(retry_after)
    return response


def ratelimit(key='ip', rate='', methods=('POST',), scope=None):
    if key not in ('ip', 'user'):
        raise ValueError("ratelimit key must be 'ip' or 'user'")
    methods = tuple(m.upper() for m in methods) if methods else None

    def decorator(view_func):
        # Named rates share one bucket per name; literal rates get one per view.
        if scope:
            bucket = scope
        elif _RATE_RE.match(rate or ''):
            bucket = f'{view_func.__module__}.{view_func.__qualname__}'
        else:
            bucket = rate

        @functools.wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if methods is None or request.method in methods:
                limit, period = resolve_rate(rate)
                retry_after = hit(f'{bucket}:{key}', _identity(request, key), limit, period)
                if retry_after:
                    return too_many_requests(request, retry_after)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
