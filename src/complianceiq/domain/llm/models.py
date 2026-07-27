"""Model and provider description value objects.

A core principle (build spec §3.2): *provider capabilities and limits are
declared as data, not hardcoded conditionals*. So instead of ``if provider ==
"anthropic": max_tokens = ...`` scattered through the code, every model is a
:class:`ModelSpec` — a small data record the router reads. Adding a model, or
swapping which model serves a task, is a configuration change, not a code change.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class ProviderName(StrEnum):
    """The LLM providers the gateway can route to.

    ``FAKE`` is a deterministic in-process provider that needs no credentials and
    no network — it is the default so the whole system runs offline.
    """

    FAKE = "fake"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"


class TaskClass(StrEnum):
    """Coarse categories of work, used to route to an appropriate model.

    Cheap/fast models serve classification and reranking; a high-capability model
    serves reasoning-heavy explanation. Routing by *task* (not by hardcoding a
    model at each call site) is what lets us tune cost/quality centrally.
    """

    REASONING = "reasoning"  # explanation, correlation narratives
    CLASSIFICATION = "classification"  # short labels/decisions
    RERANK = "rerank"  # ordering retrieved chunks
    EXTRACTION = "extraction"  # structured field extraction
    EMBEDDING = "embedding"  # vector generation
    GENERAL = "general"  # default catch-all


class ModelCapabilities(FrozenModel):
    """Declared limits/features of a model. Read by the router and validators."""

    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    supports_streaming: bool = True
    supports_embeddings: bool = False
    supports_tools: bool = False


class ModelCost(FrozenModel):
    """Billing rates for a model, in USD per one million tokens.

    Kept as ``Decimal`` (never float) because it feeds cost accounting, and money
    must not accumulate floating-point error. This is provider billing cost (USD);
    it is distinct from the *business* financial-risk figures (MAD).
    """

    input_per_million: Decimal = Field(ge=Decimal(0))
    output_per_million: Decimal = Field(ge=Decimal(0))

    def cost_for(self, *, input_tokens: int, output_tokens: int) -> Decimal:
        """Compute USD cost for a given token usage."""
        million = Decimal(1_000_000)
        return (
            Decimal(input_tokens) / million * self.input_per_million
            + Decimal(output_tokens) / million * self.output_per_million
        )


class ModelSpec(FrozenModel):
    """A fully-described, routable model.

    Attributes:
        provider: Which provider serves this model.
        model_id: The provider's identifier for the model.
        capabilities: Declared limits/features.
        cost: Billing rates.
        embedding_dimensions: Vector size for embedding models (else ``None``).
    """

    provider: ProviderName
    model_id: NonEmptyStr
    capabilities: ModelCapabilities
    cost: ModelCost
    embedding_dimensions: int | None = Field(default=None, gt=0)
