"""The :class:`MetricsSink` port — where operational measurements go.

Observability is a cross-cutting concern the application should not couple to a
specific backend (Prometheus, StatsD, OpenTelemetry, a log line). So code records
measurements against this small abstraction, and the composition root supplies a
concrete sink — an in-memory one offline, a real exporter in production — without
any caller changing.

Two primitives cover what we need: **counters** (monotonic events, e.g. requests
served) and **observations** (a distribution of values, e.g. request durations).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MetricsSink(ABC):
    """Records counters and value distributions with optional labels.

    Implementations must be safe to call from request-handling code (cheap,
    non-blocking) and must never raise into the caller — a metrics failure must
    not break a request.
    """

    @abstractmethod
    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add ``value`` to the counter ``name`` for the given label set."""
        raise NotImplementedError

    @abstractmethod
    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record one observation of ``value`` in the distribution ``name``."""
        raise NotImplementedError


class NullMetrics(MetricsSink):
    """A no-op sink (the default when observability is not configured)."""

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        return None

    def observe(self, name: str, value: float, **labels: str) -> None:
        return None
