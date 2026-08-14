"""Request value objects for LLM interactions.

Two levels exist on purpose:

- :class:`LLMRequest` is the *high-level, task-oriented* request the application
  makes ("answer this, it's a REASONING task"). It does **not** name a model —
  the router chooses one from the task.
- :class:`ProviderRequest` is the *low-level* request handed to a concrete
  provider after routing ("run these messages on model X"). Providers only ever
  see this.

This split keeps model selection in one place (the router) and keeps providers
dumb executors.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class GenerationParams(FrozenModel):
    """Sampling/output parameters for a generation call.

    Defaults are deliberately conservative: ``temperature=0.0`` makes output as
    deterministic as the provider allows, which is what a compliance system wants
    (reproducible, defensible answers over creative ones).
    """

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, gt=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: list[str] = Field(default_factory=list)


class LLMRequest(FrozenModel):
    """A task-oriented request; the router picks the model from ``task``.

    Attributes:
        messages: The conversation (system + user + optional history).
        task: The task class used for routing.
        params: Sampling/output parameters.
        feature: The product feature making the call (e.g. ``enrich``,
            ``copilot``). Used to attribute cost per feature.
        cacheable: Whether the response may be served from / written to cache.
            Deterministic (temperature 0) requests are cacheable by default.
    """

    messages: list[LLMMessage] = Field(min_length=1)
    task: TaskClass = TaskClass.GENERAL
    params: GenerationParams = Field(default_factory=GenerationParams)
    feature: NonEmptyStr = "general"
    cacheable: bool = True


class ProviderRequest(FrozenModel):
    """A concrete request for one model on one provider (post-routing).

    Attributes:
        model_id: The provider's model identifier.
        messages: The conversation to send.
        params: Sampling/output parameters.
    """

    model_id: NonEmptyStr
    messages: list[LLMMessage] = Field(min_length=1)
    params: GenerationParams = Field(default_factory=GenerationParams)
