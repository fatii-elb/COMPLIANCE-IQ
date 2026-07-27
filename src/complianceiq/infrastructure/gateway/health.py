"""Health probe for an LLM provider.

Registered with the Phase 1 :class:`ReadinessService` so ``/health/ready`` now
reflects the AI providers too. The check is intentionally **shallow and free**: it
verifies the adapter is constructed and callable (via a local ``count_tokens``),
without spending money or latency on a live API round-trip on every probe. A
deep, opt-in liveness call can be added where the cost is acceptable.
"""

from __future__ import annotations

from complianceiq.domain.ports.health import HealthProbe, HealthResult
from complianceiq.domain.ports.llm import LLMProvider


class LLMProviderHealthProbe(HealthProbe):
    """A shallow readiness probe for a single provider adapter."""

    def __init__(self, provider: LLMProvider, *, probe_model_id: str = "healthcheck") -> None:
        self._provider = provider
        self._probe_model_id = probe_model_id

    @property
    def name(self) -> str:
        return f"llm:{self._provider.name.value}"

    async def check(self) -> HealthResult:
        try:
            self._provider.count_tokens(self._probe_model_id, "ping")
        except Exception as exc:
            return HealthResult(
                name=self.name, healthy=False, detail=f"adapter error: {type(exc).__name__}"
            )
        return HealthResult(name=self.name, healthy=True, detail="adapter ready (shallow check)")
