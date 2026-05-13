from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel

LOG_STATUS_CHOICES = [
    ('success', 'Success'),
    ('failed', 'Failed'),
]

PROJECT_ACTION_CHOICES = [
    ('created', 'Project Created'),
    ('updated', 'Project Updated'),
    ('status_changed', 'Status Changed'),
    ('deleted', 'Project Deleted'),
]


class EmailTemplate(TimestampedModel):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=500)
    mjml_body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_templates',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProjectEmailAction(TimestampedModel):
    """Binds an email template to a specific action on a specific project."""
    project = models.ForeignKey(
        'projects.ExternalProject',
        on_delete=models.CASCADE,
        related_name='email_actions',
    )
    action_key = models.CharField(max_length=50, choices=PROJECT_ACTION_CHOICES)
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_actions',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('project', 'action_key')
        ordering = ['project__name', 'action_key']

    def __str__(self):
        return f"{self.project.name} / {self.get_action_key_display()}"


class EmailLog(models.Model):
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
    )
    recipient = models.EmailField()
    subject = models.CharField(max_length=500)
    context_data = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=LOG_STATUS_CHOICES)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.sent_at:%Y-%m-%d %H:%M} → {self.recipient} [{self.status}]"
