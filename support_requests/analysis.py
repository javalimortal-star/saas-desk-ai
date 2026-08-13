from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from support_requests.models import (
    ANALYSIS_SUMMARY_MAX_LENGTH,
    SUGGESTED_RESPONSE_MAX_LENGTH,
    SupportRequest,
)


class AnalysisFailureCode(StrEnum):
    MISSING_KEY = "missing_key"
    QUOTA_UNAVAILABLE = "quota_unavailable"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"

    @property
    def sanitized_message(self):
        return {
            self.MISSING_KEY: "Chave da OpenRouter não configurada.",
            self.QUOTA_UNAVAILABLE: "Cota do provedor indisponível.",
            self.TIMEOUT: "O provedor excedeu o tempo limite.",
            self.REFUSED: "O provedor recusou a análise.",
            self.PROVIDER_UNAVAILABLE: "Provedor de análise indisponível.",
            self.INVALID_RESPONSE: "O provedor retornou uma análise inválida.",
        }[self]


class AnalysisProviderFailure(Exception):
    def __init__(self, code):
        if not isinstance(code, AnalysisFailureCode):
            raise TypeError("code deve ser AnalysisFailureCode")
        self.code = code
        super().__init__(code.sanitized_message)

    @property
    def sanitized_message(self):
        return self.code.sanitized_message


@dataclass(frozen=True)
class AssistedAnalysis:
    summary: str
    category: str
    priority: str
    suggested_response: str
    provider_model: str = "fake/deterministic"
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self):
        if not self.summary.strip():
            raise ValueError("Resumo inválido")
        if len(self.summary) > ANALYSIS_SUMMARY_MAX_LENGTH:
            raise ValueError("Resumo excede o limite permitido")
        if self.category not in SupportRequest.Category.values:
            raise ValueError("Categoria inválida")
        if self.priority not in SupportRequest.Priority.values:
            raise ValueError("Prioridade inválida")
        if not self.suggested_response.strip():
            raise ValueError("Resposta sugerida inválida")
        if len(self.suggested_response) > SUGGESTED_RESPONSE_MAX_LENGTH:
            raise ValueError("Resposta sugerida excede o limite permitido")


class AnalysisProvider(Protocol):
    model: str

    def analyze(self, support_request: SupportRequest) -> AssistedAnalysis: ...


class FakeAnalysisProvider:
    model = "fake/deterministic"

    def analyze(self, support_request: SupportRequest) -> AssistedAnalysis:
        return AssistedAnalysis(
            summary="Solicitante relata dificuldade de acesso à conta.",
            category=SupportRequest.Category.ACCESS,
            priority=SupportRequest.Priority.NORMAL,
            suggested_response=(
                f"Olá, {support_request.requester_name}. "
                "Vamos ajudar você a recuperar o acesso à sua conta."
            ),
        )


def get_analysis_provider() -> AnalysisProvider:
    if settings.ANALYSIS_PROVIDER == "fake":
        return FakeAnalysisProvider()
    if settings.ANALYSIS_PROVIDER == "openrouter":
        from support_requests.openrouter import OpenRouterAnalysisProvider

        return OpenRouterAnalysisProvider(
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.OPENROUTER_MODEL,
        )
    raise ImproperlyConfigured("ANALYSIS_PROVIDER deve ser 'fake' ou 'openrouter'.")
