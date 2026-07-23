"""Health-probe port and result types.

Readiness means "every dependency this service needs is reachable". Each
dependency (database, vector store, LLM provider, Core API) is expressed as a
:class:`HealthProbe`; the readiness endpoint aggregates them. Modelling probes as
a port lets the application decide readiness policy while infrastructure supplies
the concrete checks — and lets tests inject fake probes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class HealthResult(FrozenModel):
    """The outcome of probing one dependency.

    Attributes:
        name: Stable name of the probed dependency.
        healthy: Whether the dependency is currently usable.
        detail: Short, non-sensitive status detail for diagnostics.
    """

    name: NonEmptyStr
    healthy: bool
    detail: str = ""


class HealthProbe(ABC):
    """A single, named dependency health check."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier of the dependency this probe checks."""
        raise NotImplementedError

    @abstractmethod
    async def check(self) -> HealthResult:
        """Probe the dependency and return its current health.

        Implementations must never raise for an *expected* unhealthy state —
        they return ``healthy=False`` with a safe detail instead — so the
        readiness aggregator can report on all dependencies at once.
        """
        raise NotImplementedError
