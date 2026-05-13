from rest_framework.permissions import BasePermission

from apps.approvals.engine import WorkflowEngine


class IsApprover(BasePermission):
    """
    Grants access only when the requesting user is an authorised approver
    for the step_instance resolved in the view.

    Views using this permission must set `self.step_instance` before
    `check_permissions` is called (e.g. in `get_object()`).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        from apps.approvals.models import WorkflowStepInstance
        if isinstance(obj, WorkflowStepInstance):
            engine = WorkflowEngine(obj.workflow_instance)
            return engine.can_decide(obj, request.user)
        return False
