"""Tests for configuration loading and secret hygiene."""

from __future__ import annotations

from complianceiq.infrastructure.config.settings import (
    Environment,
    LLMProviderName,
    Settings,
)


def test_defaults_are_safe_for_local() -> None:
    settings = Settings()
    assert settings.environment is Environment.LOCAL
    assert settings.is_production is False
    # Default provider requires no credentials so the stack runs offline.
    assert settings.llm_primary_provider is LLMProviderName.FAKE


def test_secrets_are_not_exposed_in_repr() -> None:
    settings = Settings(anthropic_api_key="super-secret-key")  # type: ignore[arg-type]
    # SecretStr masks the value in both repr and str.
    assert "super-secret-key" not in repr(settings)
    assert "super-secret-key" not in str(settings)
    # ...but the real value is retrievable explicitly when genuinely needed.
    assert settings.anthropic_api_key.get_secret_value() == "super-secret-key"


def test_production_flag() -> None:
    settings = Settings(environment=Environment.PRODUCTION)
    assert settings.is_production is True


def test_port_bounds_are_validated() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(port=70_000)
