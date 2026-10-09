"""
Lucide icon registry (lucide-static, vendored subset sprite).

ICON_NAMES lists every canonical Lucide id the site uses. The sprite at
static/vendor/lucide/sprite.svg contains exactly these symbols; rebuild it
after adding a name:

    python manage.py build_icon_sprite --source <lucide-static>/icons

ALIASES maps the names used in the design guide (and a few older names)
to the Lucide 1.x canonical ids.
"""

ICON_NAMES = (
    'activity', 'archive', 'arrow-left', 'arrow-right', 'arrow-up-right', 'award', 'barcode',
    'bell', 'bell-off', 'book-user', 'box', 'briefcase-medical', 'building-2', 'calendar',
    'calendar-check', 'calendar-days', 'calendar-plus', 'calendar-x', 'chart-pie', 'check',
    'check-check', 'chevron-left', 'chevron-right', 'circle-alert', 'circle-check', 'circle-dot',
    'circle-pause', 'circle-plus', 'circle-user', 'circle-x', 'clipboard', 'clipboard-list',
    'clipboard-plus', 'clock', 'coins', 'compass', 'contact', 'ellipsis', 'ellipsis-vertical',
    'eye', 'eye-off', 'file-badge', 'file-check', 'file-heart', 'file-plus', 'file-spreadsheet', 'file-text',
    'filter', 'folder', 'folder-open', 'graduation-cap', 'hand-coins', 'hand-heart', 'hand-helping',
    'hash', 'headset', 'heart-pulse', 'history', 'hospital', 'hourglass', 'house', 'id-card',
    'image', 'images', 'info', 'key-round', 'landmark', 'layers', 'list-checks', 'loader-circle',
    'lock', 'log-in', 'log-out', 'mail', 'mail-check', 'mail-open', 'map', 'map-pin', 'maximize',
    'megaphone', 'message-square', 'message-square-text', 'messages-square', 'network', 'newspaper',
    'paperclip', 'phone', 'phone-call', 'pin', 'plane-takeoff', 'play', 'plus', 'printer',
    'radiation', 'refresh-cw', 'reply', 'rotate-ccw', 'rotate-cw', 'save', 'scale', 'search',
    'send', 'settings', 'shield', 'shield-half', 'shield-user', 'sliders-horizontal', 'smartphone',
    'smile', 'square-pen', 'stethoscope', 'tag', 'tags', 'trash-2', 'triangle-alert', 'trophy',
    'user', 'user-check', 'user-cog', 'user-pen', 'user-plus', 'user-round', 'user-x', 'users', 'x',
)

ALIASES = {
    # Design-guide names (Lucide 0.x) -> Lucide 1.x canonical ids.
    'alert-triangle': 'triangle-alert',
    'home': 'house',
    'edit': 'square-pen',
    'trash': 'trash-2',
    'close': 'x',
    'spinner': 'loader-circle',
    'external-link': 'arrow-up-right',
    'help': 'info',
    'key': 'key-round',
}


def resolve(name):
    """Return the canonical id for `name`, or None when it is not registered."""
    name = (name or '').strip()
    if name.startswith('lucide-'):
        name = name[len('lucide-'):]
    name = ALIASES.get(name, name)
    return name if name in ICON_NAMES else None
