from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'status', 'is_active']
    list_filter = ['status', 'roles', 'is_staff', 'is_superuser']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']
    filter_horizontal = ['roles']

    fieldsets = UserAdmin.fieldsets + (
        ('Admin Xpermisions', {'fields': ('roles', 'status')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Admin Xpermisions', {'fields': ('email', 'first_name', 'last_name', 'roles', 'status')}),
    )
