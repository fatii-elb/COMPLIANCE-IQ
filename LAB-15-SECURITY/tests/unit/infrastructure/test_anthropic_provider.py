"""Tests for the Anthropic adapter using a stub client (offline)."""

from __future__ import annotations

from typing import Any

import pytest

from complianceiq.domain.exceptions import ProviderError
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.infrastructure.providers.anthropic_provider import AnthropicProvider


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    def __init__(self) -> None:
        self.content = [_Block("Hello from Claude.")]
        self.usage = _Usage(12, 7)
        self.stop_reason = "end_turn"


class _Messages:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _Response:
        self.last_kwargs = kwargs
        if self._fail:
            raise RuntimeError("upstream 529")
        return _Response()


class _Client:
    def __init__(self, fail: bool = False) -> None:
        self.messages = _Messages(fail=fail)


async def test_generate_maps_response_and_splits_system() -> None:
    client = _Client()
    provider = AnthropicProvider(client=client)
    result = await provider.generate(
        ProviderRequest(
            model_id="claude-x",
            messages=[LLMMessage.system("be helpful"), LLMMessage.user("hi")],
        )
    )
    assert result.text == "Hello from Claude."
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 7
    # system prompt is passed separately, not as a message turn
    assert client.messages.last_kwargs is not None
    assert client.messages.last_kwargs["system"] == "be helpful"
    assert client.messages.last_kwargs["messages"] == [{"role": "user", "content": "hi"}]


async def test_upstream_error_becomes_provider_error() -> None:
    provider = AnthropicProvider(client=_Client(fail=True))
    with pytest.raises(ProviderError):
        await provider.generate(
            ProviderRequest(model_id="claude-x", messages=[LLMMessage.user("hi")])
        )


async def test_embeddings_unsupported() -> None:
    provider = AnthropicProvider(client=_Client())
    with pytest.raises(ProviderError):
        await provider.embed("claude-x", ["text"])


def test_missing_key_and_client_raises_on_use() -> None:
    provider = AnthropicProvider()  # no key, no client
    with pytest.raises(ProviderError):
        provider._get_client()
