"""
Read-only queries for the community feed (civic hierarchy, D13).

feed_context(user) returns the three stacks above the chronological feed:
  1. emergency: active, unexpired emergency posts the user may see + hotline
  2. services:  active document types and health services (shortcuts)
  3. pinned:    pinned announcements shown as fixed anchors
"""
from apps.accounts.selectors import get_contact_number
from apps.communications.models import Announcement
from apps.communications.services import get_active_posts_queryset

EMERGENCY_LIMIT = 3
PINNED_LIMIT = 5
SERVICE_LIMIT = 6


def feed_context(user, visible_posts=None):
    """
    `visible_posts`: the already-evaluated, unfiltered feed list (newest first,
    pinned first). Passing it avoids two extra queries; without it the
    emergency and pinned stacks are queried directly.
    """
    from apps.appointments.models import DocumentType, HealthCareService

    if visible_posts is None:
        # Only titles and dates are shown here, so drop the feed's comment/reaction prefetches.
        visible = get_active_posts_queryset(user).prefetch_related(None)
        emergency = list(visible.filter(category=Announcement.CATEGORY_EMERGENCY)[:EMERGENCY_LIMIT])
        pinned = list(visible.filter(is_pinned=True).exclude(category=Announcement.CATEGORY_EMERGENCY)[:PINNED_LIMIT])
    else:
        emergency = [p for p in visible_posts if p.category == Announcement.CATEGORY_EMERGENCY][:EMERGENCY_LIMIT]
        pinned = [p for p in visible_posts
                  if p.is_pinned and p.category != Announcement.CATEGORY_EMERGENCY][:PINNED_LIMIT]

    return {
        'emergency_posts': emergency,
        'hotline_number': get_contact_number(),
        'document_services': list(DocumentType.objects.filter(is_active=True).order_by('order', 'name')[:SERVICE_LIMIT]),
        'health_services': list(HealthCareService.objects.filter(is_active=True).order_by('name')[:SERVICE_LIMIT]),
        'pinned_posts': pinned,
    }
