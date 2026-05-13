from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    from apps.audit.utils import log_auth_event
    log_auth_event(request, user, 'LOGIN')


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    from apps.audit.utils import log_auth_event
    if user:
        log_auth_event(request, user, 'LOGOUT')


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    from apps.audit.utils import log_auth_event
    log_auth_event(request, None, 'LOGIN_FAILED')
