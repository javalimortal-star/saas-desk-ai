import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_requester_can_submit_a_request_and_receive_only_a_protocol(client):
    response = client.post(
        reverse("requests:submit"),
        data={
            "requester_name": "Ana Silva",
            "requester_email": "ana@example.com",
            "subject": "Não consigo acessar minha conta",
            "message": "A recuperação de senha não envia o e-mail.",
        },
        follow=True,
    )

    assert response.status_code == 200
    assert "Solicitação recebida" in response.content.decode()
    assert "ana@example.com" not in response.content.decode()
    assert "A recuperação de senha" not in response.content.decode()


@pytest.mark.django_db
def test_requester_sees_clear_errors_for_invalid_form_data(client):
    response = client.post(
        reverse("requests:submit"),
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
