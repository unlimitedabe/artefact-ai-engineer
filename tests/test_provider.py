import json

import httpx
import pytest
from openai import OpenAI

from emporio.config import Settings
from emporio.provider import OpenAIProvider, ProviderError
from emporio.tools import tool_definitions


def test_responses_sdk_serialization_without_network():
    seen = []

    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        assert request.url.path == "/v1/responses"
        return httpx.Response(
            200,
            json={
                "id": "resp_mock",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-4.1-mini",
                "output": [
                    {
                        "type": "function_call",
                        "id": "fc_mock",
                        "status": "completed",
                        "call_id": "c1",
                        "name": "get_product_details",
                        "arguments": '{"product_id":91}',
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="test-not-a-real-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    provider = OpenAIProvider(Settings(api_key="test-not-a-real-key"), client=client)
    response = provider.respond(
        "Instructions", [{"role": "user", "content": "Preço?"}], tool_definitions()
    )
    assert response.output[0]["name"] == "get_product_details"
    assert seen[0]["store"] is False and seen[0]["parallel_tool_calls"] is False
    assert seen[0]["text"]["format"]["strict"] is True
    for tool in seen[0]["tools"]:
        assert tool["strict"] is True
        assert set(tool["parameters"]["properties"]) == set(tool["parameters"]["required"])
        assert tool["parameters"]["additionalProperties"] is False


def test_missing_key_is_explicit():
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIProvider(Settings(api_key=""))


def test_api_failure_is_safe():
    client = OpenAI(
        api_key="test-not-a-real-key",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    401,
                    json={"error": {"message": "private detail", "type": "authentication_error"}},
                )
            )
        ),
    )
    with pytest.raises(ProviderError, match="Model service unavailable"):
        OpenAIProvider(Settings(api_key="test-key"), client).respond("", [], [])
