"""Tests for the in-memory gateway adapters (rate limiter, cache, ledger)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from complianceiq.domain.exceptions import RateLimitError
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.responses import Completion, TokenUsage
from complianceiq.domain.llm.usage import UsageEvent
from complianceiq.infrastructure.gateway.cache import InMemoryResponseCache
from complianceiq.infrastructure.gateway.ledger import InMemoryUsageLedger
from complianceiq.infrastructure.gateway.rate_limiter import InMemoryRateLimiter
from tests.fakes import MutableClock


def _completion() -> Completion:
    return Completion(
        text="x",
        provider=ProviderName.FAKE,
        model_id="m",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
    )


# --- rate limiter ---


async def test_rate_limiter_allows_then_blocks_then_refills() -> None:
    clock = MutableClock()
    limiter = InMemoryRateLimiter(clock, per_minute=60, burst=1)  # 1 token, refill 1/sec
    await limiter.acquire("tenant-a")
    with pytest.raises(RateLimitError):
        await limiter.acquire("tenant-a")
    clock.advance(1)  # one token refills
    await limiter.acquire("tenant-a")  # ok again


async def test_rate_limiter_is_per_key() -> None:
    clock = MutableClock()
    limiter = InMemoryRateLimiter(clock, per_minute=60, burst=1)
    await limiter.acquire("tenant-a")
    await limiter.acquire("tenant-b")  # separate bucket, not blocked


# --- cache ---


async def test_cache_set_get_and_ttl_expiry() -> None:
    clock = MutableClock()
    cache = InMemoryResponseCache(clock)
    await cache.set("k", _completion(), ttl_seconds=10)
    assert (await cache.get("k")) is not None
    clock.advance(11)
    assert (await cache.get("k")) is None  # expired


async def test_cache_non_positive_ttl_disables_entry() -> None:
    cache = InMemoryResponseCache(MutableClock())
    await cache.set("k", _completion(), ttl_seconds=0)
    assert (await cache.get("k")) is None


# --- ledger ---


async def test_ledger_accumulates_cost_and_tokens() -> None:
    ledger = InMemoryUsageLedger()
    event = UsageEvent(
        tenant_id="tenant-a",
        feature="enrich",
        provider=ProviderName.FAKE,
        model_id="m",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        cost_usd=Decimal("0.01"),
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await ledger.record(event)
    await ledger.record(event)
    assert await ledger.tenant_cost("tenant-a") == Decimal("0.02")
    assert ledger.total_tokens("tenant-a") == 30
    assert len(ledger.events()) == 2
    assert await ledger.tenant_cost("unknown") == Decimal(0)
