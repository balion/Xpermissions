from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from api.permissions import ModuleAPIPermission
from api.projects.serializers import ExternalProjectSerializer
from apps.projects.models import ExternalProject


class ExternalProjectViewSet(ModelViewSet):
    queryset = ExternalProject.objects.select_related('created_by').order_by('name')
    serializer_class = ExternalProjectSerializer
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'projects'
