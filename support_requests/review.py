from django.db import transaction
from django.utils import timezone

from support_requests.models import SupportRequest


class InvalidResolutionTransition(Exception):
    pass


RESOLVABLE_STAGES = {
    SupportRequest.Stage.RECEIVED,
    SupportRequest.Stage.AWAITING_REVIEW,
    SupportRequest.Stage.ANALYSIS_FAILED,
}


@transaction.atomic
def resolve_support_request(*, support_request_id, category, priority, approved_response):
    support_request = SupportRequest.objects.select_for_update().get(pk=support_request_id)
    if support_request.stage not in RESOLVABLE_STAGES:
        raise InvalidResolutionTransition(
            f'A Solicitação na etapa "{support_request.get_stage_display()}" não pode ser resolvida.'
        )

    support_request.final_category = category
    support_request.final_priority = priority
    support_request.approved_response = approved_response
    support_request.resolved_at = timezone.now()
    support_request.stage = SupportRequest.Stage.RESOLVED
    support_request.save(
        update_fields=(
            "final_category",
            "final_priority",
            "approved_response",
            "resolved_at",
            "stage",
        )
    )
    return support_request
