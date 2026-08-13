from uuid import uuid4

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from support_requests.analysis import (
    AnalysisFailureCode,
    AnalysisProviderFailure,
    AssistedAnalysis,
)
from support_requests.models import AnalysisAttempt, AnalysisRun, SupportRequest
from support_requests.tasks import retry_support_request_analysis
import support_requests.tasks as analysis_tasks


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
        subject="Acesso bloqueado",
        message="Não consigo entrar.",
        stage=SupportRequest.Stage.ANALYSIS_FAILED,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["html", "api"])
@pytest.mark.parametrize(
    "initial_stage",
    [SupportRequest.Stage.AWAITING_REVIEW, SupportRequest.Stage.ANALYSIS_FAILED],
)
def test_analyst_requests_a_new_analysis_with_a_persistent_idempotency_key(
    client, analyst, support_request, monkeypatch, surface, initial_stage
):
    support_request.stage = initial_stage
    support_request.save(update_fields=["stage"])
    scheduled_run_ids = []
    monkeypatch.setattr(
        retry_support_request_analysis, "delay_on_commit", scheduled_run_ids.append
    )
    client.force_login(analyst)
    idempotency_key = uuid4()
    url_name = (
        "support_requests:analyst-retry-analysis"
        if surface == "html"
        else "support_requests:analyst-api-retry-analysis"
    )

    request_options = {"content_type": "application/json"} if surface == "api" else {}
    response = client.post(
        reverse(url_name, kwargs={"pk": support_request.pk}),
        {"idempotency_key": str(idempotency_key)},
        **request_options,
    )

    assert response.status_code == (302 if surface == "html" else 202)
    run = AnalysisRun.objects.get(support_request=support_request)
    assert run.idempotency_key == idempotency_key
    assert run.status == AnalysisRun.Status.PENDING
    assert scheduled_run_ids == [run.pk]


@pytest.mark.django_db
def test_same_idempotency_key_schedules_only_once(client, analyst, support_request, monkeypatch):
    scheduled_run_ids = []
    monkeypatch.setattr(
        retry_support_request_analysis, "delay_on_commit", scheduled_run_ids.append
    )
    client.force_login(analyst)
    url = reverse(
        "support_requests:analyst-api-retry-analysis", kwargs={"pk": support_request.pk}
    )
    data = {"idempotency_key": str(uuid4())}

    first = client.post(url, data, content_type="application/json")
    second = client.post(url, data, content_type="application/json")

    assert first.status_code == second.status_code == 202
    assert first.json()["idempotency_key"] == second.json()["idempotency_key"]
    assert AnalysisRun.objects.count() == 1
    assert scheduled_run_ids == [AnalysisRun.objects.get().pk]


@pytest.mark.django_db
def test_task_redelivery_calls_provider_and_records_attempt_only_once(
    support_request, monkeypatch
):
    class CountingProvider:
        calls = 0
        model = "test/model"

        def analyze(self, request):
            self.calls += 1
            return AssistedAnalysis(
                summary="Nova análise.",
                category=SupportRequest.Category.ACCESS,
                priority=SupportRequest.Priority.HIGH,
                suggested_response="Nova resposta sugerida.",
                provider_model="test/model",
                input_tokens=21,
                output_tokens=8,
            )

    provider = CountingProvider()
    monkeypatch.setattr(analysis_tasks, "get_analysis_provider", lambda: provider)
    run = AnalysisRun.objects.create(support_request=support_request)

    retry_support_request_analysis.run(run.pk)
    retry_support_request_analysis.run(run.pk)

    support_request.refresh_from_db()
    run.refresh_from_db()
    attempt = AnalysisAttempt.objects.get(support_request=support_request)
    assert provider.calls == 1
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW
    assert run.status == AnalysisRun.Status.COMPLETED
    assert run.attempt == attempt
    assert attempt.provider_model == "test/model"
    assert attempt.duration_ms is not None
    assert attempt.input_tokens == 21
    assert attempt.output_tokens == 8


@pytest.mark.django_db
def test_failed_retry_records_only_a_sanitized_error(support_request, monkeypatch):
    class FailingProvider:
        model = "test/requested-model"

        def analyze(self, request):
            raise AnalysisProviderFailure(AnalysisFailureCode.QUOTA_UNAVAILABLE)

    monkeypatch.setattr(
        analysis_tasks, "get_analysis_provider", lambda: FailingProvider()
    )
    run = AnalysisRun.objects.create(support_request=support_request)

    retry_support_request_analysis.run(run.pk)

    support_request.refresh_from_db()
    run.refresh_from_db()
    attempt = AnalysisAttempt.objects.get(support_request=support_request)
    assert support_request.stage == SupportRequest.Stage.ANALYSIS_FAILED
    assert run.attempt == attempt
    assert attempt.outcome == AnalysisAttempt.Outcome.FAILED
    assert attempt.sanitized_error == "Cota do provedor indisponível."
    assert attempt.duration_ms is not None
    assert attempt.provider_model == "test/requested-model"
    assert attempt.input_tokens is None
    assert attempt.output_tokens is None


