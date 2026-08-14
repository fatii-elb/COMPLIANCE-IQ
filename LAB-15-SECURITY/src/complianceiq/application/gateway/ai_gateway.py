"""The AI Gateway — the single, hardened entry point for every model call.

Nothing else in ComplianceIQ talks to a provider directly; everything goes
through this choke point. That is what lets us enforce, in *one place*, all the
cross-cutting concerns that a production LLM system needs:

- **Rate limiting & budget** per tenant (fair use + cost control).
- **Prompt-injection scanning** of untrusted input (non-negotiable rule 4).
- **Caching** of deterministic requests (tenant-scoped, content-addressed).
- **Model routing** by task class, with a **fallback chain** across providers.
- **Retries** with exponential backoff + jitter, and per-call **timeouts**.
- **Circuit breaking** to stop hammering a failing provider.
- **Token & cost accounting** written to a usage ledger.

The gateway depends only on domain **ports** and value objects — never on a
provider SDK — so it is fully testable with a deterministic fake provider and
in-memory fakes for the ports.
"""

from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol

from complianceiq.application.gateway.circuit_breaker import CircuitBreaker
from complianceiq.application.gateway.config import GatewayConfig
from complianceiq.application.gateway.keys import build_cache_key
from complianceiq.application.gateway.retry import RetryPolicy, run_with_retry
from complianceiq.application.gateway.routing import RoutingTable
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import (
    BudgetExceededError,
    ModelNotAvailableError,
    ProviderError,
    ProviderTimeoutError,
    UnsafeContentError,
)
from complianceiq.domain.llm.models import ModelSpec, ProviderName, TaskClass
from complianceiq.domain.llm.requests import LLMRequest, ProviderRequest
from complianceiq.domain.llm.responses import (
    Completion,
    CompletionChunk,
    EmbeddingResult,
    TokenUsage,
)
from complianceiq.domain.llm.usage import UsageEvent
from complianceiq.domain.policies.prompt_safety import scan_for_injection
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.gateway import RateLimiter, ResponseCache, Sleeper, UsageLedger
from complianceiq.domain.ports.llm import LLMProvider


class GatewayLogger(Protocol):
    """Minimal structured-logger surface the gateway needs.

    Declared as a protocol so the application never imports a logging library.
    Infrastructure passes a structlog logger, which satisfies it structurally.
    """

    def info(self, event: str, *args: Any, **kwargs: Any) -> Any: ...
    def warning(self, event: str, *args: Any, **kwargs: Any) -> Any: ...


class _NullGatewayLogger:
    """A no-op logger used by default (and in tests) when none is supplied."""

    def info(self, event: str, *args: Any, **kwargs: Any) -> None:
        return None

    def warning(self, event: str, *args: Any, **kwargs: Any) -> None:
        return None


