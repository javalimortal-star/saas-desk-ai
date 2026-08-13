from pathlib import Path

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
def test_bootstrap_demo_preserves_existing_review_and_password():
    call_command("bootstrap_demo")
    analyst = get_user_model().objects.get(username="demo-analyst")
    analyst.set_password("evaluator-changed-password")
    analyst.save(update_fields=["password"])
    reviewed = SupportRequest.objects.get(subject="Solicitação fictícia: outro")
    reviewed.approved_response = "Decisão humana que deve ser preservada."
    reviewed.save(update_fields=["approved_response"])

    call_command("bootstrap_demo")

    analyst.refresh_from_db()
    reviewed.refresh_from_db()
    assert analyst.check_password("evaluator-changed-password")
    assert reviewed.stage == SupportRequest.Stage.RESOLVED
    assert reviewed.approved_response == "Decisão humana que deve ser preservada."


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


@pytest.mark.django_db
def test_health_check_verifies_the_database(client):
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_public_pages_expose_evaluator_links_and_limited_demo_credentials(client, settings):
    settings.DEMO_ANALYST_PASSWORD = "public-evaluator-password"
    public_page = client.get(reverse("support_requests:submit"))
    login_page = client.get(reverse("support_requests:analyst-login"))

    assert b"api/docs" in public_page.content
    assert b"javalimortal-star/saas-desk-ai" in public_page.content
    assert b"demo-analyst" in login_page.content
    assert b"public-evaluator-password" in login_page.content
    assert "não é administradora" in login_page.content.decode()


def test_render_blueprint_uses_free_eager_demo_and_keeps_api_key_secret():
    project_root = Path(__file__).parents[1]
    blueprint = (project_root / "render.yaml").read_text(encoding="utf-8")
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")

    assert "type: web" in blueprint
    assert "type: worker" not in blueprint
    assert "type: keyvalue" not in blueprint
    assert "fromDatabase:" in blueprint
    assert "dockerCommand: python -m config.render_start" in blueprint
    assert 'CELERY_TASK_ALWAYS_EAGER\n        value: "true"' in blueprint
    assert "OPENROUTER_API_KEY\n        sync: false" in blueprint
    assert 'OPENROUTER_TIMEOUT_SECONDS\n        value: "20"' in blueprint
    assert "redis:" in compose
    assert "worker:" in compose
    assert compose.count("OPENROUTER_TIMEOUT_SECONDS: ${OPENROUTER_TIMEOUT_SECONDS:-20}") == 2


def test_render_entrypoint_prepares_database_then_starts_gunicorn(monkeypatch):
    from config import render_start

    calls = []
    monkeypatch.setattr(render_start.django, "setup", lambda: calls.append(("setup",)))
    monkeypatch.setattr(
        render_start,
        "call_command",
        lambda command, **options: calls.append((command, options)),
    )
    monkeypatch.setattr(
        render_start.os,
        "execvp",
        lambda executable, arguments: calls.append(("execvp", executable, arguments)),
    )
    monkeypatch.setenv("PORT", "10000")

    render_start.main()

    assert calls == [
        ("setup",),
        ("migrate", {"interactive": False}),
        ("bootstrap_demo", {}),
        (
            "execvp",
            "gunicorn",
            [
                "gunicorn",
                "config.wsgi:application",
                "--bind",
                "0.0.0.0:10000",
                "--timeout",
                "60",
            ],
        ),
    ]
