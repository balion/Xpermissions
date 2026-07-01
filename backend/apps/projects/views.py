import copy
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.approvals.engine import WorkflowEngine, create_workflow_instance
from apps.approvals.models import (
    INSTANCE_STATUS_IN_PROGRESS,
    STEP_STATUS_PENDING,
    ProjectApprovalConfig,
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowTemplate,
)
from apps.approvals.validators import validate_workflow_config
from apps.core.mixins import ModulePermissionMixin
from apps.email_templates.forms import ProjectEmailActionsForm
from apps.projects.forms import ExternalProjectForm
from apps.projects.models import ExternalProject
from apps.roles.services import check_project_permission, get_accessible_projects


class ProjectListView(LoginRequiredMixin, ListView):
    """
    List view accessible to any authenticated user who has at least one
    viewable project (either via module-level or per-project permission).
    The queryset is filtered to only projects they can see.
    """
    model = ExternalProject
    template_name = 'projects/list.html'
    context_object_name = 'projects'
    paginate_by = 25

    def get_queryset(self):
        qs = get_accessible_projects(self.request.user)
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()
        if status:
            qs = qs.filter(status=status)
        if query:
            qs = qs.filter(name__icontains=query)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class ProjectPermissionMixin(LoginRequiredMixin):
    """Check per-project permission after the object is resolved."""
    required_action = 'view'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not check_project_permission(self.request.user, obj, self.required_action):
            raise PermissionDenied
        return obj


class ProjectDetailView(ProjectPermissionMixin, DetailView):
    model = ExternalProject
    template_name = 'projects/detail.html'
    context_object_name = 'project'
    required_action = 'view'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email_actions'] = self.object.email_actions.select_related('template').all()
        return context


class ProjectCreateView(ModulePermissionMixin, CreateView):
    model = ExternalProject
    form_class = ExternalProjectForm
    template_name = 'projects/form.html'
    success_url = reverse_lazy('projects:list')
    module_name = 'projects'
    required_action = 'create'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Project'
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Project created successfully.')
        return super().form_valid(form)


class ProjectUpdateView(ProjectPermissionMixin, UpdateView):
    model = ExternalProject
    form_class = ExternalProjectForm
    template_name = 'projects/form.html'
    required_action = 'edit'

    def get_success_url(self):
        return reverse_lazy('projects:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Project: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Project updated successfully.')
        return super().form_valid(form)


class ProjectDeleteView(ProjectPermissionMixin, DeleteView):
    model = ExternalProject
    template_name = 'projects/confirm_delete.html'
    success_url = reverse_lazy('projects:list')
    required_action = 'delete'

    def form_valid(self, form):
        messages.success(self.request, 'Project deleted.')
        return super().form_valid(form)


