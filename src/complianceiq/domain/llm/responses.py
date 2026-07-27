"""Response value objects for LLM interactions.

Every response records **which model produced it** (``provider`` + ``model_id``)
and its **token usage**. Recording the model on embeddings is not cosmetic: in
Phase 3 it prevents the catastrophic-but-silent bug of comparing a query vector
from one embedding model against document vectors from another.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class FinishReason(StrEnum):
    """Why a generation stopped."""

    STOP = "stop"  # natural end / stop sequence
    LENGTH = "length"  # hit max_output_tokens
    CONTENT_FILTER = "content_filter"  # provider safety filter
    ERROR = "error"  # aborted due to an error


class TokenUsage(FrozenModel):
    """Token counts for one call. Feeds cost accounting and quotas."""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed by the call."""
        return self.input_tokens + self.output_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Sum two usages (used to accumulate streamed chunks)."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class Completion(FrozenModel):
    """A full (non-streamed) generation result.

    Attributes:
        text: The generated text.
        provider: Which provider produced it.
        model_id: Which model produced it.
        usage: Token usage for the call.
        finish_reason: Why generation stopped.
        cached: True if served from cache rather than a fresh provider call.
    """

    text: str
    provider: ProviderName
    model_id: NonEmptyStr
    usage: TokenUsage
    finish_reason: FinishReason = FinishReason.STOP
    cached: bool = False


class CompletionChunk(FrozenModel):
    """One piece of a streamed generation.

    Attributes:
        delta: The text fragment in this chunk.
        done: True on the final chunk.
        usage: Final token usage, present only on the terminal chunk.
    """

    # Streaming deltas legitimately carry leading/trailing spaces (a token may be
    # " the"). Unlike other value objects, this one must NOT strip whitespace, or
    # the reassembled text would lose its spacing.
    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_assignment=True, str_strip_whitespace=False
    )

    delta: str = ""
    done: bool = False
    usage: TokenUsage | None = None


class EmbeddingResult(FrozenModel):
    """A single embedding vector plus the identity of the model that made it.

    Attributes:
        vector: The embedding.
        provider: Which provider produced it.
        model_id: Which model produced it — the anti-mismatch guard.
        usage: Token usage for the embedding call.
    """

    vector: list[float] = Field(min_length=1)
    provider: ProviderName
    model_id: NonEmptyStr
    usage: TokenUsage
