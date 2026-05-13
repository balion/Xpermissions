import pytest
from rest_framework import status

from tests.factories import ModulePermissionFactory, RoleFactory, UserFactory


ROLES_URL = '/api/roles/'


def _roles_url(pk):
    return f'{ROLES_URL}{pk}/'


def _make_roles_client(api_client, *actions):
    role = RoleFactory()
    user = UserFactory()
    user.roles.add(role)
    perm_kwargs = {f'can_{a}': True for a in actions}
    ModulePermissionFactory(role=role, module='roles', **perm_kwargs)
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestRoleList:
    def test_list_requires_auth(self, api_client):
        resp = api_client.get(ROLES_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_with_permission(self, api_client):
        RoleFactory.create_batch(3)
        client, _ = _make_roles_client(api_client, 'view')
        resp = client.get(ROLES_URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_list_includes_user_count(self, api_client):
        role = RoleFactory(name='CountedRole')
        user = UserFactory()
        user.roles.add(role)
        client, _ = _make_roles_client(api_client, 'view')
        resp = client.get(ROLES_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        counted = next(r for r in results if r['name'] == 'CountedRole')
        assert counted['user_count'] >= 1


@pytest.mark.django_db
class TestRoleCreate:
    def test_create_role(self, api_client):
        client, _ = _make_roles_client(api_client, 'view', 'create')
        resp = client.post(ROLES_URL, {'name': 'New Role', 'description': 'Desc'})
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'New Role'

    def test_create_requires_create_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        resp = api_client.post(ROLES_URL, {'name': 'Fail Role'})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_name_rejected(self, api_client):
        RoleFactory(name='Unique')
        client, _ = _make_roles_client(api_client, 'view', 'create')
        resp = client.post(ROLES_URL, {'name': 'Unique'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestRoleDetail:
    def test_retrieve_includes_module_permissions(self, api_client):
        role = RoleFactory(name='DetailRole')
        ModulePermissionFactory(role=role, module='users', can_view=True)
        client, _ = _make_roles_client(api_client, 'view')
        resp = client.get(_roles_url(role.pk))
        assert resp.status_code == status.HTTP_200_OK
        assert 'module_permissions' in resp.data
        perms = resp.data['module_permissions']
        assert any(p['module'] == 'users' for p in perms)

    def test_update_role(self, api_client):
        role = RoleFactory(name='Old Name')
        client, _ = _make_roles_client(api_client, 'view', 'edit')
        resp = client.patch(_roles_url(role.pk), {'name': 'New Name'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'New Name'

    def test_delete_role(self, api_client):
        role = RoleFactory(name='ToDelete')
        client, _ = _make_roles_client(api_client, 'view', 'delete')
        resp = client.delete(_roles_url(role.pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestUserPermissionOverrideViewSet:
    url = '/api/permissions/'

    def test_list_requires_roles_permission(self, api_client):
        client, _ = _make_roles_client(api_client, 'view')
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK

    def test_create_override(self, superuser_client, user):
        payload = {
            'user': user.pk,
            'module': 'users',
            'can_view': True,
            'can_create': None,
            'can_edit': None,
            'can_delete': None,
        }
        resp = superuser_client.post(self.url, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
