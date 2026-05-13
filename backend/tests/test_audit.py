from unittest.mock import patch

import pytest

from apps.audit.models import AuditLog
from apps.audit.utils import log_auth_event, log_model_change
from tests.factories import ExternalProjectFactory, UserFactory


def _fake_request(user=None, ip='127.0.0.1'):
    class _Anon:
        is_authenticated = False

    req = type('FakeRequest', (), {
        'META': {'REMOTE_ADDR': ip, 'HTTP_USER_AGENT': 'pytest'},
        'user': user if user is not None else _Anon(),
    })()
    return req


@pytest.mark.django_db
class TestLogModelChange:
    def test_creates_audit_log(self, db):
        project = ExternalProjectFactory()
        with patch('apps.audit.utils.get_current_request', return_value=None):
            log_model_change(project, 'CREATE')

        log = AuditLog.objects.filter(action='CREATE', module='projects').first()
        assert log is not None
        assert log.object_id == str(project.pk)

    def test_stores_user_from_request(self, db):
        user = UserFactory()
        project = ExternalProjectFactory()
        req = _fake_request(user=user)
        with patch('apps.audit.utils.get_current_request', return_value=req):
            log_model_change(project, 'UPDATE')

        log = AuditLog.objects.get(action='UPDATE', module='projects')
        assert log.user == user
        assert log.ip_address == '127.0.0.1'

    def test_stores_before_after_data(self, db):
        project = ExternalProjectFactory()
        before = {'name': 'Old'}
        after = {'name': 'New'}
        with patch('apps.audit.utils.get_current_request', return_value=None):
            log_model_change(project, 'UPDATE', before=before, after=after)

        log = AuditLog.objects.get(action='UPDATE', module='projects')
        assert log.before_data == before
        assert log.after_data == after

    def test_no_exception_on_null_request(self, db):
        project = ExternalProjectFactory()
        with patch('apps.audit.utils.get_current_request', return_value=None):
            log_model_change(project, 'DELETE')

        assert AuditLog.objects.filter(action='DELETE').exists()

    def test_object_repr_truncated_to_255(self, db):
        project = ExternalProjectFactory(name='x' * 300)
        with patch('apps.audit.utils.get_current_request', return_value=None):
            log_model_change(project, 'CREATE')

        log = AuditLog.objects.filter(action='CREATE', module='projects').last()
        assert log is not None
        assert len(log.object_repr) <= 255


@pytest.mark.django_db
class TestLogAuthEvent:
    def test_login_event_created(self, db):
        user = UserFactory()
        req = _fake_request()
        log_auth_event(req, user, 'LOGIN')
        log = AuditLog.objects.get(action='LOGIN', module='accounts')
        assert log.user == user

    def test_login_failed_no_user(self, db):
        req = _fake_request()
        log_auth_event(req, None, 'LOGIN_FAILED')
        log = AuditLog.objects.get(action='LOGIN_FAILED')
        assert log.user is None

    def test_logout_event_created(self, db):
        user = UserFactory()
        req = _fake_request(user=user)
        log_auth_event(req, user, 'LOGOUT')
        assert AuditLog.objects.filter(action='LOGOUT', user=user).exists()

    def test_ip_address_stored(self, db):
        user = UserFactory()
        req = _fake_request(user=user, ip='10.0.0.1')
        log_auth_event(req, user, 'LOGIN')
        log = AuditLog.objects.get(action='LOGIN', user=user)
        assert log.ip_address == '10.0.0.1'

    def test_forwarded_ip_used(self, db):
        user = UserFactory()
        req = _fake_request(user=user)
        req.META['HTTP_X_FORWARDED_FOR'] = '1.2.3.4, 10.0.0.1'
        log_auth_event(req, user, 'LOGIN')
        log = AuditLog.objects.get(action='LOGIN', user=user)
        assert log.ip_address == '1.2.3.4'
