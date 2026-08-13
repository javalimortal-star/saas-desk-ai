from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from support_requests.models import (
    ANALYSIS_SUMMARY_MAX_LENGTH,
    SUGGESTED_RESPONSE_MAX_LENGTH,
    SupportRequest,
)


SANITIZED_PROVIDER_ERRORS = {
    "missing_key": "Chave da OpenRouter não configurada.",
    "quota_unavailable": "Cota do provedor indisponível.",
    "timeout": "O provedor excedeu o tempo limite.",
    "refused": "O provedor recusou a análise.",
    "provider_unavailable": "Provedor de análise indisponível.",
    "invalid_response": "O provedor retornou uma análise inválida.",
}


class AnalysisProviderFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(SANITIZED_PROVIDER_ERRORS[code])

    @property
    def sanitized_message(self):
        return SANITIZED_PROVIDER_ERRORS[self.code]


@dataclass(frozen=True)
class AssistedAnalysis:
    summary: str
    category: str
    priority: str
    suggested_response: str
    model: str = "fake/deterministic"
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
    def analyze(self, support_request: SupportRequest) -> AssistedAnalysis: ...


class FakeAnalysisProvider:
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
