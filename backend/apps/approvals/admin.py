from django.contrib import admin

from apps.approvals.models import (
    ApprovalDecision,
    WorkflowInstance,
    WorkflowNotificationLog,
    WorkflowStepInstance,
    WorkflowTemplate,
)


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStepInstance
    extra = 0
    readonly_fields = ('step_key', 'step_order', 'status', 'activated_at', 'completed_at', 'deadline_at')
    can_delete = False


@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(admin.ModelAdmin):
    list_display = ('pk', 'workflow_name', 'content_object', 'status', 'started_by', 'started_at')
    list_filter = ('status',)
    search_fields = ('workflow_template__name',)
    readonly_fields = ('workflow_template', 'content_type', 'object_id', 'config_snapshot',
                       'started_at', 'completed_at', 'started_by', 'status', 'current_step_order')
    inlines = [WorkflowStepInline]


class ApprovalDecisionInline(admin.TabularInline):
    model = ApprovalDecision
    extra = 0
    readonly_fields = ('user', 'action', 'comment', 'created_at')
    can_delete = False


@admin.register(WorkflowStepInstance)
class WorkflowStepInstanceAdmin(admin.ModelAdmin):
    list_display = ('pk', 'workflow_instance', 'step_key', 'step_order', 'status', 'activated_at')
    list_filter = ('status',)
    search_fields = ('step_key',)
    readonly_fields = ('workflow_instance', 'step_key', 'step_order', 'activated_at',
                       'completed_at', 'deadline_at', 'status')
    inlines = [ApprovalDecisionInline]


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'step_instance', 'user', 'action', 'created_at')
    list_filter = ('action',)
    readonly_fields = ('step_instance', 'user', 'action', 'comment', 'created_at')


@admin.register(WorkflowNotificationLog)
class WorkflowNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('pk', 'workflow_instance', 'notification_type', 'recipient', 'email_sent_at')
    list_filter = ('notification_type',)
    readonly_fields = ('workflow_instance', 'step_instance', 'notification_type', 'recipient',
                       'email_sent_at', 'email_subject', 'email_template_used')
