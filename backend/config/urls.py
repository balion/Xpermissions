from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('admin/', admin.site.urls),

    path('saml2/', include('djangosaml2.urls')),

    path('accounts/', include('apps.accounts.urls')),
    path('dashboard/', include('apps.core.urls')),
    path('users/', include('apps.accounts.user_urls')),
    path('roles/', include('apps.roles.urls')),
    path('audit/', include('apps.audit.urls')),
    path('projects/', include('apps.projects.urls')),
    path('email-templates/', include('apps.email_templates.urls')),

    path('api/', include('api.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
