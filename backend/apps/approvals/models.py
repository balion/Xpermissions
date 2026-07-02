from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TimestampedModel

# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

INSTANCE_STATUS_PENDING = 'pending'
INSTANCE_STATUS_IN_PROGRESS = 'in_progress'
INSTANCE_STATUS_APPROVED = 'approved'
INSTANCE_STATUS_REJECTED = 'rejected'
INSTANCE_STATUS_CANCELLED = 'cancelled'

INSTANCE_STATUS_CHOICES = [
    (INSTANCE_STATUS_PENDING, 'Pending'),
    (INSTANCE_STATUS_IN_PROGRESS, 'In Progress'),
    (INSTANCE_STATUS_APPROVED, 'Approved'),
    (INSTANCE_STATUS_REJECTED, 'Rejected'),
    (INSTANCE_STATUS_CANCELLED, 'Cancelled'),
]

STEP_STATUS_WAITING = 'waiting'
STEP_STATUS_PENDING = 'pending'
STEP_STATUS_APPROVED = 'approved'
STEP_STATUS_REJECTED = 'rejected'
STEP_STATUS_CHANGES_REQUESTED = 'changes_requested'
STEP_STATUS_SKIPPED = 'skipped'

STEP_STATUS_CHOICES = [
    (STEP_STATUS_WAITING, 'Waiting'),
    (STEP_STATUS_PENDING, 'Pending'),
    (STEP_STATUS_APPROVED, 'Approved'),
    (STEP_STATUS_REJECTED, 'Rejected'),
    (STEP_STATUS_CHANGES_REQUESTED, 'Changes Requested'),
    (STEP_STATUS_SKIPPED, 'Skipped'),
]

ACTION_APPROVE = 'approve'
ACTION_REJECT = 'reject'
ACTION_REQUEST_CHANGES = 'request_changes'

ACTION_CHOICES = [
    (ACTION_APPROVE, 'Approve'),
    (ACTION_REJECT, 'Reject'),
    (ACTION_REQUEST_CHANGES, 'Request Changes'),
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WorkflowTemplate(TimestampedModel):
    """Reusable workflow definition stored as a JSON config."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    config = models.JSONField()
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_workflow_templates',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} v{self.version}"

    def clean(self):
        from apps.approvals.validators import validate_workflow_config
        validate_workflow_config(self.config)

    def save(self, *args, **kwargs):
        # Bump the version whenever the config of an existing template changes.
        if self.pk:
            old_config = (
                WorkflowTemplate.objects
                .filter(pk=self.pk)
                .values_list('config', flat=True)
                .first()
            )
            if old_config is not None and old_config != self.config:
                self.version += 1
                update_fields = kwargs.get('update_fields')
                if update_fields is not None and 'version' not in update_fields:
                    kwargs['update_fields'] = list(update_fields) + ['version']
        super().save(*args, **kwargs)


class WorkflowInstance(TimestampedModel):
    """
    A running instance of a WorkflowTemplate attached to any model object
    via GenericForeignKey.
    """

    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.PROTECT,
        related_name='instances',
    )
    # Generic relation — links to any model (ExternalProject, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Frozen copy of the config at start time so template changes don't
    # affect running workflows.
    config_snapshot = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=INSTANCE_STATUS_CHOICES,
        default=INSTANCE_STATUS_PENDING,
        db_index=True,
    )
    current_step_order = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='started_workflows',
    )

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Workflow #{self.pk} for {self.content_object} [{self.status}]"

    @property
    def workflow_name(self):
        return self.config_snapshot.get('workflow_name', '')


class WorkflowStepInstance(TimestampedModel):
    """One step within a running WorkflowInstance."""

    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    step_key = models.CharField(max_length=100)
    step_order = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STEP_STATUS_CHOICES,
        default=STEP_STATUS_WAITING,
        db_index=True,
    )
    deadline_at = models.DateTimeField(null=True, blank=True)
    # Set once the on_deadline policy has been applied so the periodic
    # deadline processor never handles the same step twice.
    deadline_handled = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('workflow_instance', 'step_key')
        ordering = ['step_order']

    def __str__(self):
        return f"Step {self.step_order} ({self.step_key}) [{self.status}]"

    @property
    def step_config(self) -> dict:
        """Return this step's config dict from the parent workflow's config_snapshot."""
        for step in self.workflow_instance.config_snapshot.get('steps', []):
            if step['step_key'] == self.step_key:
                return step
        return {}


class ApprovalDecision(models.Model):
    """An individual approve / reject / request-changes action by one user."""

    step_instance = models.ForeignKey(
        WorkflowStepInstance,
        on_delete=models.CASCADE,
        related_name='decisions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approval_decisions',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user} → {self.action} on {self.step_instance}"


class WorkflowNotificationLog(models.Model):
    """Record of every workflow-related email that was sent."""

    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name='notification_logs',
    )
    step_instance = models.ForeignKey(
        WorkflowStepInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_logs',
    )
    notification_type = models.CharField(max_length=50)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='workflow_notification_logs',
    )
    email_sent_at = models.DateTimeField(auto_now_add=True)
    email_subject = models.CharField(max_length=500)
    email_template_used = models.CharField(max_length=200)

    class Meta:
        ordering = ['-email_sent_at']

    def __str__(self):
        return f"{self.notification_type} → {self.recipient} [{self.email_sent_at:%Y-%m-%d %H:%M}]"


class ProjectApprovalConfig(models.Model):
    """Per-project approval configuration — links a project to a WorkflowTemplate
    and optionally stores a project-specific JSON config override."""

    project = models.OneToOneField(
        'projects.ExternalProject',
        on_delete=models.CASCADE,
        related_name='approval_config',
    )
    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_configs',
    )
    custom_config = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            'Optional JSON config that overrides the selected template. '
            'Leave blank to use the template config as-is.'
        ),
    )
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project__name']

    def __str__(self):
        return f"Approval config for {self.project}"

    @property
    def effective_config(self) -> dict | None:
        """Return custom_config if set, otherwise the template's config."""
        if self.custom_config:
            return self.custom_config
        if self.workflow_template:
            return self.workflow_template.config
        return None
