from django.apps import AppConfig


class EmailTemplatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.email_templates'
    label = 'email_templates'

    def ready(self):
        import apps.email_templates.signals  # noqa: F401, pylint: disable=unused-import
