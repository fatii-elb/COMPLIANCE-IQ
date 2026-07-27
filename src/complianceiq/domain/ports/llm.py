"""The :class:`LLMProvider` port.

This is *the* abstraction that keeps ComplianceIQ vendor-neutral. The application
and the gateway depend only on this interface; concrete adapters (Anthropic, an
OpenAI-compatible endpoint, or a deterministic fake) implement it in the
infrastructure layer. No provider-specific type ever crosses this boundary.

A provider is a *dumb executor*: it runs a fully-resolved
:class:`~complianceiq.domain.llm.requests.ProviderRequest` on a named model. All
cross-cutting concerns (routing, retries, rate limiting, caching, cost) live in
the gateway, not here — so a new provider is genuinely small to add.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.requests import ProviderRequest
from complianceiq.domain.llm.responses import Completion, CompletionChunk, EmbeddingResult


class LLMProvider(ABC):
    """A vendor-neutral interface to a language-model provider."""

    @property
    @abstractmethod
    def name(self) -> ProviderName:
        """The provider's identity (used for routing, metrics, and cost)."""
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> Completion:
        """Run a single, non-streamed generation.

        Implementations translate ``request`` into the vendor's call, then map
        the vendor response back into a domain :class:`Completion` — including
        real token usage. On an upstream failure they raise a domain
        :class:`~complianceiq.domain.exceptions.ProviderError` (never a raw SDK
        exception), so the gateway can apply retries/fallback uniformly.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: ProviderRequest) -> AsyncIterator[CompletionChunk]:
        """Run a streamed generation, yielding chunks as they arrive.

        The final chunk carries ``done=True`` and the total ``usage``. Providers
        that cannot stream should raise
        :class:`~complianceiq.domain.exceptions.ProviderError`.
        """
        raise NotImplementedError

    @abstractmethod
    async def embed(self, model_id: str, texts: Sequence[str]) -> list[EmbeddingResult]:
        """Embed a batch of texts with ``model_id``.

        Each result records the producing model so query/document embeddings can
        never be silently mismatched. Providers without an embedding model raise
        :class:`~complianceiq.domain.exceptions.ProviderError`.
        """
        raise NotImplementedError

    @abstractmethod
    def count_tokens(self, model_id: str, text: str) -> int:
        """Estimate the token count of ``text`` for ``model_id``.

        Used for pre-flight budget/limit checks. Implementations may approximate;
        authoritative counts come from the provider's response usage.
        """
        raise NotImplementedError
