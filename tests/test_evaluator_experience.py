import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
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
