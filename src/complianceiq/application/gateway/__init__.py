"""The AI Gateway use case and its supporting policies.

Public surface:

- :class:`AIGateway` — the central, policy-enforcing interface to all providers.
- :class:`GatewayConfig` — tunable policies (timeouts, limits, budget, cache TTL).
- :class:`RoutingTable` — task → ordered model candidates (primary + fallbacks).
- :class:`RetryPolicy` — backoff/jitter parameters.
- :class:`CircuitBreaker` — per-provider failure isolation.

All of it depends only on domain ports and value objects, so the gateway is
testable end-to-end with a deterministic fake provider.
"""

from complianceiq.application.gateway.ai_gateway import AIGateway, GatewayLogger
from complianceiq.application.gateway.circuit_breaker import CircuitBreaker, CircuitState
from complianceiq.application.gateway.config import GatewayConfig
from complianceiq.application.gateway.keys import build_cache_key
from complianceiq.application.gateway.retry import RetryPolicy, run_with_retry
from complianceiq.application.gateway.routing import RoutingTable

__all__ = [
    "AIGateway",
    "CircuitBreaker",
    "CircuitState",
    "GatewayConfig",
    "GatewayLogger",
    "RetryPolicy",
    "RoutingTable",
    "build_cache_key",
    "run_with_retry",
]
