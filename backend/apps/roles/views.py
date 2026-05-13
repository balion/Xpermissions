from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import ModulePermissionMixin
from apps.projects.models import ExternalProject
from apps.roles.forms import RoleForm, RolePermissionsForm
from apps.roles.models import MODULE_CHOICES, Role


class RoleListView(ModulePermissionMixin, ListView):
    template_name = 'roles/list.html'
    context_object_name = 'roles'
    paginate_by = 25
    module_name = 'roles'
    required_action = 'view'

    def get_queryset(self):
        from django.db.models import Count
        return Role.objects.annotate(user_count=Count('users')).order_by('name')


class RoleDetailView(ModulePermissionMixin, DetailView):
    model = Role
    template_name = 'roles/detail.html'
    context_object_name = 'role'
    module_name = 'roles'
    required_action = 'view'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['module_permissions'] = self.object.module_permissions.all()
        context['project_permissions'] = self.object.project_permissions.select_related('project').all()
        return context


class RoleCreateView(ModulePermissionMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'roles/form.html'
    success_url = reverse_lazy('roles:list')
    module_name = 'roles'
    required_action = 'create'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Role'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Role created successfully.')
        return super().form_valid(form)


class RoleUpdateView(ModulePermissionMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'roles/form.html'
    module_name = 'roles'
    required_action = 'edit'

    def get_success_url(self):
        return reverse_lazy('roles:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Role: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Role updated successfully.')
        return super().form_valid(form)


class RoleDeleteView(ModulePermissionMixin, DeleteView):
    model = Role
    template_name = 'roles/confirm_delete.html'
    success_url = reverse_lazy('roles:list')
    module_name = 'roles'
    required_action = 'delete'

    def form_valid(self, form):
        messages.success(self.request, 'Role deleted.')
        return super().form_valid(form)


class RolePermissionsView(ModulePermissionMixin, View):
    """Bulk-edit all module permissions for a role."""
    module_name = 'roles'
    required_action = 'edit'
    template_name = 'roles/permissions_form.html'
    ACTIONS = ('view', 'create', 'edit', 'delete')

    def get(self, request, pk):
        role = get_object_or_404(Role, pk=pk)
        form = RolePermissionsForm(role=role)
        return render(request, self.template_name, self._ctx(role, form))

    def post(self, request, pk):
        role = get_object_or_404(Role, pk=pk)
        form = RolePermissionsForm(request.POST, role=role)
        if form.is_valid():
            form.save()
            messages.success(request, 'Permissions updated.')
            return redirect('roles:detail', pk=pk)
        return render(request, self.template_name, self._ctx(role, form))

    def _ctx(self, role, form):
        table_rows = [
            {
                'module': module_key,
                'label': module_label,
                'fields': [form[f'{module_key}_{action}'] for action in self.ACTIONS],
            }
            for module_key, module_label in MODULE_CHOICES
        ]
        project_rows = [
            {
                'project': project,
                'fields': [form[f'proj_{project.pk}_{action}'] for action in self.ACTIONS],
            }
            for project in ExternalProject.objects.order_by('name')
        ]
        return {
            'role': role,
            'form': form,
            'table_rows': table_rows,
            'project_rows': project_rows,
            'actions': self.ACTIONS,
        }
