from django.conf import settings
from django.db import models

ACTION_CHOICES = [
    ('CREATE', 'Create'),
    ('UPDATE', 'Update'),
    ('DELETE', 'Delete'),
    ('VIEW', 'View'),
    ('LOGIN', 'Login'),
    ('LOGOUT', 'Logout'),
    ('LOGIN_FAILED', 'Login Failed'),
]


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    module = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=255, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        user_str = str(self.user) if self.user else 'Anonymous'
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {user_str} — {self.action} {self.module}"
