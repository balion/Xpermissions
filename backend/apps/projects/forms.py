from django import forms

from apps.projects.models import ExternalProject


class ExternalProjectForm(forms.ModelForm):
    # Django 6.0 default: bare domains become https:// (silences the
    # RemovedInDjango60Warning without the deprecated transitional setting).
    url = forms.URLField(
        required=False,
        assume_scheme='https',
        widget=forms.URLInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = ExternalProject
        fields = ['name', 'description', 'url', 'api_key', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
