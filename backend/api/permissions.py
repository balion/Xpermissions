from rest_framework.permissions import BasePermission

from apps.roles.services import check_module_permission

ACTION_MAP = {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'edit',
    'partial_update': 'edit',
    'destroy': 'delete',
}


class ModuleAPIPermission(BasePermission):
    """
    DRF permission class that mirrors ModulePermissionMixin for viewsets.
    Expects the viewset to declare `module_name`.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        module = getattr(view, 'module_name', None)
        if not module:
            return request.user.is_superuser

        action = ACTION_MAP.get(view.action, 'view')
        return check_module_permission(request.user, module, action)


class IsSuperadminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_superuser or request.user.roles.filter(is_superadmin=True).exists()
