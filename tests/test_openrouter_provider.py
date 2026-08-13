import json

import httpx2
import pytest
from django.test import override_settings
from openai import OpenAI

from support_requests.analysis import (
    AnalysisFailureCode,
    AnalysisProviderFailure,
    get_analysis_provider,
)
from support_requests.models import SupportRequest
from support_requests.openrouter import OpenRouterAnalysisProvider


def test_openrouter_provider_requests_and_validates_structured_analysis():
    captured_request = {}

    def handle_request(request):
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers["authorization"]
        captured_request["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "generation-1",
                "object": "chat.completion",
                "created": 1,
                "model": "openai/gpt-oss-20b:free",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "summary": "Solicitante relata cobrança duplicada.",
                                    "category": "billing",
                                    "priority": "high",
                                    "suggested_response": "Vamos verificar as duas cobranças.",
                                }
                            ),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
            },
        )

    client = OpenAI(
        api_key="test-key-not-secret",
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle_request)),
    )
    provider = OpenRouterAnalysisProvider(
        api_key="test-key-not-secret",
        model="openrouter/free",
        client=client,
    )
    support_request = SupportRequest(
        requester_name="Bruno Lima",
        requester_email="bruno@example.com",
        subject="Cobrança duplicada",
        message="Minha assinatura foi cobrada duas vezes neste mês.",
    )

    result = provider.analyze(support_request)

    assert result.summary == "Solicitante relata cobrança duplicada."
    assert result.category == SupportRequest.Category.BILLING
    assert result.priority == SupportRequest.Priority.HIGH
    assert result.suggested_response == "Vamos verificar as duas cobranças."
    assert result.provider_model == "openai/gpt-oss-20b:free"
    assert result.input_tokens == 120
    assert result.output_tokens == 40
    assert captured_request["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured_request["authorization"] == "Bearer test-key-not-secret"
    assert captured_request["body"]["model"] == "openrouter/free"
    assert captured_request["body"]["provider"] == {"require_parameters": True}
    response_format = captured_request["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True


def test_openrouter_provider_rejects_a_missing_key_without_network_access():
    provider = OpenRouterAnalysisProvider(api_key="", model="openrouter/free")
    support_request = SupportRequest(
        subject="Cobrança duplicada",
        message="Minha assinatura foi cobrada duas vezes.",
    )

    with pytest.raises(AnalysisProviderFailure) as failure:
        provider.analyze(support_request)

    assert failure.value.code == AnalysisFailureCode.MISSING_KEY
    assert failure.value.sanitized_message == "Chave da OpenRouter não configurada."


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (402, "quota_unavailable"),
        (408, "timeout"),
        (403, "refused"),
        (429, "quota_unavailable"),
        (503, "provider_unavailable"),
    ],
)
def test_openrouter_provider_maps_external_errors_to_sanitized_failures(status_code, expected_code):
    def handle_request(request):
        return httpx2.Response(
            status_code,
            json={"error": {"code": status_code, "message": "secret upstream diagnostic"}},
        )

    client = OpenAI(
        api_key="test-key-not-secret",
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle_request)),
    )
    provider = OpenRouterAnalysisProvider(
        api_key="test-key-not-secret", model="openrouter/free", client=client
    )
    support_request = SupportRequest(subject="Assunto", message="Mensagem")

    with pytest.raises(AnalysisProviderFailure) as failure:
        provider.analyze(support_request)

    assert failure.value.code == AnalysisFailureCode(expected_code)
    assert "secret upstream diagnostic" not in failure.value.sanitized_message


def test_openrouter_provider_rejects_invalid_structured_output():
    def handle_request(request):
        return httpx2.Response(
            200,
            json={
                "id": "generation-1",
                "object": "chat.completion",
                "created": 1,
                "model": "free/model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"summary":"Resumo","category":"invented"}',
                        },
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="test-key-not-secret",
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle_request)),
    )
    provider = OpenRouterAnalysisProvider(
        api_key="test-key-not-secret", model="openrouter/free", client=client
    )

    with pytest.raises(AnalysisProviderFailure) as failure:
        provider.analyze(SupportRequest(subject="Assunto", message="Mensagem"))

    assert failure.value.code == AnalysisFailureCode.INVALID_RESPONSE


@override_settings(
    ANALYSIS_PROVIDER="openrouter",
    OPENROUTER_API_KEY="",
    OPENROUTER_MODEL="openrouter/free",
)
def test_provider_factory_selects_openrouter_from_server_configuration():
    provider = get_analysis_provider()

    assert isinstance(provider, OpenRouterAnalysisProvider)
    assert provider.model == "openrouter/free"


def test_openrouter_provider_maps_transport_timeout():
    def handle_request(request):
        raise httpx2.ReadTimeout("secret timeout diagnostic", request=request)

    client = OpenAI(
        api_key="test-key-not-secret",
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle_request)),
    )
    provider = OpenRouterAnalysisProvider(
        api_key="test-key-not-secret", model="openrouter/free", client=client
    )

    with pytest.raises(AnalysisProviderFailure) as failure:
        provider.analyze(SupportRequest(subject="Assunto", message="Mensagem"))

    assert failure.value.code == AnalysisFailureCode.TIMEOUT
    assert "secret timeout diagnostic" not in failure.value.sanitized_message


def test_openrouter_provider_maps_a_model_refusal():
    def handle_request(request):
        return httpx2.Response(
            200,
            json={
                "id": "generation-1",
                "object": "chat.completion",
                "created": 1,
                "model": "free/model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": None, "refusal": "blocked"},
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="test-key-not-secret",
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle_request)),
    )
    provider = OpenRouterAnalysisProvider(
        api_key="test-key-not-secret", model="openrouter/free", client=client
    )

    with pytest.raises(AnalysisProviderFailure) as failure:
        provider.analyze(SupportRequest(subject="Assunto", message="Mensagem"))

    assert failure.value.code == AnalysisFailureCode.REFUSED
