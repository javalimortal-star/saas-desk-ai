from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from support_requests.models import PublicSubmissionBucket, SupportRequest


VALID_REQUEST = {
    "requester_name": "Pessoa Fictícia",
    "requester_email": "pessoa@example.com",
    "subject": "Dúvida fictícia",
    "message": "Esta é uma solicitação fictícia para a demonstração.",
}


@pytest.mark.django_db
def test_public_form_explains_demo_data_and_exposes_all_length_limits(client):
    response = client.get(reverse("support_requests:submit"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "demonstração" in content
    assert "dados fictícios" in content
    assert 'name="requester_name" maxlength="120"' in content
    assert 'name="requester_email" maxlength="254"' in content
    assert 'name="subject" maxlength="160"' in content
    assert 'name="message"' in content and 'maxlength="4000"' in content


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["form", "api"])
def test_public_surfaces_reject_values_over_the_documented_limits(client, surface):
    data = {**VALID_REQUEST, "requester_name": "x" * 121}
    url = reverse(
        "support_requests:submit" if surface == "form" else "support_requests:api-create"
    )

    request_options = {"content_type": "application/json"} if surface == "api" else {}
    response = client.post(url, data, **request_options)

    assert response.status_code == (400 if surface == "api" else 200)
    assert SupportRequest.objects.count() == 0


@pytest.mark.django_db
@override_settings(PUBLIC_SUBMISSION_LIMIT=2, PUBLIC_SUBMISSION_WINDOW_SECONDS=3600)
@pytest.mark.parametrize("surface", ["form", "api"])
def test_public_submissions_are_rate_limited_by_remote_address(client, monkeypatch, surface):
    monkeypatch.setattr(
        "support_requests.tasks.analyze_support_request.delay_on_commit", lambda request_id: None
    )
    url = reverse(
        "support_requests:submit" if surface == "form" else "support_requests:api-create"
    )
    request_options = {"content_type": "application/json"} if surface == "api" else {}

    assert client.post(url, VALID_REQUEST, REMOTE_ADDR="203.0.113.10", **request_options).status_code in (201, 302)
    assert client.post(url, VALID_REQUEST, REMOTE_ADDR="203.0.113.10", **request_options).status_code in (201, 302)
    limited = client.post(url, VALID_REQUEST, REMOTE_ADDR="203.0.113.10", **request_options)
    other_ip = client.post(url, VALID_REQUEST, REMOTE_ADDR="203.0.113.11", **request_options)

    assert limited.status_code == 429
    assert "Muitos envios" in limited.content.decode()
    assert int(limited.headers["Retry-After"]) > 0
    assert other_ip.status_code in (201, 302)
    assert PublicSubmissionBucket.objects.count() == 2
    assert not PublicSubmissionBucket.objects.filter(ip_hash__in=["203.0.113.10", "203.0.113.11"]).exists()


@pytest.mark.django_db
def test_confirmation_never_exposes_private_data_and_protocol_is_not_queryable(client, monkeypatch):
    monkeypatch.setattr(
        "support_requests.tasks.analyze_support_request.delay_on_commit", lambda request_id: None
    )
    response = client.post(reverse("support_requests:submit"), VALID_REQUEST, follow=True)
    content = response.content.decode()

    assert response.status_code == 200
    assert str(SupportRequest.objects.get().protocol) in content
    for private_value in VALID_REQUEST.values():
        assert private_value not in content
    with pytest.raises(NoReverseMatch):
        reverse("support_requests:submitted", kwargs={"protocol": SupportRequest.objects.get().protocol})


@pytest.mark.django_db
@override_settings(DEMO_RETENTION_DAYS=7)
def test_retention_command_removes_only_expired_submissions_and_is_repeatable():
    expired = SupportRequest.objects.create(**VALID_REQUEST)
    retained = SupportRequest.objects.create(
        **{**VALID_REQUEST, "requester_email": "recent@example.com"}
    )
    SupportRequest.objects.filter(pk=expired.pk).update(
        created_at=timezone.now() - timedelta(days=8)
    )

    call_command("purge_demo_data")
    call_command("purge_demo_data")

    assert not SupportRequest.objects.filter(pk=expired.pk).exists()
    assert SupportRequest.objects.filter(pk=retained.pk).exists()
