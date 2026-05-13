import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('config', models.JSONField()),
                ('version', models.PositiveIntegerField(default=1)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_workflow_templates',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField()),
                ('config_snapshot', models.JSONField()),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('in_progress', 'In Progress'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('cancelled', 'Cancelled'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('current_step_order', models.PositiveIntegerField(default=1)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
                ('started_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='started_workflows',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('workflow_template', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='instances',
                    to='approvals.workflowtemplate',
                )),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['content_type', 'object_id'], name='approvals_w_content_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['status'], name='approvals_w_status_idx'),
        ),
        migrations.CreateModel(
            name='WorkflowStepInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('step_key', models.CharField(max_length=100)),
                ('step_order', models.PositiveIntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('waiting', 'Waiting'),
                        ('pending', 'Pending'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('changes_requested', 'Changes Requested'),
                        ('skipped', 'Skipped'),
                    ],
                    db_index=True,
                    default='waiting',
                    max_length=20,
                )),
                ('deadline_at', models.DateTimeField(blank=True, null=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('workflow_instance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='steps',
                    to='approvals.workflowinstance',
                )),
            ],
            options={
                'ordering': ['step_order'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='workflowstepinstance',
            unique_together={('workflow_instance', 'step_key')},
        ),
        migrations.CreateModel(
            name='ApprovalDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('approve', 'Approve'),
                        ('reject', 'Reject'),
                        ('request_changes', 'Request Changes'),
                    ],
                    max_length=20,
                )),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('step_instance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='decisions',
                    to='approvals.workflowstepinstance',
                )),
                ('user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='approval_decisions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowNotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(max_length=50)),
                ('email_sent_at', models.DateTimeField(auto_now_add=True)),
                ('email_subject', models.CharField(max_length=500)),
                ('email_template_used', models.CharField(max_length=200)),
                ('workflow_instance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_logs',
                    to='approvals.workflowinstance',
                )),
                ('step_instance', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notification_logs',
                    to='approvals.workflowstepinstance',
                )),
                ('recipient', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='workflow_notification_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-email_sent_at'],
            },
        ),
    ]
