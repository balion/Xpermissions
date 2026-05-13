import pytest
from rest_framework import status

from tests.factories import ModulePermissionFactory, RoleFactory, UserFactory


USERS_URL = '/api/users/'


def _users_url(pk):
    return f'{USERS_URL}{pk}/'


def _set_password_url(pk):
    return f'{USERS_URL}{pk}/set_password/'


def _make_users_client(api_client, *actions):
    """Return an APIClient with a user whose role has the given module actions."""
    role = RoleFactory()
    user = UserFactory()
    user.roles.add(role)
    perm_kwargs = {f'can_{a}': True for a in actions}
    ModulePermissionFactory(role=role, module='users', **perm_kwargs)
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestUserList:
    def test_list_requires_auth(self, api_client):
        resp = api_client.get(USERS_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_requires_view_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        resp = api_client.get(USERS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_with_view_permission(self, api_client):
        client, _ = _make_users_client(api_client, 'view')
        resp = client.get(USERS_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert 'results' in resp.data or isinstance(resp.data, list)

    def test_superuser_can_list(self, superuser_client):
        resp = superuser_client.get(USERS_URL)
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestUserCreate:
    def test_create_user(self, api_client):
        client, _ = _make_users_client(api_client, 'view', 'create')
        payload = {
            'email': 'new@example.com',
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'securepass99',
        }
        resp = client.post(USERS_URL, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['email'] == 'new@example.com'

    def test_create_requires_create_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        payload = {
            'email': 'new2@example.com',
            'username': 'newuser2',
            'first_name': 'X',
            'last_name': 'Y',
            'password': 'securepass99',
        }
        resp = api_client.post(USERS_URL, payload)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_with_roles(self, api_client):
        role = RoleFactory(name='AssignedRole')
        client, _ = _make_users_client(api_client, 'view', 'create')
        payload = {
            'email': 'roled@example.com',
            'username': 'roleduser',
            'first_name': 'Roled',
            'last_name': 'User',
            'password': 'securepass99',
            'role_ids': [role.pk],
        }
        resp = client.post(USERS_URL, payload)
        assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestUserRetrieve:
    def test_retrieve_own_user(self, api_client):
        client, user = _make_users_client(api_client, 'view')
        resp = client.get(_users_url(user.pk))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['email'] == user.email

    def test_retrieve_other_user(self, api_client):
        client, _ = _make_users_client(api_client, 'view')
        other = UserFactory()
        resp = client.get(_users_url(other.pk))
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestUserUpdate:
    def test_update_user(self, api_client):
        client, user = _make_users_client(api_client, 'view', 'edit')
        resp = client.patch(_users_url(user.pk), {'first_name': 'Updated'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['first_name'] == 'Updated'

    def test_update_requires_edit_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        resp = api_client.patch(_users_url(user.pk), {'first_name': 'X'})
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestUserDelete:
    def test_delete_user(self, api_client):
        client, _ = _make_users_client(api_client, 'view', 'delete')
        target = UserFactory()
        resp = client.delete(_users_url(target.pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_requires_delete_permission(self, user, api_client):
        api_client.force_authenticate(user=user)
        target = UserFactory()
        resp = api_client.delete(_users_url(target.pk))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSetPassword:
    def test_set_password_success(self, api_client):
        client, user = _make_users_client(api_client, 'view', 'edit')
        resp = client.post(_set_password_url(user.pk), {'password': 'NewSecure99!'})
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password('NewSecure99!')

    def test_set_password_too_short(self, superuser_client, user):
        resp = superuser_client.post(_set_password_url(user.pk), {'password': 'abc'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in resp.data

    def test_set_password_too_common(self, superuser_client, user):
        resp = superuser_client.post(_set_password_url(user.pk), {'password': 'password'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
