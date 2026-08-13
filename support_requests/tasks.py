from time import perf_counter

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from support_requests.analysis import AnalysisProviderFailure, get_analysis_provider
from support_requests.models import AnalysisAttempt, AnalysisRun, SupportRequest


@shared_task
def analyze_support_request(support_request_id):
    with transaction.atomic():
        support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
        if support_request.stage != SupportRequest.Stage.RECEIVED:
            return
        support_request.stage = SupportRequest.Stage.ANALYZING
        support_request.save(update_fields=["stage"])

    started_at = perf_counter()
    provider = get_analysis_provider()
    try:
        analysis = provider.analyze(support_request)
    except AnalysisProviderFailure as failure:
        duration_ms = round((perf_counter() - started_at) * 1000)
        with transaction.atomic():
            support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
            if support_request.stage != SupportRequest.Stage.ANALYZING:
                return
            AnalysisAttempt.objects.record_failure(
                support_request,
                failure.sanitized_message,
                duration_ms,
                provider_model=getattr(provider, "model", ""),
            )
            support_request.stage = SupportRequest.Stage.ANALYSIS_FAILED
            support_request.save(update_fields=["stage"])
        return

    duration_ms = round((perf_counter() - started_at) * 1000)

    with transaction.atomic():
        support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
        if support_request.stage != SupportRequest.Stage.ANALYZING:
            return
        AnalysisAttempt.objects.record_for(support_request, analysis, duration_ms)
        support_request.stage = SupportRequest.Stage.AWAITING_REVIEW
        support_request.save(update_fields=["stage"])


@shared_task
def retry_support_request_analysis(analysis_run_id):
    with transaction.atomic():
        run = (
            AnalysisRun.objects.select_for_update()
            .select_related("support_request")
            .get(pk=analysis_run_id)
        )
        if run.status != AnalysisRun.Status.PENDING:
            return
        support_request = SupportRequest.objects.select_for_update().get(pk=run.support_request_id)
        if support_request.stage not in {
            SupportRequest.Stage.AWAITING_REVIEW,
            SupportRequest.Stage.ANALYSIS_FAILED,
        }:
            run.status = AnalysisRun.Status.SKIPPED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            return
        run.status = AnalysisRun.Status.PROCESSING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])
        support_request.stage = SupportRequest.Stage.ANALYZING
        support_request.save(update_fields=["stage"])

    started_at = perf_counter()
    provider = get_analysis_provider()
    try:
        analysis = provider.analyze(support_request)
    except AnalysisProviderFailure as failure:
        duration_ms = round((perf_counter() - started_at) * 1000)
        with transaction.atomic():
            run = AnalysisRun.objects.select_for_update().get(pk=analysis_run_id)
            if run.status != AnalysisRun.Status.PROCESSING:
                return
            support_request = SupportRequest.objects.select_for_update().get(
                pk=run.support_request_id
            )
            if support_request.stage != SupportRequest.Stage.ANALYZING:
                run.status = AnalysisRun.Status.SKIPPED
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "completed_at"])
                return
            attempt = AnalysisAttempt.objects.record_failure(
                support_request,
                failure.sanitized_message,
                duration_ms,
                provider_model=getattr(provider, "model", ""),
            )
            run.status = AnalysisRun.Status.COMPLETED
            run.attempt = attempt
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "attempt", "completed_at"])
            support_request.stage = SupportRequest.Stage.ANALYSIS_FAILED
            support_request.save(update_fields=["stage"])
        return

    duration_ms = round((perf_counter() - started_at) * 1000)
    with transaction.atomic():
        run = AnalysisRun.objects.select_for_update().get(pk=analysis_run_id)
        if run.status != AnalysisRun.Status.PROCESSING:
            return
        support_request = SupportRequest.objects.select_for_update().get(pk=run.support_request_id)
        if support_request.stage != SupportRequest.Stage.ANALYZING:
            run.status = AnalysisRun.Status.SKIPPED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            return
        attempt = AnalysisAttempt.objects.record_for(support_request, analysis, duration_ms)
        run.status = AnalysisRun.Status.COMPLETED
        run.attempt = attempt
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "attempt", "completed_at"])
        support_request.stage = SupportRequest.Stage.AWAITING_REVIEW
        support_request.save(update_fields=["stage"])
