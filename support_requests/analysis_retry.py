from math import ceil

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from support_requests.models import AnalysisRun, SupportRequest


RETRYABLE_STAGES = {
    SupportRequest.Stage.AWAITING_REVIEW,
    SupportRequest.Stage.ANALYSIS_FAILED,
}


class InvalidAnalysisRetryTransition(Exception):
    pass


class AnalysisRetryRateLimited(Exception):
    def __init__(self, retry_after_seconds):
        self.retry_after_seconds = max(1, ceil(retry_after_seconds))
        super().__init__("Aguarde antes de solicitar uma nova Tentativa de análise.")


class IdempotencyKeyConflict(Exception):
    pass


@transaction.atomic
def request_analysis_retry(*, support_request_id, idempotency_key):
    existing = AnalysisRun.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.support_request_id != support_request_id:
            raise IdempotencyKeyConflict("A chave de idempotência já está em uso.")
        return existing, False

    support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
    if support_request.stage not in RETRYABLE_STAGES:
        raise InvalidAnalysisRetryTransition(
            f'A Solicitação na etapa "{support_request.get_stage_display()}" '
            "não permite nova Tentativa de análise."
        )

    run, created = AnalysisRun.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={"support_request": support_request},
    )
    if not created:
        if run.support_request_id != support_request_id:
            raise IdempotencyKeyConflict("A chave de idempotência já está em uso.")
        return run, False

    cooldown_seconds = settings.ANALYSIS_RETRY_COOLDOWN_SECONDS
    latest_run = (
        support_request.analysis_runs.exclude(pk=run.pk).order_by("-created_at").first()
    )
    if latest_run:
        elapsed = (timezone.now() - latest_run.created_at).total_seconds()
        if elapsed < cooldown_seconds:
            raise AnalysisRetryRateLimited(cooldown_seconds - elapsed)

    from support_requests.tasks import retry_support_request_analysis

    retry_support_request_analysis.delay_on_commit(run.pk)
    return run, True
