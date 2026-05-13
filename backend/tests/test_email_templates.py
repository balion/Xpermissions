from unittest.mock import MagicMock, patch

import pytest

from apps.email_templates.models import EmailLog, ProjectEmailAction
from apps.email_templates.services import (
    compile_mjml,
    render_template,
    send_email_from_template,
    send_project_action_email,
)
from tests.factories import EmailTemplateFactory, ExternalProjectFactory, ProjectEmailActionFactory


SIMPLE_MJML = (
    '<mjml><mj-body><mj-section><mj-column>'
    '<mj-text>Hello {{ name }}</mj-text>'
    '</mj-column></mj-section></mj-body></mjml>'
)


@pytest.mark.django_db
class TestCompileMjml:
    def test_compiles_valid_mjml(self):
        html = compile_mjml(
            '<mjml><mj-body><mj-section><mj-column>'
            '<mj-text>Hello</mj-text>'
            '</mj-column></mj-section></mj-body></mjml>'
        )
        assert '<html' in html.lower() or 'DOCTYPE' in html

    def test_raises_on_invalid_mjml(self):
        with pytest.raises((ValueError, Exception)):
            compile_mjml('<not-mjml>')


@pytest.mark.django_db
class TestRenderTemplate:
    def test_renders_subject_and_body(self):
        template = EmailTemplateFactory(
            subject='Hello {{ name }}',
            mjml_body=SIMPLE_MJML,
        )
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>Hello Test</html>'):
            subject, html = render_template(template, {'name': 'Test'})
        assert subject == 'Hello Test'
        assert 'Hello Test' in html

    def test_renders_context_variables(self):
        template = EmailTemplateFactory(
            subject='Order {{ order_id }}',
            mjml_body=SIMPLE_MJML,
        )
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>body</html>'):
            subject, _ = render_template(template, {'order_id': '42'})
        assert '42' in subject


@pytest.mark.django_db
class TestSendEmailFromTemplate:
    def test_success_creates_email_log(self, email_template):
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>body</html>'), \
             patch('django.core.mail.send_mail') as mock_send:
            result = send_email_from_template(email_template, 'recipient@example.com', {})

        assert result is True
        mock_send.assert_called_once()
        log = EmailLog.objects.get(template=email_template)
        assert log.status == 'success'
        assert log.recipient == 'recipient@example.com'

    def test_failure_creates_failed_log(self, email_template):
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>body</html>'), \
             patch('django.core.mail.send_mail', side_effect=Exception('SMTP error')):
            result = send_email_from_template(email_template, 'fail@example.com', {})

        assert result is False
        log = EmailLog.objects.get(template=email_template)
        assert log.status == 'failed'
        assert 'SMTP error' in log.error

    def test_context_stored_in_log(self, email_template):
        ctx = {'project_name': 'MyProject', 'status': 'active'}
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>body</html>'), \
             patch('django.core.mail.send_mail'):
            send_email_from_template(email_template, 'ctx@example.com', ctx)

        log = EmailLog.objects.get(template=email_template)
        assert log.context_data == ctx


@pytest.mark.django_db
class TestSendProjectActionEmail:
    def test_sends_when_active_action_exists(self):
        action = ProjectEmailActionFactory(action_key='created', is_active=True)
        with patch('apps.email_templates.services.compile_mjml', return_value='<html>body</html>'), \
             patch('django.core.mail.send_mail'):
            result = send_project_action_email(action.project, 'created', 'x@example.com', {})
        assert result is True

    def test_returns_false_when_no_action_configured(self, project):
        result = send_project_action_email(project, 'created', 'x@example.com', {})
        assert result is False

    def test_returns_false_when_action_inactive(self):
        action = ProjectEmailActionFactory(action_key='updated', is_active=False)
        result = send_project_action_email(action.project, 'updated', 'x@example.com', {})
        assert result is False

    def test_returns_false_when_template_is_null(self):
        action = ProjectEmailActionFactory(action_key='deleted', template=None, is_active=True)
        result = send_project_action_email(action.project, 'deleted', 'x@example.com', {})
        assert result is False

    def test_different_project_same_action_not_triggered(self):
        action = ProjectEmailActionFactory(action_key='created', is_active=True)
        other_project = ExternalProjectFactory(name='OtherProject')
        result = send_project_action_email(other_project, 'created', 'x@example.com', {})
        assert result is False
