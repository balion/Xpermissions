from django.urls import path

from apps.accounts import user_views

app_name = 'users'

urlpatterns = [
    path('', user_views.UserListView.as_view(), name='list'),
    path('ldap-import/', user_views.LDAPImportView.as_view(), name='ldap_import'),
    path('<int:pk>/', user_views.UserDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', user_views.UserUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', user_views.UserDeleteView.as_view(), name='delete'),
]
