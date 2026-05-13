from rest_framework import serializers

from apps.approvals.models import (
    ACTION_CHOICES,
    ApprovalDecision,
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowTemplate,
)


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = WorkflowTemplate
        fields = [
            'id', 'name', 'description', 'config', 'version',
            'is_active', 'created_by', 'created_by_email', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_email', 'created_at', 'updated_at']

    def validate_config(self, value):
        from apps.approvals.validators import validate_workflow_config
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_workflow_config(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message) from exc
        return value

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ApprovalDecisionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ApprovalDecision
        fields = ['id', 'user', 'user_email', 'action', 'comment', 'created_at']
        read_only_fields = ['id', 'user', 'user_email', 'created_at']


class WorkflowStepInstanceSerializer(serializers.ModelSerializer):
    decisions = ApprovalDecisionSerializer(many=True, read_only=True)
    step_config = serializers.DictField(read_only=True)

    class Meta:
        model = WorkflowStepInstance
        fields = [
            'id', 'step_key', 'step_order', 'status',
            'deadline_at', 'activated_at', 'completed_at',
            'step_config', 'decisions',
        ]
        read_only_fields = fields


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    workflow_template_name = serializers.CharField(source='workflow_template.name', read_only=True)
    started_by_email = serializers.EmailField(source='started_by.email', read_only=True)
    workflow_name = serializers.CharField(read_only=True)
    steps = WorkflowStepInstanceSerializer(many=True, read_only=True)
    content_type_label = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowInstance
        fields = [
            'id', 'workflow_template', 'workflow_template_name', 'workflow_name',
            'content_type', 'content_type_label', 'object_id',
            'status', 'current_step_order',
            'started_by', 'started_by_email', 'started_at', 'completed_at',
            'steps',
        ]
        read_only_fields = fields

    def get_content_type_label(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"


class StartWorkflowSerializer(serializers.Serializer):
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=WorkflowTemplate.objects.filter(is_active=True),
    )
    content_type_id = serializers.IntegerField()
    object_id = serializers.IntegerField()

    def validate(self, attrs):
        from django.contrib.contenttypes.models import ContentType
        try:
            ct = ContentType.objects.get(pk=attrs['content_type_id'])
        except ContentType.DoesNotExist as exc:
            raise serializers.ValidationError({'content_type_id': 'ContentType not found.'}) from exc

        model_class = ct.model_class()
        if model_class is None:
            raise serializers.ValidationError({'content_type_id': 'ContentType model class not found.'})

        try:
            model_class.objects.get(pk=attrs['object_id'])
        except model_class.DoesNotExist as exc:
            raise serializers.ValidationError({'object_id': 'Object not found.'}) from exc

        attrs['content_type'] = ct
        return attrs


class DecideSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    comment = serializers.CharField(required=False, allow_blank=True, default='')
