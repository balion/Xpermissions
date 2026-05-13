import pytest
from rest_framework.test import APIClient

from tests.factories import (
    EmailTemplateFactory,
    ExternalProjectFactory,
    ModulePermissionFactory,
    ProjectPermissionFactory,
    RoleFactory,
    SuperuserFactory,
    UserFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory(password='testpass123')


@pytest.fixture
def superuser(db):
    return SuperuserFactory(password='testpass123')


@pytest.fixture
def superadmin_role(db):
    return RoleFactory(name='Superadmin', is_superadmin=True)


@pytest.fixture
def role(db):
    return RoleFactory(name='Staff')


@pytest.fixture
def project(db):
    return ExternalProjectFactory()


@pytest.fixture
def email_template(db):
    return EmailTemplateFactory()


@pytest.fixture
def auth_client(user, api_client):
    """APIClient authenticated as a regular user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def superuser_client(superuser, api_client):
    """APIClient authenticated as Django superuser."""
    api_client.force_authenticate(user=superuser)
    return api_client


@pytest.fixture
def role_user(db, role):
    """User with a standard role that has full users-module permissions."""
    u = UserFactory()
    u.roles.add(role)
    ModulePermissionFactory(
        role=role,
        module='users',
        can_view=True,
        can_create=True,
        can_edit=True,
        can_delete=True,
    )
    return u


@pytest.fixture
def role_user_client(role_user, api_client):
    api_client.force_authenticate(user=role_user)
    return api_client


@pytest.fixture
def projects_role(db):
    return RoleFactory(name='ProjectsRole')


@pytest.fixture
def project_viewer_user(db, projects_role, project):
    """User with per-project view permission only."""
    u = UserFactory()
    u.roles.add(projects_role)
    ProjectPermissionFactory(role=projects_role, project=project, can_view=True)
    return u
