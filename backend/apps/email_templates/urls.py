from django.urls import path

from apps.email_templates import views

app_name = 'email_templates'

urlpatterns = [
    path('', views.EmailTemplateListView.as_view(), name='list'),
    path('new/', views.EmailTemplateCreateView.as_view(), name='create'),
    path('<int:pk>/', views.EmailTemplateDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.EmailTemplateUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.EmailTemplateDeleteView.as_view(), name='delete'),
    path('<int:pk>/preview/', views.EmailTemplatePreviewView.as_view(), name='preview'),
    path('<int:pk>/send-test/', views.EmailTemplateTestSendView.as_view(), name='send_test'),
    path('preview/', views.EmailTemplatePreviewView.as_view(), name='preview_raw'),
    path('log/', views.EmailLogListView.as_view(), name='log'),
]
