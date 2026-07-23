"""The system :class:`Clock` adapter.

Implements the domain ``Clock`` port using the real wall clock. Kept in the
infrastructure layer because "reading the current time" is I/O against the
outside world; the domain depends only on the abstraction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from complianceiq.domain.ports.clock import Clock


class SystemClock(Clock):
    """A :class:`Clock` backed by the operating-system clock (UTC)."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        return datetime.now(UTC)
