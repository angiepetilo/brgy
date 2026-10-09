"""Key pages per role, shared by the Stage D page and label tests."""
from django.urls import reverse

ANONYMOUS_PAGES = ('landing', 'accounts:login')
RESIDENT_PAGES = ('communications:feed', 'appointments:list', 'chat:inbox', 'accounts:profile',
                  'communications:announcements_list', 'communications:emergency_list',
                  'appointments:health_schedule', 'chat:notifications_list')
ADMIN_PAGES = ('communications:feed', 'records:hub', 'accounts:residents_tabbed', 'history:overview',
               'statistics:overview', 'accounts:system_dashboard', 'blotter:case_list',
               'blotter:case_create', 'appointments:list', 'appointments:service_list')


def urls(names):
    return [reverse(name) for name in names]
