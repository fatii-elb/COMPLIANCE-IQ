"""Anthropic (Claude) provider adapter — the primary LLM provider.

Implements the :class:`LLMProvider` port against Anthropic's Messages API. Two
design choices keep this clean and testable:

1. **Lazy SDK import.** The ``anthropic`` package is imported only when a real
   client is built, so the module (and the default fake path) load even where the
   SDK isn't installed.
2. **Injectable client.** The constructor accepts an optional client object. Tests
   pass a lightweight stub with the same shape, so the mapping logic is verified
   with no network and no key.

All upstream failures are translated to a domain
:class:`~complianceiq.domain.exceptions.ProviderError`, so the gateway's
retry/fallback logic treats every provider uniformly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from complianceiq.domain.exceptions import ProviderError
from complianceiq.domain.llm.messages import LLMMessage, MessageRole
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
from complianceiq.infrastructure.providers.fake import approx_tokens

# Anthropic stop reasons → our FinishReason.
_FINISH_REASONS: dict[str, FinishReason] = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
}


class AnthropicProvider(LLMProvider):
    """Adapter over Anthropic's Messages API."""

    def __init__(self, *, api_key: str | None = None, client: Any | None = None) -> None:
        """Args:
        api_key: The Anthropic API key. Required if ``client`` is not supplied.
        client: An optional pre-built async client (used by tests). If omitted,
            a real ``anthropic.AsyncAnthropic`` is created lazily.
        """
        self._api_key = api_key
        self._client = client

    @property
    def name(self) -> ProviderName:
        return ProviderName.ANTHROPIC

    def _get_client(self) -> Any:
        """Return the async client, building a real one on first use."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover - exercised only without the SDK
                raise ProviderError(
                    "anthropic SDK is not installed",
                    details={"provider": self.name.value},
                ) from exc
            if not self._api_key:
                raise ProviderError(
                    "anthropic API key is not configured",
                    details={"provider": self.name.value},
                )
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def _split_messages(messages: Sequence[LLMMessage]) -> tuple[str, list[dict[str, str]]]:
        """Split into a system prompt and the user/assistant turns.

        Anthropic takes the system instruction as a separate top-level parameter,
        not as a message; multiple system messages are concatenated.
        """
        system_parts = [m.content for m in messages if m.role is MessageRole.SYSTEM]
        turns = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role is not MessageRole.SYSTEM
        ]
        return "\n\n".join(system_parts), turns

    def _build_kwargs(self, request: ProviderRequest) -> dict[str, Any]:
        system, turns = self._split_messages(request.messages)
        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "max_tokens": request.params.max_output_tokens,
            "temperature": request.params.temperature,
            "messages": turns,
        }
        if system:
            kwargs["system"] = system
        if request.params.top_p is not None:
            kwargs["top_p"] = request.params.top_p
        if request.params.stop:
            kwargs["stop_sequences"] = request.params.stop
        return kwargs

    async def generate(self, request: ProviderRequest) -> Completion:
        client = self._get_client()
        try:
            response = await client.messages.create(**self._build_kwargs(request))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "anthropic generation failed",
                details={"provider": self.name.value, "reason": type(exc).__name__},
            ) from exc

        text = "".join(getattr(block, "text", "") for block in getattr(response, "content", []))
        usage = getattr(response, "usage", None)
        stop_reason = getattr(response, "stop_reason", "end_turn") or "end_turn"
        return Completion(
            text=text,
            provider=self.name,
            model_id=request.model_id,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            ),
            finish_reason=_FINISH_REASONS.get(stop_reason, FinishReason.STOP),
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[CompletionChunk]:
        client = self._get_client()
        try:
            async with client.messages.stream(**self._build_kwargs(request)) as stream:
                async for text in stream.text_stream:
                    yield CompletionChunk(delta=text, done=False)
                final = await stream.get_final_message()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "anthropic streaming failed",
                details={"provider": self.name.value, "reason": type(exc).__name__},
            ) from exc

        usage = getattr(final, "usage", None)
        yield CompletionChunk(
            delta="",
            done=True,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            ),
        )

    async def embed(self, model_id: str, texts: Sequence[str]) -> list[EmbeddingResult]:
        # Anthropic does not expose an embeddings endpoint; embeddings are served
        # by the OpenAI-compatible provider or a dedicated embedding provider.
        raise ProviderError(
            "anthropic provider does not support embeddings",
            details={"provider": self.name.value},
        )

    def count_tokens(self, model_id: str, text: str) -> int:
        # Local estimate to avoid a network round-trip; authoritative counts come
        # from the response usage.
        return approx_tokens(text)
