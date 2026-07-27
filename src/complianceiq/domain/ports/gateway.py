"""Ports for the gateway's cross-cutting concerns.

The gateway needs four capabilities from the outside world: throttle callers
(:class:`RateLimiter`), remember answers (:class:`ResponseCache`), record spend
(:class:`UsageLedger`), and wait between retries (:class:`Sleeper`). Each is a
port so the application can be tested deterministically (in-memory fakes) and so
production can swap in Redis/Postgres-backed adapters without touching gateway
logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from complianceiq.domain.llm.responses import Completion
from complianceiq.domain.llm.usage import UsageEvent


class RateLimiter(ABC):
    """Throttles calls per key (typically per tenant)."""

    @abstractmethod
    async def acquire(self, key: str, *, cost: int = 1) -> None:
        """Consume ``cost`` units for ``key``.

        Raises:
            RateLimitError: If the key has exceeded its allowance. Callers must
                not proceed with the model call.
        """
        raise NotImplementedError


class ResponseCache(ABC):
    """A content-addressed cache of completions with per-entry TTL."""

    @abstractmethod
    async def get(self, key: str) -> Completion | None:
        """Return the cached completion for ``key``, or ``None`` on miss/expiry."""
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: Completion, *, ttl_seconds: int) -> None:
        """Store ``value`` under ``key`` for ``ttl_seconds``."""
        raise NotImplementedError


class UsageLedger(ABC):
    """Records usage/cost events and answers spend queries for budgeting."""

    @abstractmethod
    async def record(self, event: UsageEvent) -> None:
        """Persist a usage event."""
        raise NotImplementedError

    @abstractmethod
    async def tenant_cost(self, tenant_id: str) -> Decimal:
        """Return the total USD spend recorded for ``tenant_id``."""
        raise NotImplementedError


class Sleeper(ABC):
    """An awaitable delay — injected so retry backoff is deterministic in tests."""

    @abstractmethod
    async def sleep(self, seconds: float) -> None:
        """Suspend for ``seconds``."""
        raise NotImplementedError
