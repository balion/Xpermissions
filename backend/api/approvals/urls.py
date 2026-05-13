from django.urls import path
from rest_framework.routers import DefaultRouter

from api.approvals.views import MyPendingView, WorkflowInstanceViewSet, WorkflowTemplateViewSet

router = DefaultRouter()
router.register(r'templates', WorkflowTemplateViewSet, basename='api-workflow-templates')
router.register(r'instances', WorkflowInstanceViewSet, basename='api-workflow-instances')

urlpatterns = [
    path('my-pending/', MyPendingView.as_view(), name='api-my-pending-approvals'),
    *router.urls,
]
