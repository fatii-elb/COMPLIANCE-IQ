"""In-memory usage/cost ledger.

Implements the :class:`UsageLedger` port. It accumulates :class:`UsageEvent`s and
answers per-tenant spend queries used for budget enforcement. It also exposes a
few read helpers (per-feature / per-model breakdowns) useful for the metrics that
Phase 7 will surface.

A durable (PostgreSQL) ledger implements the same port later; the gateway does
not change. This adapter is intentionally simple and process-local.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from complianceiq.domain.llm.usage import UsageEvent
from complianceiq.domain.ports.gateway import UsageLedger


class InMemoryUsageLedger(UsageLedger):
    """Accumulates usage events and answers spend queries."""

    def __init__(self) -> None:
        self._events: list[UsageEvent] = []
        self._cost_by_tenant: dict[str, Decimal] = defaultdict(lambda: Decimal(0))

    async def record(self, event: UsageEvent) -> None:
        self._events.append(event)
        self._cost_by_tenant[event.tenant_id] += event.cost_usd

    async def tenant_cost(self, tenant_id: str) -> Decimal:
        return self._cost_by_tenant.get(tenant_id, Decimal(0))

    # --- read helpers (not part of the port; used by tests and Phase 7 metrics) ---

    def events(self) -> list[UsageEvent]:
        """Return a copy of all recorded events."""
        return list(self._events)

    def total_tokens(self, tenant_id: str) -> int:
        """Total tokens (input + output) recorded for a tenant."""
        return sum(e.usage.total_tokens for e in self._events if e.tenant_id == tenant_id)

    def totals(self) -> dict[str, object]:
        """Aggregate, non-tenant-scoped usage totals (for operational metrics)."""
        input_tokens = sum(e.usage.input_tokens for e in self._events)
        output_tokens = sum(e.usage.output_tokens for e in self._events)
        cost_usd = sum((e.cost_usd for e in self._events), Decimal(0))
        cache_hits = sum(1 for e in self._events if e.cached)
        return {
            "calls": len(self._events),
            "cache_hits": cache_hits,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": str(cost_usd),
        }
