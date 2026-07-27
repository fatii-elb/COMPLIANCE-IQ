"""In-memory token-bucket rate limiter (per key/tenant).

A **token bucket** holds up to ``capacity`` tokens and refills at a steady rate.
Each call consumes a token; if the bucket is empty, the call is rejected. This
allows short bursts (up to capacity) while bounding the sustained rate — the
standard, fair way to rate-limit.

This adapter keeps buckets in process memory, which is correct for a single
instance. A Redis-backed adapter (shared across instances) implements the same
:class:`RateLimiter` port in a later phase; the gateway never changes.

Time comes from the injected :class:`Clock`, so tests are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from complianceiq.domain.exceptions import RateLimitError
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.gateway import RateLimiter


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class InMemoryRateLimiter(RateLimiter):
    """Per-key token-bucket rate limiter."""

    def __init__(self, clock: Clock, *, per_minute: int, burst: int | None = None) -> None:
        """Args:
        clock: Time source (injected for determinism).
        per_minute: Sustained allowance per key, per minute.
        burst: Bucket capacity (max burst). Defaults to ``per_minute``.
        """
        self._clock = clock
        self._refill_per_second = per_minute / 60.0
        self._capacity = float(burst if burst is not None else per_minute)
        self._buckets: dict[str, _Bucket] = {}

    async def acquire(self, key: str, *, cost: int = 1) -> None:
        now = self._clock.now().timestamp()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self._capacity, updated_at=now)
            self._buckets[key] = bucket
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
            bucket.updated_at = now

        if bucket.tokens < cost:
            raise RateLimitError(
                "rate limit exceeded",
                details={"key": key, "retry_after_seconds": self._retry_after(bucket, cost)},
            )
        bucket.tokens -= cost

    def _retry_after(self, bucket: _Bucket, cost: int) -> float:
        """Seconds until enough tokens have refilled to serve ``cost``."""
        if self._refill_per_second <= 0:
            return 0.0
        deficit = cost - bucket.tokens
        return round(max(0.0, deficit) / self._refill_per_second, 3)
