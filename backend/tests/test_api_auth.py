import pytest
from django.urls import reverse
from rest_framework import status

from tests.factories import UserFactory


@pytest.mark.django_db
class TestLoginView:
    url = '/api/auth/login/'

    def test_valid_credentials_returns_tokens(self, api_client):
        user = UserFactory(password='mypassword99', status='active')
        resp = api_client.post(self.url, {'email': user.email, 'password': 'mypassword99'})
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        assert 'refresh' in resp.data
        assert resp.data['user']['email'] == user.email

    def test_wrong_password_returns_401(self, api_client):
        user = UserFactory(password='correct99')
        resp = api_client.post(self.url, {'email': user.email, 'password': 'wrong99'})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_locked_user_returns_403(self, api_client):
        user = UserFactory(password='testpass123', status='locked')
        resp = api_client.post(self.url, {'email': user.email, 'password': 'testpass123'})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_fields_returns_400(self, api_client):
        resp = api_client.post(self.url, {'email': 'x@example.com'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_user_returns_401(self, api_client):
        resp = api_client.post(self.url, {'email': 'nobody@example.com', 'password': 'pass'})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRefreshView:
    login_url = '/api/auth/login/'
    refresh_url = '/api/auth/refresh/'

    def _get_tokens(self, api_client):
        user = UserFactory(password='testpass123', status='active')
        resp = api_client.post(self.login_url, {'email': user.email, 'password': 'testpass123'})
        return resp.data['refresh']

    def test_valid_refresh_returns_new_access(self, api_client):
        refresh = self._get_tokens(api_client)
        resp = api_client.post(self.refresh_url, {'refresh': refresh})
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

    def test_invalid_token_returns_401(self, api_client):
        resp = api_client.post(self.refresh_url, {'refresh': 'not.a.token'})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeView:
    url = '/api/auth/me/'

    def test_authenticated_returns_profile(self, auth_client, user):
        resp = auth_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['email'] == user.email

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_role_names_included(self, api_client):
        from tests.factories import RoleFactory
        role = RoleFactory(name='Tester')
        user = UserFactory(password='testpass123', status='active')
        user.roles.add(role)
        api_client.force_authenticate(user=user)
        resp = api_client.get(self.url)
        assert 'Tester' in resp.data['role_names']
