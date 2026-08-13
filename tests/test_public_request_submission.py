import pytest
from django.urls import reverse

from support_requests.models import SupportRequest


@pytest.mark.django_db
def test_requester_can_submit_a_request_and_receive_only_a_protocol(client):
    response = client.post(
        reverse("support_requests:submit"),
        data={
            "requester_name": "Ana Silva",
            "requester_email": "ana@example.com",
            "subject": "Não consigo acessar minha conta",
            "message": "A recuperação de senha não envia o e-mail.",
        },
        follow=True,
    )

    support_request = SupportRequest.objects.get()
    content = response.content.decode()

    assert response.status_code == 200
    assert "Solicitação recebida" in content
    assert str(support_request.protocol) in content
    assert support_request.stage == SupportRequest.Stage.RECEIVED
    for private_value in (
        support_request.requester_name,
        support_request.requester_email,
        support_request.subject,
        support_request.message,
    ):
        assert private_value not in content

    assert response.redirect_chain[-1][0] == reverse("support_requests:submitted")


@pytest.mark.django_db
def test_requester_sees_clear_errors_for_invalid_form_data(client):
    response = client.post(
        reverse("support_requests:submit"),
        data={
            "requester_name": "Ana Silva",
            "requester_email": "email-invalido",
            "subject": "",
            "message": "",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Corrija os erros abaixo" in content
    assert "Insira um endereço de email válido" in content
    assert content.count("Este campo é obrigatório") >= 2


@pytest.mark.django_db
def test_confirmation_without_a_recent_submission_returns_not_found(client):
    response = client.get(reverse("support_requests:submitted"))

    assert response.status_code == 404
