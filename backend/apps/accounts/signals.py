from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import User


@receiver(post_save, sender=User)
def log_user_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')


@receiver(post_delete, sender=User)
def log_user_delete(sender, instance, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'DELETE')
