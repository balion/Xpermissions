from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.auth.views import LoginView, MeView, RefreshView
from api.audit.views import AuditLogViewSet
from api.email_templates.views import EmailLogViewSet, EmailTemplateViewSet
from api.projects.views import ExternalProjectViewSet
from api.roles.views import RoleViewSet, UserPermissionOverrideViewSet
from api.users.views import UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='api-users')
router.register(r'roles', RoleViewSet, basename='api-roles')
router.register(r'permissions', UserPermissionOverrideViewSet, basename='api-permissions')
router.register(r'projects', ExternalProjectViewSet, basename='api-projects')
router.register(r'audit', AuditLogViewSet, basename='api-audit')
router.register(r'email-templates', EmailTemplateViewSet, basename='api-email-templates')
router.register(r'email-log', EmailLogViewSet, basename='api-email-log')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='api-login'),
    path('auth/refresh/', RefreshView.as_view(), name='api-refresh'),
    path('auth/me/', MeView.as_view(), name='api-me'),
    path('approvals/', include('api.approvals.urls')),
    path('', include(router.urls)),
]
