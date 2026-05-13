from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from api.approvals.permissions import IsApprover
from api.approvals.serializers import (
    DecideSerializer,
    StartWorkflowSerializer,
    WorkflowInstanceSerializer,
    WorkflowStepInstanceSerializer,
    WorkflowTemplateSerializer,
)
from api.permissions import ModuleAPIPermission
from apps.approvals.engine import WorkflowEngine, create_workflow_instance
from apps.approvals.models import (
    STEP_STATUS_PENDING,
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowTemplate,
)


class WorkflowTemplateViewSet(ModelViewSet):
    queryset = WorkflowTemplate.objects.select_related('created_by').order_by('name')
    serializer_class = WorkflowTemplateSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'approvals'


class WorkflowInstanceViewSet(ReadOnlyModelViewSet):
    """
    Read-only viewset for WorkflowInstances.
    Starting a workflow is handled via /start/.
    Decisions are posted to /steps/{step_id}/decide/.
    """

    serializer_class = WorkflowInstanceSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'approvals'

    def get_queryset(self):
        return (
            WorkflowInstance.objects
            .select_related('workflow_template', 'content_type', 'started_by')
            .prefetch_related('steps__decisions__user')
            .order_by('-started_at')
        )

    @extend_schema(request=StartWorkflowSerializer, responses=WorkflowInstanceSerializer)
    @action(detail=False, methods=['post'], url_path='start')
    def start(self, request):
        serializer = StartWorkflowSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        content_object = data['content_type'].model_class().objects.get(pk=data['object_id'])

        instance = create_workflow_instance(
            template=data['template_id'],
            content_object=content_object,
            started_by=request.user,
        )
        return Response(
            WorkflowInstanceSerializer(instance, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses=WorkflowStepInstanceSerializer(many=True))
    @action(detail=True, methods=['get'], url_path='steps')
    def steps(self, request, pk=None):
        instance = self.get_object()
        steps = instance.steps.prefetch_related('decisions__user').order_by('step_order')
        serializer = WorkflowStepInstanceSerializer(steps, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(request=DecideSerializer, responses=WorkflowStepInstanceSerializer)
    @action(
        detail=True,
        methods=['post'],
        url_path=r'steps/(?P<step_pk>[^/.]+)/decide',
        permission_classes=[IsAuthenticated, IsApprover],
    )
    def decide(self, request, pk=None, step_pk=None):
        instance = self.get_object()

        try:
            step = instance.steps.get(pk=step_pk)
        except WorkflowStepInstance.DoesNotExist:
            return Response({'detail': 'Step not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, step)

        serializer = DecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        engine = WorkflowEngine(instance)
        try:
            engine.decide(
                step_instance=step,
                user=request.user,
                action=serializer.validated_data['action'],
                comment=serializer.validated_data.get('comment', ''),
            )
        except (ValueError, PermissionError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        step.refresh_from_db()
        return Response(WorkflowStepInstanceSerializer(step, context={'request': request}).data)

    @extend_schema(responses=WorkflowInstanceSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        qs = self.get_queryset().filter(started_by=request.user)
        serializer = WorkflowInstanceSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class MyPendingView(APIView):
    """Return all pending step instances where the current user is an approver."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=WorkflowStepInstanceSerializer(many=True))
    def get(self, request):
        pending_steps = WorkflowStepInstance.objects.filter(
            status=STEP_STATUS_PENDING,
        ).select_related(
            'workflow_instance__workflow_template',
            'workflow_instance__content_type',
        ).prefetch_related('decisions__user')

        approver_steps = [
            step for step in pending_steps
            if WorkflowEngine(step.workflow_instance).can_decide(step, request.user)
        ]

        serializer = WorkflowStepInstanceSerializer(
            approver_steps, many=True, context={'request': request}
        )
        return Response(serializer.data)
