import pytest

from apps.roles.services import check_module_permission, check_project_permission, get_accessible_projects
from tests.factories import (
    ExternalProjectFactory,
    ModulePermissionFactory,
    ProjectPermissionFactory,
    RoleFactory,
    UserFactory,
    UserPermissionOverrideFactory,
)


@pytest.mark.django_db
class TestCheckModulePermission:
    def test_superuser_always_allowed(self, superuser):
        assert check_module_permission(superuser, 'users', 'view') is True
        assert check_module_permission(superuser, 'users', 'delete') is True

    def test_superadmin_role_always_allowed(self):
        role = RoleFactory(is_superadmin=True)
        user = UserFactory()
        user.roles.add(role)
        assert check_module_permission(user, 'users', 'view') is True
        assert check_module_permission(user, 'audit', 'delete') is True

    def test_no_roles_denied(self, user):
        assert check_module_permission(user, 'users', 'view') is False

    def test_role_with_view_permission(self):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module='users', can_view=True)
        assert check_module_permission(user, 'users', 'view') is True
        assert check_module_permission(user, 'users', 'create') is False

    def test_multiple_roles_union(self):
        role_a = RoleFactory(name='RoleA')
        role_b = RoleFactory(name='RoleB')
        user = UserFactory()
        user.roles.add(role_a, role_b)
        ModulePermissionFactory(role=role_a, module='roles', can_view=True)
        ModulePermissionFactory(role=role_b, module='roles', can_create=True)
        assert check_module_permission(user, 'roles', 'view') is True
        assert check_module_permission(user, 'roles', 'create') is True
        assert check_module_permission(user, 'roles', 'delete') is False

    def test_override_grants_explicit_true(self):
        user = UserFactory()
        UserPermissionOverrideFactory(user=user, module='audit', can_view=True)
        assert check_module_permission(user, 'audit', 'view') is True

    def test_override_denies_explicit_false(self):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module='audit', can_view=True)
        UserPermissionOverrideFactory(user=user, module='audit', can_view=False)
        assert check_module_permission(user, 'audit', 'view') is False

    def test_override_null_falls_through_to_role(self):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module='audit', can_view=True)
        UserPermissionOverrideFactory(user=user, module='audit', can_view=None)
        assert check_module_permission(user, 'audit', 'view') is True


@pytest.mark.django_db
class TestCheckProjectPermission:
    def test_superuser_allowed(self, superuser, project):
        assert check_project_permission(superuser, project, 'view') is True

    def test_superadmin_role_allowed(self, project):
        role = RoleFactory(is_superadmin=True)
        user = UserFactory()
        user.roles.add(role)
        assert check_project_permission(user, project, 'view') is True

    def test_global_projects_module_permission_grants_access(self, project):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module='projects', can_view=True)
        assert check_project_permission(user, project, 'view') is True

    def test_per_project_permission(self, project):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ProjectPermissionFactory(role=role, project=project, can_view=True, can_edit=False)
        assert check_project_permission(user, project, 'view') is True
        assert check_project_permission(user, project, 'edit') is False

    def test_no_permission_denied(self, user, project):
        assert check_project_permission(user, project, 'view') is False

    def test_per_project_does_not_grant_other_project(self):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        project_a = ExternalProjectFactory(name='Alpha')
        project_b = ExternalProjectFactory(name='Beta')
        ProjectPermissionFactory(role=role, project=project_a, can_view=True)
        assert check_project_permission(user, project_a, 'view') is True
        assert check_project_permission(user, project_b, 'view') is False


@pytest.mark.django_db
class TestGetAccessibleProjects:
    def test_superuser_gets_all(self, superuser):
        ExternalProjectFactory.create_batch(3)
        qs = get_accessible_projects(superuser)
        assert qs.count() == 3

    def test_superadmin_role_gets_all(self):
        ExternalProjectFactory.create_batch(2)
        role = RoleFactory(is_superadmin=True)
        user = UserFactory()
        user.roles.add(role)
        assert get_accessible_projects(user).count() == 2

    def test_global_module_permission_gets_all(self):
        ExternalProjectFactory.create_batch(2)
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ModulePermissionFactory(role=role, module='projects', can_view=True)
        assert get_accessible_projects(user).count() == 2

    def test_per_project_permission_gets_subset(self):
        p1 = ExternalProjectFactory(name='P1')
        p2 = ExternalProjectFactory(name='P2')
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ProjectPermissionFactory(role=role, project=p1, can_view=True)
        qs = get_accessible_projects(user)
        assert p1 in qs
        assert p2 not in qs

    def test_no_permissions_returns_empty(self, user):
        ExternalProjectFactory.create_batch(2)
        assert get_accessible_projects(user).count() == 0