class ProjectEmailActionsView(ModulePermissionMixin, View):
    """Configure email templates for each action of a project."""
    module_name = 'projects'
    required_action = 'edit'
    template_name = 'projects/email_actions.html'

    def _get_project(self, pk):
        return get_object_or_404(ExternalProject, pk=pk)

    def get(self, request, pk):
        project = self._get_project(pk)
        form = ProjectEmailActionsForm(project=project)
        return render(request, self.template_name, self._ctx(project, form))

    def post(self, request, pk):
        project = self._get_project(pk)
        form = ProjectEmailActionsForm(request.POST, project=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Email actions updated.')
            return redirect('projects:detail', pk=pk)
        return render(request, self.template_name, self._ctx(project, form))

    def _ctx(self, project, form):
        from apps.email_templates.models import PROJECT_ACTION_CHOICES
        action_rows = [
            {
                'action_key': action_key,
                'action_label': action_label,
                'template_field': form[f'{action_key}_template'],
                'active_field': form[f'{action_key}_active'],
            }
            for action_key, action_label in PROJECT_ACTION_CHOICES
        ]
        return {'project': project, 'form': form, 'action_rows': action_rows}


# ---------------------------------------------------------------------------
# Approval workflow — helpers
# ---------------------------------------------------------------------------

def _parse_custom_config(raw: str) -> tuple[dict | None, str | None]:
    """Parse and validate raw JSON string. Returns (config, error_message)."""
    if not raw:
        return None, None
    try:
        parsed = json.loads(raw)
        validate_workflow_config(parsed)
        return parsed, None
    except json.JSONDecodeError as exc:
        return None, f'Invalid JSON: {exc}'
    except ValidationError as exc:
        return None, exc.message


def _config_json_for_display(config, raw_config) -> str:
    """Return the JSON string to pre-fill the editor textarea."""
    if raw_config is not None:
        return raw_config
    if config and config.custom_config:
        return json.dumps(config.custom_config, indent=2)
    if config and config.workflow_template:
        return json.dumps(config.workflow_template.config, indent=2)
    return ''


def _pending_steps_for_user(project, user) -> list:
    """Return [{instance, step}] for all pending steps the user can approve."""
    result = []
    active = project.workflow_instances.filter(status=INSTANCE_STATUS_IN_PROGRESS)
    for inst in active:
        engine = WorkflowEngine(inst)
        for step in inst.steps.filter(status=STEP_STATUS_PENDING):
            if engine.can_decide(step, user):
                result.append({'instance': inst, 'step': step})
    return result


def _start_instance_from_custom_config(approval_config, project, user) -> WorkflowInstance:
    """Create and start a WorkflowInstance using the project's custom JSON config."""
    custom = approval_config.custom_config
    stored = approval_config.workflow_template
    if stored is None:
        stored, _ = WorkflowTemplate.objects.get_or_create(
            name=f'__custom__{project.pk}',
            defaults={'config': custom},
        )
        stored.config = custom
        stored.save(update_fields=['config'])

    ct = ContentType.objects.get_for_model(project)
    instance = WorkflowInstance.objects.create(
        workflow_template=stored,
        content_type=ct,
        object_id=project.pk,
        config_snapshot=copy.deepcopy(custom),
        started_by=user,
    )
    for step_cfg in sorted(custom.get('steps', []), key=lambda s: s['step_order']):
        WorkflowStepInstance.objects.create(
            workflow_instance=instance,
            step_key=step_cfg['step_key'],
            step_order=step_cfg['step_order'],
        )
    WorkflowEngine(instance).start()
    return instance


# ---------------------------------------------------------------------------
# Approval workflow views
# ---------------------------------------------------------------------------

def _get_project_or_403(user, pk, action='view'):
    """Fetch a project, enforcing the per-project permission for *action*."""
    project = get_object_or_404(ExternalProject, pk=pk)
    if not check_project_permission(user, project, action):
        raise PermissionDenied
    return project


class ProjectApprovalView(LoginRequiredMixin, View):
    """Approval configuration + status page for a project."""

    template_name = 'projects/approval.html'

    def get(self, request, pk):
        project = _get_project_or_403(request.user, pk, 'view')
        return render(request, self.template_name, self._ctx(request, project))

    def post(self, request, pk):
        project = _get_project_or_403(request.user, pk, 'edit')
        template_id = request.POST.get('workflow_template') or None
        raw_config = request.POST.get('custom_config', '').strip()
        is_enabled = request.POST.get('is_enabled') == 'on'

        template = get_object_or_404(WorkflowTemplate, pk=template_id) if template_id else None
        custom_config, config_error = _parse_custom_config(raw_config)

        if config_error:
            messages.error(request, config_error)
            return render(request, self.template_name, self._ctx(request, project, raw_config=raw_config))

        config, _ = ProjectApprovalConfig.objects.get_or_create(project=project)
        config.workflow_template = template
        config.custom_config = custom_config
        config.is_enabled = is_enabled
        config.save()
        messages.success(request, 'Approval configuration saved.')
        return redirect('projects:approval', pk=pk)

    def _ctx(self, request, project, raw_config=None):
        try:
            config = project.approval_config
        except ProjectApprovalConfig.DoesNotExist:
            config = None

        templates = WorkflowTemplate.objects.filter(is_active=True).order_by('name')
        instances = project.workflow_instances.select_related(
            'workflow_template', 'started_by',
        ).prefetch_related('steps').order_by('-started_at')[:10]

        return {
            'project': project,
            'approval_config': config,
            'templates': templates,
            'instances': instances,
            'pending_steps': _pending_steps_for_user(project, request.user),
            'config_json': _config_json_for_display(config, raw_config),
        }


class ProjectWorkflowStartView(LoginRequiredMixin, View):
    """POST — start a new workflow instance for a project using its approval config."""

    def post(self, request, pk):
        project = _get_project_or_403(request.user, pk, 'edit')

        try:
            approval_config = project.approval_config
        except ProjectApprovalConfig.DoesNotExist:
            messages.error(request, 'No approval configuration set for this project.')
            return redirect('projects:approval', pk=pk)

        if not approval_config.is_enabled:
            messages.error(request, 'Approval module is disabled for this project.')
            return redirect('projects:approval', pk=pk)

        if not approval_config.effective_config:
            messages.error(request, 'No workflow template or custom config configured.')
            return redirect('projects:approval', pk=pk)

        if approval_config.custom_config:
            instance = _start_instance_from_custom_config(approval_config, project, request.user)
        else:
            instance = create_workflow_instance(
                approval_config.workflow_template, project, started_by=request.user,
            )

        messages.success(request, f'Workflow "{instance.workflow_name}" started.')
        return redirect('projects:workflow_instance', pk=pk, instance_pk=instance.pk)


class ProjectWorkflowInstanceView(LoginRequiredMixin, View):
    """Detail/history view for a single WorkflowInstance of a project."""

    template_name = 'projects/workflow_instance.html'

    def get(self, request, pk, instance_pk):
        project = _get_project_or_403(request.user, pk, 'view')
        instance = get_object_or_404(
            project.workflow_instances.select_related('workflow_template', 'started_by'),
            pk=instance_pk,
        )
        steps = instance.steps.prefetch_related('decisions__user').order_by('step_order')
        engine = WorkflowEngine(instance)
        steps_ctx = [
            {
                'step': step,
                'can_decide': (
                    step.status == STEP_STATUS_PENDING
                    and engine.can_decide(step, request.user)
                ),
            }
            for step in steps
        ]
        return render(request, self.template_name, {
            'project': project,
            'instance': instance,
            'steps_ctx': steps_ctx,
        })


class ProjectWorkflowDecideView(LoginRequiredMixin, View):
    """POST — approve/reject/request_changes on a step."""

    def post(self, request, pk, instance_pk, step_pk):
        project = _get_project_or_403(request.user, pk, 'view')
        instance = get_object_or_404(project.workflow_instances, pk=instance_pk)
        step = get_object_or_404(WorkflowStepInstance, pk=step_pk, workflow_instance=instance)

        action = request.POST.get('action', '')
        comment = request.POST.get('comment', '').strip()

        engine = WorkflowEngine(instance)
        try:
            engine.decide(step, request.user, action, comment=comment)
            messages.success(request, f'Decision "{action}" recorded.')
        except PermissionError:
            messages.error(request, 'You are not an authorised approver for this step.')
        except ValueError as exc:
            messages.error(request, str(exc))

        return redirect('projects:workflow_instance', pk=pk, instance_pk=instance_pk)
