from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class ModulePermissionMixin(LoginRequiredMixin):
    """
    Mixin for class-based views that enforces module-level CRUD permissions.
    Set `module_name` and `required_action` on the view class.
    """
    module_name: str = None
    required_action: str = 'view'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        from apps.roles.services import check_module_permission
        if not check_module_permission(request.user, self.module_name, self.required_action):
            raise PermissionDenied

        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
