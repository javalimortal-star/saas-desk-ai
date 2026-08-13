from time import perf_counter

from celery import shared_task
from django.db import transaction

from support_requests.analysis import AnalysisProviderFailure, get_analysis_provider
from support_requests.models import AnalysisAttempt, SupportRequest


@shared_task
def analyze_support_request(support_request_id):
    with transaction.atomic():
        support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
        if support_request.stage != SupportRequest.Stage.RECEIVED:
            return
        support_request.stage = SupportRequest.Stage.ANALYZING
        support_request.save(update_fields=["stage"])

    started_at = perf_counter()
    try:
        analysis = get_analysis_provider().analyze(support_request)
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
