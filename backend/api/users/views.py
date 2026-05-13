from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from api.users.serializers import UserCreateSerializer, UserDetailSerializer, UserListSerializer
from api.permissions import ModuleAPIPermission
from apps.accounts.models import User


class UserViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = User.objects.prefetch_related('roles').order_by('email')
    permission_classes = [IsAuthenticated, ModuleAPIPermission]
    module_name = 'users'

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('list',):
            return UserListSerializer
        return UserDetailSerializer

    @action(detail=True, methods=['post'])
    def set_password(self, request, pk=None):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        user = self.get_object()
        password = request.data.get('password', '')
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({'detail': 'Password updated.'})
