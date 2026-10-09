"""
Client IP resolution.

X-Forwarded-For is client-controlled. It is trusted only when the site runs
behind a known number of reverse proxies (settings.TRUSTED_PROXY_COUNT > 0).
Each trusted proxy appends the address it received the connection from, so the
real client is the entry at position -TRUSTED_PROXY_COUNT. Anything to the left
of that entry can be forged by the client and is ignored.
"""
from django.conf import settings


def get_client_ip(request):
    """Best-effort client IP that cannot be spoofed with a fake X-Forwarded-For."""
    remote_addr = request.META.get('REMOTE_ADDR', '') or ''
    proxy_count = int(getattr(settings, 'TRUSTED_PROXY_COUNT', 0) or 0)
    if proxy_count > 0:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        entries = [part.strip() for part in xff.split(',') if part.strip()]
        if len(entries) >= proxy_count:
            return entries[-proxy_count]
    return remote_addr
