import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from support_requests.models import AnalysisAttempt, SupportRequest


@pytest.fixture
def analyst(django_user_model):
    user = django_user_model.objects.create_user(username="analyst", password="password")
    user.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))
    return user


def create_request(*, subject, stage, category=None, priority=None, final=False):
    from django.utils import timezone

    request = SupportRequest.objects.create(
        requester_name="Pessoa Fictícia",
        requester_email=f"{subject}@example.com",
        subject=subject,
        message="Mensagem fictícia.",
        stage=stage,
        final_category=category if final else "",
        final_priority=priority if final else "",
        approved_response="Resposta aprovada." if final else "",
        resolved_at=timezone.now() if final else None,
    )
    if final:
        return request
    elif category:
        AnalysisAttempt.objects.create(
            support_request=request,
            outcome=AnalysisAttempt.Outcome.SUCCEEDED,
            summary="Resumo.",
            recommended_category=category,
            recommended_priority=priority,
            suggested_response="Resposta sugerida.",
            provider_model="test/model",
        )
    return request


@pytest.fixture
def dashboard_requests():
    assisted = create_request(
        subject="assisted",
        stage=SupportRequest.Stage.AWAITING_REVIEW,
        category=SupportRequest.Category.ACCESS,
        priority=SupportRequest.Priority.HIGH,
    )
    resolved = create_request(
        subject="resolved",
        stage=SupportRequest.Stage.RESOLVED,
        category=SupportRequest.Category.BILLING,
        priority=SupportRequest.Priority.LOW,
        final=True,
    )
    AnalysisAttempt.objects.create(
        support_request=resolved,
        outcome=AnalysisAttempt.Outcome.SUCCEEDED,
        summary="Recomendação anterior à decisão humana.",
        recommended_category=SupportRequest.Category.ACCESS,
        recommended_priority=SupportRequest.Priority.HIGH,
        suggested_response="Resposta anterior.",
        provider_model="test/model",
    )
    unclassified = create_request(
        subject="received", stage=SupportRequest.Stage.RECEIVED
    )
    return assisted, resolved, unclassified


@pytest.mark.django_db
def test_dashboard_shows_stage_totals_and_effective_distributions(
    client, analyst, dashboard_requests
):
    client.force_login(analyst)
    response = client.get(reverse("support_requests:analyst-list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["stage_totals"] == {
        SupportRequest.Stage.RECEIVED: 1,
        SupportRequest.Stage.ANALYZING: 0,
        SupportRequest.Stage.AWAITING_REVIEW: 1,
        SupportRequest.Stage.ANALYSIS_FAILED: 0,
        SupportRequest.Stage.RESOLVED: 1,
    }
    assert response.context["category_totals"] == {"access": 1, "billing": 1}
    assert response.context["priority_totals"] == {"high": 1, "low": 1}
    assert "Nenhuma classificação disponível" not in content


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["html", "api"])
def test_dashboard_filters_can_be_combined_and_use_final_values(
    client, analyst, dashboard_requests, surface
):
    client.force_login(analyst)
    url_name = (
        "support_requests:analyst-list"
        if surface == "html"
        else "support_requests:analyst-api-list"
    )
    response = client.get(
        reverse(url_name),
        {
            "stage": SupportRequest.Stage.RESOLVED,
            "category": SupportRequest.Category.BILLING,
            "priority": SupportRequest.Priority.LOW,
        },
    )

    assert response.status_code == 200
    if surface == "html":
        assert [item.subject for item in response.context["support_requests"]] == [
            "resolved"
        ]
        assert response.context["filter_form"].cleaned_data == {
            "stage": SupportRequest.Stage.RESOLVED,
            "category": SupportRequest.Category.BILLING,
            "priority": SupportRequest.Priority.LOW,
        }
    else:
        assert [item["subject"] for item in response.json()] == ["resolved"]


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["html", "api"])
def test_dashboard_rejects_invalid_filter_values(client, analyst, dashboard_requests, surface):
    client.force_login(analyst)
    url_name = (
        "support_requests:analyst-list"
        if surface == "html"
        else "support_requests:analyst-api-list"
    )
    response = client.get(reverse(url_name), {"stage": "deleted", "priority": "urgent"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_dashboard_empty_filter_state_is_clear(client, analyst, dashboard_requests):
    client.force_login(analyst)
    response = client.get(
        reverse("support_requests:analyst-list"),
        {"category": SupportRequest.Category.FEATURE_QUESTION},
    )

    assert response.status_code == 200
    assert "Nenhuma Solicitação corresponde aos filtros" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_and_filtered_api_remain_private(client):
    params = {"stage": SupportRequest.Stage.RECEIVED}
    html = client.get(reverse("support_requests:analyst-list"), params)
    api = client.get(reverse("support_requests:analyst-api-list"), params)

    assert html.status_code == 302
    assert api.status_code == 403
