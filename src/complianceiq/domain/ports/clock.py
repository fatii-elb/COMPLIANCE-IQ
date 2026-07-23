"""The :class:`Clock` port.

Time is an external dependency like any other. Injecting a clock instead of
calling ``datetime.now()`` directly makes time-dependent logic deterministic in
tests (a frozen clock) and keeps the domain free of hidden I/O. The system
adapter lives in the infrastructure layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Abstract source of the current time.

    Implementations must always return timezone-aware UTC datetimes so that
    every timestamp in the system is unambiguous.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        raise NotImplementedError
