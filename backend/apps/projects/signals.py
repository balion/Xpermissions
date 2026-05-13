from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.projects.models import ExternalProject


@receiver(post_save, sender=ExternalProject)
def log_project_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')


@receiver(post_delete, sender=ExternalProject)
def log_project_delete(sender, instance, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'DELETE')
