"""Apply on_deadline policies to pending steps whose deadline has passed.

Run periodically (cron / systemd timer / Celery beat):

    python manage.py process_workflow_deadlines
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.approvals.engine import WorkflowEngine
from apps.approvals.models import STEP_STATUS_PENDING, WorkflowStepInstance


class Command(BaseCommand):
    help = 'Apply on_deadline policies to pending workflow steps whose deadline has passed.'

    def handle(self, *args, **options):
        overdue = (
            WorkflowStepInstance.objects
            .filter(
                status=STEP_STATUS_PENDING,
                deadline_handled=False,
                deadline_at__lt=timezone.now(),
            )
            .select_related('workflow_instance')
        )
        handled = 0
        for step in overdue:
            WorkflowEngine(step.workflow_instance).handle_deadline(step)
            handled += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {handled} overdue step(s).'))
