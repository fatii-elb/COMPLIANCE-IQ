"""Gateway configuration value object.

Groups the tunable policies of the AI gateway (timeouts, retries, rate limits,
budget, cache TTL, injection threshold, circuit-breaker settings) into one
immutable object. The composition root builds it from :class:`Settings`; the
gateway reads it. Keeping these as *data* (not scattered constants) means an
operator tunes behaviour via configuration, not code edits.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.enums import Severity


class GatewayConfig(FrozenModel):
    """Tunable policies for the AI gateway.

    Attributes:
        request_timeout_seconds: Hard timeout for a single provider call.
        max_retries: Extra attempts after the first, on retryable failures.
        retry_base_delay_seconds: Base for exponential backoff.
        retry_max_delay_seconds: Cap on any single backoff delay.
        rate_limit_per_minute: Allowed calls per tenant per minute.
        tenant_budget_usd: Max cumulative spend per tenant; ``0`` = unlimited.
        cache_ttl_seconds: How long a cached completion stays valid.
        injection_block_threshold: Minimum injection severity that blocks a call.
        circuit_failure_threshold: Consecutive failures that open a provider's
            circuit breaker.
        circuit_reset_seconds: How long a breaker stays open before probing again.
    """

    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_base_delay_seconds: float = Field(default=0.5, gt=0)
    retry_max_delay_seconds: float = Field(default=8.0, gt=0)
    rate_limit_per_minute: int = Field(default=60, gt=0)
    tenant_budget_usd: Decimal = Field(default=Decimal("50"), ge=Decimal(0))
    cache_ttl_seconds: int = Field(default=3600, ge=0)
    injection_block_threshold: Severity = Severity.HIGH
    circuit_failure_threshold: int = Field(default=5, gt=0)
    circuit_reset_seconds: float = Field(default=30.0, gt=0)
