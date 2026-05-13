from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from api.email_templates.serializers import (
    EmailLogSerializer,
    EmailTemplateDetailSerializer,
    EmailTemplateListSerializer,
)
from api.permissions import ModuleAPIPermission
from apps.email_templates.models import EmailLog, EmailTemplate
from apps.email_templates.services import preview_template, send_email_from_template


class EmailTemplateViewSet(ModelViewSet):
    queryset = EmailTemplate.objects.order_by('name')
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'email_templates'

    def get_serializer_class(self):
        if self.action == 'list':
            return EmailTemplateListSerializer
        return EmailTemplateDetailSerializer

    @action(detail=True, methods=['post'], url_path='preview')
    def preview(self, request, pk=None):
        template = self.get_object()
        try:
            html = preview_template(template)
            return Response({'html': html})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='send-test')
    def send_test(self, request, pk=None):
        template = self.get_object()
        recipient = request.data.get('recipient', request.user.email)
        ok = send_email_from_template(template, recipient, {'user': request.user})
        if ok:
            return Response({'detail': f'Test email sent to {recipient}.'})
        return Response({'detail': 'Send failed. Check email log.'}, status=status.HTTP_502_BAD_GATEWAY)


class EmailLogViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = EmailLog.objects.select_related('template').order_by('-sent_at')
    serializer_class = EmailLogSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'email_templates'
