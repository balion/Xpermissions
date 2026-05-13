from rest_framework import serializers

from apps.email_templates.models import EmailLog, EmailTemplate


class EmailTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ['id', 'name', 'description', 'subject', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmailTemplateDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'description', 'subject', 'mjml_body',
            'is_active', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class EmailLogSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)

    class Meta:
        model = EmailLog
        fields = ['id', 'template', 'template_name', 'recipient', 'subject',
                  'sent_at', 'status', 'error']
        read_only_fields = fields
