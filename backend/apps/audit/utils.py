import logging

from apps.audit.middleware import get_current_request

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def log_model_change(instance, action: str, before: dict = None, after: dict = None):
    """
    Creates an AuditLog entry for a model change.
    Safely skips logging if the AuditLog table doesn't exist yet (e.g. during migrations).
    """
    try:
        from apps.audit.models import AuditLog
    except Exception:
        return

    request = get_current_request()
    user = None
    ip = None
    user_agent = ''

    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user
        ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

    module = instance.__class__.__module__.split('.')
    module_name = module[-2] if len(module) >= 2 else module[-1]

    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            module=module_name,
            object_id=str(instance.pk or ''),
            object_repr=str(instance)[:255],
            before_data=before,
            after_data=after,
            ip_address=ip or None,
            user_agent=user_agent,
        )
    except Exception:
        logger.exception('Failed to write audit log for %s %s', action, instance)


def log_auth_event(request, user, action: str):
    """Log LOGIN / LOGOUT / LOGIN_FAILED events."""
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=user if hasattr(user, 'pk') else None,
            action=action,
            module='accounts',
            object_repr=str(user),
            ip_address=get_client_ip(request) or None,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
    except Exception:
        logger.exception('Failed to write auth audit log for %s %s', action, user)
