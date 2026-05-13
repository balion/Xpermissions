"""Tests for the Approval Workflow module."""
import pytest
from django.core.exceptions import ValidationError

from apps.approvals.engine import WorkflowEngine, create_workflow_instance
from apps.approvals.models import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ACTION_REQUEST_CHANGES,
    INSTANCE_STATUS_APPROVED,
    INSTANCE_STATUS_IN_PROGRESS,
    INSTANCE_STATUS_REJECTED,
    STEP_STATUS_APPROVED,
    STEP_STATUS_PENDING,
    STEP_STATUS_REJECTED,
    STEP_STATUS_SKIPPED,
    STEP_STATUS_WAITING,
    ApprovalDecision,
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowTemplate,
)
from apps.approvals.validators import validate_workflow_config
from tests.factories import ExternalProjectFactory, RoleFactory, UserFactory


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SIMPLE_CONFIG = {
    'workflow_name': 'Test Workflow',
    'steps': [
        {
            'step_key': 'review',
            'step_order': 1,
            'approval_type': 'any',
            'approvers': [{'type': 'user', 'id': None}],  # id filled per test
        }
    ],
}

TWO_STEP_CONFIG = {
    'workflow_name': 'Two-Step Workflow',
    'steps': [
        {
            'step_key': 'step_one',
            'step_order': 1,
            'approval_type': 'any',
            'approvers': [{'type': 'user', 'id': None}],
        },
        {
            'step_key': 'step_two',
            'step_order': 2,
            'approval_type': 'any',
            'approvers': [{'type': 'user', 'id': None}],
        },
    ],
}


def _make_config(approver_user_ids, approval_type='any'):
    return {
        'workflow_name': 'Test Workflow',
        'steps': [
            {
                'step_key': 'review',
                'step_order': 1,
                'approval_type': approval_type,
                'approvers': [{'type': 'user', 'id': uid} for uid in approver_user_ids],
            }
        ],
    }


def _make_two_step_config(approver1_id, approver2_id):
    return {
        'workflow_name': 'Two-Step',
        'steps': [
            {
                'step_key': 'step_one',
                'step_order': 1,
                'approval_type': 'any',
                'approvers': [{'type': 'user', 'id': approver1_id}],
            },
            {
                'step_key': 'step_two',
                'step_order': 2,
                'approval_type': 'any',
                'approvers': [{'type': 'user', 'id': approver2_id}],
            },
        ],
    }


@pytest.fixture
def approver(db):
    return UserFactory()


@pytest.fixture
def requester(db):
    return UserFactory()


@pytest.fixture
def project(db):
    return ExternalProjectFactory()


