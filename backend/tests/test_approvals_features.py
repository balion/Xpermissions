"""Tests for the extended workflow-engine features: cancel/resubmit,
dynamic approvers, quorum, self-approval, deadline policies, event
callbacks, concurrency guard and template versioning."""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.approvals.engine import WorkflowEngine, create_workflow_instance
from apps.approvals.models import (
    ACTION_APPROVE,
    ACTION_REQUEST_CHANGES,
    INSTANCE_STATUS_APPROVED,
    INSTANCE_STATUS_CANCELLED,
    INSTANCE_STATUS_IN_PROGRESS,
    INSTANCE_STATUS_REJECTED,
    STEP_STATUS_APPROVED,
    STEP_STATUS_CHANGES_REQUESTED,
    STEP_STATUS_PENDING,
    STEP_STATUS_REJECTED,
    STEP_STATUS_SKIPPED,
    WorkflowTemplate,
)
from apps.approvals.validators import validate_workflow_config
from tests.factories import (
    ExternalProjectFactory,
    ProjectPermissionFactory,
    RoleFactory,
    UserFactory,
)


@pytest.fixture
def approver(db):
    return UserFactory()


@pytest.fixture
def requester(db):
    return UserFactory()


@pytest.fixture
def project(db):
    return ExternalProjectFactory()


def _config(steps, **extra):
    return {'workflow_name': 'Featured WF', 'steps': steps, **extra}


def _step(approvers, order=1, key=None, **extra):
    return {
        'step_key': key or f'step_{order}',
        'step_order': order,
        'approval_type': extra.pop('approval_type', 'any'),
        'approvers': approvers,
        **extra,
    }


def _start(config, project, started_by=None):
    template = WorkflowTemplate.objects.create(name='T', config=config)
    return create_workflow_instance(template, project, started_by=started_by)


# ---------------------------------------------------------------------------
# decide() hardening
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDecideHardening:
    def test_unknown_action_raises(self, approver, project):
        instance = _start(_config([_step([{'type': 'user', 'id': approver.pk}])]), project)
        step = instance.steps.first()
        with pytest.raises(ValueError, match="Unknown action"):
            WorkflowEngine(instance).decide(step, approver, 'frobnicate')

    def test_duplicate_approve_raises(self, approver, project):
        other = UserFactory()
        config = _config([_step(
            [{'type': 'user', 'id': approver.pk}, {'type': 'user', 'id': other.pk}],
            approval_type='all',
        )])
        instance = _start(config, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_APPROVE)
        with pytest.raises(ValueError, match="already approved"):
            engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS


# ---------------------------------------------------------------------------
# cancel / resubmit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancel:
    def test_cancel_in_progress(self, approver, project):
        instance = _start(_config([_step([{'type': 'user', 'id': approver.pk}])]), project)
        WorkflowEngine(instance).cancel(user=approver)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_CANCELLED
        assert instance.completed_at is not None
        assert instance.steps.first().status == STEP_STATUS_SKIPPED

    def test_cannot_cancel_finished(self, approver, project):
        instance = _start(_config([_step([{'type': 'user', 'id': approver.pk}])]), project)
        engine = WorkflowEngine(instance)
        engine.decide(instance.steps.first(), approver, ACTION_APPROVE)
        instance.refresh_from_db()
        with pytest.raises(ValueError, match="Cannot cancel"):
            engine.cancel()


@pytest.mark.django_db
class TestResubmit:
    def _blocked_instance(self, approver, project):
        instance = _start(_config([_step([{'type': 'user', 'id': approver.pk}])]), project)
        engine = WorkflowEngine(instance)
        engine.decide(instance.steps.first(), approver, ACTION_REQUEST_CHANGES)
        return instance, engine

    def test_resubmit_reactivates_step(self, approver, project):
        instance, engine = self._blocked_instance(approver, project)
        step = instance.steps.first()
        step.refresh_from_db()
        assert step.status == STEP_STATUS_CHANGES_REQUESTED

        engine.resubmit(user=approver)
        step.refresh_from_db()
        assert step.status == STEP_STATUS_PENDING

        # The workflow can now complete normally.
        engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED

    def test_resubmit_without_blocked_step_raises(self, approver, project):
        instance = _start(_config([_step([{'type': 'user', 'id': approver.pk}])]), project)
        with pytest.raises(ValueError, match="No step is awaiting changes"):
            WorkflowEngine(instance).resubmit()


