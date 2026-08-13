import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from support_requests.models import SupportRequest


@pytest.fixture
def support_request():
    return SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
    )


@pytest.fixture
def analyst(django_user_model):
    user = django_user_model.objects.create_user(username="analyst", password="safe-test-password")
    user.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))
    return user


@pytest.mark.django_db
def test_analyst_can_log_in_view_the_queue_and_log_out(client, analyst, support_request):
    login_response = client.post(
        reverse("support_requests:analyst-login"),
        {"username": "analyst", "password": "safe-test-password"},
    )

    assert login_response.status_code == 302
    assert login_response.url == reverse("support_requests:analyst-list")

    queue_response = client.get(login_response.url)
    content = queue_response.content.decode()

    assert queue_response.status_code == 200
    assert support_request.subject in content
    assert support_request.get_stage_display() in content

    logout_response = client.post(reverse("support_requests:analyst-logout"))

    assert logout_response.status_code == 302
    assert logout_response.url == reverse("support_requests:analyst-login")
    assert client.get(reverse("support_requests:analyst-list")).status_code == 302


@pytest.mark.django_db
def test_analyst_can_open_a_request_detail(client, analyst, support_request):
    client.force_login(analyst)

    response = client.get(
        reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert support_request.requester_name in content
    assert support_request.requester_email in content
    assert support_request.subject in content
    assert support_request.message in content
    assert str(support_request.protocol) in content


@pytest.mark.django_db
def test_internal_pages_reject_visitors_and_users_without_analyst_permission(
    client, django_user_model, analyst, support_request
):
    queue_url = reverse("support_requests:analyst-list")
    detail_url = reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})

    for url in (queue_url, detail_url):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(f"{reverse('support_requests:analyst-login')}?next=")

    account_without_permission = django_user_model.objects.create_user(
        username="requester", password="safe-test-password"
    )
    client.force_login(account_without_permission)

    assert client.get(queue_url).status_code == 403
    assert client.get(detail_url).status_code == 403
    assert analyst.is_staff is False
    assert analyst.is_superuser is False


@pytest.mark.django_db
def test_analyst_can_list_and_detail_requests_through_the_api(client, analyst, support_request):
    client.force_login(analyst)

    list_response = client.get(reverse("support_requests:analyst-api-list"))
    detail_response = client.get(
        reverse("support_requests:analyst-api-detail", kwargs={"pk": support_request.pk})
    )

    assert list_response.status_code == 200
    list_payload = list_response.json()
    created_at = parse_datetime(list_payload[0].pop("created_at"))
    assert list_payload[0].pop("effective_category") is None
    assert list_payload[0].pop("effective_category_label") == "—"
    assert list_payload[0].pop("effective_priority") is None
    assert list_payload[0].pop("effective_priority_label") == "—"
    assert list_payload == [{
        "id": support_request.pk,
        "protocol": str(support_request.protocol),
        "requester_name": support_request.requester_name,
        "requester_email": support_request.requester_email,
        "subject": support_request.subject,
        "message": support_request.message,
        "stage": SupportRequest.Stage.RECEIVED,
    }]
    assert created_at == support_request.created_at
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    detail_payload.pop("created_at")
    assert detail_payload.pop("analysis_attempts") == []
    assert detail_payload == list_payload[0]


@pytest.mark.django_db
def test_internal_api_rejects_visitors_and_users_without_analyst_permission(
    client, django_user_model, support_request
):
    urls = (
        reverse("support_requests:analyst-api-list"),
        reverse("support_requests:analyst-api-detail", kwargs={"pk": support_request.pk}),
    )

    for url in urls:
        assert client.get(url).status_code == 403

    account_without_permission = django_user_model.objects.create_user(
        username="requester", password="safe-test-password"
    )
    client.force_login(account_without_permission)

    for url in urls:
        assert client.get(url).status_code == 403
