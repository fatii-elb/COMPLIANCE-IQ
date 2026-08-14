"""Tests for the system clock adapter."""

from __future__ import annotations

from datetime import UTC

from complianceiq.infrastructure.clock import SystemClock


def test_system_clock_returns_timezone_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == UTC.utcoffset(None)