# ---------------------------------------------------------------------------
# Approver resolution — attribute paths, role by name, self-approval
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDynamicApprovers:
    def test_attribute_approver_resolves_from_object(self, requester):
        owner = UserFactory()
        project = ExternalProjectFactory(created_by=owner)
        config = _config([_step([{'type': 'attribute', 'path': 'created_by'}])])
        instance = _start(config, project, started_by=requester)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        assert engine.can_decide(step, owner) is True
        assert engine.can_decide(step, requester) is False

    def test_role_approver_by_name(self, project):
        role = RoleFactory(name='Finance')
        member = UserFactory()
        member.roles.add(role)
        config = _config([_step([{'type': 'role', 'name': 'Finance'}])])
        instance = _start(config, project)
        assert WorkflowEngine(instance).can_decide(instance.steps.first(), member) is True

    def test_self_approval_disallowed(self, project):
        starter = UserFactory()
        config = _config([_step(
            [{'type': 'user', 'id': starter.pk}],
            allow_self_approval=False,
        )])
        instance = _start(config, project, started_by=starter)
        assert WorkflowEngine(instance).can_decide(instance.steps.first(), starter) is False

    def test_no_approvers_skip_policy(self, approver, project):
        config = _config([
            _step([{'type': 'user', 'id': 999999}], order=1, on_no_approvers='skip'),
            _step([{'type': 'user', 'id': approver.pk}], order=2),
        ])
        instance = _start(config, project)
        assert instance.steps.get(step_order=1).status == STEP_STATUS_SKIPPED
        assert instance.steps.get(step_order=2).status == STEP_STATUS_PENDING


