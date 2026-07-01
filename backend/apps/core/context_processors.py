def user_permissions(request):
    """Expose the current user's module-permission map to all templates.

    Used by the sidebar to show navigation items only to users who may view
    the corresponding module. Returns an empty map for anonymous users.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'user_permissions': {}}

    from apps.roles.services import get_user_permissions_map
    return {'user_permissions': get_user_permissions_map(user)}
