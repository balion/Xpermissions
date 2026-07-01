import json

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.approvals.engine import WorkflowEngine
from apps.approvals.forms import WorkflowTemplateForm
from apps.approvals.models import (
    STEP_STATUS_PENDING,
    WorkflowStepInstance,
    WorkflowTemplate,
)
from apps.core.mixins import ModulePermissionMixin
from apps.projects.models import ExternalProject

MODULE = 'approvals'


def _pending_steps_for_user(user):
    """Return [{step, instance, content_object, url}] the user may decide on."""
    steps = (
        WorkflowStepInstance.objects
        .filter(status=STEP_STATUS_PENDING)
        .select_related(
            'workflow_instance__content_type',
            'workflow_instance__workflow_template',
        )
    )
    result = []
    for step in steps:
        instance = step.workflow_instance
        if not WorkflowEngine(instance).can_decide(step, user):
            continue
        content_object = instance.content_object
        url = None
        if isinstance(content_object, ExternalProject):
            url = reverse(
                'projects:workflow_instance',
                kwargs={'pk': content_object.pk, 'instance_pk': instance.pk},
            )
        result.append({
            'step': step,
            'instance': instance,
            'content_object': content_object,
            'url': url,
        })
    return result


class ApprovalsOverviewView(ModulePermissionMixin, TemplateView):
    """Landing page: projects with approval config, my pending steps, templates."""

    template_name = 'approvals/overview.html'
    module_name = MODULE
    required_action = 'view'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = (
            ExternalProject.objects
            .select_related('approval_config__workflow_template')
            .order_by('name')
        )
        context['pending_steps'] = _pending_steps_for_user(self.request.user)
        context['templates'] = WorkflowTemplate.objects.order_by('name')
        return context


class WorkflowTemplateListView(ModulePermissionMixin, ListView):
    model = WorkflowTemplate
    template_name = 'approvals/template_list.html'
    context_object_name = 'templates'
    paginate_by = 25
    module_name = MODULE
    required_action = 'view'

    def get_queryset(self):
        return WorkflowTemplate.objects.select_related('created_by').order_by('name')


class WorkflowTemplateDetailView(ModulePermissionMixin, DetailView):
    model = WorkflowTemplate
    template_name = 'approvals/template_detail.html'
    context_object_name = 'template'
    module_name = MODULE
    required_action = 'view'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['config_pretty'] = json.dumps(self.object.config, indent=2, ensure_ascii=False)
        return context


class WorkflowTemplateCreateView(ModulePermissionMixin, CreateView):
    model = WorkflowTemplate
    form_class = WorkflowTemplateForm
    template_name = 'approvals/template_form.html'
    success_url = reverse_lazy('approvals:template_list')
    module_name = MODULE
    required_action = 'create'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'New Workflow Template'
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Workflow template created.')
        return super().form_valid(form)


class WorkflowTemplateUpdateView(ModulePermissionMixin, UpdateView):
    model = WorkflowTemplate
    form_class = WorkflowTemplateForm
    template_name = 'approvals/template_form.html'
    module_name = MODULE
    required_action = 'edit'

    def get_success_url(self):
        return reverse('approvals:template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Template: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Workflow template updated.')
        return super().form_valid(form)


class WorkflowTemplateDeleteView(ModulePermissionMixin, DeleteView):
    model = WorkflowTemplate
    template_name = 'approvals/template_confirm_delete.html'
    success_url = reverse_lazy('approvals:template_list')
    module_name = MODULE
    required_action = 'delete'

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'Cannot delete: this template is used by existing workflows.',
            )
            return redirect('approvals:template_list')
        messages.success(self.request, 'Workflow template deleted.')
        return response
