from django.urls import path

from apps.projects import views

app_name = 'projects'

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='list'),
    path('new/', views.ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='delete'),
    path('<int:pk>/email-actions/', views.ProjectEmailActionsView.as_view(), name='email_actions'),
    path('<int:pk>/approval/', views.ProjectApprovalView.as_view(), name='approval'),
    path('<int:pk>/approval/start/', views.ProjectWorkflowStartView.as_view(), name='workflow_start'),
    path(
        '<int:pk>/approval/instances/<int:instance_pk>/',
        views.ProjectWorkflowInstanceView.as_view(),
        name='workflow_instance',
    ),
    path(
        '<int:pk>/approval/instances/<int:instance_pk>/steps/<int:step_pk>/decide/',
        views.ProjectWorkflowDecideView.as_view(),
        name='workflow_decide',
    ),
    path(
        '<int:pk>/approval/instances/<int:instance_pk>/cancel/',
        views.ProjectWorkflowCancelView.as_view(),
        name='workflow_cancel',
    ),
    path(
        '<int:pk>/approval/instances/<int:instance_pk>/resubmit/',
        views.ProjectWorkflowResubmitView.as_view(),
        name='workflow_resubmit',
    ),
]
