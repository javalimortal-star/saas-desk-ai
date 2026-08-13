from support_requests.models import SupportRequest
from support_requests.public_protection import consume_public_submission
from support_requests.tasks import analyze_support_request


def submit_support_request(*, client_ip=None, **request_data):
    if client_ip:
        consume_public_submission(client_ip)
    support_request = SupportRequest.objects.create(**request_data)
    analyze_support_request.delay_on_commit(support_request.pk)
    return support_request
