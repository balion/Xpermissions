from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import TimestampedModel

PROJECT_STATUS_ACTIVE = 'active'
PROJECT_STATUS_INACTIVE = 'inactive'
PROJECT_STATUS_PENDING_APPROVAL = 'pending_approval'

STATUS_CHOICES = [
    (PROJECT_STATUS_ACTIVE, 'Active'),
    (PROJECT_STATUS_INACTIVE, 'Inactive'),
    (PROJECT_STATUS_PENDING_APPROVAL, 'Pending Approval'),
]


class ExternalProject(TimestampedModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PROJECT_STATUS_ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_projects',
    )
    workflow_instances = GenericRelation(
        'approvals.WorkflowInstance',
        content_type_field='content_type',
        object_id_field='object_id',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def approval_status(self):
        """Return status of the most recent workflow instance, or None."""
        instance = self.workflow_instances.order_by('-started_at').first()
        return instance.status if instance else None

    def start_approval_workflow(self, template, started_by=None):
        """Convenience method — start a named workflow for this project."""
        from apps.approvals.engine import create_workflow_instance
        return create_workflow_instance(template, self, started_by=started_by)

    def mark_project_approved(self, workflow_instance=None):
        """Callback invoked by WorkflowEngine when workflow is fully approved."""
        self.status = PROJECT_STATUS_ACTIVE
        self.save(update_fields=['status', 'updated_at'])

    def mark_project_rejected(self, workflow_instance=None):
        """Callback invoked by WorkflowEngine when workflow is rejected."""
        self.status = PROJECT_STATUS_INACTIVE
        self.save(update_fields=['status', 'updated_at'])
