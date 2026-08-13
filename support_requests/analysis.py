from dataclasses import dataclass
from typing import Protocol

from support_requests.models import SupportRequest


@dataclass(frozen=True)
class AssistedAnalysis:
    summary: str
    category: str
    priority: str
    suggested_response: str


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
