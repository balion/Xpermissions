from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from api.audit.serializers import AuditLogSerializer
from api.permissions import ModuleAPIPermission
from apps.audit.models import AuditLog


class AuditLogViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'audit'

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user').order_by('-timestamp')
        action = self.request.query_params.get('action')
        module = self.request.query_params.get('module')
        if action:
            qs = qs.filter(action=action)
        if module:
            qs = qs.filter(module=module)
        return qs
