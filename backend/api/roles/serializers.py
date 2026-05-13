from rest_framework import serializers

from apps.roles.models import ModulePermission, Role, UserPermissionOverride


class ModulePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModulePermission
        fields = ['id', 'module', 'can_view', 'can_create', 'can_edit', 'can_delete']


class RoleSerializer(serializers.ModelSerializer):
    module_permissions = ModulePermissionSerializer(many=True, read_only=True)
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_superadmin', 'module_permissions',
                  'user_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class RoleListSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_superadmin', 'user_count']


class UserPermissionOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermissionOverride
        fields = ['id', 'user', 'module', 'can_view', 'can_create', 'can_edit', 'can_delete']
