import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.email_templates.models import EmailTemplate, ProjectEmailAction
from apps.projects.models import ExternalProject
from apps.roles.models import ModulePermission, ProjectPermission, Role, UserPermissionOverride


class RoleFactory(DjangoModelFactory):
    class Meta:
        model = Role
        django_get_or_create = ('name',)

    name = factory.Sequence(lambda n: f'Role {n}')
    description = 'Test role'
    is_superadmin = False


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    first_name = 'Test'
    last_name = 'User'
    status = 'active'
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password', 'testpass123')
        obj = super()._create(model_class, *args, **kwargs)
        obj.set_password(password)
        obj.save()
        return obj


class SuperuserFactory(UserFactory):
    is_superuser = True
    is_staff = True
    username = factory.Sequence(lambda n: f'superuser{n}')
    email = factory.Sequence(lambda n: f'superuser{n}@example.com')


class ExternalProjectFactory(DjangoModelFactory):
    class Meta:
        model = ExternalProject

    name = factory.Sequence(lambda n: f'Project {n}')
    description = 'A test project'
    url = 'https://example.com'
    api_key = factory.Sequence(lambda n: f'key-{n}')
    status = 'active'


class ModulePermissionFactory(DjangoModelFactory):
    class Meta:
        model = ModulePermission
        django_get_or_create = ('role', 'module')

    role = factory.SubFactory(RoleFactory)
    module = 'users'
    can_view = True
    can_create = False
    can_edit = False
    can_delete = False


class ProjectPermissionFactory(DjangoModelFactory):
    class Meta:
        model = ProjectPermission
        django_get_or_create = ('role', 'project')

    role = factory.SubFactory(RoleFactory)
    project = factory.SubFactory(ExternalProjectFactory)
    can_view = True
    can_create = False
    can_edit = False
    can_delete = False


class UserPermissionOverrideFactory(DjangoModelFactory):
    class Meta:
        model = UserPermissionOverride
        django_get_or_create = ('user', 'module')

    user = factory.SubFactory(UserFactory)
    module = 'users'
    can_view = None
    can_create = None
    can_edit = None
    can_delete = None


class EmailTemplateFactory(DjangoModelFactory):
    class Meta:
        model = EmailTemplate

    name = factory.Sequence(lambda n: f'Template {n}')
    subject = 'Hello {{ name }}'
    mjml_body = '<mjml><mj-body><mj-section><mj-column><mj-text>Hello</mj-text></mj-column></mj-section></mj-body></mjml>'
    is_active = True


class ProjectEmailActionFactory(DjangoModelFactory):
    class Meta:
        model = ProjectEmailAction
        django_get_or_create = ('project', 'action_key')

    project = factory.SubFactory(ExternalProjectFactory)
    action_key = 'created'
    template = factory.SubFactory(EmailTemplateFactory)
    is_active = True


class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    user = factory.SubFactory(UserFactory)
    action = 'CREATE'
    module = 'users'
    object_id = '1'
    object_repr = 'Test Object'
