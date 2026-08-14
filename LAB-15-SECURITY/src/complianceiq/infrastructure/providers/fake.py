"""Deterministic, in-process fake LLM provider.

This is the default provider: it needs no API key and no network, so the whole
system runs and is fully testable offline. Its output is a deterministic function
of the input, which makes it perfect for unit tests (assert exact text/usage) and
for local development of downstream features before real models are wired.

It implements the same :class:`LLMProvider` port as the real adapters, so code
that works against the fake works unchanged against Claude.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import AsyncIterator, Sequence

from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.domain.llm.responses import (
    Completion,
    CompletionChunk,
    EmbeddingResult,
    FinishReason,
    TokenUsage,
)
from complianceiq.domain.ports.llm import LLMProvider


def approx_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). At least 1 for non-empty text."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class FakeLLMProvider(LLMProvider):
    """A deterministic provider whose responses are a function of the input."""

    def __init__(self, *, embedding_dimensions: int = 16) -> None:
        """Args:
        embedding_dimensions: Size of the pseudo-embedding vectors produced.
        """
        self._embedding_dimensions = embedding_dimensions

    @property
    def name(self) -> ProviderName:
        return ProviderName.FAKE

    def _render(self, request: ProviderRequest) -> str:
        """Deterministically render a response from the last user message."""
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role.value == "user"),
            "",
        )
        return f"[fake:{request.model_id}] {last_user}".strip()

    def _usage_for(self, request: ProviderRequest, output: str) -> TokenUsage:
        input_tokens = sum(approx_tokens(m.content) for m in request.messages)
        return TokenUsage(input_tokens=input_tokens, output_tokens=approx_tokens(output))

    async def generate(self, request: ProviderRequest) -> Completion:
        output = self._render(request)
        return Completion(
            text=output,
            provider=self.name,
            model_id=request.model_id,
            usage=self._usage_for(request, output),
            finish_reason=FinishReason.STOP,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[CompletionChunk]:
        output = self._render(request)
        words = output.split(" ")
        for index, word in enumerate(words):
            delta = word if index == 0 else f" {word}"
            yield CompletionChunk(delta=delta, done=False)
        yield CompletionChunk(delta="", done=True, usage=self._usage_for(request, output))

    async def embed(self, model_id: str, texts: Sequence[str]) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for text in texts:
            results.append(
                EmbeddingResult(
                    vector=self._pseudo_vector(text),
                    provider=self.name,
                    model_id=model_id,
                    usage=TokenUsage(input_tokens=approx_tokens(text), output_tokens=0),
                )
            )
        return results

    def count_tokens(self, model_id: str, text: str) -> int:
        return approx_tokens(text)

    def _pseudo_vector(self, text: str) -> list[float]:
        """A deterministic, L2-normalised pseudo-embedding derived from a hash.

        Not semantically meaningful — it only needs to be stable and well-formed
        so downstream vector-store code can be exercised offline.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [(digest[i % len(digest)] - 128) / 128.0 for i in range(self._embedding_dimensions)]
        norm = math.sqrt(sum(component * component for component in raw)) or 1.0
        return [component / norm for component in raw]