# ---------------------------------------------------------------------------
# Quorum
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQuorum:
    def test_quorum_completes_at_count(self, project):
        users = [UserFactory() for _ in range(4)]
        config = _config([_step(
            [{'type': 'user', 'id': u.pk} for u in users],
            approval_type='quorum',
            quorum_count=2,
        )])
        instance = _start(config, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)

        engine.decide(step, users[0], ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS

        step.refresh_from_db()
        engine.decide(step, users[1], ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------

def _make_overdue(step):
    step.deadline_at = timezone.now() - timedelta(hours=1)
    step.save(update_fields=['deadline_at'])


@pytest.mark.django_db
class TestDeadlinePolicies:
    def _instance(self, approver, project, **step_extra):
        config = _config([
            _step([{'type': 'user', 'id': approver.pk}], order=1,
                  deadline_hours=1, **step_extra),
            _step([{'type': 'user', 'id': approver.pk}], order=2),
        ])
        return _start(config, project)

    def test_notify_policy_marks_handled_keeps_pending(self, approver, project):
        instance = self._instance(approver, project)  # default policy: notify
        step = instance.steps.get(step_order=1)
        _make_overdue(step)
        WorkflowEngine(instance).handle_deadline(step)
        step.refresh_from_db()
        assert step.status == STEP_STATUS_PENDING
        assert step.deadline_handled is True

    def test_skip_policy_advances(self, approver, project):
        instance = self._instance(approver, project, on_deadline='skip')
        step = instance.steps.get(step_order=1)
        _make_overdue(step)
        WorkflowEngine(instance).handle_deadline(step)
        assert instance.steps.get(step_order=1).status == STEP_STATUS_SKIPPED
        assert instance.steps.get(step_order=2).status == STEP_STATUS_PENDING

    def test_auto_approve_policy(self, approver, project):
        instance = self._instance(approver, project, on_deadline='auto_approve')
        step = instance.steps.get(step_order=1)
        _make_overdue(step)
        WorkflowEngine(instance).handle_deadline(step)
        assert instance.steps.get(step_order=1).status == STEP_STATUS_APPROVED
        assert instance.steps.get(step_order=2).status == STEP_STATUS_PENDING

    def test_auto_reject_policy(self, approver, project):
        instance = self._instance(approver, project, on_deadline='auto_reject')
        step = instance.steps.get(step_order=1)
        _make_overdue(step)
        WorkflowEngine(instance).handle_deadline(step)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_REJECTED
        assert instance.steps.get(step_order=1).status == STEP_STATUS_REJECTED

    def test_future_deadline_not_handled(self, approver, project):
        instance = self._instance(approver, project, on_deadline='auto_reject')
        step = instance.steps.get(step_order=1)
        WorkflowEngine(instance).handle_deadline(step)
        step.refresh_from_db()
        assert step.status == STEP_STATUS_PENDING
        assert step.deadline_handled is False

    def test_management_command_processes_overdue(self, approver, project):
        from django.core.management import call_command
        instance = self._instance(approver, project, on_deadline='skip')
        step = instance.steps.get(step_order=1)
        _make_overdue(step)
        call_command('process_workflow_deadlines')
        assert instance.steps.get(step_order=1).status == STEP_STATUS_SKIPPED


# ---------------------------------------------------------------------------
# Event callbacks
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEventCallbacks:
    def _config_with_callbacks(self, approver):
        return _config(
            [_step([{'type': 'user', 'id': approver.pk}])],
            callbacks={
                'on_approved': 'mark_project_approved',
                'on_rejected': 'mark_project_rejected',
            },
        )

    def test_on_approved_called(self, approver):
        project = ExternalProjectFactory(status='inactive')
        instance = _start(self._config_with_callbacks(approver), project)
        WorkflowEngine(instance).decide(instance.steps.first(), approver, ACTION_APPROVE)
        project.refresh_from_db()
        assert project.status == 'active'

    def test_on_rejected_called(self, approver):
        project = ExternalProjectFactory(status='active')
        instance = _start(self._config_with_callbacks(approver), project)
        WorkflowEngine(instance).decide(instance.steps.first(), approver, 'reject')
        project.refresh_from_db()
        assert project.status == 'inactive'

    def test_on_rejected_not_called_on_approval(self, approver):
        project = ExternalProjectFactory(status='inactive')
        config = _config(
            [_step([{'type': 'user', 'id': approver.pk}])],
            callbacks={'on_rejected': 'mark_project_rejected'},
        )
        instance = _start(config, project)
        WorkflowEngine(instance).decide(instance.steps.first(), approver, ACTION_APPROVE)
        project.refresh_from_db()
        assert project.status == 'inactive'  # unchanged — no on_approved callback


# ---------------------------------------------------------------------------
# Concurrency guard + template versioning
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestConcurrencyGuard:
    def test_allow_concurrent_false_blocks_second_instance(self, approver, project):
        config = _config(
            [_step([{'type': 'user', 'id': approver.pk}])],
            allow_concurrent=False,
        )
        template = WorkflowTemplate.objects.create(name='T', config=config)
        create_workflow_instance(template, project)
        with pytest.raises(ValueError, match="already running"):
            create_workflow_instance(template, project)

    def test_concurrent_allowed_by_default(self, approver, project):
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        create_workflow_instance(template, project)
        create_workflow_instance(template, project)  # no exception


@pytest.mark.django_db
class TestTemplateVersioning:
    def test_config_change_bumps_version(self, approver):
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        assert template.version == 1
        template.config = {**config, 'workflow_name': 'Renamed'}
        template.save()
        template.refresh_from_db()
        assert template.version == 2

    def test_non_config_change_keeps_version(self, approver):
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        template.description = 'Updated description'
        template.save()
        template.refresh_from_db()
        assert template.version == 1


# ---------------------------------------------------------------------------
# Cancel / resubmit HTML views
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelResubmitViews:
    def _viewer(self, project, can_edit=False):
        role = RoleFactory()
        user = UserFactory()
        user.roles.add(role)
        ProjectPermissionFactory(role=role, project=project, can_view=True, can_edit=can_edit)
        return user

    def test_requester_can_cancel(self, client, approver, project):
        requester = self._viewer(project)
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        instance = _start(config, project, started_by=requester)

        client.force_login(requester)
        from django.urls import reverse
        response = client.post(reverse(
            'projects:workflow_cancel',
            kwargs={'pk': project.pk, 'instance_pk': instance.pk},
        ))
        assert response.status_code == 302
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_CANCELLED

    def test_viewer_cannot_cancel_foreign_workflow(self, client, approver, project):
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        instance = _start(config, project, started_by=UserFactory())

        client.force_login(self._viewer(project))
        from django.urls import reverse
        response = client.post(reverse(
            'projects:workflow_cancel',
            kwargs={'pk': project.pk, 'instance_pk': instance.pk},
        ))
        assert response.status_code == 403
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS

    def test_editor_can_resubmit(self, client, approver, project):
        editor = self._viewer(project, can_edit=True)
        config = _config([_step([{'type': 'user', 'id': approver.pk}])])
        instance = _start(config, project, started_by=UserFactory())
        WorkflowEngine(instance).decide(
            instance.steps.first(), approver, ACTION_REQUEST_CHANGES,
        )

        client.force_login(editor)
        from django.urls import reverse
        response = client.post(reverse(
            'projects:workflow_resubmit',
            kwargs={'pk': project.pk, 'instance_pk': instance.pk},
        ))
        assert response.status_code == 302
        assert instance.steps.first().status == STEP_STATUS_PENDING


# ---------------------------------------------------------------------------
# Validator — new keys
# ---------------------------------------------------------------------------

class TestValidatorNewKeys:
    def _base_step(self, **extra):
        return {
            'step_key': 'a', 'step_order': 1, 'approval_type': 'any',
            'approvers': [{'type': 'user', 'id': 1}],
            **extra,
        }

    def test_quorum_requires_count(self):
        step = self._base_step(approval_type='quorum')
        with pytest.raises(ValidationError, match='quorum_count'):
            validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_quorum_with_count_valid(self):
        step = self._base_step(approval_type='quorum', quorum_count=2)
        validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_attribute_approver_requires_path(self):
        step = self._base_step(approvers=[{'type': 'attribute'}])
        with pytest.raises(ValidationError, match='path'):
            validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_role_approver_by_name_valid(self):
        step = self._base_step(approvers=[{'type': 'role', 'name': 'Finance'}])
        validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_role_approver_without_id_or_name_invalid(self):
        step = self._base_step(approvers=[{'type': 'role'}])
        with pytest.raises(ValidationError, match="'id' or 'name'"):
            validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_invalid_on_deadline(self):
        step = self._base_step(on_deadline='explode')
        with pytest.raises(ValidationError, match='on_deadline'):
            validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_invalid_recipients(self):
        step = self._base_step(notifications={
            'on_activate': {'template': 'tpl', 'recipients': 'everyone'},
        })
        with pytest.raises(ValidationError, match='recipients'):
            validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_new_notification_events_valid(self):
        step = self._base_step(notifications={
            'on_deadline': {'template': 'tpl'},
            'on_request_changes': {'template': 'tpl', 'recipients': 'requester'},
        })
        validate_workflow_config({'workflow_name': 'WF', 'steps': [step]})

    def test_invalid_callbacks_event(self):
        with pytest.raises(ValidationError, match='callbacks'):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [self._base_step()],
                'callbacks': {'on_started': 'method'},
            })

    def test_valid_callbacks(self):
        validate_workflow_config({
            'workflow_name': 'WF',
            'steps': [self._base_step()],
            'callbacks': {'on_approved': 'm1', 'on_rejected': 'm2'},
            'allow_concurrent': False,
        })

    def test_allow_concurrent_must_be_bool(self):
        with pytest.raises(ValidationError, match='allow_concurrent'):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [self._base_step()],
                'allow_concurrent': 'no',
            })
