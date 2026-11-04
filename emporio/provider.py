"""Responses API adapter, isolated so orchestration tests need no paid calls."""

from dataclasses import dataclass, field
from typing import Protocol

from openai import APIError, OpenAI

from emporio.config import Settings

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "kind": {
            "type": "string",
            "enum": ["store_answer", "clarification", "out_of_scope", "greeting"],
        },
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "kind", "evidence_ids"],
    "additionalProperties": False,
}


@dataclass
class ModelResponse:
    output: list[dict] = field(default_factory=list)
    text: str = ""


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def respond(
        self, instructions: str, messages: list[dict], tools: list[dict]
    ) -> ModelResponse: ...


class OpenAIProvider:
    def __init__(self, settings: Settings, client=None):
        if not settings.api_key:
            raise ProviderError("Configure OPENAI_API_KEY or choose AGENT_MODE=demo")
        self.model = settings.model
        self.client = client or OpenAI(api_key=settings.api_key, timeout=30.0, max_retries=1)

    def respond(self, instructions: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=messages,
                tools=tools,
                parallel_tool_calls=False,
                store=False,
                max_output_tokens=1600,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "customer_reply",
                        "schema": FINAL_SCHEMA,
                        "strict": True,
                    }
                },
            )
        except APIError as exc:
            raise ProviderError(
                "Model service unavailable; check API access, billing and model"
            ) from exc
        if response.status != "completed":
            raise ProviderError("Model response did not complete")
        return ModelResponse(
            output=[item.model_dump(exclude_none=True) for item in response.output],
            text=response.output_text,
        )
