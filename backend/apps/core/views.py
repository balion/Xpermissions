from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = self._get_stats()
        context['recent_logs'] = self._get_recent_logs()
        return context

    def _get_stats(self):
        from apps.accounts.models import User
        from apps.roles.models import Role
        from apps.projects.models import ExternalProject

        return {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(status='active').count(),
            'locked_users': User.objects.filter(status='locked').count(),
            'pending_users': User.objects.filter(status='pending').count(),
            'total_roles': Role.objects.count(),
            'total_projects': ExternalProject.objects.count(),
        }

    def _get_recent_logs(self):
        from apps.audit.models import AuditLog
        return AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
