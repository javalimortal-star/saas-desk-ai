import json
from typing import Literal

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from support_requests.analysis import AnalysisProviderFailure, AssistedAnalysis
from support_requests.models import (
    ANALYSIS_SUMMARY_MAX_LENGTH,
    SUGGESTED_RESPONSE_MAX_LENGTH,
    SupportRequest,
)


class OpenRouterAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=ANALYSIS_SUMMARY_MAX_LENGTH)
    category: Literal["access", "billing", "technical_problem", "feature_question", "other"]
    priority: Literal["low", "normal", "high"]
    suggested_response: str = Field(min_length=1, max_length=SUGGESTED_RESPONSE_MAX_LENGTH)


class OpenRouterAnalysisProvider:
    def __init__(self, *, api_key, model, client=None):
        self.api_key = api_key
        self.model = model
        self.client = client

    def analyze(self, support_request):
        if not self.api_key:
            raise AnalysisProviderFailure("missing_key")
        if self.client is None:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                max_retries=0,
            )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Analise a solicitação de atendimento. Produza somente os campos "
                            "definidos pelo esquema e não invente informações."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Assunto: {support_request.subject}\n"
                            f"Mensagem: {support_request.message}"
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "assisted_analysis",
                        "strict": True,
                        "schema": OpenRouterAnalysisPayload.model_json_schema(),
                    },
                },
                extra_body={"provider": {"require_parameters": True}},
            )
        except APITimeoutError as error:
            raise AnalysisProviderFailure("timeout") from error
        except APIConnectionError as error:
            raise AnalysisProviderFailure("provider_unavailable") from error
        except APIStatusError as error:
            status_mapping = {
                402: "quota_unavailable",
                403: "refused",
                408: "timeout",
                429: "quota_unavailable",
            }
            code = status_mapping.get(error.status_code, "provider_unavailable")
            raise AnalysisProviderFailure(code) from error

        content = response.choices[0].message.content
        if not content:
            raise AnalysisProviderFailure("refused")
        try:
            payload = OpenRouterAnalysisPayload.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise AnalysisProviderFailure("invalid_response") from error
        usage = response.usage
        return AssistedAnalysis(
            summary=payload.summary,
            category=payload.category,
            priority=payload.priority,
            suggested_response=payload.suggested_response,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
