from django import forms

from apps.roles.models import MODULE_CHOICES, ModulePermission, ProjectPermission, Role, UserPermissionOverride


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description', 'is_superadmin']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_superadmin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ModulePermissionForm(forms.ModelForm):
    class Meta:
        model = ModulePermission
        fields = ['module', 'can_view', 'can_create', 'can_edit', 'can_delete']
        widgets = {
            'module': forms.Select(attrs={'class': 'form-select'}),
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RolePermissionsForm(forms.Form):
    """Bulk form for setting all module + project permissions on a role at once."""

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self._setup_module_fields(role)
        self._setup_project_fields(role)

    def _setup_module_fields(self, role):
        existing = {p.module: p for p in role.module_permissions.all()} if role else {}
        for module_key, _ in MODULE_CHOICES:
            perm = existing.get(module_key)
            for action in ('view', 'create', 'edit', 'delete'):
                initial = getattr(perm, f'can_{action}', False) if perm else False
                self.fields[f'{module_key}_{action}'] = forms.BooleanField(
                    required=False,
                    initial=initial,
                    widget=forms.CheckboxInput(attrs={'class': 'perm-cb'}),
                )

    def _setup_project_fields(self, role):
        from apps.projects.models import ExternalProject
        existing = {}
        if role:
            existing = {pp.project_id: pp for pp in role.project_permissions.select_related('project').all()}
        self._projects = list(ExternalProject.objects.order_by('name'))
        for project in self._projects:
            perm = existing.get(project.pk)
            for action in ('view', 'create', 'edit', 'delete'):
                initial = getattr(perm, f'can_{action}', False) if perm else False
                self.fields[f'proj_{project.pk}_{action}'] = forms.BooleanField(
                    required=False,
                    initial=initial,
                    widget=forms.CheckboxInput(attrs={'class': 'perm-cb'}),
                )

    def save(self):
        for module_key, _ in MODULE_CHOICES:
            defaults = {
                f'can_{action}': self.cleaned_data.get(f'{module_key}_{action}', False)
                for action in ('view', 'create', 'edit', 'delete')
            }
            ModulePermission.objects.update_or_create(
                role=self.role, module=module_key, defaults=defaults
            )
        for project in self._projects:
            defaults = {
                f'can_{action}': self.cleaned_data.get(f'proj_{project.pk}_{action}', False)
                for action in ('view', 'create', 'edit', 'delete')
            }
            ProjectPermission.objects.update_or_create(
                role=self.role, project=project, defaults=defaults
            )


def _null_bool_widget():
    return forms.Select(
        choices=[('', '—'), ('true', 'Yes'), ('false', 'No')],
        attrs={'class': 'form-select form-select-sm'},
    )


class UserPermissionOverrideForm(forms.ModelForm):
    class Meta:
        model = UserPermissionOverride
        fields = ['module', 'can_view', 'can_create', 'can_edit', 'can_delete']
        widgets = {
            'module': forms.Select(attrs={'class': 'form-select'}),
            'can_view': _null_bool_widget(),
            'can_create': _null_bool_widget(),
            'can_edit': _null_bool_widget(),
            'can_delete': _null_bool_widget(),
        }
