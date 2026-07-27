"""Retry with exponential backoff and jitter.

Transient upstream failures (a blip, a 503, a timeout) should be retried a few
times before giving up. Two refinements matter:

- **Exponential backoff:** wait longer after each failure (0.5s, 1s, 2s…) so we
  don't hammer a struggling provider.
- **Jitter:** randomise the delay so many clients retrying at once don't
  synchronise into a "thundering herd" that repeatedly spikes the provider.

The delay uses *full jitter*: a random value in ``[0, capped_backoff)``. Both the
wait (:class:`Sleeper`) and the randomness are injected, so retry behaviour is
fully deterministic under test.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.ports.gateway import Sleeper

T = TypeVar("T")


class RetryPolicy(FrozenModel):
    """Parameters for retrying a retryable operation.

    Attributes:
        max_retries: Extra attempts after the first (0 = no retries).
        base_delay_seconds: Backoff base; delay grows as base·2^(attempt-1).
        max_delay_seconds: Cap on any single delay before jitter.
        jitter: Whether to apply full jitter.
    """

    max_retries: int = Field(ge=0)
    base_delay_seconds: float = Field(gt=0)
    max_delay_seconds: float = Field(gt=0)
    jitter: bool = True

    def delay_for(self, attempt: int, rand: float) -> float:
        """Compute the backoff delay for a 1-based ``attempt``.

        Args:
            attempt: The retry attempt number (1 = first retry).
            rand: A value in ``[0, 1)`` used for jitter (injected for determinism).
        """
        exponential: float = self.base_delay_seconds * float(2 ** (attempt - 1))
        capped: float = min(exponential, self.max_delay_seconds)
        return capped * rand if self.jitter else capped


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    sleeper: Sleeper,
    retry_on: tuple[type[Exception], ...],
    rand: Callable[[], float] = random.random,
) -> T:
    """Run ``operation``, retrying on ``retry_on`` errors per ``policy``.

    Args:
        operation: A zero-arg coroutine factory (called fresh each attempt).
        policy: Backoff/retry parameters.
        sleeper: Injected delay mechanism.
        retry_on: Exception types considered retryable. Anything else propagates
            immediately (we never retry a validation or safety error).
        rand: Randomness source for jitter.

    Returns:
        The operation's result.

    Raises:
        The last retryable exception if all attempts fail, or any non-retryable
        exception immediately.
    """
    attempt = 0
    while True:
        try:
            return await operation()
        except retry_on as exc:
            attempt += 1
            if attempt > policy.max_retries:
                raise exc
            await sleeper.sleep(policy.delay_for(attempt, rand()))
