"""Provider construction and routing-table assembly from settings.

This is where configuration becomes concrete objects: which providers are
available (based on which credentials are present) and which model serves each
task. The **model catalog** below is *data* — capabilities and costs are declared,
not hardcoded in conditionals — honouring build-spec §3.2.

Costs are approximate public USD list prices per million tokens and live here so
they are easy to update without touching gateway logic.
"""

from __future__ import annotations

from decimal import Decimal

from complianceiq.application.gateway.routing import RoutingTable
from complianceiq.domain.llm.models import (
    ModelCapabilities,
    ModelCost,
    ModelSpec,
    ProviderName,
    TaskClass,
)
from complianceiq.domain.ports.llm import LLMProvider
from complianceiq.infrastructure.config.settings import LLMProviderName, Settings
from complianceiq.infrastructure.providers.anthropic_provider import AnthropicProvider
from complianceiq.infrastructure.providers.fake import FakeLLMProvider
from complianceiq.infrastructure.providers.openai_compatible import OpenAICompatibleProvider

# --- Fake model catalog (offline default) -----------------------------------
_FAKE_CAPS = ModelCapabilities(max_input_tokens=100_000, max_output_tokens=4_096)
_FAKE_EMBED_CAPS = ModelCapabilities(
    max_input_tokens=8_192, max_output_tokens=1, supports_embeddings=True
)
_ZERO_COST = ModelCost(input_per_million=Decimal(0), output_per_million=Decimal(0))

_FAKE_REASONING = ModelSpec(
    provider=ProviderName.FAKE, model_id="fake-reasoning", capabilities=_FAKE_CAPS, cost=_ZERO_COST
)
_FAKE_FAST = ModelSpec(
    provider=ProviderName.FAKE, model_id="fake-fast", capabilities=_FAKE_CAPS, cost=_ZERO_COST
)
_FAKE_EMBED = ModelSpec(
    provider=ProviderName.FAKE,
    model_id="fake-embed",
    capabilities=_FAKE_EMBED_CAPS,
    cost=_ZERO_COST,
    embedding_dimensions=16,
)


def build_providers(settings: Settings) -> dict[ProviderName, LLMProvider]:
    """Instantiate the providers for which credentials/config are present.

    The fake provider is always available so the system runs offline. Real
    providers are added only when configured, so an unconfigured provider is
    simply absent from routing (and the gateway skips it).
    """
    providers: dict[ProviderName, LLMProvider] = {ProviderName.FAKE: FakeLLMProvider()}

    if settings.anthropic_api_key.get_secret_value():
        providers[ProviderName.ANTHROPIC] = AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value()
        )

    if settings.openai_base_url and settings.openai_api_key.get_secret_value():
        providers[ProviderName.OPENAI_COMPATIBLE] = OpenAICompatibleProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.gateway_request_timeout_seconds,
        )

    return providers


def _anthropic_specs(settings: Settings) -> tuple[ModelSpec, ModelSpec]:
    """Reasoning + fast Claude model specs (approx. Sonnet/Haiku list prices)."""
    caps = ModelCapabilities(max_input_tokens=200_000, max_output_tokens=8_192)
    reasoning = ModelSpec(
        provider=ProviderName.ANTHROPIC,
        model_id=settings.anthropic_model_reasoning,
        capabilities=caps,
        cost=ModelCost(input_per_million=Decimal("3.00"), output_per_million=Decimal("15.00")),
    )
    fast = ModelSpec(
        provider=ProviderName.ANTHROPIC,
        model_id=settings.anthropic_model_fast,
        capabilities=caps,
        cost=ModelCost(input_per_million=Decimal("0.80"), output_per_million=Decimal("4.00")),
    )
    return reasoning, fast


def _openai_chat_spec(settings: Settings) -> ModelSpec:
    return ModelSpec(
        provider=ProviderName.OPENAI_COMPATIBLE,
        model_id=settings.openai_chat_model,
        capabilities=ModelCapabilities(max_input_tokens=128_000, max_output_tokens=16_384),
        cost=ModelCost(input_per_million=Decimal("0.15"), output_per_million=Decimal("0.60")),
    )


def _openai_embedding_spec(settings: Settings) -> ModelSpec:
    return ModelSpec(
        provider=ProviderName.OPENAI_COMPATIBLE,
        model_id=settings.openai_embedding_model,
        capabilities=ModelCapabilities(
            max_input_tokens=8_192, max_output_tokens=1, supports_embeddings=True
        ),
        cost=ModelCost(input_per_million=Decimal("0.02"), output_per_million=Decimal(0)),
        embedding_dimensions=settings.openai_embedding_dimensions,
    )


def build_routing_table(settings: Settings) -> RoutingTable:
    """Assemble the task → model routing table from settings.

    The primary provider determines the routes; a configured OpenAI-compatible
    provider becomes the fallback for a Claude-primary deployment. When the
    primary is ``fake``, everything routes to the fake models so the whole system
    works with no credentials.
    """
    primary = settings.llm_primary_provider
    openai_configured = bool(
        settings.openai_base_url and settings.openai_api_key.get_secret_value()
    )

    if primary is LLMProviderName.ANTHROPIC:
        reasoning, fast = _anthropic_specs(settings)
        fallback = [_openai_chat_spec(settings)] if openai_configured else []
        embedding = _openai_embedding_spec(settings) if openai_configured else _FAKE_EMBED
        return RoutingTable(
            routes={
                TaskClass.REASONING: [reasoning, *fallback],
                TaskClass.GENERAL: [reasoning, *fallback],
                TaskClass.CLASSIFICATION: [fast, *fallback],
                TaskClass.RERANK: [fast, *fallback],
                TaskClass.EXTRACTION: [fast, *fallback],
            },
            embedding_model=embedding,
        )

    if primary is LLMProviderName.OPENAI_COMPATIBLE and openai_configured:
        chat = _openai_chat_spec(settings)
        return RoutingTable(
            routes={
                TaskClass.REASONING: [chat],
                TaskClass.GENERAL: [chat],
                TaskClass.CLASSIFICATION: [chat],
                TaskClass.RERANK: [chat],
                TaskClass.EXTRACTION: [chat],
            },
            embedding_model=_openai_embedding_spec(settings),
        )

    # Default: fake provider serves everything (offline, no credentials).
    return RoutingTable(
        routes={
            TaskClass.REASONING: [_FAKE_REASONING],
            TaskClass.GENERAL: [_FAKE_REASONING],
            TaskClass.CLASSIFICATION: [_FAKE_FAST],
            TaskClass.RERANK: [_FAKE_FAST],
            TaskClass.EXTRACTION: [_FAKE_FAST],
        },
        embedding_model=_FAKE_EMBED,
    )
