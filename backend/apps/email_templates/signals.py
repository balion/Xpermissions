from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.email_templates.models import EmailTemplate


@receiver(post_save, sender=EmailTemplate)
def log_template_save(sender, instance, created, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'CREATE' if created else 'UPDATE')


@receiver(post_delete, sender=EmailTemplate)
def log_template_delete(sender, instance, **kwargs):
    from apps.audit.utils import log_model_change
    log_model_change(instance, 'DELETE')
