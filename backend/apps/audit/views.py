from django.views.generic import DetailView, ListView

from apps.audit.models import AuditLog
from apps.core.mixins import ModulePermissionMixin


class AuditLogListView(ModulePermissionMixin, ListView):
    model = AuditLog
    template_name = 'audit/list.html'
    context_object_name = 'logs'
    paginate_by = 50
    module_name = 'audit'
    required_action = 'view'

    def get_queryset(self):
        qs = super().get_queryset().select_related('user')
        action = self.request.GET.get('action', '').strip()
        module = self.request.GET.get('module', '').strip()
        user_q = self.request.GET.get('user', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if action:
            qs = qs.filter(action=action)
        if module:
            qs = qs.filter(module=module)
        if user_q:
            qs = qs.filter(user__email__icontains=user_q)
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_choices'] = AuditLog._meta.get_field('action').choices
        context['module_list'] = (
            AuditLog.objects.values_list('module', flat=True)
            .distinct()
            .order_by('module')
        )
        context['filters'] = {
            'action': self.request.GET.get('action', ''),
            'module': self.request.GET.get('module', ''),
            'user': self.request.GET.get('user', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        return context


class AuditLogDetailView(ModulePermissionMixin, DetailView):
    model = AuditLog
    template_name = 'audit/detail.html'
    context_object_name = 'log'
    module_name = 'audit'
    required_action = 'view'
