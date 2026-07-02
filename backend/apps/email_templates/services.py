from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.email_templates.models import EmailTemplate
    from apps.projects.models import ExternalProject


def compile_mjml(mjml_source: str) -> str:
    """Compile MJML source to HTML. Raises ValueError on MJML errors."""
    try:
        import mjml as mjml_lib
    except ImportError as exc:
        raise RuntimeError("mjml package is not installed. Run: pip install mjml") from exc

    result = mjml_lib.mjml_to_html(mjml_source)
    if result.errors:
        raise ValueError('\n'.join(str(e) for e in result.errors))
    return result.html


def render_template(template: EmailTemplate, context: dict) -> tuple[str, str]:
    """
    Render MJML template with Django template variables, compile to HTML.
    Returns (subject, html).
    """
    from django.template import Context, Template

    rendered_mjml = Template(template.mjml_body).render(
        Context(context, autoescape=False)
    )
    html = compile_mjml(rendered_mjml)
    subject = Template(template.subject).render(Context(context, autoescape=False))
    return subject, html


def _json_safe(value):
    """Coerce a template context to something a JSONField can store.

    Contexts routinely contain model instances (project, user, workflow);
    anything not JSON-serializable is stored as its string representation.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def send_email_from_template(
    template: EmailTemplate,
    recipient_email: str,
    context: dict,
) -> bool:
    """Render template, send email, write to EmailLog. Returns True on success."""
    from django.core.mail import send_mail

    from apps.email_templates.models import EmailLog

    try:
        subject, html = render_template(template, context)
        send_mail(
            subject=subject,
            message='',
            from_email=None,
            recipient_list=[recipient_email],
            html_message=html,
        )
        EmailLog.objects.create(
            template=template,
            recipient=recipient_email,
            subject=subject,
            context_data=_json_safe(context),
            status='success',
        )
        return True
    except Exception as exc:
        EmailLog.objects.create(
            template=template,
            recipient=recipient_email,
            subject=template.subject,
            context_data=_json_safe(context),
            status='failed',
            error=str(exc),
        )
        return False


def send_project_action_email(
    project: ExternalProject,
    action_key: str,
    recipient_email: str,
    context: dict,
) -> bool:
    """
    Find the active template bound to a project action and send an email.
    Returns False silently if no active action is configured.

    Usage from other modules:
        from apps.email_templates.services import send_project_action_email
        send_project_action_email(project, 'status_changed', user.email, {'project': project})
    """
    from apps.email_templates.models import ProjectEmailAction

    action = ProjectEmailAction.objects.filter(
        project=project, action_key=action_key, is_active=True
    ).select_related('template').first()
    if not action or not action.template:
        return False
    return send_email_from_template(action.template, recipient_email, context)


def preview_template(template: EmailTemplate, sample_context: dict | None = None) -> str:
    """Compile template with optional sample context. Returns HTML string."""
    from django.template import Context, Template

    ctx = sample_context or {}
    rendered_mjml = Template(template.mjml_body).render(
        Context(ctx, autoescape=False)
    )
    return compile_mjml(rendered_mjml)
