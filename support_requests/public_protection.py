import hashlib
import hmac
from datetime import datetime, timedelta, timezone as datetime_timezone
from math import ceil

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from support_requests.models import PublicSubmissionBucket


class PublicSubmissionRateLimited(Exception):
    def __init__(self, retry_after_seconds):
        self.retry_after_seconds = max(1, ceil(retry_after_seconds))
        super().__init__("Muitos envios. Aguarde antes de enviar outra Solicitação.")


def _hash_ip(client_ip):
    return hmac.new(
        settings.SECRET_KEY.encode(), client_ip.encode(), hashlib.sha256
    ).hexdigest()


@transaction.atomic
def consume_public_submission(client_ip):
    window_seconds = settings.PUBLIC_SUBMISSION_WINDOW_SECONDS
    now = timezone.now()
    window_timestamp = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(window_timestamp, tz=datetime_timezone.utc)
    bucket, _ = PublicSubmissionBucket.objects.get_or_create(
        ip_hash=_hash_ip(client_ip),
        window_started_at=window_start,
    )
    bucket = PublicSubmissionBucket.objects.select_for_update().get(pk=bucket.pk)
    if bucket.submission_count >= settings.PUBLIC_SUBMISSION_LIMIT:
        window_end = window_start + timedelta(seconds=window_seconds)
        raise PublicSubmissionRateLimited((window_end - now).total_seconds())
    bucket.submission_count += 1
    bucket.save(update_fields=["submission_count"])
