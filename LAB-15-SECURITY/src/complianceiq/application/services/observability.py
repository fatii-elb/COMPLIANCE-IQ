"""Observability service — assembles the operational view of the running service.

Combines two sources into the ``/metrics`` exposition and a JSON snapshot: the
HTTP/request metrics collected in a :class:`MetricsReporter` (the in-memory sink),
and the AI usage totals (tokens, cost, cache hits) from the gateway's usage ledger.
Both are injected as narrow protocols, so this application service depends on
neither the concrete metrics backend nor the concrete ledger.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsReporter(Protocol):
    """The read side of the metrics sink (the in-memory adapter provides it)."""

    def render_prometheus(self) -> str: ...

    def snapshot(self) -> dict[str, object]: ...


@runtime_checkable
class UsageTotals(Protocol):
    """Aggregate usage totals (the in-memory usage ledger provides it)."""

    def totals(self) -> dict[str, object]: ...


class ObservabilityService:
    """Produces the metrics exposition and a structured snapshot."""

    def __init__(self, *, metrics: MetricsReporter, usage: UsageTotals) -> None:
        self._metrics = metrics
        self._usage = usage

    def prometheus(self) -> str:
        """Render Prometheus text: HTTP series plus AI-usage gauges."""
        body = self._metrics.render_prometheus()
        totals = self._usage.totals()
        gauges = [
            f"ai_gateway_calls_total {totals['calls']}",
            f"ai_gateway_cache_hits_total {totals['cache_hits']}",
            f"ai_gateway_input_tokens_total {totals['input_tokens']}",
            f"ai_gateway_output_tokens_total {totals['output_tokens']}",
            f"ai_gateway_cost_usd_total {totals['cost_usd']}",
        ]
        return body + "\n".join(gauges) + "\n"

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-friendly snapshot of metrics plus AI-usage totals."""
        snap = self._metrics.snapshot()
        snap["ai_usage"] = self._usage.totals()
        return snap
