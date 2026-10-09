from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared helpers (HTTP, template tags, middleware). No models."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'
