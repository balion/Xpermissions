import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import ModulePermissionMixin
from apps.email_templates.forms import EmailTemplateForm, TestSendForm
from apps.email_templates.models import EmailLog, EmailTemplate
from apps.email_templates.services import preview_template, send_email_from_template


class EmailTemplateListView(ModulePermissionMixin, ListView):
    model = EmailTemplate
    template_name = 'email_templates/list.html'
    context_object_name = 'templates'
    paginate_by = 25
    module_name = 'email_templates'
    required_action = 'view'


class EmailTemplateDetailView(ModulePermissionMixin, DetailView):
    model = EmailTemplate
    template_name = 'email_templates/detail.html'
    context_object_name = 'template'
    module_name = 'email_templates'
    required_action = 'view'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_logs'] = self.object.logs.order_by('-sent_at')[:20]
        context['test_form'] = TestSendForm()
        return context


class EmailTemplateCreateView(ModulePermissionMixin, CreateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'email_templates/form.html'
    success_url = reverse_lazy('email_templates:list')
    module_name = 'email_templates'
    required_action = 'create'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Email Template'
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Template created.')
        return super().form_valid(form)


class EmailTemplateUpdateView(ModulePermissionMixin, UpdateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'email_templates/form.html'
    module_name = 'email_templates'
    required_action = 'edit'

    def get_success_url(self):
        return reverse_lazy('email_templates:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Template updated.')
        return super().form_valid(form)


class EmailTemplateDeleteView(ModulePermissionMixin, DeleteView):
    model = EmailTemplate
    template_name = 'email_templates/confirm_delete.html'
    success_url = reverse_lazy('email_templates:list')
    module_name = 'email_templates'
    required_action = 'delete'

    def form_valid(self, form):
        messages.success(self.request, 'Template deleted.')
        return super().form_valid(form)


class EmailTemplatePreviewView(ModulePermissionMixin, View):
    """AJAX endpoint — returns compiled HTML for a given MJML body."""
    module_name = 'email_templates'
    required_action = 'view'

    def post(self, request, pk=None):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        try:
            mjml_source = body.get('mjml_body', '')
            if pk:
                template = get_object_or_404(EmailTemplate, pk=pk)
                mjml_source = mjml_source or template.mjml_body
            html = preview_template(EmailTemplate(mjml_body=mjml_source, subject=''))
            return JsonResponse({'html': html})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)


class EmailTemplateTestSendView(ModulePermissionMixin, View):
    """Send a test email to an address provided via POST."""
    module_name = 'email_templates'
    required_action = 'edit'

    def post(self, request, pk):
        template = get_object_or_404(EmailTemplate, pk=pk)
        form = TestSendForm(request.POST)
        if form.is_valid():
            ok = send_email_from_template(
                template,
                form.cleaned_data['recipient'],
                {'user': request.user},
            )
            if ok:
                messages.success(request, f"Test email sent to {form.cleaned_data['recipient']}.")
            else:
                messages.error(request, 'Failed to send test email. Check Email Log for details.')
        else:
            messages.error(request, 'Invalid email address.')
        return redirect('email_templates:detail', pk=pk)


class EmailLogListView(ModulePermissionMixin, ListView):
    model = EmailLog
    template_name = 'email_templates/log.html'
    context_object_name = 'logs'
    paginate_by = 50
    module_name = 'email_templates'
    required_action = 'view'

    def get_queryset(self):
        qs = super().get_queryset().select_related('template')
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        return context
