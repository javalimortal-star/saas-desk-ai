from celery import shared_task
from django.db import transaction

from support_requests.analysis import get_analysis_provider
from support_requests.models import AnalysisAttempt, SupportRequest


@shared_task
def analyze_support_request(support_request_id):
    support_request = SupportRequest.objects.get(pk=support_request_id)
    support_request.stage = SupportRequest.Stage.ANALYZING
    support_request.save(update_fields=["stage"])

    analysis = get_analysis_provider().analyze(support_request)

    with transaction.atomic():
        support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
        AnalysisAttempt.objects.record_for(support_request, analysis)
        support_request.stage = SupportRequest.Stage.AWAITING_REVIEW
        support_request.save(update_fields=["stage"])
