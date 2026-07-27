"""Reusable test doubles for Phase 2 (gateway & providers).

These fakes let the gateway and adapters be tested deterministically and offline:
a clock we can advance by hand, a sleeper that records instead of waiting, and a
scriptable provider that can fail a set number of times before succeeding.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

from complianceiq.domain.exceptions import ProviderError
from complianceiq.domain.llm.models import (
    ModelCapabilities,
    ModelCost,
    ModelSpec,
    ProviderName,
)
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.domain.llm.responses import (
    Completion,
    CompletionChunk,
    EmbeddingResult,
    FinishReason,
    TokenUsage,
)
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.gateway import Sleeper
from complianceiq.domain.ports.llm import LLMProvider


class MutableClock(Clock):
    """A clock whose time can be advanced explicitly in tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


class RecordingSleeper(Sleeper):
    """A sleeper that records requested delays instead of waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


class ScriptedProvider(LLMProvider):
    """A provider that can fail a fixed number of times before succeeding."""

    def __init__(
        self,
        provider_name: ProviderName,
        *,
        fail_first: int = 0,
        text: str = "ok",
        always_fail: bool = False,
    ) -> None:
        self._name = provider_name
        self._remaining_failures = fail_first
        self._always_fail = always_fail
        self._text = text
        self.calls = 0

    @property
    def name(self) -> ProviderName:
        return self._name

    async def generate(self, request: ProviderRequest) -> Completion:
        self.calls += 1
        if self._always_fail or self._remaining_failures > 0:
            self._remaining_failures = max(0, self._remaining_failures - 1)
            raise ProviderError("scripted failure", details={"provider": self._name.value})
        return Completion(
            text=self._text,
            provider=self._name,
            model_id=request.model_id,
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            finish_reason=FinishReason.STOP,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[CompletionChunk]:
        self.calls += 1
        if self._always_fail:
            raise ProviderError("scripted stream failure")
        yield CompletionChunk(delta=self._text, done=False)
        yield CompletionChunk(
            delta="", done=True, usage=TokenUsage(input_tokens=10, output_tokens=5)
        )

    async def embed(self, model_id: str, texts: Sequence[str]) -> list[EmbeddingResult]:
        if self._always_fail:
            raise ProviderError("scripted embed failure")
        return [
            EmbeddingResult(
                vector=[0.1, 0.2, 0.3],
                provider=self._name,
                model_id=model_id,
                usage=TokenUsage(input_tokens=3, output_tokens=0),
            )
            for _ in texts
        ]

    def count_tokens(self, model_id: str, text: str) -> int:
        return max(1, len(text) // 4)


def make_spec(
    provider: ProviderName,
    model_id: str,
    *,
    input_cost: str = "1.00",
    output_cost: str = "2.00",
    embedding_dimensions: int | None = None,
) -> ModelSpec:
    """Build a ModelSpec quickly for routing in tests."""
    from decimal import Decimal

    return ModelSpec(
        provider=provider,
        model_id=model_id,
        capabilities=ModelCapabilities(
            max_input_tokens=100_000,
            max_output_tokens=4_096,
            supports_embeddings=embedding_dimensions is not None,
        ),
        cost=ModelCost(
            input_per_million=Decimal(input_cost), output_per_million=Decimal(output_cost)
        ),
        embedding_dimensions=embedding_dimensions,
    )
