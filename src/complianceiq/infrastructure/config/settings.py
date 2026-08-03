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

from decimal import Decimal
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
    OPENAI_COMPATIBLE = "openai_compatible"


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

    # --- LLM providers (Phase 2) ---
    llm_primary_provider: LLMProviderName = LLMProviderName.FAKE

    # Anthropic (Claude) — primary provider when selected.
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model_reasoning: str = "claude-3-5-sonnet-latest"
    anthropic_model_fast: str = "claude-3-5-haiku-latest"

    # OpenAI-compatible — secondary provider / fallback / embeddings.
    openai_base_url: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, gt=0)

    # --- AI gateway policies (Phase 2) ---
    gateway_request_timeout_seconds: float = Field(default=30.0, gt=0)
    gateway_max_retries: int = Field(default=2, ge=0)
    gateway_retry_base_delay_seconds: float = Field(default=0.5, gt=0)
    gateway_retry_max_delay_seconds: float = Field(default=8.0, gt=0)
    gateway_rate_limit_per_minute: int = Field(default=60, gt=0)
    gateway_tenant_budget_usd: Decimal = Field(default=Decimal("50"), ge=Decimal(0))
    gateway_cache_ttl_seconds: int = Field(default=3600, ge=0)

    # --- Knowledge base & retrieval (Phase 3) ---
    knowledge_corpus_dir: str = "corpus/frameworks"
    knowledge_corpus_version: str = "v1"
    knowledge_autoload: bool = True  # ingest the bundled corpus at startup
    retrieval_candidate_multiplier: int = Field(default=4, ge=1, le=20)
    retrieval_rerank_top_k: int = Field(default=20, ge=1, le=100)
    retrieval_rrf_k: int = Field(default=60, ge=1)
    retrieval_mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    retrieval_context_token_budget: int = Field(default=2000, ge=128)
    retrieval_chunk_max_tokens: int = Field(default=400, ge=64)

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