def _create_template(config, db_marker=None):
    return WorkflowTemplate.objects.create(
        name='Test Template',
        config=config,
    )


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidateWorkflowConfig:
    def test_valid_minimal_config(self):
        config = {
            'workflow_name': 'My WF',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'user', 'id': 1}],
                }
            ],
        }
        validate_workflow_config(config)  # should not raise

    def test_missing_workflow_name(self):
        with pytest.raises(ValidationError, match='workflow_name'):
            validate_workflow_config({'steps': [{'step_key': 'a', 'step_order': 1, 'approval_type': 'any', 'approvers': [{'type': 'user', 'id': 1}]}]})

    def test_empty_steps(self):
        with pytest.raises(ValidationError, match='steps'):
            validate_workflow_config({'workflow_name': 'WF', 'steps': []})

    def test_invalid_approval_type(self):
        with pytest.raises(ValidationError, match='approval_type'):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [{'step_key': 'a', 'step_order': 1, 'approval_type': 'invalid', 'approvers': [{'type': 'user', 'id': 1}]}],
            })

    def test_duplicate_step_key(self):
        with pytest.raises(ValidationError, match="Duplicate step_key"):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [
                    {'step_key': 'a', 'step_order': 1, 'approval_type': 'any', 'approvers': [{'type': 'user', 'id': 1}]},
                    {'step_key': 'a', 'step_order': 2, 'approval_type': 'any', 'approvers': [{'type': 'user', 'id': 1}]},
                ],
            })

    def test_duplicate_step_order(self):
        with pytest.raises(ValidationError, match="Duplicate step_order"):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [
                    {'step_key': 'a', 'step_order': 1, 'approval_type': 'any', 'approvers': [{'type': 'user', 'id': 1}]},
                    {'step_key': 'b', 'step_order': 1, 'approval_type': 'any', 'approvers': [{'type': 'user', 'id': 1}]},
                ],
            })

    def test_invalid_approver_type(self):
        with pytest.raises(ValidationError, match="'type' must be one of"):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [{'step_key': 'a', 'step_order': 1, 'approval_type': 'any', 'approvers': [{'type': 'nobody', 'id': 1}]}],
            })

    def test_not_a_dict(self):
        with pytest.raises(ValidationError, match="must be a JSON object"):
            validate_workflow_config([])

    def test_all_approval_types_accepted(self):
        for atype in ('any', 'all', 'majority'):
            config = {
                'workflow_name': 'WF',
                'steps': [{'step_key': 'a', 'step_order': 1, 'approval_type': atype, 'approvers': [{'type': 'user', 'id': 1}]}],
            }
            validate_workflow_config(config)

    def test_deadline_hours_invalid(self):
        with pytest.raises(ValidationError, match="deadline_hours"):
            validate_workflow_config({
                'workflow_name': 'WF',
                'steps': [{
                    'step_key': 'a', 'step_order': 1, 'approval_type': 'any',
                    'approvers': [{'type': 'user', 'id': 1}],
                    'deadline_hours': -1,
                }],
            })


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWorkflowEngineStart:
    def test_start_sets_status_in_progress(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project, started_by=approver)
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS

    def test_start_activates_first_step(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project, started_by=approver)
        step = instance.steps.first()
        assert step.status == STEP_STATUS_PENDING
        assert step.activated_at is not None

    def test_later_steps_remain_waiting(self, approver, project):
        config = _make_two_step_config(approver.pk, approver.pk)
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        waiting = instance.steps.filter(status=STEP_STATUS_WAITING)
        assert waiting.count() == 1
        assert waiting.first().step_key == 'step_two'

    def test_cannot_start_twice(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        engine = WorkflowEngine(instance)
        with pytest.raises(ValueError, match="Cannot start"):
            engine.start()


@pytest.mark.django_db
class TestWorkflowEngineDecide:
    def _setup(self, approver, project, approval_type='any', second_approver=None):
        ids = [approver.pk]
        if second_approver:
            ids.append(second_approver.pk)
        config = _make_config(ids, approval_type=approval_type)
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project, started_by=approver)
        step = instance.steps.get(step_key='review')
        return instance, step

    def test_approve_single_approver_completes_workflow(self, approver, project):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED
        step.refresh_from_db()
        assert step.status == STEP_STATUS_APPROVED

    def test_reject_sets_workflow_rejected(self, approver, project):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_REJECT)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_REJECTED
        step.refresh_from_db()
        assert step.status == STEP_STATUS_REJECTED

    def test_non_approver_raises_permission_error(self, approver, project, requester):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        with pytest.raises(PermissionError):
            engine.decide(step, requester, ACTION_APPROVE)

    def test_decide_on_non_pending_step_raises(self, approver, project):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_APPROVE)
        step.refresh_from_db()
        with pytest.raises(ValueError, match="not pending"):
            engine.decide(step, approver, ACTION_APPROVE)

    def test_request_changes_keeps_step_pending(self, approver, project):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_REQUEST_CHANGES)
        step.refresh_from_db()
        assert step.status == STEP_STATUS_PENDING

    def test_all_approval_type_requires_all_approvers(self, approver, project, requester):
        instance, step = self._setup(approver, project, approval_type='all', second_approver=requester)
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        # With 'all', one approval of two is not enough.
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        step.refresh_from_db()
        assert step.status == STEP_STATUS_PENDING
        # Second approver tips it over.
        engine.decide(step, requester, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED

    def test_majority_approval_type(self, approver, project):
        user2 = UserFactory()
        user3 = UserFactory()
        config = _make_config([approver.pk, user2.pk, user3.pk], approval_type='majority')
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        # 1 of 3 not enough
        engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        # 2 of 3 is majority
        engine.decide(step, user2, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED

    def test_reject_skips_remaining_steps(self, approver, project):
        config = _make_two_step_config(approver.pk, approver.pk)
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step1 = instance.steps.get(step_key='step_one')
        engine = WorkflowEngine(instance)
        engine.decide(step1, approver, ACTION_REJECT)
        skipped = instance.steps.filter(status=STEP_STATUS_SKIPPED)
        assert skipped.count() == 1
        assert skipped.first().step_key == 'step_two'

    def test_two_step_workflow_advances(self, approver, project, requester):
        config = _make_two_step_config(approver.pk, requester.pk)
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step1 = instance.steps.get(step_key='step_one')
        step2 = instance.steps.get(step_key='step_two')
        engine = WorkflowEngine(instance)

        engine.decide(step1, approver, ACTION_APPROVE)
        step2.refresh_from_db()
        assert step2.status == STEP_STATUS_PENDING

        engine.decide(step2, requester, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED

    def test_decision_record_created(self, approver, project):
        instance, step = self._setup(approver, project)
        engine = WorkflowEngine(instance)
        decision = engine.decide(step, approver, ACTION_APPROVE, comment='OK')
        assert isinstance(decision, ApprovalDecision)
        assert decision.action == ACTION_APPROVE
        assert decision.comment == 'OK'
        assert decision.user == approver


@pytest.mark.django_db
class TestWorkflowEngineCallback:
    def test_approved_callback_called(self, approver, project):
        config = {
            'workflow_name': 'WF',
            'callback': 'mark_project_approved',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'user', 'id': approver.pk}],
                }
            ],
        }
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_APPROVE)

        project.refresh_from_db()
        from apps.projects.models import PROJECT_STATUS_ACTIVE
        assert project.status == PROJECT_STATUS_ACTIVE

    def test_rejected_callback_called(self, approver, project):
        config = {
            'workflow_name': 'WF',
            'callback': 'mark_project_rejected',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'user', 'id': approver.pk}],
                }
            ],
        }
        template = WorkflowTemplate.objects.create(name='T', config=config)
        project.status = 'active'
        project.save()
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        engine.decide(step, approver, ACTION_REJECT)

        project.refresh_from_db()
        from apps.projects.models import PROJECT_STATUS_INACTIVE
        assert project.status == PROJECT_STATUS_INACTIVE

    def test_missing_callback_method_logged_not_raised(self, approver, project):
        config = {
            'workflow_name': 'WF',
            'callback': 'nonexistent_method',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'user', 'id': approver.pk}],
                }
            ],
        }
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        engine = WorkflowEngine(instance)
        # Should not raise — just logs a warning.
        engine.decide(step, approver, ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED


@pytest.mark.django_db
class TestCanDecide:
    def test_approver_can_decide(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        assert WorkflowEngine(instance).can_decide(step, approver) is True

    def test_non_approver_cannot_decide(self, approver, project, requester):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        assert WorkflowEngine(instance).can_decide(step, requester) is False

    def test_role_based_approver(self, project):
        role = RoleFactory()
        member = UserFactory()
        member.roles.add(role)
        config = {
            'workflow_name': 'WF',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'role', 'id': role.pk}],
                }
            ],
        }
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        assert WorkflowEngine(instance).can_decide(step, member) is True

    def test_non_role_member_cannot_decide(self, project):
        role = RoleFactory()
        outsider = UserFactory()
        config = {
            'workflow_name': 'WF',
            'steps': [
                {
                    'step_key': 'review',
                    'step_order': 1,
                    'approval_type': 'any',
                    'approvers': [{'type': 'role', 'id': role.pk}],
                }
            ],
        }
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        step = instance.steps.first()
        assert WorkflowEngine(instance).can_decide(step, outsider) is False


@pytest.mark.django_db
class TestCreateWorkflowInstance:
    def test_creates_instance_and_steps(self, approver, project):
        config = _make_two_step_config(approver.pk, approver.pk)
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project, started_by=approver)
        assert WorkflowStepInstance.objects.filter(workflow_instance=instance).count() == 2

    def test_config_snapshot_frozen(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        # Mutate the template config.
        template.config['workflow_name'] = 'Changed'
        template.save()
        # Snapshot should be unchanged.
        assert instance.config_snapshot['workflow_name'] == 'Test Workflow'

    def test_content_object_linked(self, approver, project):
        config = _make_config([approver.pk])
        template = WorkflowTemplate.objects.create(name='T', config=config)
        instance = create_workflow_instance(template, project)
        assert instance.content_object == project
