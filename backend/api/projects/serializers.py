from rest_framework import serializers

from apps.projects.models import ExternalProject


class ExternalProjectSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ExternalProject
        fields = [
            'id', 'name', 'description', 'url', 'api_key', 'status',
            'created_by', 'created_by_email', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_email', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)
