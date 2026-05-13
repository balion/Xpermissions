from django.urls import path

from apps.roles import views

app_name = 'roles'

urlpatterns = [
    path('', views.RoleListView.as_view(), name='list'),
    path('new/', views.RoleCreateView.as_view(), name='create'),
    path('<int:pk>/', views.RoleDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.RoleUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.RoleDeleteView.as_view(), name='delete'),
    path('<int:pk>/permissions/', views.RolePermissionsView.as_view(), name='permissions'),
]
