import json

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from support_requests.analysis import AnalysisFailureCode, AnalysisProviderFailure, AssistedAnalysis
from support_requests.models import (
    ANALYSIS_SUMMARY_MAX_LENGTH,
    SUGGESTED_RESPONSE_MAX_LENGTH,
    SupportRequestCategory,
    SupportRequestPriority,
)


class OpenRouterAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=ANALYSIS_SUMMARY_MAX_LENGTH)
    category: SupportRequestCategory
    priority: SupportRequestPriority
    suggested_response: str = Field(min_length=1, max_length=SUGGESTED_RESPONSE_MAX_LENGTH)


class OpenRouterAnalysisProvider:
    def __init__(self, *, api_key, model, client=None):
        self.api_key = api_key
        self.model = model
        self.client = client

    def analyze(self, support_request):
        if not self.api_key:
            raise AnalysisProviderFailure(AnalysisFailureCode.MISSING_KEY)
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
            raise AnalysisProviderFailure(AnalysisFailureCode.TIMEOUT) from error
        except APIConnectionError as error:
            raise AnalysisProviderFailure(AnalysisFailureCode.PROVIDER_UNAVAILABLE) from error
        except APIStatusError as error:
            status_mapping = {
                402: AnalysisFailureCode.QUOTA_UNAVAILABLE,
                403: AnalysisFailureCode.REFUSED,
                408: AnalysisFailureCode.TIMEOUT,
                429: AnalysisFailureCode.QUOTA_UNAVAILABLE,
            }
            code = status_mapping.get(error.status_code, AnalysisFailureCode.PROVIDER_UNAVAILABLE)
            raise AnalysisProviderFailure(code) from error

        try:
            content = response.choices[0].message.content
            if not content:
                raise AnalysisProviderFailure(AnalysisFailureCode.REFUSED)
            payload = OpenRouterAnalysisPayload.model_validate(json.loads(content))
            provider_model = response.model
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else None
            output_tokens = usage.completion_tokens if usage else None
        except AnalysisProviderFailure:
            raise
        except (
            AttributeError,
            IndexError,
            json.JSONDecodeError,
            ValidationError,
            TypeError,
        ) as error:
            raise AnalysisProviderFailure(AnalysisFailureCode.INVALID_RESPONSE) from error
        return AssistedAnalysis(
            summary=payload.summary,
            category=payload.category,
            priority=payload.priority,
            suggested_response=payload.suggested_response,
            provider_model=provider_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