@pytest.mark.django_db
def test_queued_retry_does_not_overwrite_a_human_resolution(support_request, monkeypatch):
    provider_calls = []
    monkeypatch.setattr(
        analysis_tasks,
        "get_analysis_provider",
        lambda: type(
            "Provider",
            (),
            {"analyze": lambda self, request: provider_calls.append(request.pk)},
        )(),
    )
    run = AnalysisRun.objects.create(support_request=support_request)
    support_request.stage = SupportRequest.Stage.RESOLVED
    support_request.final_category = SupportRequest.Category.ACCESS
    support_request.final_priority = SupportRequest.Priority.NORMAL
    support_request.approved_response = "Concluído pelo Analista."
    support_request.resolved_at = timezone.now()
    support_request.save()

    retry_support_request_analysis.run(run.pk)

    support_request.refresh_from_db()
    run.refresh_from_db()
    assert provider_calls == []
    assert run.status == AnalysisRun.Status.SKIPPED
    assert run.attempt is None
    assert support_request.stage == SupportRequest.Stage.RESOLVED


@pytest.mark.django_db
@pytest.mark.parametrize("provider_fails", [False, True])
def test_provider_result_does_not_overwrite_a_concurrent_resolution(
    support_request, monkeypatch, provider_fails
):
    class ResolvingProvider:
        model = "test/model"

        def analyze(self, request):
            SupportRequest.objects.filter(pk=request.pk).update(
                stage=SupportRequest.Stage.RESOLVED,
                final_category=SupportRequest.Category.OTHER,
                final_priority=SupportRequest.Priority.NORMAL,
                approved_response="Resolvida por outra operação.",
                resolved_at=timezone.now(),
            )
            if provider_fails:
                raise AnalysisProviderFailure(AnalysisFailureCode.TIMEOUT)
            return AssistedAnalysis(
                summary="Resultado tardio.",
                category=SupportRequest.Category.ACCESS,
                priority=SupportRequest.Priority.HIGH,
                suggested_response="Não deve ser persistida.",
            )

    monkeypatch.setattr(
        analysis_tasks, "get_analysis_provider", lambda: ResolvingProvider()
    )
    run = AnalysisRun.objects.create(support_request=support_request)

    retry_support_request_analysis.run(run.pk)

    support_request.refresh_from_db()
    run.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.RESOLVED
    assert support_request.approved_response == "Resolvida por outra operação."
    assert run.status == AnalysisRun.Status.SKIPPED
    assert run.attempt is None
    assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db
def test_retry_history_remains_visible_in_chronological_order(
    client, analyst, support_request
):
    first = AnalysisAttempt.objects.create(
        support_request=support_request,
        outcome=AnalysisAttempt.Outcome.FAILED,
        sanitized_error="Provedor indisponível.",
    )
    second = AnalysisAttempt.objects.create(
        support_request=support_request,
        outcome=AnalysisAttempt.Outcome.SUCCEEDED,
        summary="Análise concluída.",
        recommended_category=SupportRequest.Category.ACCESS,
        recommended_priority=SupportRequest.Priority.NORMAL,
        suggested_response="Resposta sugerida.",
        provider_model="test/model",
    )
    client.force_login(analyst)

    response = client.get(
        reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index(first.sanitized_error) < content.index(second.summary)

    api_response = client.get(
        reverse("support_requests:analyst-api-detail", kwargs={"pk": support_request.pk})
    )
    attempts = api_response.json()["analysis_attempts"]
    assert [attempt["id"] for attempt in attempts] == [first.pk, second.pk]
    assert attempts[0]["sanitized_error"] == first.sanitized_error
    assert attempts[1]["provider_model"] == second.provider_model


@pytest.mark.django_db
def test_retry_frequency_is_limited_but_idempotent_replay_is_allowed(
    client, analyst, support_request, monkeypatch
):
    monkeypatch.setattr(retry_support_request_analysis, "delay_on_commit", lambda run_id: None)
    client.force_login(analyst)
    url = reverse(
        "support_requests:analyst-api-retry-analysis", kwargs={"pk": support_request.pk}
    )
    first_key = str(uuid4())

    assert client.post(
        url, {"idempotency_key": first_key}, content_type="application/json"
    ).status_code == 202
    limited = client.post(
        url, {"idempotency_key": str(uuid4())}, content_type="application/json"
    )
    replay = client.post(
        url, {"idempotency_key": first_key}, content_type="application/json"
    )

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert replay.status_code == 202
    assert AnalysisRun.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stage", [SupportRequest.Stage.RECEIVED, SupportRequest.Stage.ANALYZING, SupportRequest.Stage.RESOLVED]
)
def test_retry_rejects_disallowed_stages(client, analyst, support_request, stage):
    if stage == SupportRequest.Stage.RESOLVED:
        support_request.final_category = SupportRequest.Category.ACCESS
        support_request.final_priority = SupportRequest.Priority.NORMAL
        support_request.approved_response = "Concluído."
        support_request.resolved_at = timezone.now()
    support_request.stage = stage
    support_request.save()
    client.force_login(analyst)

    response = client.post(
        reverse(
            "support_requests:analyst-api-retry-analysis", kwargs={"pk": support_request.pk}
        ),
        {"idempotency_key": str(uuid4())},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert AnalysisRun.objects.count() == 0
