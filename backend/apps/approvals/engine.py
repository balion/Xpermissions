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
)

logger = logging.getLogger(__name__)
User = get_user_model()


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

        self._activate_step(first_step)

    @transaction.atomic
    def decide(
        self,
        step_instance: WorkflowStepInstance,
        user: User,
        action: str,
        comment: str = '',
    ) -> ApprovalDecision:
        """Record a decision for a step and advance the workflow if complete."""
        if step_instance.workflow_instance_id != self.instance.pk:
            raise ValueError("Step does not belong to this workflow instance.")

        if step_instance.status != STEP_STATUS_PENDING:
            raise ValueError(f"Step is not pending (current status: '{step_instance.status}').")

        if not self.can_decide(step_instance, user):
            raise PermissionError(f"User {user} is not an authorised approver for this step.")

        decision = ApprovalDecision.objects.create(
            step_instance=step_instance,
            user=user,
            action=action,
            comment=comment,
        )

        if action == ACTION_REJECT:
            self._reject_workflow(step_instance)
        elif action == ACTION_REQUEST_CHANGES:
            # Keep step in pending — additional decisions can follow or
            # the requester will resubmit; workflow stays in-progress.
            pass
        elif action == ACTION_APPROVE:
            if self._is_step_complete(step_instance):
                self._complete_step(step_instance)
                self._advance_workflow(step_instance)

        return decision

    def can_decide(self, step_instance: WorkflowStepInstance, user: User) -> bool:
        """Return True if *user* is an authorised approver for *step_instance*."""
        approvers = self._resolve_approvers(step_instance)
        return user in approvers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _activate_step(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_PENDING
        step.activated_at = timezone.now()

        cfg = step.step_config
        if cfg.get('deadline_hours'):
            step.deadline_at = step.activated_at + timedelta(hours=cfg['deadline_hours'])

        step.save(update_fields=['status', 'activated_at', 'deadline_at', 'updated_at'])
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
            self._activate_step(next_step)

    def _reject_workflow(self, step: WorkflowStepInstance) -> None:
        step.status = STEP_STATUS_REJECTED
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'completed_at', 'updated_at'])

        # Mark all waiting/pending steps as skipped.
        self.instance.steps.filter(
            status__in=[STEP_STATUS_WAITING, STEP_STATUS_PENDING]
        ).exclude(pk=step.pk).update(status=STEP_STATUS_SKIPPED)

        self.instance.status = INSTANCE_STATUS_REJECTED
        self.instance.completed_at = timezone.now()
        self.instance.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._send_step_notifications(step, 'on_reject')
        self._run_callback()

    def _complete_workflow(self) -> None:
        self.instance.status = INSTANCE_STATUS_APPROVED
        self.instance.completed_at = timezone.now()
        self.instance.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._run_callback()

    # ------------------------------------------------------------------
    # Approver resolution
    # ------------------------------------------------------------------

    def _resolve_approvers(self, step: WorkflowStepInstance) -> list:
        cfg = step.step_config
        approvers_cfg = cfg.get('approvers', [])
        users = []
        for entry in approvers_cfg:
            users.extend(self._resolve_single_approver(entry))
        return users

    def _resolve_single_approver(self, entry: dict) -> list:
        approver_type = entry.get('type')
        approver_id = entry.get('id')
        resolver = {
            'user': self._approvers_by_user,
            'role': self._approvers_by_role,
            'group': self._approvers_by_group,
        }.get(approver_type)
        if resolver is None:
            logger.warning("Unknown approver type '%s'.", approver_type)
            return []
        return resolver(approver_id)

    def _approvers_by_user(self, approver_id) -> list:
        try:
            return [User.objects.get(pk=approver_id)]
        except User.DoesNotExist:
            logger.warning("Approver user pk=%s not found.", approver_id)
            return []

    def _approvers_by_role(self, approver_id) -> list:
        from apps.roles.models import Role
        try:
            role = Role.objects.get(pk=approver_id)
            return list(User.objects.filter(roles=role, is_active=True))
        except Role.DoesNotExist:
            logger.warning("Approver role pk=%s not found.", approver_id)
            return []

    def _approvers_by_group(self, approver_id) -> list:
        from django.contrib.auth.models import Group
        try:
            group = Group.objects.get(pk=approver_id)
            return list(group.user_set.filter(is_active=True))
        except Group.DoesNotExist:
            logger.warning("Approver group pk=%s not found.", approver_id)
            return []

    # ------------------------------------------------------------------
    # Step completion logic
    # ------------------------------------------------------------------

    def _is_step_complete(self, step: WorkflowStepInstance) -> bool:
        """Determine whether enough approvals have been given to complete the step."""
        cfg = step.step_config
        approval_type = cfg.get('approval_type', 'all')
        total_approvers = len(self._resolve_approvers(step))
        approve_count = step.decisions.filter(action=ACTION_APPROVE).count()

        if total_approvers == 0:
            return False
        if approval_type == 'any':
            return approve_count >= 1
        if approval_type == 'all':
            return approve_count >= total_approvers
        if approval_type == 'majority':
            return approve_count > total_approvers / 2
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
    # Callback
    # ------------------------------------------------------------------

    def _run_callback(self) -> None:
        callback_method = self.instance.config_snapshot.get('callback')
        if not callback_method:
            return

        content_object = self.instance.content_object
        if content_object is None:
            logger.warning("Workflow #%s: content_object is None, skipping callback.", self.instance.pk)
            return

        method = getattr(content_object, callback_method, None)
        if method is None:
            logger.warning(
                "Workflow #%s: callback method '%s' not found on %s.",
                self.instance.pk, callback_method, type(content_object).__name__,
            )
            return

        try:
            method(workflow_instance=self.instance)
        except Exception:
            logger.exception(
                "Workflow #%s: callback '%s' raised an exception.",
                self.instance.pk, callback_method,
            )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_workflow_instance(
    template,
    content_object,
    started_by=None,
) -> WorkflowInstance:
    """
    Create a WorkflowInstance (and all step instances) from a template,
    then immediately start it.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(content_object)
    instance = WorkflowInstance.objects.create(
        workflow_template=template,
        content_type=ct,
        object_id=content_object.pk,
        config_snapshot=copy.deepcopy(template.config),
        started_by=started_by,
    )

    steps_cfg = template.config.get('steps', [])
    for step_cfg in sorted(steps_cfg, key=lambda s: s['step_order']):
        WorkflowStepInstance.objects.create(
            workflow_instance=instance,
            step_key=step_cfg['step_key'],
            step_order=step_cfg['step_order'],
        )

    engine = WorkflowEngine(instance)
    engine.start()
    return instance
