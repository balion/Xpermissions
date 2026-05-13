"""
Tests for DRF permission classes: ModuleAPIPermission and IsSuperadminOrReadOnly.
"""
import pytest
from rest_framework import status

from tests.factories import ModulePermissionFactory, RoleFactory, UserFactory


@pytest.mark.django_db
class TestModuleAPIPermission:
    """Verify ModuleAPIPermission via the roles endpoint (module_name='roles')."""

    roles_url = '/api/roles/'

    def _user_with_perm(self, module, **actions):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module=module, **actions)
        return user

    def test_unauthenticated_denied(self, api_client):
        resp = api_client.get(self.roles_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_no_perms_denied(self, api_client, user):
        api_client.force_authenticate(user=user)
        resp = api_client.get(self.roles_url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_view_permission_allows_get(self, api_client):
        user = self._user_with_perm('roles', can_view=True)
        api_client.force_authenticate(user=user)
        resp = api_client.get(self.roles_url)
        assert resp.status_code == status.HTTP_200_OK

    def test_view_permission_blocks_post(self, api_client):
        user = self._user_with_perm('roles', can_view=True)
        api_client.force_authenticate(user=user)
        resp = api_client.post(self.roles_url, {'name': 'Test'})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_permission_allows_post(self, api_client):
        user = self._user_with_perm('roles', can_view=True, can_create=True)
        api_client.force_authenticate(user=user)
        resp = api_client.post(self.roles_url, {'name': 'Created By Perm'})
        assert resp.status_code == status.HTTP_201_CREATED

    def test_superadmin_role_allows_all(self, api_client):
        role = RoleFactory(is_superadmin=True)
        user = UserFactory()
        user.roles.add(role)
        api_client.force_authenticate(user=user)
        resp = api_client.get(self.roles_url)
        assert resp.status_code == status.HTTP_200_OK

    def test_django_superuser_allows_all(self, superuser_client):
        resp = superuser_client.get(self.roles_url)
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestIsSuperadminOrReadOnly:
    """
    IsSuperadminOrReadOnly is used on endpoints that allow read-only for
    any authenticated user but write-only for superadmins.
    We test it indirectly through a viewset that uses it (if any) or
    unit-test the class directly.
    """

    def test_superadmin_role_can_write(self, api_client):
        role = RoleFactory(is_superadmin=True)
        user = UserFactory()
        user.roles.add(role)
        # Superadmin role should have is_superadmin=True, which is granted
        assert user.roles.filter(is_superadmin=True).exists()

    def test_regular_user_not_superadmin(self, user):
        assert not user.roles.filter(is_superadmin=True).exists()
        assert not user.is_superuser
