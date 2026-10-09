"""
Shared template filters.

display_name: safe display for a nullable user FK. Chaining
`default:obj.fk.attr` raises VariableDoesNotExist when the FK is NULL,
because filter arguments are resolved strictly. Use instead:

    {% load core_tags %}
    {{ appointment.processed_by|display_name:"Health Officer" }}

icon: Lucide SVG icon from static/vendor/lucide/sprite.svg (see below).
"""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

from apps.core import icons

register = template.Library()


@register.simple_tag
def icon(name, size=20, cls='', style=''):
    """
    Inline Lucide icon from the local sprite:

        {% icon 'file-text' %} Barangay Clearance

    The SVG is decorative (aria-hidden); always pair it with visible text,
    or give the parent control an aria-label. Unknown names raise
    TemplateSyntaxError so a typo cannot ship a blank icon.
    """
    canonical = icons.resolve(str(name))
    if canonical is None:
        raise template.TemplateSyntaxError(f'Unknown icon name: {name!r} (add it to apps.core.icons.ICON_NAMES)')
    classes = f'icon icon-{canonical} {cls}'.strip()
    href = f"{static('vendor/lucide/sprite.svg')}#lucide-{canonical}"
    if style:
        return format_html(
            '<svg class="{}" aria-hidden="true" focusable="false" width="{}" height="{}" style="{}"><use href="{}"></use></svg>',
            classes, size, size, style, href,
        )
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false" width="{}" height="{}"><use href="{}"></use></svg>',
        classes, size, size, href,
    )


@register.filter
def display_name(user, fallback=''):
    """Return full name, then username, then the fallback ('' if none)."""
    if not user:
        return fallback or ''
    get_full_name = getattr(user, 'get_full_name', None)
    full = (get_full_name() if callable(get_full_name) else '') or ''
    if full.strip():
        return full.strip()
    username = getattr(user, 'username', '') or ''
    return username or (fallback or '')
