import json

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.approvals.models import WorkflowTemplate
from apps.approvals.validators import validate_workflow_config

CONFIG_PLACEHOLDER = """\
{
  "workflow_name": "Project Approval",
  "callback": "mark_project_approved",
  "steps": [
    {
      "step_key": "manager_review",
      "step_order": 1,
      "approval_type": "any",
      "approvers": [
        {"type": "role", "id": 1}
      ]
    }
  ]
}"""


class WorkflowTemplateForm(forms.ModelForm):
    """Create/edit a reusable workflow template; ``config`` is edited as JSON."""

    config = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace',
            'rows': 22,
            'spellcheck': 'false',
            'placeholder': CONFIG_PLACEHOLDER,
        }),
        help_text='JSON workflow definition — workflow_name, steps[], approvers[], optional conditions.',
    )

    class Meta:
        model = WorkflowTemplate
        fields = ['name', 'description', 'config', 'version', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'version': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.config:
            self.initial['config'] = json.dumps(self.instance.config, indent=2)

    def clean_config(self):
        raw = self.cleaned_data['config']
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f'Invalid JSON: {exc}') from exc
        try:
            validate_workflow_config(parsed)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        return parsed
