"""Workflow engine — all state-transition logic lives here."""
import copy
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.approvals.models import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ACTION_REQUEST_CHANGES,
    INSTANCE_STATUS_APPROVED,
    INSTANCE_STATUS_CANCELLED,
    INSTANCE_STATUS_IN_PROGRESS,
    INSTANCE_STATUS_PENDING,
    INSTANCE_STATUS_REJECTED,
    STEP_STATUS_APPROVED,
    STEP_STATUS_CHANGES_REQUESTED,
    STEP_STATUS_PENDING,
    STEP_STATUS_REJECTED,
    STEP_STATUS_SKIPPED,
    STEP_STATUS_WAITING,
    ApprovalDecision,
    WorkflowInstance,
    WorkflowStepInstance,
)

from apps.approvals.policies import (
    DEADLINE_AUTO_APPROVE,
    DEADLINE_AUTO_REJECT,
    DEADLINE_NOTIFY,
    DEADLINE_SKIP,
    NO_APPROVERS_BLOCK,
    NO_APPROVERS_SKIP,
)

logger = logging.getLogger(__name__)
User = get_user_model()

VALID_ACTIONS = {ACTION_APPROVE, ACTION_REJECT, ACTION_REQUEST_CHANGES}


class WorkflowEngine:
    """
    Drives a WorkflowInstance through its steps.

    Usage:
        engine = WorkflowEngine(instance)
        engine.start()
        engine.decide(step_instance, user, ACTION_APPROVE, comment="LGTM")
    """

    def __init__(self, instance: WorkflowInstance):
        self.instance = instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @transaction.atomic
    def start(self) -> None:
        """Activate the first step and mark instance as in-progress."""
        if self.instance.status != 'pending':
            raise ValueError(f"Cannot start a workflow in '{self.instance.status}' state.")

        self.instance.status = INSTANCE_STATUS_IN_PROGRESS
        self.instance.save(update_fields=['status', 'updated_at'])

        first_step = self.instance.steps.order_by('step_order').first()
        if first_step is None:
            raise ValueError("Workflow has no steps.")

        self._activate_or_skip(first_step)

    @transaction.atomic
    def decide(
        self,
        step_instance: WorkflowStepInstance,
        user: User,
        action: str,
        comment: str = '',
    ) -> ApprovalDecision:
        """Record a decision for a step and advance the workflow if complete."""
        if action not in VALID_ACTIONS:
            raise ValueError(f"Unknown action '{action}'.")

        if step_instance.workflow_instance_id != self.instance.pk:
            raise ValueError("Step does not belong to this workflow instance.")

        # Re-fetch under a row lock so concurrent decisions serialise.
        step_instance = (
            WorkflowStepInstance.objects.select_for_update().get(pk=step_instance.pk)
        )

        if step_instance.status != STEP_STATUS_PENDING:
            raise ValueError(f"Step is not pending (current status: '{step_instance.status}').")

        if not self.can_decide(step_instance, user):
            raise PermissionError(f"User {user} is not an authorised approver for this step.")

        if action == ACTION_APPROVE and step_instance.decisions.filter(
            user=user, action=ACTION_APPROVE,
        ).exists():
            raise ValueError("You have already approved this step.")

        decision = ApprovalDecision.objects.create(
            step_instance=step_instance,
            user=user,
            action=action,
            comment=comment,
        )

        if action == ACTION_REJECT:
            self._reject_workflow(step_instance)
        elif action == ACTION_REQUEST_CHANGES:
            # Block the step until the requester resubmits (see resubmit()).
            step_instance.status = STEP_STATUS_CHANGES_REQUESTED
            step_instance.save(update_fields=['status', 'updated_at'])
            self._send_step_notifications(step_instance, 'on_request_changes')
        elif action == ACTION_APPROVE:
            if self._is_step_complete(step_instance):
                self._complete_step(step_instance)
                self._advance_workflow(step_instance)

        return decision

    @transaction.atomic
    def cancel(self, user: User = None) -> None:
        """Cancel a pending/in-progress workflow; open steps become skipped."""
        if self.instance.status not in (INSTANCE_STATUS_PENDING, INSTANCE_STATUS_IN_PROGRESS):
            raise ValueError(f"Cannot cancel a workflow in '{self.instance.status}' state.")

        self.instance.steps.filter(
            status__in=[STEP_STATUS_WAITING, STEP_STATUS_PENDING, STEP_STATUS_CHANGES_REQUESTED]
        ).update(status=STEP_STATUS_SKIPPED)

        self.instance.status = INSTANCE_STATUS_CANCELLED
        self.instance.completed_at = timezone.now()
        self.instance.save(update_fields=['status', 'completed_at', 'updated_at'])
        logger.info("Workflow #%s cancelled by %s.", self.instance.pk, user)

    @transaction.atomic
    def resubmit(self, user: User = None) -> WorkflowStepInstance:
        """Re-activate the step blocked by request_changes (fresh deadline,
        on_activate notifications fire again)."""
        if self.instance.status != INSTANCE_STATUS_IN_PROGRESS:
            raise ValueError(
                f"Cannot resubmit a workflow in '{self.instance.status}' state."
            )

        step = (
            self.instance.steps
            .select_for_update()
            .filter(status=STEP_STATUS_CHANGES_REQUESTED)
            .order_by('step_order')
            .first()
        )
        if step is None:
            raise ValueError("No step is awaiting changes.")

        step.deadline_handled = False
        self._activate_step(step)
        logger.info("Workflow #%s step '%s' resubmitted by %s.", self.instance.pk, step.step_key, user)
        return step

    @transaction.atomic
    def handle_deadline(self, step: WorkflowStepInstance) -> None:
        """Apply the step's on_deadline policy once its deadline has passed.

        Policies: 'notify' (default — send on_deadline notification only),
        'skip', 'auto_approve', 'auto_reject'.
        """
        step = WorkflowStepInstance.objects.select_for_update().get(pk=step.pk)
        if step.status != STEP_STATUS_PENDING or step.deadline_handled:
            return
        if not step.deadline_at or step.deadline_at > timezone.now():
            return

        step.deadline_handled = True
        step.save(update_fields=['deadline_handled', 'updated_at'])
        self._send_step_notifications(step, 'on_deadline')

        policy = step.step_config.get('on_deadline', DEADLINE_NOTIFY)
        if policy == DEADLINE_SKIP:
            self._skip_step(step)
            self._advance_workflow(step)
        elif policy == DEADLINE_AUTO_APPROVE:
            self._complete_step(step)
            self._advance_workflow(step)
        elif policy == DEADLINE_AUTO_REJECT:
            self._reject_workflow(step)

    def can_decide(self, step_instance: WorkflowStepInstance, user: User) -> bool:
        """Return True if *user* is an authorised approver for *step_instance*."""
        cfg = step_instance.step_config
        if not cfg.get('allow_self_approval', True) and user == self.instance.started_by:
            return False
        approvers = self._resolve_approvers(step_instance)
        return user in approvers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _activate_or_skip(self, step: WorkflowStepInstance) -> None:
        """Activate *step* if its data conditions pass; otherwise skip it and
        try the next step in order. If no step is activatable, the workflow is
        considered fully approved."""
        current = step
        while current is not None:
            if self._step_conditions_met(current):
                if self._no_approvers_should_skip(current):
                    self._skip_step(current)
                else:
                    self._activate_step(current)
                    return
            else:
                self._skip_step(current)
            current = (
                self.instance.steps
                .filter(step_order__gt=current.step_order)
                .order_by('step_order')
                .first()
            )
        self._complete_workflow()

    def _no_approvers_should_skip(self, step: WorkflowStepInstance) -> bool:
        """True if the step resolves to zero approvers and its policy says skip."""
        if self._resolve_approvers(step):
            return False
        policy = step.step_config.get('on_no_approvers', NO_APPROVERS_BLOCK)
        if policy == NO_APPROVERS_SKIP:
            logger.warning(
                "Workflow #%s step '%s': no approvers resolved — skipping (on_no_approvers).",
                self.instance.pk, step.step_key,
            )
            return True
        logger.warning(
            "Workflow #%s step '%s': no approvers resolved — the step will block "
            "until config or data changes.",
            self.instance.pk, step.step_key,
        )
        return False

    def _step_conditions_met(self, step: WorkflowStepInstance) -> bool:
        from apps.approvals.conditions import evaluate_conditions
        conditions = step.step_config.get('conditions')
        if not conditions:
            return True
        return evaluate_conditions(conditions, self.instance.content_object)

    def _skip_step(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_SKIPPED
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'completed_at', 'updated_at'])

    def _activate_step(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_PENDING
        step.activated_at = timezone.now()

        cfg = step.step_config
        if cfg.get('deadline_hours'):
            step.deadline_at = step.activated_at + timedelta(hours=cfg['deadline_hours'])

        step.save(update_fields=[
            'status', 'activated_at', 'deadline_at', 'deadline_handled', 'updated_at',
        ])
        self.instance.current_step_order = step.step_order
        self.instance.save(update_fields=['current_step_order', 'updated_at'])
        self._send_step_notifications(step, 'on_activate')

    def _complete_step(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_APPROVED
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._send_step_notifications(step, 'on_complete')

    def _advance_workflow(self, completed_step: WorkflowStepInstance) -> None:
        next_step = (
            self.instance.steps
            .filter(step_order__gt=completed_step.step_order)
            .order_by('step_order')
            .first()
        )
        if next_step is None:
            self._complete_workflow()
        else:
            self._activate_or_skip(next_step)

    def _reject_workflow(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_REJECTED
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'completed_at', 'updated_at'])

        # Mark all waiting/pending steps as skipped.
        self.instance.steps.filter(
            status__in=[STEP_STATUS_WAITING, STEP_STATUS_PENDING, STEP_STATUS_CHANGES_REQUESTED]
        ).exclude(pk=step.pk).update(status=STEP_STATUS_SKIPPED)

        self.instance.status = INSTANCE_STATUS_REJECTED
        self.instance.completed_at = timezone.now()
        self.instance.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._send_step_notifications(step, 'on_reject')
        self._run_callbacks('on_rejected')

    def _complete_workflow(self) -> None:
        self.instance.status = INSTANCE_STATUS_APPROVED
        self.instance.completed_at = timezone.now()
        self.instance.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._run_callbacks('on_approved')

    # ------------------------------------------------------------------
    # Approver resolution
    # ------------------------------------------------------------------

    def _resolve_approvers(self, step: WorkflowStepInstance) -> list:
        cfg = step.step_config
        approvers_cfg = cfg.get('approvers', [])
        users: list = []
        seen: set = set()
        for entry in approvers_cfg:
            for user in self._resolve_single_approver(entry):
                if user.pk not in seen:
                    seen.add(user.pk)
                    users.append(user)
        return users

    def _resolve_single_approver(self, entry: dict) -> list:
        approver_type = entry.get('type')
        resolver = {
            'user': self._approvers_by_user,
            'role': self._approvers_by_role,
            'group': self._approvers_by_group,
            'attribute': self._approvers_by_attribute,
        }.get(approver_type)
        if resolver is None:
            logger.warning("Unknown approver type '%s'.", approver_type)
            return []
        return resolver(entry)

    def _approvers_by_user(self, entry: dict) -> list:
        approver_id = entry.get('id')
        try:
            return [User.objects.get(pk=approver_id)]
        except User.DoesNotExist:
            logger.warning("Approver user pk=%s not found.", approver_id)
            return []

    def _approvers_by_role(self, entry: dict) -> list:
        from apps.roles.models import Role
        role = self._get_by_id_or_name(Role.objects, entry)
        if role is None:
            logger.warning("Approver role %r not found.", entry)
            return []
        return list(User.objects.filter(roles=role, is_active=True))

    def _approvers_by_group(self, entry: dict) -> list:
        from django.contrib.auth.models import Group
        group = self._get_by_id_or_name(Group.objects, entry)
        if group is None:
            logger.warning("Approver group %r not found.", entry)
            return []
        return list(group.user_set.filter(is_active=True))

    @staticmethod
    def _get_by_id_or_name(manager, entry: dict):
        """Look an object up by 'id' (preferred) or 'name' — makes configs
        portable between environments where pks differ."""
        if entry.get('id') is not None:
            return manager.filter(pk=entry['id']).first()
        if entry.get('name'):
            return manager.filter(name=entry['name']).first()
        return None

    def _approvers_by_attribute(self, entry: dict) -> list:
        """Resolve approvers dynamically from the content object, e.g.
        {"type": "attribute", "path": "created_by"} or "owner.manager".
        The path may yield a single user, a queryset/manager or an iterable."""
        from apps.approvals.conditions import resolve_field

        value = resolve_field(self.instance.content_object, entry.get('path'))
        if value is None:
            logger.warning(
                "Workflow #%s: attribute approver path '%s' resolved to None.",
                self.instance.pk, entry.get('path'),
            )
            return []
        if isinstance(value, User):
            return [value] if value.is_active else []
        if hasattr(value, 'all'):  # manager / queryset
            value = value.all()
        try:
            return [u for u in value if isinstance(u, User) and u.is_active]
        except TypeError:
            logger.warning(
                "Workflow #%s: attribute approver path '%s' resolved to a "
                "non-user value (%r).",
                self.instance.pk, entry.get('path'), value,
            )
            return []

    # ------------------------------------------------------------------
    # Step completion logic
    # ------------------------------------------------------------------

    def _is_step_complete(self, step: WorkflowStepInstance) -> bool:
        """Determine whether enough approvals have been given to complete the step."""
        cfg = step.step_config
        approval_type = cfg.get('approval_type', 'all')
        total_approvers = len(self._resolve_approvers(step))
        # Count distinct users so repeated approvals by one person don't
        # satisfy 'all'/'majority' thresholds.
        approve_count = (
            step.decisions.filter(action=ACTION_APPROVE)
            .values('user').distinct().count()
        )

        if total_approvers == 0:
            return False
        if approval_type == 'any':
            return approve_count >= 1
        if approval_type == 'all':
            return approve_count >= total_approvers
        if approval_type == 'majority':
            return approve_count > total_approvers / 2
        if approval_type == 'quorum':
            return approve_count >= cfg.get('quorum_count', 1)
        return False

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _send_step_notifications(self, step: WorkflowStepInstance, event: str) -> None:
        from apps.approvals.notifications import send_workflow_notification

        cfg = step.step_config
        notifications = cfg.get('notifications', {})
        notification_cfg = notifications.get(event)
        if not notification_cfg:
            return

        template_name = notification_cfg.get('template')
        if not template_name:
            return

        recipients = self._resolve_notification_recipients(step, notification_cfg)
        for recipient in recipients:
            try:
                send_workflow_notification(
                    workflow_instance=self.instance,
                    step_instance=step,
                    notification_type=event,
                    recipient=recipient,
                    template_name=template_name,
                )
            except Exception:
                logger.exception(
                    "Failed to send '%s' notification to %s for workflow #%s step '%s'.",
                    event, recipient, self.instance.pk, step.step_key,
                )

    def _resolve_notification_recipients(
        self, step: WorkflowStepInstance, notification_cfg: dict
    ) -> list:
        recipients_cfg = notification_cfg.get('recipients', 'approvers')

        if recipients_cfg == 'approvers':
            return self._resolve_approvers(step)

        if recipients_cfg == 'requester':
            return [self.instance.started_by] if self.instance.started_by else []

        if recipients_cfg == 'all':
            approvers = self._resolve_approvers(step)
            requester = self.instance.started_by
            combined = list(approvers)
            if requester and requester not in combined:
                combined.append(requester)
            return combined

        return []

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _run_callbacks(self, event: str) -> None:
        """Invoke completion callbacks on the content object.

        Two config shapes are supported:
        - legacy: "callback": "method"          → called for both outcomes
        - preferred: "callbacks": {"on_approved": "m1", "on_rejected": "m2"}
        """
        snapshot = self.instance.config_snapshot
        names = []
        if snapshot.get('callback'):
            names.append(snapshot['callback'])
        event_callback = (snapshot.get('callbacks') or {}).get(event)
        if event_callback:
            names.append(event_callback)
        if not names:
            return

        content_object = self.instance.content_object
        if content_object is None:
            logger.warning("Workflow #%s: content_object is None, skipping callbacks.", self.instance.pk)
            return

        for name in names:
            method = getattr(content_object, name, None)
            if method is None:
                logger.warning(
                    "Workflow #%s: callback method '%s' not found on %s.",
                    self.instance.pk, name, type(content_object).__name__,
                )
                continue
            try:
                method(workflow_instance=self.instance)
            except Exception:
                logger.exception(
                    "Workflow #%s: callback '%s' raised an exception.",
                    self.instance.pk, name,
                )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_workflow_instance(
    template,
    content_object,
    started_by=None,
    config=None,
) -> WorkflowInstance:
    """
    Create a WorkflowInstance (and all step instances) from a template,
    then immediately start it.

    Pass *config* to snapshot a different config than the template's own
    (used by per-project custom_config overrides).
    """
    from django.contrib.contenttypes.models import ContentType

    effective_config = copy.deepcopy(config if config is not None else template.config)
    ct = ContentType.objects.get_for_model(content_object)

    if effective_config.get('allow_concurrent', True) is False:
        already_running = WorkflowInstance.objects.filter(
            content_type=ct,
            object_id=content_object.pk,
            status__in=[INSTANCE_STATUS_PENDING, INSTANCE_STATUS_IN_PROGRESS],
        ).exists()
        if already_running:
            raise ValueError(
                "A workflow is already running for this object "
                "(allow_concurrent is false)."
            )

    instance = WorkflowInstance.objects.create(
        workflow_template=template,
        content_type=ct,
        object_id=content_object.pk,
        config_snapshot=effective_config,
        started_by=started_by,
    )

    steps_cfg = effective_config.get('steps', [])
    for step_cfg in sorted(steps_cfg, key=lambda s: s['step_order']):
        WorkflowStepInstance.objects.create(
            workflow_instance=instance,
            step_key=step_cfg['step_key'],
            step_order=step_cfg['step_order'],
        )

    engine = WorkflowEngine(instance)
    engine.start()
    return instance
