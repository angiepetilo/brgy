from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed
        from apps.accounts import login_security

        user_login_failed.connect(login_security.on_login_failed, dispatch_uid='accounts.login_failed')
        user_logged_in.connect(login_security.on_logged_in, dispatch_uid='accounts.logged_in')
