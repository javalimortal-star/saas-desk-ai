from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from support_requests.models import PublicSubmissionBucket, SupportRequest


class Command(BaseCommand):
    help = "Remove dados da demonstração anteriores ao período de retenção configurado."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.DEMO_RETENTION_DAYS)
        deleted_requests, _ = SupportRequest.objects.filter(created_at__lt=cutoff).delete()
        PublicSubmissionBucket.objects.filter(window_started_at__lt=cutoff).delete()
        self.stdout.write(f"{deleted_requests} registro(s) expirado(s) removido(s).")
