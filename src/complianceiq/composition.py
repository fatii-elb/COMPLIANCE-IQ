"""Composition root — the single place the whole system is wired together.

This module (and only this module) is allowed to import from *both* the
infrastructure and presentation layers. It constructs the concrete adapters,
assembles them into a container, builds the FastAPI app, and bolts on the
infrastructure middleware. Everything else in the codebase depends on
abstractions; here, once, we choose the concretions.

Having a single explicit composition root — instead of scattered global
singletons or a service locator — means the entire dependency graph is visible
in one file and is trivial to reconfigure for tests or new environments.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from complianceiq import __version__
from complianceiq.application.app_info import AppInfo
from complianceiq.application.gateway.ai_gateway import AIGateway
from complianceiq.application.gateway.config import GatewayConfig
from complianceiq.application.services.health import ReadinessService
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.health import HealthProbe
from complianceiq.infrastructure.clock import SystemClock
from complianceiq.infrastructure.config.settings import Settings, get_settings
from complianceiq.infrastructure.gateway import (
    AsyncSleeper,
    InMemoryRateLimiter,
    InMemoryResponseCache,
    InMemoryUsageLedger,
    LLMProviderHealthProbe,
)
from complianceiq.infrastructure.http.middleware import (
    CorrelationIdMiddleware,
    RequestSizeLimitMiddleware,
)
from complianceiq.infrastructure.logging.setup import configure_logging, get_logger
from complianceiq.infrastructure.providers import build_providers, build_routing_table
from complianceiq.presentation.app import create_app


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """The wired object graph.

    Exposes exactly the services the presentation :class:`Container` protocol
    requires (``app_info``, ``readiness_service``) plus the shared ``clock`` and
    ``settings`` that later phases' use cases will consume. Being a frozen
    dataclass, it is immutable once built.
    """

    settings: Settings
    clock: Clock
    app_info: AppInfo
    readiness_service: ReadinessService
    ai_gateway: AIGateway


def build_container(settings: Settings | None = None) -> ApplicationContainer:
    """Construct the application container from settings.

    Args:
        settings: Optional explicit settings (tests inject overrides). Defaults
            to the process settings loaded from the environment.

    Returns:
        A fully-wired :class:`ApplicationContainer`.
    """
    settings = settings or get_settings()

    clock: Clock = SystemClock()

    # --- AI gateway (Phase 2) ---
    # Build providers from credentials, assemble the routing table, and wire the
    # gateway with in-memory adapters for its cross-cutting ports. Each adapter
    # implements a domain port, so a Redis/Postgres-backed version can replace it
    # later without touching the gateway.
    gateway_config = GatewayConfig(
        request_timeout_seconds=settings.gateway_request_timeout_seconds,
        max_retries=settings.gateway_max_retries,
        retry_base_delay_seconds=settings.gateway_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.gateway_retry_max_delay_seconds,
        rate_limit_per_minute=settings.gateway_rate_limit_per_minute,
        tenant_budget_usd=settings.gateway_tenant_budget_usd,
        cache_ttl_seconds=settings.gateway_cache_ttl_seconds,
    )
    providers = build_providers(settings)
    routing = build_routing_table(settings)
    ai_gateway = AIGateway(
        providers=providers,
        routing=routing,
        config=gateway_config,
        rate_limiter=InMemoryRateLimiter(clock, per_minute=gateway_config.rate_limit_per_minute),
        cache=InMemoryResponseCache(clock),
        ledger=InMemoryUsageLedger(),
        sleeper=AsyncSleeper(),
        clock=clock,
        logger=get_logger("ai.gateway"),
    )

    # Readiness now includes a shallow probe per configured provider. More probes
    # (vector store, database, Core API) are registered in later phases.
    probes: list[HealthProbe] = [
        LLMProviderHealthProbe(provider) for provider in providers.values()
    ]
    readiness_service = ReadinessService(probes)

    app_info = AppInfo(
        name=settings.app_name,
        version=__version__,
        environment=settings.environment.value,
    )

    return ApplicationContainer(
        settings=settings,
        clock=clock,
        app_info=app_info,
        readiness_service=readiness_service,
        ai_gateway=ai_gateway,
    )


def build_app(settings: Settings | None = None) -> FastAPI:
    """Build the production-ready ASGI application.

    Configures logging, constructs the container, creates the FastAPI app, and
    attaches infrastructure middleware in the correct order (correlation ID
    outermost so every inner layer and error handler sees it).
    """
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    logger = get_logger("composition")
    logger.info(
        "starting_service",
        app=settings.app_name,
        environment=settings.environment.value,
        version=__version__,
    )

    container = build_container(settings)
    app = create_app(container)

    # Middleware executes in reverse order of registration (last added is
    # outermost). We want: CorrelationId (outermost) → RequestSizeLimit → app.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.request_max_bytes)
    app.add_middleware(CorrelationIdMiddleware)

    return app
