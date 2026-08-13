from dataclasses import dataclass
from typing import Protocol

from support_requests.models import (
    ANALYSIS_SUMMARY_MAX_LENGTH,
    SUGGESTED_RESPONSE_MAX_LENGTH,
    SupportRequest,
)


@dataclass(frozen=True)
class AssistedAnalysis:
    summary: str
    category: str
    priority: str
    suggested_response: str

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
    return FakeAnalysisProvider()
