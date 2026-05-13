from django.db.models import Count

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from api.permissions import ModuleAPIPermission
from api.roles.serializers import RoleListSerializer, RoleSerializer, UserPermissionOverrideSerializer
from apps.roles.models import Role, UserPermissionOverride


class RoleViewSet(ModelViewSet):
    queryset = (
        Role.objects
        .prefetch_related('module_permissions')
        .annotate(user_count=Count('users'))
        .order_by('name')
    )
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'roles'

    def get_serializer_class(self):
        if self.action == 'list':
            return RoleListSerializer
        return RoleSerializer


class UserPermissionOverrideViewSet(ModelViewSet):
    queryset = UserPermissionOverride.objects.select_related('user').order_by('user__email')
    serializer_class = UserPermissionOverrideSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'roles'
