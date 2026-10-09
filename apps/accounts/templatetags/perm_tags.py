from django import template

from apps.accounts.permissions import check_user_perm

register = template.Library()


@register.simple_tag
def user_can(user, module, action):
    """{% user_can request.user 'statistics' 'view' as can_view %}: same rule the views enforce."""
    return check_user_perm(user, module, action)
