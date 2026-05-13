from django.contrib import admin

from apps.projects.models import ExternalProject


@admin.register(ExternalProject)
class ExternalProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'url', 'created_by', 'created_at']
    list_filter = ['status']
    search_fields = ['name', 'url']
