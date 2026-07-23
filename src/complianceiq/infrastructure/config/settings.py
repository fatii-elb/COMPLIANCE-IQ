"""Application configuration (twelve-factor, via ``pydantic-settings``).

All configuration comes from environment variables (prefix ``CIQ_``) or a local
``.env`` file — never from hard-coded literals in source. Settings are validated
once at startup and then treated as immutable; a misconfiguration fails fast and
loudly rather than surfacing as a mysterious runtime error later.

Secrets (API keys, JWT keys, DB URLs) are typed as ``SecretStr`` so they cannot
be accidentally logged: their ``repr`` is ``**********`` and the raw value is
only reachable via an explicit ``.get_secret_value()`` call.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment. Governs environment-specific behaviour."""

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProviderName(StrEnum):
    """Selectable primary LLM provider. ``fake`` requires no credentials."""

    FAKE = "fake"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Strongly-typed, validated application settings.

    Field names map to ``CIQ_<UPPER_SNAKE>`` environment variables. See
    ``.env.example`` for the full template.
    """

    model_config = SettingsConfigDict(
        env_prefix="CIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Identity ---
    app_name: str = "complianceiq-ai"
    environment: Environment = Environment.LOCAL
    debug: bool = False

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    request_max_bytes: int = Field(default=1_048_576, ge=1_024)

    # --- Security / auth (verification only; Core Service issues tokens) ---
    jwt_audience: str = "complianceiq"
    jwt_issuer: str = "complianceiq-core"
    jwt_public_key: SecretStr = SecretStr("")

    # --- Database (wired in Phase 6) ---
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://complianceiq:complianceiq@postgres:5432/complianceiq"
    )

    # --- LLM providers (wired in Phase 2) ---
    anthropic_api_key: SecretStr = SecretStr("")
    llm_primary_provider: LLMProviderName = LLMProviderName.FAKE

    # --- Core Service client (wired in Phase 6) ---
    core_api_base_url: str = "http://core-stub:9000"

    @property
    def is_production(self) -> bool:
        """Whether this instance runs in the production environment."""
        return self.environment is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the ``.env`` file and environment are read exactly once. Tests that
    need to override configuration clear this cache (see ``tests/conftest.py``).
    """
    return Settings()
