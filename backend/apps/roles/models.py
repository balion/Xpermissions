from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel

MODULE_CHOICES = [
    ('users', 'User Management'),
    ('roles', 'Roles & Permissions'),
    ('audit', 'Audit Log'),
    ('projects', 'External Projects'),
    ('email_templates', 'Email Templates'),
    ('approvals', 'Approval Workflows'),
    ('settings', 'System Settings'),
]


class Role(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_superadmin = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ModulePermission(TimestampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='module_permissions')
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        unique_together = ('role', 'module')
        ordering = ['module']

    def __str__(self):
        return f"{self.role.name} — {self.module}"


class ProjectPermission(TimestampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='project_permissions')
    project = models.ForeignKey(
        'projects.ExternalProject',
        on_delete=models.CASCADE,
        related_name='role_permissions',
    )
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        unique_together = ('role', 'project')
        ordering = ['project__name']

    def __str__(self):
        return f"{self.role.name} — {self.project.name}"


class UserPermissionOverride(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permission_overrides'
    )
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    can_view = models.BooleanField(null=True, blank=True)
    can_create = models.BooleanField(null=True, blank=True)
    can_edit = models.BooleanField(null=True, blank=True)
    can_delete = models.BooleanField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'module')
        ordering = ['module']

    def __str__(self):
        return f"{self.user} override — {self.module}"
