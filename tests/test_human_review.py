import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from support_requests.models import AnalysisAttempt, SupportRequest
from support_requests.review import InvalidHumanReview, resolve_support_request
from support_requests.tasks import analyze_support_request


@pytest.fixture
def analyst(django_user_model):
    user = django_user_model.objects.create_user(username="analyst", password="password")
    user.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))
    return user


@pytest.fixture
def support_request():
    return SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
        stage=SupportRequest.Stage.AWAITING_REVIEW,
    )


@pytest.mark.django_db
def test_analyst_edits_an_assisted_analysis_and_resolves_from_the_detail(
    client, analyst, support_request
):
    attempt = AnalysisAttempt.objects.create(
        support_request=support_request,
        outcome=AnalysisAttempt.Outcome.SUCCEEDED,
        summary="Solicitante relata dificuldade de acesso.",
        recommended_category=SupportRequest.Category.ACCESS,
        recommended_priority=SupportRequest.Priority.NORMAL,
        suggested_response="Vamos ajudar a recuperar seu acesso.",
        provider_model="fake-v1",
    )
    client.force_login(analyst)
    detail_url = reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})

    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert detail_response.context["review_form"].initial == {
        "category": SupportRequest.Category.ACCESS,
        "priority": SupportRequest.Priority.NORMAL,
        "approved_response": "Vamos ajudar a recuperar seu acesso.",
    }

    response = client.post(
        reverse("support_requests:analyst-approve", kwargs={"pk": support_request.pk}),
        {
            "category": SupportRequest.Category.TECHNICAL_PROBLEM,
            "priority": SupportRequest.Priority.HIGH,
            "approved_response": "Vamos corrigir o problema técnico e avisaremos por e-mail.",
        },
    )

    assert response.status_code == 302
    assert response.url == detail_url
    support_request.refresh_from_db()
    attempt.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.RESOLVED
    assert support_request.final_category == SupportRequest.Category.TECHNICAL_PROBLEM
    assert support_request.final_priority == SupportRequest.Priority.HIGH
    assert support_request.approved_response == (
        "Vamos corrigir o problema técnico e avisaremos por e-mail."
    )
    assert support_request.resolved_at is not None
    assert attempt.recommended_category == SupportRequest.Category.ACCESS
    assert attempt.recommended_priority == SupportRequest.Priority.NORMAL
    assert attempt.suggested_response == "Vamos ajudar a recuperar seu acesso."


