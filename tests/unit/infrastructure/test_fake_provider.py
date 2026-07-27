"""Tests for the deterministic fake LLM provider."""

from __future__ import annotations

from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.infrastructure.providers.fake import FakeLLMProvider, approx_tokens


def _req(text: str = "hello world") -> ProviderRequest:
    return ProviderRequest(model_id="fake-x", messages=[LLMMessage.user(text)])


async def test_generate_is_deterministic() -> None:
    provider = FakeLLMProvider()
    a = await provider.generate(_req("hello"))
    b = await provider.generate(_req("hello"))
    assert a.text == b.text
    assert a.provider is ProviderName.FAKE
    assert a.model_id == "fake-x"
    assert a.usage.input_tokens >= 0


async def test_stream_reassembles_to_generate_text() -> None:
    provider = FakeLLMProvider()
    full = (await provider.generate(_req("alpha beta gamma"))).text
    chunks = [c async for c in provider.stream(_req("alpha beta gamma"))]
    streamed = "".join(c.delta for c in chunks)
    assert streamed == full
    assert chunks[-1].done is True
    assert chunks[-1].usage is not None


async def test_embed_returns_normalised_vectors() -> None:
    provider = FakeLLMProvider(embedding_dimensions=8)
    results = await provider.embed("fake-embed", ["a", "b"])
    assert len(results) == 2
    assert all(len(r.vector) == 8 for r in results)
    # deterministic
    again = await provider.embed("fake-embed", ["a"])
    assert again[0].vector == results[0].vector


def test_count_tokens_and_approx() -> None:
    assert approx_tokens("") == 0
    assert approx_tokens("abcd") >= 1
    assert FakeLLMProvider().count_tokens("m", "abcdefgh") == 2
