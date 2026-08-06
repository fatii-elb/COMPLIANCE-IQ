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
from pathlib import Path

from fastapi import FastAPI

from complianceiq import __version__
from complianceiq.application.agents import (
    AgentSuite,
    ComplianceAnalystAgent,
    RemediationEngineerAgent,
    ReportWriterAgent,
    RiskAnalystAgent,
)
from complianceiq.application.app_info import AppInfo
from complianceiq.application.gateway.ai_gateway import AIGateway
from complianceiq.application.gateway.config import GatewayConfig
from complianceiq.application.graphs import (
    CopilotGraph,
    EnrichmentGraph,
    RemediationGraph,
    ReportGraph,
)
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.application.services.health import ReadinessService
from complianceiq.application.tools import AgentBudget, ToolRegistry, build_corpus_tools
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.core import CoreClient
from complianceiq.domain.ports.health import HealthProbe
from complianceiq.infrastructure.auth import (
    build_rs256_verifier,
    build_token_verifier,
    looks_like_jwk,
)
from complianceiq.infrastructure.clock import SystemClock
from complianceiq.infrastructure.config.settings import Settings, get_settings
from complianceiq.infrastructure.core import build_core_client
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
from complianceiq.infrastructure.knowledge import (
    KnowledgeStack,
    VectorStoreHealthProbe,
    build_knowledge_stack,
    load_corpus,
)
from complianceiq.infrastructure.logging.setup import configure_logging, get_logger
from complianceiq.infrastructure.prompts.loader import load_prompts
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
    knowledge: KnowledgeStack
    agents: AgentSuite
    token_verifier: TokenVerifier
    core_client: CoreClient


def build_agent_suite(
    settings: Settings,
    *,
    gateway: AIGateway,
    knowledge: KnowledgeStack,
    clock: Clock,
) -> AgentSuite:
    """Wire the Phase 4 prompts, graphs, tools, and bounded agents.

    Prompts are loaded from the ``prompts/`` asset directory (versioned files),
    the four LangGraph workflows are built over the retrieval stack and gateway,
    the knowledge tool is registered, and each capability is exposed as a
    budget-bounded agent.
    """
    logger = get_logger("ai.graphs")
    prompts = PromptRegistry(load_prompts(Path(settings.prompts_dir)))
    budget = AgentBudget(
        max_iterations=settings.agent_max_iterations,
        wall_clock_seconds=settings.agent_wall_clock_seconds,
    )

    enrichment_graph = EnrichmentGraph(
        retriever=knowledge.retriever,
        assembler=knowledge.assembler,
        gateway=gateway,
        prompts=prompts,
        config=knowledge.config,
        logger=logger,
    )
    copilot_graph = CopilotGraph(
        retriever=knowledge.retriever,
        assembler=knowledge.assembler,
        gateway=gateway,
        prompts=prompts,
        config=knowledge.config,
        logger=logger,
    )
    remediation_graph = RemediationGraph(
        retriever=knowledge.retriever,
        assembler=knowledge.assembler,
        gateway=gateway,
        prompts=prompts,
        config=knowledge.config,
        logger=logger,
    )
    report_graph = ReportGraph(gateway=gateway, prompts=prompts, clock=clock, logger=logger)

    tools = ToolRegistry(
        build_corpus_tools(knowledge.retriever, knowledge.assembler, knowledge.config)
    )

    return AgentSuite(
        prompts=prompts,
        tools=tools,
        copilot=copilot_graph,
        compliance_analyst=ComplianceAnalystAgent(
            graph=enrichment_graph, registry=tools, clock=clock, budget=budget
        ),
        remediation_engineer=RemediationEngineerAgent(
            graph=remediation_graph, registry=tools, clock=clock, budget=budget
        ),
        report_writer=ReportWriterAgent(
            graph=report_graph, registry=tools, clock=clock, budget=budget
        ),
        risk_analyst=RiskAnalystAgent(
            gateway=gateway,
            prompts=prompts,
            registry=tools,
            config=knowledge.config,
            clock=clock,
            budget=budget,
        ),
    )


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

    # --- Knowledge base & RAG (Phase 3) ---
    # In-memory vector store + keyword index behind the VectorStore/KeywordIndex
    # ports; the pgvector-backed store (ADR-0005) swaps in here in Phase 6.
    knowledge = build_knowledge_stack(settings, ai_gateway)

    # --- Workflows & agents (Phase 4) ---
    # Versioned prompts, the four LangGraph workflows, the knowledge tool, and the
    # bounded agents that expose each capability under hard budgets.
    agents = build_agent_suite(settings, gateway=ai_gateway, knowledge=knowledge, clock=clock)

    # --- Authentication (Phase 5 HS256 / Phase 6 RS256) ---
    # If the Core's public key (an RSA JWK) is configured, verify tokens
    # asymmetrically (production); otherwise fall back to the symmetric HS256
    # secret (local dev/testing). Both implement the same TokenVerifier port.
    public_key = settings.jwt_public_key.get_secret_value()
    token_verifier: TokenVerifier
    if looks_like_jwk(public_key):
        token_verifier = build_rs256_verifier(
            public_key_jwk=public_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            clock=clock,
        )
    else:
        token_verifier = build_token_verifier(
            secret=settings.jwt_hs256_secret.get_secret_value(),
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            clock=clock,
        )

    # --- Core Service client (Phase 6) ---
    # `stub` (offline default) seeds findings in-process; `http` calls the real
    # Core over REST. Either way the app depends only on the CoreClient port.
    core_client = build_core_client(settings)

    # Readiness includes a shallow probe per provider plus the vector store.
    probes: list[HealthProbe] = [
        LLMProviderHealthProbe(provider) for provider in providers.values()
    ]
    probes.append(VectorStoreHealthProbe(knowledge.vector_store))
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
        knowledge=knowledge,
        agents=agents,
        token_verifier=token_verifier,
        core_client=core_client,
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

    # Corpus autoload: on startup, if enabled and the store is empty, ingest the
    # bundled copyright-compliant corpus so `docker compose up` yields a working,
    # queryable knowledge base with no manual step.
    async def _seed_corpus() -> None:
        if not settings.knowledge_autoload:
            return
        if await container.knowledge.vector_store.count() > 0:
            return
        documents = load_corpus(container.knowledge.corpus_dir)
        if not documents:
            logger.warning("corpus_autoload_empty", corpus_dir=str(container.knowledge.corpus_dir))
            return
        report = await container.knowledge.ingestion.ingest(documents)
        logger.info(
            "corpus_autoloaded",
            documents=report.documents,
            chunks=report.chunks,
            corpus_version=report.corpus_version,
        )

    app = create_app(container, on_startup=[_seed_corpus])

    # Middleware executes in reverse order of registration (last added is
    # outermost). We want: CorrelationId (outermost) → RequestSizeLimit → app.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.request_max_bytes)
    app.add_middleware(CorrelationIdMiddleware)

    return app
