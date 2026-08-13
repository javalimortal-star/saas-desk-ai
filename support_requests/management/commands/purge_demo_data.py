from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from support_requests.models import AnalysisRun, PublicSubmissionBucket, SupportRequest


class Command(BaseCommand):
    help = "Remove dados da demonstração anteriores ao período de retenção configurado."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.DEMO_RETENTION_DAYS)
        active_stages = (SupportRequest.Stage.RECEIVED, SupportRequest.Stage.ANALYZING)
        active_runs = (AnalysisRun.Status.PENDING, AnalysisRun.Status.PROCESSING)
        expired_requests = (
            SupportRequest.objects.filter(created_at__lt=cutoff)
            .exclude(stage__in=active_stages)
            .exclude(analysis_runs__status__in=active_runs)
        )
        deleted_requests, _ = expired_requests.delete()
        PublicSubmissionBucket.objects.filter(window_started_at__lt=cutoff).delete()
        self.stdout.write(f"{deleted_requests} registro(s) expirado(s) removido(s).")
