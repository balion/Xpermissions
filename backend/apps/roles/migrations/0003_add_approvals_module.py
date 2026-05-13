from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0002_alter_modulepermission_module_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modulepermission',
            name='module',
            field=models.CharField(
                choices=[
                    ('users', 'User Management'),
                    ('roles', 'Roles & Permissions'),
                    ('audit', 'Audit Log'),
                    ('projects', 'External Projects'),
                    ('email_templates', 'Email Templates'),
                    ('approvals', 'Approval Workflows'),
                    ('settings', 'System Settings'),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='userpermissionoverride',
            name='module',
            field=models.CharField(
                choices=[
                    ('users', 'User Management'),
                    ('roles', 'Roles & Permissions'),
                    ('audit', 'Audit Log'),
                    ('projects', 'External Projects'),
                    ('email_templates', 'Email Templates'),
                    ('approvals', 'Approval Workflows'),
                    ('settings', 'System Settings'),
                ],
                max_length=50,
            ),
        ),
    ]
