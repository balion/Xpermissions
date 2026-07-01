"""Tests for the Approvals HTML UI: overview, template CRUD, sidebar gating."""
import pytest
from django.urls import reverse

from apps.approvals.engine import create_workflow_instance
from apps.approvals.models import WorkflowTemplate
from tests.factories import (
    ExternalProjectFactory,
    ModulePermissionFactory,
    RoleFactory,
    UserFactory,
)

VALID_CONFIG_JSON = (
    '{"workflow_name": "WF", "steps": [{"step_key": "review", "step_order": 1, '
    '"approval_type": "any", "approvers": [{"type": "role", "id": 1}]}]}'
)


def _user_with_approvals(**perms):
    """User whose role grants the given approvals-module permissions."""
    role = RoleFactory()
    user = UserFactory()
    user.roles.add(role)
    ModulePermissionFactory(role=role, module='approvals', **perms)
    return user


@pytest.mark.django_db
class TestApprovalsOverview:
    def test_requires_approvals_view_permission(self, client):
        client.force_login(UserFactory())
        assert client.get(reverse('approvals:overview')).status_code == 403

    def test_visible_with_permission(self, client):
        client.force_login(_user_with_approvals(can_view=True))
        response = client.get(reverse('approvals:overview'))
        assert response.status_code == 200

    def test_overview_lists_projects(self, client):
        project = ExternalProjectFactory(name='Visible Project')
        client.force_login(_user_with_approvals(can_view=True))
        response = client.get(reverse('approvals:overview'))
        assert b'Visible Project' in response.content


@pytest.mark.django_db
class TestSidebarGating:
    def test_link_shown_for_permitted_user(self, client):
        client.force_login(_user_with_approvals(can_view=True))
        response = client.get(reverse('dashboard:index'))
        assert reverse('approvals:overview').encode() in response.content

    def test_link_hidden_for_unpermitted_user(self, client):
        client.force_login(UserFactory())
        response = client.get(reverse('dashboard:index'))
        assert reverse('approvals:overview').encode() not in response.content


@pytest.mark.django_db
class TestWorkflowTemplateCrud:
    def test_list_requires_view(self, client):
        client.force_login(UserFactory())
        assert client.get(reverse('approvals:template_list')).status_code == 403

    def test_create_requires_create_permission(self, client):
        # view-only user may not open the create form.
        client.force_login(_user_with_approvals(can_view=True))
        assert client.get(reverse('approvals:template_create')).status_code == 403

    def test_create_valid_template(self, client):
        client.force_login(_user_with_approvals(can_view=True, can_create=True))
        response = client.post(
            reverse('approvals:template_create'),
            data={'name': 'My WF', 'config': VALID_CONFIG_JSON, 'version': 1, 'is_active': 'on'},
        )
        assert response.status_code == 302
        tpl = WorkflowTemplate.objects.get(name='My WF')
        assert tpl.config['workflow_name'] == 'WF'
        assert tpl.created_by is not None

    def test_create_invalid_json_shows_error(self, client):
        client.force_login(_user_with_approvals(can_view=True, can_create=True))
        response = client.post(
            reverse('approvals:template_create'),
            data={'name': 'Bad', 'config': '{not json', 'version': 1},
        )
        assert response.status_code == 200
        assert not WorkflowTemplate.objects.filter(name='Bad').exists()

    def test_create_invalid_schema_shows_error(self, client):
        client.force_login(_user_with_approvals(can_view=True, can_create=True))
        response = client.post(
            reverse('approvals:template_create'),
            data={'name': 'Bad', 'config': '{"workflow_name": "x", "steps": []}', 'version': 1},
        )
        assert response.status_code == 200
        assert not WorkflowTemplate.objects.filter(name='Bad').exists()

    def test_delete_protected_when_used(self, client):
        approver = UserFactory()
        config = {
            'workflow_name': 'WF',
            'steps': [{
                'step_key': 'review', 'step_order': 1, 'approval_type': 'any',
                'approvers': [{'type': 'user', 'id': approver.pk}],
            }],
        }
        template = WorkflowTemplate.objects.create(name='Used', config=config)
        create_workflow_instance(template, ExternalProjectFactory())

        client.force_login(_user_with_approvals(can_view=True, can_delete=True))
        response = client.post(reverse('approvals:template_delete', kwargs={'pk': template.pk}))
        assert response.status_code == 302
        # Still present — PROTECT prevented the delete.
        assert WorkflowTemplate.objects.filter(pk=template.pk).exists()

    def test_delete_unused_template(self, client):
        template = WorkflowTemplate.objects.create(name='Unused', config={
            'workflow_name': 'WF',
            'steps': [{
                'step_key': 'review', 'step_order': 1, 'approval_type': 'any',
                'approvers': [{'type': 'role', 'id': 1}],
            }],
        })
        client.force_login(_user_with_approvals(can_view=True, can_delete=True))
        response = client.post(reverse('approvals:template_delete', kwargs={'pk': template.pk}))
        assert response.status_code == 302
        assert not WorkflowTemplate.objects.filter(pk=template.pk).exists()
