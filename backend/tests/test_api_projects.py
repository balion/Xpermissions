import pytest
from rest_framework import status

from tests.factories import ExternalProjectFactory, ModulePermissionFactory, RoleFactory, UserFactory


PROJECTS_URL = '/api/projects/'


def _project_url(pk):
    return f'{PROJECTS_URL}{pk}/'


def _make_projects_client(api_client, *actions):
    role = RoleFactory()
    user = UserFactory()
    user.roles.add(role)
    perm_kwargs = {f'can_{a}': True for a in actions}
    ModulePermissionFactory(role=role, module='projects', **perm_kwargs)
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestProjectList:
    def test_list_requires_auth(self, api_client):
        resp = api_client.get(PROJECTS_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_without_permission_denied(self, user, api_client):
        api_client.force_authenticate(user=user)
        resp = api_client.get(PROJECTS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_with_view_permission(self, api_client):
        ExternalProjectFactory.create_batch(2)
        client, _ = _make_projects_client(api_client, 'view')
        resp = client.get(PROJECTS_URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_superuser_can_list(self, superuser_client):
        resp = superuser_client.get(PROJECTS_URL)
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestProjectCreate:
    def test_create_project(self, api_client):
        client, _ = _make_projects_client(api_client, 'view', 'create')
        payload = {'name': 'New Project', 'status': 'active'}
        resp = client.post(PROJECTS_URL, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'New Project'

    def test_create_requires_create_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        resp = api_client.post(PROJECTS_URL, {'name': 'Fail'})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_api_key_write_only(self, api_client):
        client, _ = _make_projects_client(api_client, 'view', 'create')
        payload = {'name': 'Secret Project', 'api_key': 'super-secret', 'status': 'active'}
        resp = client.post(PROJECTS_URL, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert 'api_key' not in resp.data


@pytest.mark.django_db
class TestProjectUpdate:
    def test_update_project(self, api_client):
        project = ExternalProjectFactory(name='Old')
        client, _ = _make_projects_client(api_client, 'view', 'edit')
        resp = client.patch(_project_url(project.pk), {'name': 'New'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'New'


@pytest.mark.django_db
class TestProjectDelete:
    def test_delete_project(self, api_client):
        project = ExternalProjectFactory()
        client, _ = _make_projects_client(api_client, 'view', 'delete')
        resp = client.delete(_project_url(project.pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
