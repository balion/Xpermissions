from django import forms

from apps.email_templates.models import PROJECT_ACTION_CHOICES, EmailTemplate, ProjectEmailAction

MJML_PLACEHOLDER = """\
<mjml>
  <mj-body>
    <mj-section>
      <mj-column>
        <mj-text font-size="20px" font-weight="bold">Hello {{ user.first_name }}!</mj-text>
        <mj-text>Your content here.</mj-text>
        <mj-button background-color="#0d6efd" href="{{ action_url }}">
          Call to action
        </mj-button>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>"""


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['name', 'description', 'subject', 'mjml_body', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Welcome {{ user.first_name }}!',
            }),
            'mjml_body': forms.Textarea(attrs={
                'class': 'form-control font-monospace mjml-editor',
                'rows': 24,
                'spellcheck': 'false',
                'placeholder': MJML_PLACEHOLDER,
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TestSendForm(forms.Form):
    recipient = forms.EmailField(
        label='Send test to',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
    )


class ProjectEmailActionsForm(forms.Form):
    """Configure which template fires for each action on a specific project."""

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        existing = {
            a.action_key: a
            for a in ProjectEmailAction.objects.filter(project=project).select_related('template')
        } if project else {}
        templates_qs = EmailTemplate.objects.filter(is_active=True).order_by('name')
        for action_key, action_label in PROJECT_ACTION_CHOICES:
            action = existing.get(action_key)
            self.fields[f'{action_key}_template'] = forms.ModelChoiceField(
                queryset=templates_qs,
                required=False,
                initial=action.template if action else None,
                label=action_label,
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
                empty_label='— No template —',
            )
            self.fields[f'{action_key}_active'] = forms.BooleanField(
                required=False,
                initial=action.is_active if action else True,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            )

    def save(self):
        for action_key, _ in PROJECT_ACTION_CHOICES:
            template = self.cleaned_data.get(f'{action_key}_template')
            is_active = self.cleaned_data.get(f'{action_key}_active', True)
            if template:
                ProjectEmailAction.objects.update_or_create(
                    project=self.project,
                    action_key=action_key,
                    defaults={'template': template, 'is_active': is_active},
                )
            else:
                ProjectEmailAction.objects.filter(
                    project=self.project, action_key=action_key
                ).delete()
