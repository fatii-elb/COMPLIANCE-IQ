"""LLM domain value objects — the provider-agnostic vocabulary of AI calls.

Nothing here knows about Anthropic, OpenAI, or HTTP. These immutable types are
the *contract* between the application (which asks for generations/embeddings by
task) and the infrastructure adapters (which fulfil them). Keeping this
vocabulary pure is what makes providers swappable and the gateway testable with a
deterministic fake.
"""

from complianceiq.domain.llm.messages import LLMMessage, MessageRole
from complianceiq.domain.llm.models import (
    ModelCapabilities,
    ModelCost,
    ModelSpec,
    ProviderName,
    TaskClass,
)
from complianceiq.domain.llm.requests import (
    GenerationParams,
    LLMRequest,
    ProviderRequest,
)
from complianceiq.domain.llm.responses import (
    Completion,
    CompletionChunk,
    EmbeddingResult,
    FinishReason,
    TokenUsage,
)
from complianceiq.domain.llm.usage import UsageEvent

__all__ = [
    "Completion",
    "CompletionChunk",
    "EmbeddingResult",
    "FinishReason",
    "GenerationParams",
    "LLMMessage",
    "LLMRequest",
    "MessageRole",
    "ModelCapabilities",
    "ModelCost",
    "ModelSpec",
    "ProviderName",
    "ProviderRequest",
    "TaskClass",
    "TokenUsage",
    "UsageEvent",
]
