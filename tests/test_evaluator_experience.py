import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from support_requests.access import is_support_request_analyst
from support_requests.models import SupportRequest


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_creates_non_admin_analyst_and_varied_queue():
    call_command("seed_demo")
    initial_ids = set(SupportRequest.objects.values_list("pk", flat=True))
    call_command("seed_demo")

    analyst = get_user_model().objects.get(username="demo-analyst")
    assert analyst.is_staff is False
    assert analyst.is_superuser is False
    assert is_support_request_analyst(analyst)
    assert set(SupportRequest.objects.values_list("pk", flat=True)) == initial_ids
    assert set(SupportRequest.objects.values_list("stage", flat=True)) == set(
        SupportRequest.Stage.values
    )
    assert set(
        SupportRequest.objects.exclude(final_category="").values_list("final_category", flat=True)
    ) | set(
        SupportRequest.objects.filter(analysis_attempts__outcome="succeeded").values_list(
            "analysis_attempts__recommended_category", flat=True
        )
    ) == set(SupportRequest.Category.values)
    assert set(
        SupportRequest.objects.exclude(final_priority="").values_list("final_priority", flat=True)
    ) | set(
        SupportRequest.objects.filter(analysis_attempts__outcome="succeeded").values_list(
            "analysis_attempts__recommended_priority", flat=True
        )
    ) == set(SupportRequest.Priority.values)


@pytest.mark.django_db
def test_seed_demo_refuses_to_take_over_an_existing_account():
    user = get_user_model().objects.create_user(
        username="demo-analyst",
        email="real-person@example.com",
        password="original-password",
        is_staff=True,
    )

    with pytest.raises(CommandError):
        call_command("seed_demo")

    user.refresh_from_db()
    assert user.is_staff is True
    assert user.check_password("original-password")
    assert not is_support_request_analyst(user)


@pytest.mark.django_db
def test_openapi_and_swagger_expose_real_contracts_and_analyst_security(client):
    schema_response = client.get(reverse("api-schema"), HTTP_ACCEPT="application/json")
    docs_response = client.get(reverse("api-docs"))

    assert schema_response.status_code == 200
    schema = schema_response.json()
    assert "/api/v1/requests/" in schema["paths"]
    assert "/api/v1/analyst/requests/" in schema["paths"]
    assert "/api/v1/analyst/requests/{id}/approve/" in schema["paths"]
    assert "/api/v1/analyst/requests/{id}/retry-analysis/" in schema["paths"]
    assert schema["paths"]["/api/v1/analyst/requests/"]["get"]["security"]
    public_responses = schema["paths"]["/api/v1/requests/"]["post"]["responses"]
    approval_responses = schema["paths"]["/api/v1/analyst/requests/{id}/approve/"]["post"][
        "responses"
    ]
    retry_responses = schema["paths"]["/api/v1/analyst/requests/{id}/retry-analysis/"]["post"][
        "responses"
    ]
    assert set(public_responses) >= {"201", "400", "429"}
    assert set(approval_responses) >= {"200", "400", "409"}
    assert set(retry_responses) >= {"202", "400", "409", "429"}
    assert "Retry-After" in public_responses["429"]["headers"]
    assert "Retry-After" in retry_responses["429"]["headers"]
    validation_schema = public_responses["400"]["content"]["application/json"]["schema"]
    invalid_response = client.post(
        reverse("support_requests:api-create"),
        {"requester_email": "invalid"},
        content_type="application/json",
    )
    assert invalid_response.status_code == 400
    assert set(invalid_response.json()) >= {
        "requester_name",
        "requester_email",
        "subject",
        "message",
    }
    assert validation_schema["type"] == "object"
    assert validation_schema["additionalProperties"]["type"] == "array"
    assert docs_response.status_code == 200
    assert "swagger" in docs_response.content.decode().lower()


def test_fake_provider_is_explicit_and_openrouter_never_falls_back_to_it(settings):
    from django.core.exceptions import ImproperlyConfigured

    from support_requests.analysis import FakeAnalysisProvider, get_analysis_provider
    from support_requests.openrouter import OpenRouterAnalysisProvider

    settings.ANALYSIS_PROVIDER = "fake"
    assert isinstance(get_analysis_provider(), FakeAnalysisProvider)
    settings.ANALYSIS_PROVIDER = "openrouter"
    assert isinstance(get_analysis_provider(), OpenRouterAnalysisProvider)
    settings.ANALYSIS_PROVIDER = "automatic"
    with pytest.raises(ImproperlyConfigured):
        get_analysis_provider()