class AIGateway:
    """The central, policy-enforcing interface to all language-model providers."""

    def __init__(
        self,
        *,
        providers: Mapping[ProviderName, LLMProvider],
        routing: RoutingTable,
        config: GatewayConfig,
        rate_limiter: RateLimiter,
        cache: ResponseCache,
        ledger: UsageLedger,
        sleeper: Sleeper,
        clock: Clock,
        logger: GatewayLogger | None = None,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._providers = providers
        self._routing = routing
        self._config = config
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._ledger = ledger
        self._sleeper = sleeper
        self._clock = clock
        self._log: GatewayLogger = logger or _NullGatewayLogger()
        self._rand = rand
        self._retry_policy = RetryPolicy(
            max_retries=config.max_retries,
            base_delay_seconds=config.retry_base_delay_seconds,
            max_delay_seconds=config.retry_max_delay_seconds,
        )
        # One breaker per configured provider (all specs reference configured
        # providers; unconfigured ones are simply skipped during routing).
        self._breakers: dict[ProviderName, CircuitBreaker] = {
            name: CircuitBreaker(
                clock,
                failure_threshold=config.circuit_failure_threshold,
                reset_seconds=config.circuit_reset_seconds,
            )
            for name in providers
        }

    # ------------------------------------------------------------------ public

    async def generate(self, request: LLMRequest, auth: AuthContext) -> Completion:
        """Produce a full completion, applying every gateway policy.

        Order matters: cheap, protective checks first (rate limit → budget →
        injection), then cache, then the routed provider calls with
        retry/fallback. Raises typed domain errors the presentation layer maps to
        HTTP.
        """
        tenant = auth.tenant_id
        await self._preflight(request, tenant)

        specs = self._require_route(request.task)
        cache_key = build_cache_key(tenant, request) if request.cacheable else None

        if cache_key is not None:
            hit = await self._cache.get(cache_key)
            if hit is not None:
                served = hit.model_copy(update={"cached": True})
                await self._record(tenant, request.feature, served, cost=Decimal(0), cached=True)
                self._log.info("ai_cache_hit", tenant_id=tenant, feature=request.feature)
                return served

        last_error: ProviderError | None = None
        for spec in specs:
            provider = self._providers.get(spec.provider)
            if provider is None:
                continue
            breaker = self._breakers[spec.provider]
            if not breaker.allow():
                self._log.warning("ai_circuit_open", provider=spec.provider.value)
                continue

            provider_request = ProviderRequest(
                model_id=spec.model_id, messages=request.messages, params=request.params
            )
            try:
                completion = await run_with_retry(
                    functools.partial(self._generate_once, provider, provider_request),
                    policy=self._retry_policy,
                    sleeper=self._sleeper,
                    retry_on=(ProviderError,),
                    rand=self._rand,
                )
            except ProviderError as exc:
                breaker.record_failure()
                last_error = exc
                self._log.warning(
                    "ai_provider_failed",
                    provider=spec.provider.value,
                    model=spec.model_id,
                    error=exc.code,
                )
                continue

            breaker.record_success()
            cost = spec.cost.cost_for(
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
            )
            await self._record(tenant, request.feature, completion, cost=cost, cached=False)
            if cache_key is not None:
                await self._cache.set(
                    cache_key, completion, ttl_seconds=self._config.cache_ttl_seconds
                )
            self._log.info(
                "ai_generate_ok",
                tenant_id=tenant,
                provider=spec.provider.value,
                model=spec.model_id,
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
                cost_usd=str(cost),
            )
            return completion

        raise ProviderError(
            "all candidate providers failed for the task",
            details={"task": request.task.value},
        ) from last_error

    async def stream(
        self, request: LLMRequest, auth: AuthContext
    ) -> AsyncIterator[CompletionChunk]:
        """Stream a completion chunk-by-chunk.

        Pre-flight checks run first. Fallback to another provider is only possible
        *before the first chunk is emitted*; once bytes are on the wire we cannot
        cleanly switch, so a mid-stream failure propagates.
        """
        tenant = auth.tenant_id
        await self._preflight(request, tenant)
        specs = self._require_route(request.task)

        last_error: ProviderError | None = None
        for spec in specs:
            provider = self._providers.get(spec.provider)
            if provider is None:
                continue
            breaker = self._breakers[spec.provider]
            if not breaker.allow():
                continue

            provider_request = ProviderRequest(
                model_id=spec.model_id, messages=request.messages, params=request.params
            )
            emitted = False
            final_usage: TokenUsage | None = None
            try:
                async for chunk in provider.stream(provider_request):
                    emitted = True
                    if chunk.usage is not None:
                        final_usage = chunk.usage
                    yield chunk
            except ProviderError as exc:
                breaker.record_failure()
                last_error = exc
                if emitted:
                    raise
                continue

            breaker.record_success()
            usage = final_usage or TokenUsage(input_tokens=0, output_tokens=0)
            cost = spec.cost.cost_for(
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
            )
            await self._record_stream(tenant, request.feature, spec, usage, cost)
            return

        raise ProviderError(
            "all candidate providers failed for the task",
            details={"task": request.task.value},
        ) from last_error

    async def embed(
        self,
        texts: Sequence[str],
        auth: AuthContext,
        *,
        feature: str = "embedding",
    ) -> list[EmbeddingResult]:
        """Embed a batch of texts using the configured embedding model."""
        tenant = auth.tenant_id
        await self._rate_limiter.acquire(tenant)

        spec = self._routing.embedding_model
        if spec is None:
            raise ModelNotAvailableError("no embedding model is configured")
        provider = self._providers.get(spec.provider)
        if provider is None:
            raise ModelNotAvailableError(
                "embedding provider is not configured",
                details={"provider": spec.provider.value},
            )

        results = await run_with_retry(
            functools.partial(self._embed_once, provider, spec.model_id, texts),
            policy=self._retry_policy,
            sleeper=self._sleeper,
            retry_on=(ProviderError,),
            rand=self._rand,
        )

        total = TokenUsage(input_tokens=0, output_tokens=0)
        for result in results:
            total = total + result.usage
        cost = spec.cost.cost_for(
            input_tokens=total.input_tokens, output_tokens=total.output_tokens
        )
        await self._ledger.record(
            UsageEvent(
                tenant_id=tenant,
                feature=feature,
                provider=spec.provider,
                model_id=spec.model_id,
                usage=total,
                cost_usd=cost,
                cached=False,
                occurred_at=self._clock.now(),
            )
        )
        return results

    def count_tokens(self, text: str, *, task: TaskClass = TaskClass.GENERAL) -> int:
        """Estimate the token count of ``text`` using the model routed for ``task``."""
        for spec in self._routing.plan_for(task):
            provider = self._providers.get(spec.provider)
            if provider is not None:
                return provider.count_tokens(spec.model_id, text)
        raise ModelNotAvailableError("no provider configured for the task")

    # ---------------------------------------------------------------- internals

    async def _preflight(self, request: LLMRequest, tenant: str) -> None:
        """Run the protective checks that must pass before any model call."""
        await self._rate_limiter.acquire(tenant)
        await self._enforce_budget(tenant)
        self._scan_untrusted(request)

    async def _enforce_budget(self, tenant: str) -> None:
        """Block the call if the tenant has exhausted its spend budget."""
        budget = self._config.tenant_budget_usd
        if budget <= 0:
            return  # 0 means unlimited
        spent = await self._ledger.tenant_cost(tenant)
        if spent >= budget:
            raise BudgetExceededError(
                "tenant spend budget exhausted",
                details={"spent_usd": str(spent), "budget_usd": str(budget)},
            )

    def _scan_untrusted(self, request: LLMRequest) -> None:
        """Reject the request if untrusted messages contain prompt injection."""
        threshold = self._config.injection_block_threshold
        for message in request.messages:
            if message.role.is_trusted:
                continue
            result = scan_for_injection(message.content)
            if result.exceeds(threshold):
                labels = [signal.label for signal in result.signals]
                self._log.warning("ai_injection_blocked", labels=labels)
                raise UnsafeContentError(
                    "input rejected: potential prompt injection detected",
                    details={"signals": labels},
                )

    def _require_route(self, task: TaskClass) -> list[ModelSpec]:
        """Return the route for ``task`` or raise if none is configured."""
        specs = self._routing.plan_for(task)
        if not specs:
            raise ModelNotAvailableError(
                "no model is routed for the task", details={"task": task.value}
            )
        return specs

    async def _generate_once(self, provider: LLMProvider, request: ProviderRequest) -> Completion:
        """One provider call wrapped in a hard timeout."""
        try:
            return await asyncio.wait_for(
                provider.generate(request), timeout=self._config.request_timeout_seconds
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "provider call timed out",
                details={"provider": provider.name.value},
            ) from exc

    async def _embed_once(
        self, provider: LLMProvider, model_id: str, texts: Sequence[str]
    ) -> list[EmbeddingResult]:
        """One embedding call wrapped in a hard timeout."""
        try:
            return await asyncio.wait_for(
                provider.embed(model_id, texts), timeout=self._config.request_timeout_seconds
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "embedding call timed out",
                details={"provider": provider.name.value},
            ) from exc

    async def _record(
        self,
        tenant: str,
        feature: str,
        completion: Completion,
        *,
        cost: Decimal,
        cached: bool,
    ) -> None:
        """Write a usage event for a completion."""
        await self._ledger.record(
            UsageEvent(
                tenant_id=tenant,
                feature=feature,
                provider=completion.provider,
                model_id=completion.model_id,
                usage=completion.usage,
                cost_usd=cost,
                cached=cached,
                occurred_at=self._clock.now(),
            )
        )

    async def _record_stream(
        self,
        tenant: str,
        feature: str,
        spec: ModelSpec,
        usage: TokenUsage,
        cost: Decimal,
    ) -> None:
        """Write a usage event for a streamed completion."""
        await self._ledger.record(
            UsageEvent(
                tenant_id=tenant,
                feature=feature,
                provider=spec.provider,
                model_id=spec.model_id,
                usage=usage,
                cost_usd=cost,
                cached=False,
                occurred_at=self._clock.now(),
            )
        )
