from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_email', 'timestamp', 'action', 'module',
            'object_id', 'object_repr', 'before_data', 'after_data',
            'ip_address', 'user_agent',
        ]
        read_only_fields = fields
