from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'module', 'object_repr', 'ip_address']
    list_filter = ['action', 'module']
    search_fields = ['user__email', 'object_repr', 'ip_address']
    readonly_fields = ['timestamp', 'user', 'action', 'module', 'object_id',
                       'object_repr', 'before_data', 'after_data', 'ip_address', 'user_agent']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
