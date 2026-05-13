from django.contrib import admin

from apps.roles.models import ModulePermission, Role, UserPermissionOverride


class ModulePermissionInline(admin.TabularInline):
    model = ModulePermission
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_superadmin', 'created_at']
    list_filter = ['is_superadmin']
    search_fields = ['name']
    inlines = [ModulePermissionInline]


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ['user', 'module', 'can_view', 'can_create', 'can_edit', 'can_delete']
    list_filter = ['module']
    search_fields = ['user__email', 'user__username']
