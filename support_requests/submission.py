from support_requests.models import SupportRequest
from support_requests.tasks import analyze_support_request


def submit_support_request(**request_data):
    support_request = SupportRequest.objects.create(**request_data)
    analyze_support_request.delay_on_commit(support_request.pk)
    return support_request
