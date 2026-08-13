"""Tests for retry with exponential backoff and jitter."""

from __future__ import annotations

import pytest

from complianceiq.application.gateway.retry import RetryPolicy, run_with_retry
from complianceiq.domain.exceptions import ProviderError, ValidationError
from tests.fakes import RecordingSleeper


def test_delay_exponential_without_jitter() -> None:
    policy = RetryPolicy(max_retries=5, base_delay_seconds=0.5, max_delay_seconds=100, jitter=False)
    assert policy.delay_for(1, rand=0.0) == 0.5
    assert policy.delay_for(2, rand=0.0) == 1.0
    assert policy.delay_for(3, rand=0.0) == 2.0


def test_delay_is_capped() -> None:
    policy = RetryPolicy(
        max_retries=10, base_delay_seconds=1.0, max_delay_seconds=4.0, jitter=False
    )
    assert policy.delay_for(10, rand=0.0) == 4.0  # would be 512 uncapped


def test_full_jitter_scales_by_rand() -> None:
    policy = RetryPolicy(max_retries=5, base_delay_seconds=2.0, max_delay_seconds=100, jitter=True)
    # attempt 1 cap = 2.0; with rand=0.5 → 1.0
    assert policy.delay_for(1, rand=0.5) == 1.0
    assert policy.delay_for(1, rand=0.0) == 0.0


async def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    async def operation() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ProviderError("transient")
        return "ok"

    sleeper = RecordingSleeper()
    policy = RetryPolicy(max_retries=3, base_delay_seconds=0.1, max_delay_seconds=1.0)
    result = await run_with_retry(
        operation, policy=policy, sleeper=sleeper, retry_on=(ProviderError,), rand=lambda: 0.0
    )
    assert result == "ok"
    assert calls["n"] == 3
    assert len(sleeper.delays) == 2  # two backoffs before the third success


async def test_exhausts_and_raises_last_error() -> None:
    async def operation() -> str:
        raise ProviderError("always")

    sleeper = RecordingSleeper()
    policy = RetryPolicy(max_retries=2, base_delay_seconds=0.1, max_delay_seconds=1.0)
    with pytest.raises(ProviderError):
        await run_with_retry(
            operation, policy=policy, sleeper=sleeper, retry_on=(ProviderError,), rand=lambda: 0.0
        )
    assert len(sleeper.delays) == 2  # max_retries backoffs


async def test_non_retryable_propagates_immediately() -> None:
    async def operation() -> str:
        raise ValidationError("bad")

    sleeper = RecordingSleeper()
    policy = RetryPolicy(max_retries=5, base_delay_seconds=0.1, max_delay_seconds=1.0)
    with pytest.raises(ValidationError):
        await run_with_retry(
            operation, policy=policy, sleeper=sleeper, retry_on=(ProviderError,), rand=lambda: 0.0
        )
    assert sleeper.delays == []  # never retried
