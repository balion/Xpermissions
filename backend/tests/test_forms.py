import pytest

from apps.accounts.forms import UserCreateForm, UserUpdateForm
from apps.email_templates.forms import ProjectEmailActionsForm
from apps.email_templates.models import PROJECT_ACTION_CHOICES, ProjectEmailAction
from apps.roles.forms import RolePermissionsForm
from apps.roles.models import MODULE_CHOICES, ModulePermission, ProjectPermission
from tests.factories import (
    EmailTemplateFactory,
    ExternalProjectFactory,
    ProjectEmailActionFactory,
    RoleFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestUserCreateForm:
    def _valid_data(self, **overrides):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'First',
            'last_name': 'Last',
            'status': 'active',
            'password1': 'Str0ngPass!99',
            'password2': 'Str0ngPass!99',
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = UserCreateForm(data=self._valid_data())
        assert form.is_valid(), form.errors

    def test_password_mismatch_invalid(self):
        data = self._valid_data(password2='different')
        form = UserCreateForm(data=data)
        assert not form.is_valid()
        assert 'password2' in form.errors

    def test_duplicate_email_invalid(self, db):
        UserFactory(email='taken@example.com')
        form = UserCreateForm(data=self._valid_data(email='taken@example.com'))
        assert not form.is_valid()

    def test_roles_field_not_required(self):
        form = UserCreateForm(data=self._valid_data())
        assert form.fields['roles'].required is False

    def test_roles_can_be_assigned(self, db):
        role = RoleFactory(name='TestRole')
        data = self._valid_data()
        data['roles'] = [role.pk]
        form = UserCreateForm(data=data)
        assert form.is_valid(), form.errors
        user = form.save()
        assert role in user.roles.all()


@pytest.mark.django_db
class TestUserUpdateForm:
    def test_valid_form(self, user):
        data = {
            'username': user.username,
            'email': user.email,
            'first_name': 'Updated',
            'last_name': user.last_name,
            'status': 'active',
        }
        form = UserUpdateForm(data=data, instance=user)
        assert form.is_valid(), form.errors

    def test_update_roles(self, user, db):
        role = RoleFactory(name='NewRole')
        data = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'status': user.status,
            'roles': [role.pk],
        }
        form = UserUpdateForm(data=data, instance=user)
        assert form.is_valid(), form.errors
        form.save()
        assert role in user.roles.all()

    def test_clear_roles(self, user, role, db):
        user.roles.add(role)
        data = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'status': user.status,
            'roles': [],
        }
        form = UserUpdateForm(data=data, instance=user)
        assert form.is_valid(), form.errors
        form.save()
        assert user.roles.count() == 0


@pytest.mark.django_db
class TestRolePermissionsForm:
    def test_creates_module_permissions(self, db):
        role = RoleFactory()
        data = {}
        for module_key, _ in MODULE_CHOICES:
            for action in ('view', 'create', 'edit', 'delete'):
                data[f'{module_key}_{action}'] = module_key == 'users' and action == 'view'
        project = ExternalProjectFactory()
        data[f'proj_{project.pk}_view'] = True
        for action in ('create', 'edit', 'delete'):
            data[f'proj_{project.pk}_{action}'] = False

        form = RolePermissionsForm(data=data, role=role)
        assert form.is_valid(), form.errors
        form.save()

        perm = ModulePermission.objects.get(role=role, module='users')
        assert perm.can_view is True
        assert perm.can_create is False

    def test_updates_existing_permissions(self, db):
        role = RoleFactory()
        ModulePermission.objects.create(role=role, module='users', can_view=False)
        project = ExternalProjectFactory()

        data = {}
        for module_key, _ in MODULE_CHOICES:
            for action in ('view', 'create', 'edit', 'delete'):
                data[f'{module_key}_{action}'] = module_key == 'users' and action == 'view'
        for action in ('view', 'create', 'edit', 'delete'):
            data[f'proj_{project.pk}_{action}'] = False

        form = RolePermissionsForm(data=data, role=role)
        assert form.is_valid(), form.errors
        form.save()

        perm = ModulePermission.objects.get(role=role, module='users')
        assert perm.can_view is True

    def test_saves_project_permissions(self, db):
        role = RoleFactory()
        project = ExternalProjectFactory()

        data = {}
        for module_key, _ in MODULE_CHOICES:
            for action in ('view', 'create', 'edit', 'delete'):
                data[f'{module_key}_{action}'] = False
        data[f'proj_{project.pk}_view'] = True
        data[f'proj_{project.pk}_edit'] = True
        for action in ('create', 'delete'):
            data[f'proj_{project.pk}_{action}'] = False

        form = RolePermissionsForm(data=data, role=role)
        assert form.is_valid(), form.errors
        form.save()

        pp = ProjectPermission.objects.get(role=role, project=project)
        assert pp.can_view is True
        assert pp.can_edit is True
        assert pp.can_create is False


@pytest.mark.django_db
class TestProjectEmailActionsForm:
    def test_creates_action_for_template(self, db):
        project = ExternalProjectFactory()
        template = EmailTemplateFactory()
        data = {}
        for action_key, _ in PROJECT_ACTION_CHOICES:
            data[f'{action_key}_template'] = template.pk if action_key == 'created' else ''
            data[f'{action_key}_active'] = True

        form = ProjectEmailActionsForm(data=data, project=project)
        assert form.is_valid(), form.errors
        form.save()

        action = ProjectEmailAction.objects.get(project=project, action_key='created')
        assert action.template == template
        assert action.is_active is True

    def test_removes_action_when_no_template(self, db):
        project = ExternalProjectFactory()
        template = EmailTemplateFactory()
        ProjectEmailActionFactory(project=project, action_key='created', template=template, is_active=True)

        data = {}
        for action_key, _ in PROJECT_ACTION_CHOICES:
            data[f'{action_key}_template'] = ''
            data[f'{action_key}_active'] = False

        form = ProjectEmailActionsForm(data=data, project=project)
        assert form.is_valid(), form.errors
        form.save()

        assert not ProjectEmailAction.objects.filter(project=project, action_key='created').exists()

    def test_updates_existing_action(self, db):
        project = ExternalProjectFactory()
        old_template = EmailTemplateFactory(name='Old')
        new_template = EmailTemplateFactory(name='New')
        ProjectEmailActionFactory(project=project, action_key='updated', template=old_template)

        data = {}
        for action_key, _ in PROJECT_ACTION_CHOICES:
            if action_key == 'updated':
                data[f'{action_key}_template'] = new_template.pk
                data[f'{action_key}_active'] = True
            else:
                data[f'{action_key}_template'] = ''
                data[f'{action_key}_active'] = False

        form = ProjectEmailActionsForm(data=data, project=project)
        assert form.is_valid(), form.errors
        form.save()

        action = ProjectEmailAction.objects.get(project=project, action_key='updated')
        assert action.template == new_template

    def test_initial_values_from_existing(self, db):
        project = ExternalProjectFactory()
        template = EmailTemplateFactory()
        ProjectEmailActionFactory(project=project, action_key='created', template=template, is_active=True)

        form = ProjectEmailActionsForm(project=project)
        field = form.fields.get('created_template')
        assert field is not None
        assert field.initial == template
