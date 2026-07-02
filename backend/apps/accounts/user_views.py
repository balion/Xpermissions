from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from apps.accounts.forms import UserUpdateForm
from apps.accounts.models import STATUS_PENDING, User
from apps.core.mixins import ModulePermissionMixin


class UserListView(ModulePermissionMixin, ListView):
    model = User
    template_name = 'users/list.html'
    context_object_name = 'users'
    paginate_by = 25
    module_name = 'users'
    required_action = 'view'

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().prefetch_related('roles')
        query = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        if query:
            qs = qs.filter(
                Q(email__icontains=query)
                | Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class UserDetailView(ModulePermissionMixin, DetailView):
    model = User
    template_name = 'users/detail.html'
    context_object_name = 'user_obj'
    module_name = 'users'
    required_action = 'view'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('roles')


class UserUpdateView(ModulePermissionMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'users/form.html'
    module_name = 'users'
    required_action = 'edit'

    def get_success_url(self):
        return reverse_lazy('users:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit User: {self.object.display_name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'User updated successfully.')
        return super().form_valid(form)


class UserDeleteView(ModulePermissionMixin, DeleteView):
    model = User
    template_name = 'users/confirm_delete.html'
    success_url = reverse_lazy('users:list')
    module_name = 'users'
    required_action = 'delete'

    def form_valid(self, form):
        messages.success(self.request, 'User deleted.')
        return super().form_valid(form)


class LDAPImportView(ModulePermissionMixin, View):
    template_name = 'users/ldap_import.html'
    module_name = 'users'
    required_action = 'create'

    def get(self, request):
        return render(request, self.template_name, self._ctx())

    def post(self, request):
        action = request.POST.get('action', 'search')
        if action == 'search':
            return self._handle_search(request)
        return self._handle_import(request)

    def _ctx(self, **extra):
        from apps.roles.models import Role
        return {'roles': Role.objects.order_by('name'), 'results': [], 'query': '', **extra}

    def _handle_search(self, request):
        from apps.accounts.ldap_utils import search_ldap_users
        query = request.POST.get('q', '').strip()
        error = None
        results = []
        if query:
            try:
                results = search_ldap_users(query)
            except Exception as exc:
                error = str(exc)
        return render(request, self.template_name, self._ctx(query=query, results=results, error=error))

    def _handle_import(self, request):
        from apps.roles.models import Role
        selected = request.POST.getlist('selected')
        role_ids = request.POST.getlist('roles')
        roles = Role.objects.filter(pk__in=role_ids)
        imported = skipped = 0

        for email in selected:
            email = email.strip().lower()
            if not email:
                continue
            if User.objects.filter(email=email).exists():
                skipped += 1
                continue
            first_name = request.POST.get(f'fn_{email}', '')
            last_name = request.POST.get(f'ln_{email}', '')
            user = User(
                email=email,
                username=self._unique_username(email),
                first_name=first_name,
                last_name=last_name,
                status=STATUS_PENDING,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
            if roles:
                user.roles.set(roles)
            imported += 1

        if skipped:
            messages.warning(request, f'Skipped {skipped} user(s) that already exist.')
        messages.success(request, f'Imported {imported} user(s). They will activate on first SSO login.')
        return redirect('users:list')

    def _unique_username(self, email: str) -> str:
        base = email.split('@')[0]
        username = base
        n = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{n}'
            n += 1
        return username
