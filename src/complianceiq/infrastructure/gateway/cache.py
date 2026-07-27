"""In-memory TTL cache of completions.

Implements the :class:`ResponseCache` port with a simple time-to-live map. Keys
are produced by the gateway's tenant-scoped, content-addressed key builder, so
this store never needs to know about tenancy — it just maps opaque keys to
completions with an expiry.

A Redis-backed adapter (shared across instances) implements the same port later;
the gateway is unchanged. Time comes from the injected :class:`Clock`.
"""

from __future__ import annotations

from dataclasses import dataclass

from complianceiq.domain.llm.responses import Completion
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.gateway import ResponseCache


@dataclass
class _Entry:
    value: Completion
    expires_at: float


class InMemoryResponseCache(ResponseCache):
    """A per-key TTL cache for completions."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    async def get(self, key: str) -> Completion | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._clock.now().timestamp() >= entry.expires_at:
            # Lazily evict on read; expired entries never serve stale data.
            del self._entries[key]
            return None
        return entry.value

    async def set(self, key: str, value: Completion, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return  # a non-positive TTL disables caching for this entry
        expires_at = self._clock.now().timestamp() + ttl_seconds
        self._entries[key] = _Entry(value=value, expires_at=expires_at)
