"""OpenAI-compatible provider adapter — the secondary provider.

Talks to any endpoint that implements the OpenAI HTTP API (``/chat/completions``
and ``/embeddings``): OpenAI itself, Azure OpenAI, or a self-hosted gateway. It
provides the fallback in the routing chain and (unlike Anthropic) supplies
embeddings.

Design mirrors the Anthropic adapter: an injectable ``httpx.AsyncClient`` so the
mapping logic is tested offline with ``httpx.MockTransport`` (no network, no key),
and uniform translation of failures to :class:`ProviderError`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from complianceiq.domain.exceptions import ProviderError
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

_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
}


class OpenAICompatibleProvider(LLMProvider):
    """Adapter over an OpenAI-compatible HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Args:
        base_url: API base URL (e.g. ``https://api.openai.com/v1``).
        api_key: Bearer token for authentication.
        client: Optional pre-built async client (tests inject a MockTransport).
        timeout: Per-request timeout for a self-built client.
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    @property
    def name(self) -> ProviderName:
        return ProviderName.OPENAI_COMPATIBLE

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _chat_body(self, request: ProviderRequest, *, stream: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model_id,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "max_tokens": request.params.max_output_tokens,
            "temperature": request.params.temperature,
            "stream": stream,
        }
        if request.params.top_p is not None:
            body["top_p"] = request.params.top_p
        if request.params.stop:
            body["stop"] = request.params.stop
        return body

    async def generate(self, request: ProviderRequest) -> Completion:
        client = self._get_client()
        try:
            response = await client.post(
                "/chat/completions",
                headers=self._headers(),
                json=self._chat_body(request, stream=False),
            )
            response.raise_for_status()
            data = response.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "openai-compatible generation failed",
                details={"provider": self.name.value, "reason": type(exc).__name__},
            ) from exc

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        return Completion(
            text=message.get("content", "") or "",
            provider=self.name,
            model_id=request.model_id,
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            finish_reason=_FINISH_REASONS.get(
                choice.get("finish_reason", "stop"), FinishReason.STOP
            ),
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[CompletionChunk]:
        client = self._get_client()
        output_chars = 0
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                headers=self._headers(),
                json=self._chat_body(request, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        break
                    delta = _parse_sse_delta(payload)
                    if delta:
                        output_chars += len(delta)
                        yield CompletionChunk(delta=delta, done=False)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "openai-compatible streaming failed",
                details={"provider": self.name.value, "reason": type(exc).__name__},
            ) from exc

        # Streaming responses rarely include usage; estimate output from what we saw.
        input_tokens = sum(approx_tokens(m.content) for m in request.messages)
        yield CompletionChunk(
            delta="",
            done=True,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=max(1, output_chars // 4)),
        )

    async def embed(self, model_id: str, texts: Sequence[str]) -> list[EmbeddingResult]:
        client = self._get_client()
        try:
            response = await client.post(
                "/embeddings",
                headers=self._headers(),
                json={"model": model_id, "input": list(texts)},
            )
            response.raise_for_status()
            data = response.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "openai-compatible embedding failed",
                details={"provider": self.name.value, "reason": type(exc).__name__},
            ) from exc

        entries = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        results: list[EmbeddingResult] = []
        for text, entry in zip(texts, entries, strict=False):
            results.append(
                EmbeddingResult(
                    vector=[float(x) for x in entry.get("embedding", [])],
                    provider=self.name,
                    model_id=model_id,
                    usage=TokenUsage(input_tokens=approx_tokens(text), output_tokens=0),
                )
            )
        return results

    def count_tokens(self, model_id: str, text: str) -> int:
        return approx_tokens(text)


def _parse_sse_delta(payload: str) -> str:
    """Extract the incremental text from one OpenAI SSE data line."""
    import json

    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    choices = obj.get("choices") or [{}]
    return str(choices[0].get("delta", {}).get("content", "") or "")
