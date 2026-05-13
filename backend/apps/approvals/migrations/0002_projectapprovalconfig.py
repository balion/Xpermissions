import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approvals', '0001_initial'),
        ('projects', '0002_add_pending_approval_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectApprovalConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('custom_config', models.JSONField(
                    blank=True,
                    null=True,
                    help_text='Optional JSON config that overrides the selected template. Leave blank to use the template config as-is.',
                )),
                ('is_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='approval_config',
                    to='projects.externalproject',
                )),
                ('workflow_template', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='project_configs',
                    to='approvals.workflowtemplate',
                )),
            ],
            options={
                'ordering': ['project__name'],
            },
        ),
    ]
