from apps.roles.models import ModulePermission, ProjectPermission, UserPermissionOverride


def check_module_permission(user, module: str, action: str) -> bool:
    """
    Returns True if the user may perform `action` on `module`.
    action: 'view' | 'create' | 'edit' | 'delete'
    Grants access if ANY of the user's roles allows it (union of permissions).
    """
    if user.is_superuser:
        return True

    if user.roles.filter(is_superadmin=True).exists():
        return True

    override = UserPermissionOverride.objects.filter(user=user, module=module).first()
    if override:
        value = getattr(override, f'can_{action}', None)
        if value is not None:
            return value

    return ModulePermission.objects.filter(
        role__in=user.roles.all(),
        module=module,
        **{f'can_{action}': True},
    ).exists()


def check_project_permission(user, project, action: str) -> bool:
    """
    Returns True if the user may perform `action` on a specific project.
    Falls back to the global 'projects' module permission if no per-project
    record exists (global access covers all projects).
    """
    if user.is_superuser:
        return True
    if user.roles.filter(is_superadmin=True).exists():
        return True
    if check_module_permission(user, 'projects', action):
        return True
    return ProjectPermission.objects.filter(
        role__in=user.roles.all(),
        project=project,
        **{f'can_{action}': True},
    ).exists()


def get_accessible_projects(user):
    """Return queryset of projects the user can view."""
    from apps.projects.models import ExternalProject
    if user.is_superuser or user.roles.filter(is_superadmin=True).exists():
        return ExternalProject.objects.all()
    if check_module_permission(user, 'projects', 'view'):
        return ExternalProject.objects.all()
    accessible_ids = ProjectPermission.objects.filter(
        role__in=user.roles.all(),
        can_view=True,
    ).values_list('project_id', flat=True)
    return ExternalProject.objects.filter(pk__in=accessible_ids)


def get_user_permissions_map(user) -> dict:
    """Returns {module: {action: bool}} for all modules."""
    from apps.roles.models import MODULE_CHOICES
    actions = ('view', 'create', 'edit', 'delete')
    return {
        module: {action: check_module_permission(user, module, action) for action in actions}
        for module, _ in MODULE_CHOICES
    }
