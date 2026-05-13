from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.roles.models import ModulePermission, Role, UserPermissionOverride


@receiver(post_save, sender=Role)
def log_role_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')


@receiver(post_delete, sender=Role)
def log_role_delete(sender, instance, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'DELETE')


@receiver(post_save, sender=ModulePermission)
def log_permission_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')


@receiver(post_save, sender=UserPermissionOverride)
def log_override_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')
