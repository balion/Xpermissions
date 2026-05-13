from django.contrib import admin

from apps.email_templates.models import EmailLog, EmailTemplate, ProjectEmailAction


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'subject']
    readonly_fields = ['created_by', 'created_at', 'updated_at']


@admin.register(ProjectEmailAction)
class ProjectEmailActionAdmin(admin.ModelAdmin):
    list_display = ['project', 'action_key', 'template', 'is_active']
    list_filter = ['action_key', 'is_active']


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['sent_at', 'recipient', 'subject', 'template', 'status']
    list_filter = ['status']
    search_fields = ['recipient', 'subject']
    readonly_fields = list_display + ['context_data', 'error']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
