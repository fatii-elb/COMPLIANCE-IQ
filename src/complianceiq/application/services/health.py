"""Readiness use case.

*Liveness* asks "is the process up?" — a trivially cheap check. *Readiness* asks
"can this process actually serve traffic right now?", which means every hard
dependency must be reachable. Orchestrators use readiness to decide whether to
route traffic; a failing readiness check pulls the instance out of rotation
without killing it.

The service aggregates a set of :class:`HealthProbe` ports. In Phase 1 there are
no external dependencies yet, so the probe set may be empty and readiness is
trivially healthy — but the mechanism exists so Phase 3/6 dependencies (vector
store, database, provider, Core API) plug in without touching the endpoint.
"""

from __future__ import annotations

import asyncio

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.ports.health import HealthProbe, HealthResult


class ReadinessReport(FrozenModel):
    """Aggregate readiness across all probed dependencies.

    Attributes:
        ready: True only if every probe reported healthy.
        components: The individual probe results, for diagnostics.
    """

    ready: bool
    components: list[HealthResult]


class ReadinessService:
    """Aggregates dependency health probes into a single readiness verdict."""

    def __init__(self, probes: list[HealthProbe]) -> None:
        """Args:
        probes: The dependency probes to evaluate. May be empty.
        """
        self._probes = probes

    async def check(self) -> ReadinessReport:
        """Run all probes concurrently and combine their results.

        Probes are contractually forbidden from raising on an *expected*
        unhealthy state, so a single misbehaving probe cannot abort the whole
        readiness check for the others; any unexpected exception is still
        surfaced as an unhealthy component rather than crashing the endpoint.
        """
        if not self._probes:
            return ReadinessReport(ready=True, components=[])

        raw = await asyncio.gather(
            *(probe.check() for probe in self._probes),
            return_exceptions=True,
        )

        components: list[HealthResult] = []
        for probe, outcome in zip(self._probes, raw, strict=True):
            if isinstance(outcome, HealthResult):
                components.append(outcome)
            else:
                components.append(
                    HealthResult(
                        name=probe.name,
                        healthy=False,
                        detail="probe raised unexpectedly",
                    )
                )

        return ReadinessReport(
            ready=all(component.healthy for component in components),
            components=components,
        )
