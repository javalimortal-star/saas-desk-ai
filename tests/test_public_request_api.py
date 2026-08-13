import uuid

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_requester_can_submit_a_request_through_the_api(client):
    response = client.post(
        reverse("request-api-list"),
        data={
            "requester_name": "Bruno Lima",
            "requester_email": "bruno@example.com",
            "subject": "Cobrança duplicada",
            "message": "Minha assinatura foi cobrada duas vezes neste mês.",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert set(response.json()) == {"protocol"}
    protocol = uuid.UUID(response.json()["protocol"])
    assert protocol.version == 4


@pytest.mark.django_db
def test_api_returns_clear_errors_without_echoing_invalid_data(client):
    response = client.post(
        reverse("request-api-list"),
        data={
            "requester_name": "Bruno Lima",
            "requester_email": "segredo-invalido",
            "subject": "",
            "message": "",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert set(response.json()) == {"requester_email", "subject", "message"}
    assert "segredo-invalido" not in response.content.decode()
