from django.urls import path

from apps.approvals import views

app_name = 'approvals'

urlpatterns = [
    path('', views.ApprovalsOverviewView.as_view(), name='overview'),
    path('templates/', views.WorkflowTemplateListView.as_view(), name='template_list'),
    path('templates/new/', views.WorkflowTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/', views.WorkflowTemplateDetailView.as_view(), name='template_detail'),
    path('templates/<int:pk>/edit/', views.WorkflowTemplateUpdateView.as_view(), name='template_update'),
    path('templates/<int:pk>/delete/', views.WorkflowTemplateDeleteView.as_view(), name='template_delete'),
]
