"""Circuit breaker — stop hammering a failing provider.

If a provider is down, retrying every request wastes time and money and slows the
whole service. A **circuit breaker** watches failures: after too many in a row it
"opens" and short-circuits calls (fail fast / skip to fallback) for a cool-down
period. Then it goes "half-open" to test one probe request; success closes it,
failure re-opens it.

```
 CLOSED --(failures ≥ threshold)--> OPEN --(cool-down elapsed)--> HALF_OPEN
   ^                                                                  |
   └────────────────(probe succeeds)──────────────────────────────────┘
                     (probe fails → back to OPEN)
```

State is in-memory and per-provider. Time comes from the injected :class:`Clock`,
so behaviour is deterministic under test.
"""

from __future__ import annotations

from enum import StrEnum

from complianceiq.domain.ports.clock import Clock


class CircuitState(StrEnum):
    """The three states of a circuit breaker."""

    CLOSED = "closed"  # healthy: calls allowed
    OPEN = "open"  # failing: calls short-circuited
    HALF_OPEN = "half_open"  # probing: one trial call allowed


class CircuitBreaker:
    """A per-provider failure circuit breaker."""

    def __init__(self, clock: Clock, *, failure_threshold: int, reset_seconds: float) -> None:
        """Args:
        clock: Time source (injected for determinism).
        failure_threshold: Consecutive failures that open the circuit.
        reset_seconds: Cool-down before an open circuit becomes half-open.
        """
        self._clock = clock
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """The current (possibly time-updated) state."""
        self._maybe_half_open()
        return self._state

    def allow(self) -> bool:
        """Whether a call may proceed right now.

        Allowed when CLOSED or HALF_OPEN; blocked when OPEN and still cooling down.
        """
        self._maybe_half_open()
        return self._state is not CircuitState.OPEN

    def record_success(self) -> None:
        """Reset to healthy after a successful call."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Register a failure; open the circuit if the threshold is reached."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock.now().timestamp()

    def _maybe_half_open(self) -> None:
        """Transition OPEN → HALF_OPEN once the cool-down has elapsed."""
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            elapsed = self._clock.now().timestamp() - self._opened_at
            if elapsed >= self._reset_seconds:
                self._state = CircuitState.HALF_OPEN