@pytest.mark.django_db
@pytest.mark.parametrize(
    "initial_stage",
    [SupportRequest.Stage.RECEIVED, SupportRequest.Stage.ANALYSIS_FAILED],
)
def test_api_allows_manual_treatment_without_a_successful_recommendation(
    client, analyst, support_request, initial_stage
):
    support_request.stage = initial_stage
    support_request.save(update_fields=["stage"])
    client.force_login(analyst)

    response = client.post(
        reverse("support_requests:analyst-api-approve", kwargs={"pk": support_request.pk}),
        {
            "category": SupportRequest.Category.OTHER,
            "priority": SupportRequest.Priority.LOW,
            "approved_response": "Recebemos sua solicitação e concluímos o atendimento.",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["stage"] == SupportRequest.Stage.RESOLVED
    support_request.refresh_from_db()
    assert support_request.final_category == SupportRequest.Category.OTHER
    assert support_request.final_priority == SupportRequest.Priority.LOW
    assert support_request.approved_response == (
        "Recebemos sua solicitação e concluímos o atendimento."
    )
    if initial_stage == SupportRequest.Stage.RECEIVED:
        analyze_support_request.run(support_request.pk)
        support_request.refresh_from_db()
        assert support_request.stage == SupportRequest.Stage.RESOLVED
        assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["html", "api"])
def test_resolution_requires_all_human_review_fields_and_changes_nothing(
    client, analyst, support_request, surface
):
    client.force_login(analyst)
    url_name = (
        "support_requests:analyst-approve"
        if surface == "html"
        else "support_requests:analyst-api-approve"
    )
    request_args = {}
    if surface == "api":
        request_args["content_type"] = "application/json"
    response = client.post(
        reverse(url_name, kwargs={"pk": support_request.pk}),
        {"category": "", "priority": "", "approved_response": "   "},
        **request_args,
    )

    assert response.status_code == 400
    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW
    assert support_request.final_category == ""
    assert support_request.final_priority == ""
    assert support_request.approved_response == ""
    assert support_request.resolved_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("initial_stage", "expected_status"),
    [(SupportRequest.Stage.ANALYZING, 409), (SupportRequest.Stage.RESOLVED, 409)],
)
def test_html_and_api_consistently_reject_invalid_resolution_transitions(
    client, analyst, support_request, initial_stage, expected_status
):
    support_request.stage = initial_stage
    update_fields = ["stage"]
    if initial_stage == SupportRequest.Stage.RESOLVED:
        support_request.final_category = SupportRequest.Category.ACCESS
        support_request.final_priority = SupportRequest.Priority.NORMAL
        support_request.approved_response = "Resposta já aprovada."
        support_request.resolved_at = timezone.now()
        update_fields.extend(
            ["final_category", "final_priority", "approved_response", "resolved_at"]
        )
    support_request.save(update_fields=update_fields)
    original_response = support_request.approved_response
    client.force_login(analyst)
    data = {
        "category": SupportRequest.Category.ACCESS,
        "priority": SupportRequest.Priority.NORMAL,
        "approved_response": "Resposta aprovada.",
    }

    html_response = client.post(
        reverse("support_requests:analyst-approve", kwargs={"pk": support_request.pk}), data
    )
    api_response = client.post(
        reverse("support_requests:analyst-api-approve", kwargs={"pk": support_request.pk}),
        data,
        content_type="application/json",
    )

    assert html_response.status_code == expected_status
    assert api_response.status_code == expected_status
    assert "não pode ser resolvida" in api_response.json()["detail"]
    support_request.refresh_from_db()
    assert support_request.stage == initial_stage
    assert support_request.approved_response == original_response


@pytest.mark.django_db
def test_database_rejects_a_partial_resolution(support_request):
    with pytest.raises(IntegrityError), transaction.atomic():
        SupportRequest.objects.filter(pk=support_request.pk).update(
            stage=SupportRequest.Stage.RESOLVED
        )

    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW


@pytest.mark.django_db
def test_review_endpoints_require_an_analyst(client, support_request):
    data = {
        "category": SupportRequest.Category.ACCESS,
        "priority": SupportRequest.Priority.NORMAL,
        "approved_response": "Resposta aprovada.",
    }

    html_response = client.post(
        reverse("support_requests:analyst-approve", kwargs={"pk": support_request.pk}), data
    )
    api_response = client.post(
        reverse("support_requests:analyst-api-approve", kwargs={"pk": support_request.pk}),
        data,
        content_type="application/json",
    )

    assert html_response.status_code == 302
    assert api_response.status_code == 403
    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_data",
    [
        {
            "category": "unknown",
            "priority": SupportRequest.Priority.NORMAL,
            "approved_response": "Ok",
        },
        {
            "category": SupportRequest.Category.ACCESS,
            "priority": "urgent",
            "approved_response": "Ok",
        },
        {
            "category": SupportRequest.Category.ACCESS,
            "priority": SupportRequest.Priority.NORMAL,
            "approved_response": "   ",
        },
        {
            "category": SupportRequest.Category.ACCESS,
            "priority": SupportRequest.Priority.NORMAL,
            "approved_response": "x" * 4001,
        },
    ],
)
def test_domain_operation_rejects_invalid_human_review(support_request, invalid_data):
    with pytest.raises(InvalidHumanReview):
        resolve_support_request(support_request_id=support_request.pk, **invalid_data)

    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW
    assert support_request.approved_response == ""
