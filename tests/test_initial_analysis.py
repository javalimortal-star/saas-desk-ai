import pytest
from threading import Event, Thread
from django.db import connections
from django.contrib.auth.models import Permission
from django.urls import reverse

from support_requests.models import AnalysisAttempt, SupportRequest
from support_requests.tasks import analyze_support_request
import support_requests.tasks as analysis_tasks
from support_requests.analysis import (
    AnalysisProviderFailure,
    AssistedAnalysis,
    FakeAnalysisProvider,
)


@pytest.mark.django_db
def test_controlled_task_produces_an_assisted_analysis_visible_to_the_analyst(
    client, django_user_model
):
    support_request = SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
    )

    analyze_support_request.run(support_request.pk)

    support_request.refresh_from_db()
    attempt = AnalysisAttempt.objects.get(support_request=support_request)
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW
    assert attempt.summary == "Solicitante relata dificuldade de acesso à conta."
    assert attempt.recommended_category == SupportRequest.Category.ACCESS
    assert attempt.recommended_priority == SupportRequest.Priority.NORMAL
    assert attempt.suggested_response == (
        "Olá, Ana Silva. Vamos ajudar você a recuperar o acesso à sua conta."
    )

    analyst = django_user_model.objects.create_user(username="analyst", password="password")
    analyst.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))
    client.force_login(analyst)
    response = client.get(
        reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Análise assistida" in content
    assert attempt.summary in content
    assert attempt.get_recommended_category_display() in content
    assert attempt.get_recommended_priority_display() in content
    assert attempt.suggested_response in content


@pytest.mark.django_db
def test_public_form_schedules_analysis_without_waiting_for_the_provider(client, monkeypatch):
    scheduled_request_ids = []
    monkeypatch.setattr(
        analyze_support_request,
        "delay_on_commit",
        scheduled_request_ids.append,
    )

    response = client.post(
        reverse("support_requests:submit"),
        data={
            "requester_name": "Ana Silva",
            "requester_email": "ana@example.com",
            "subject": "Não consigo acessar minha conta",
            "message": "A recuperação de senha não envia o e-mail.",
        },
    )

    support_request = SupportRequest.objects.get()
    assert response.status_code == 302
    assert scheduled_request_ids == [support_request.pk]
    assert support_request.stage == SupportRequest.Stage.RECEIVED
    assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db
def test_public_api_schedules_analysis_without_waiting_for_the_provider(client, monkeypatch):
    scheduled_request_ids = []
    monkeypatch.setattr(
        analyze_support_request,
        "delay_on_commit",
        scheduled_request_ids.append,
    )

    response = client.post(
        reverse("support_requests:api-create"),
        data={
            "requester_name": "Bruno Lima",
            "requester_email": "bruno@example.com",
            "subject": "Cobrança duplicada",
            "message": "Minha assinatura foi cobrada duas vezes neste mês.",
        },
        content_type="application/json",
    )

    support_request = SupportRequest.objects.get()
    assert response.status_code == 201
    assert scheduled_request_ids == [support_request.pk]
    assert support_request.stage == SupportRequest.Stage.RECEIVED
    assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db(transaction=True)
def test_analysis_moves_through_a_committed_analyzing_stage(monkeypatch):
    support_request = SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
    )
    provider_started = Event()
    allow_provider_to_finish = Event()
    task_errors = []

    class BlockingProvider:
        def analyze(self, current_request):
            provider_started.set()
            allow_provider_to_finish.wait(timeout=5)
            return FakeAnalysisProvider().analyze(current_request)

    monkeypatch.setattr(analysis_tasks, "get_analysis_provider", BlockingProvider)

    def run_task():
        try:
            analyze_support_request.run(support_request.pk)
        except Exception as error:
            task_errors.append(error)
        finally:
            connections.close_all()

    task_thread = Thread(target=run_task)
    task_thread.start()
    assert provider_started.wait(timeout=5)

    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.ANALYZING

    allow_provider_to_finish.set()
    task_thread.join(timeout=5)

    assert task_thread.is_alive() is False
    assert task_errors == []
    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.AWAITING_REVIEW


@pytest.mark.django_db
def test_invalid_assisted_analysis_is_rejected_before_it_is_recorded(monkeypatch):
    support_request = SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
    )

    class InvalidProvider:
        def analyze(self, current_request):
            return AssistedAnalysis(
                summary="Resumo",
                category="categoria_inventada",
                priority=SupportRequest.Priority.NORMAL,
                suggested_response="Resposta sugerida.",
            )

    monkeypatch.setattr(analysis_tasks, "get_analysis_provider", InvalidProvider)

    with pytest.raises(ValueError, match="Categoria inválida"):
        analyze_support_request.run(support_request.pk)

    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.ANALYZING
    assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db
def test_oversized_assisted_analysis_is_rejected_before_it_is_recorded(monkeypatch):
    support_request = SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Não consigo acessar minha conta",
        message="A recuperação de senha não envia o e-mail.",
    )

    class OversizedProvider:
        def analyze(self, current_request):
            return AssistedAnalysis(
                summary="x" * 1001,
                category=SupportRequest.Category.ACCESS,
                priority=SupportRequest.Priority.NORMAL,
                suggested_response="Resposta sugerida.",
            )

    monkeypatch.setattr(analysis_tasks, "get_analysis_provider", OversizedProvider)

    with pytest.raises(ValueError, match="Resumo excede o limite permitido"):
        analyze_support_request.run(support_request.pk)

    support_request.refresh_from_db()
    assert support_request.stage == SupportRequest.Stage.ANALYZING
    assert support_request.analysis_attempts.count() == 0


@pytest.mark.django_db
def test_provider_failure_is_sanitized_and_keeps_the_original_request(
    client, django_user_model, monkeypatch
):
    support_request = SupportRequest.objects.create(
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        subject="Cobrança duplicada",
        message="Minha assinatura foi cobrada duas vezes.",
    )

    class FailingProvider:
        def analyze(self, current_request):
            raise AnalysisProviderFailure("provider_unavailable")

    monkeypatch.setattr(analysis_tasks, "get_analysis_provider", FailingProvider)

    analyze_support_request.run(support_request.pk)

    support_request.refresh_from_db()
    attempt = support_request.analysis_attempts.get()
    assert support_request.stage == SupportRequest.Stage.ANALYSIS_FAILED
    assert support_request.message == "Minha assinatura foi cobrada duas vezes."
    assert attempt.outcome == AnalysisAttempt.Outcome.FAILED
    assert attempt.sanitized_error == "Provedor de análise indisponível."
    assert "provider_unavailable" not in attempt.sanitized_error
    assert attempt.summary is None

    analyst = django_user_model.objects.create_user(username="analyst", password="password")
    analyst.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))
    client.force_login(analyst)
    response = client.get(
        reverse("support_requests:analyst-detail", kwargs={"pk": support_request.pk})
    )

    assert attempt.sanitized_error in response.content.decode()
    assert "provider_unavailable" not in response.content.decode()
