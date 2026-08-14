"""Tests for the circuit breaker."""

from __future__ import annotations

from complianceiq.application.gateway.circuit_breaker import CircuitBreaker, CircuitState
from tests.fakes import MutableClock


def _breaker(clock: MutableClock) -> CircuitBreaker:
    return CircuitBreaker(clock, failure_threshold=3, reset_seconds=30.0)


def test_starts_closed_and_allows() -> None:
    breaker = _breaker(MutableClock())
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow() is True


def test_opens_after_threshold_failures() -> None:
    breaker = _breaker(MutableClock())
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow() is False


def test_half_opens_after_reset_window() -> None:
    clock = MutableClock()
    breaker = _breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.allow() is False
    clock.advance(31)  # past the 30s cool-down
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.allow() is True


def test_success_closes_and_resets() -> None:
    clock = MutableClock()
    breaker = _breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    # counter reset: two more failures should not open it yet
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
