"""Tests for the OpenAI-compatible provider using httpx.MockTransport (offline)."""

from __future__ import annotations

import httpx
import pytest

from complianceiq.domain.exceptions import ProviderError
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.infrastructure.providers.openai_compatible import OpenAICompatibleProvider


def _provider(handler) -> OpenAICompatibleProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test.local")
    return OpenAICompatibleProvider(base_url="http://test.local", api_key="k", client=client)


async def test_generate_maps_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    provider = _provider(handler)
    result = await provider.generate(
        ProviderRequest(model_id="gpt", messages=[LLMMessage.user("hi")])
    )
    assert result.text == "hello"
    assert result.usage.input_tokens == 5
    assert result.usage.output_tokens == 3


async def test_embed_maps_and_orders_by_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
                "usage": {"prompt_tokens": 4},
            },
        )

    provider = _provider(handler)
    results = await provider.embed("embed", ["first", "second"])
    assert len(results) == 2
    # sorted by index → first result is index 0
    assert results[0].vector == [0.1, 0.2]


async def test_http_error_is_translated_to_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = _provider(handler)
    with pytest.raises(ProviderError):
        await provider.generate(ProviderRequest(model_id="gpt", messages=[LLMMessage.user("hi")]))


async def test_stream_parses_sse_and_reassembles() -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    provider = _provider(handler)
    chunks = [
        c
        async for c in provider.stream(
            ProviderRequest(model_id="gpt", messages=[LLMMessage.user("hi")])
        )
    ]
    assert "".join(c.delta for c in chunks) == "Hello"
    assert chunks[-1].done is True
    assert chunks[-1].usage is not None
