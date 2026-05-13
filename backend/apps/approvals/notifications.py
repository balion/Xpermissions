"""Workflow email notifications."""
import logging

from apps.approvals.models import WorkflowInstance, WorkflowNotificationLog, WorkflowStepInstance

logger = logging.getLogger(__name__)


def send_workflow_notification(
    workflow_instance: WorkflowInstance,
    step_instance: WorkflowStepInstance | None,
    notification_type: str,
    recipient,
    template_name: str,
) -> bool:
    """
    Send a workflow-related email using a named EmailTemplate.
    Logs the attempt to WorkflowNotificationLog regardless of outcome.
    Returns True on success.
    """
    from apps.email_templates.models import EmailTemplate
    from apps.email_templates.services import send_email_from_template

    template = EmailTemplate.objects.filter(name=template_name, is_active=True).first()
    if template is None:
        logger.warning(
            "Workflow notification: template '%s' not found or inactive — skipping.",
            template_name,
        )
        return False

    context = _build_context(workflow_instance, step_instance, recipient)

    try:
        subject, _ = _render_subject(template, context)
    except Exception:
        subject = template.subject

    success = send_email_from_template(template, recipient.email, context)

    WorkflowNotificationLog.objects.create(
        workflow_instance=workflow_instance,
        step_instance=step_instance,
        notification_type=notification_type,
        recipient=recipient,
        email_subject=subject,
        email_template_used=template_name,
    )

    return success


def _build_context(
    workflow_instance: WorkflowInstance,
    step_instance: WorkflowStepInstance | None,
    recipient,
) -> dict:
    ctx: dict = {
        'workflow': workflow_instance,
        'workflow_name': workflow_instance.workflow_name,
        'content_object': workflow_instance.content_object,
        'recipient': recipient,
    }
    if step_instance is not None:
        ctx['step'] = step_instance
        ctx['step_key'] = step_instance.step_key
    return ctx


def _render_subject(template, context: dict) -> tuple[str, str]:
    """Return (subject, html) for logging purposes; delegates to email_templates service."""
    from apps.email_templates.services import render_template
    return render_template(template, context)
