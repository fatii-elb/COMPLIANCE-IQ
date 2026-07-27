"""Tests for provider construction and routing-table assembly from settings."""

from __future__ import annotations

from complianceiq.domain.llm.models import ProviderName, TaskClass
from complianceiq.infrastructure.config.settings import LLMProviderName, Settings
from complianceiq.infrastructure.gateway.health import LLMProviderHealthProbe
from complianceiq.infrastructure.providers.registry import (
    build_providers,
    build_routing_table,
)


def test_default_settings_yield_only_fake_provider() -> None:
    providers = build_providers(Settings())
    assert set(providers.keys()) == {ProviderName.FAKE}


def test_anthropic_added_when_key_present() -> None:
    providers = build_providers(Settings(anthropic_api_key="sk-test"))  # type: ignore[arg-type]
    assert ProviderName.ANTHROPIC in providers


def test_openai_added_when_configured() -> None:
    settings = Settings(openai_base_url="http://x.local", openai_api_key="k")  # type: ignore[arg-type]
    providers = build_providers(settings)
    assert ProviderName.OPENAI_COMPATIBLE in providers


def test_default_routing_uses_fake_models() -> None:
    routing = build_routing_table(Settings())
    plan = routing.plan_for(TaskClass.REASONING)
    assert plan and plan[0].provider is ProviderName.FAKE
    assert routing.embedding_model is not None
    assert routing.embedding_model.provider is ProviderName.FAKE


def test_anthropic_primary_with_openai_fallback() -> None:
    settings = Settings(
        llm_primary_provider=LLMProviderName.ANTHROPIC,
        anthropic_api_key="sk-test",  # type: ignore[arg-type]
        openai_base_url="http://x.local",
        openai_api_key="k",  # type: ignore[arg-type]
    )
    routing = build_routing_table(settings)
    reasoning = routing.plan_for(TaskClass.REASONING)
    assert reasoning[0].provider is ProviderName.ANTHROPIC
    assert reasoning[-1].provider is ProviderName.OPENAI_COMPATIBLE  # fallback present


async def test_provider_health_probe_reports_ready() -> None:
    providers = build_providers(Settings())
    probe = LLMProviderHealthProbe(providers[ProviderName.FAKE])
    result = await probe.check()
    assert result.name == "llm:fake"
    assert result.healthy is True
