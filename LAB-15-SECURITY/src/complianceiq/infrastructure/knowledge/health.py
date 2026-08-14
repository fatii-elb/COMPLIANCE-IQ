"""Readiness probe for the knowledge base's vector store.

Registered with the Phase-1 ``ReadinessService`` so ``/health/ready`` reflects the
retrieval subsystem too. It reports the number of indexed chunks; an empty store
is still "ready" (the service can run) but the detail makes an un-ingested corpus
visible to operators.
"""

from __future__ import annotations

from complianceiq.domain.ports.health import HealthProbe, HealthResult
from complianceiq.domain.ports.knowledge import VectorStore


class VectorStoreHealthProbe(HealthProbe):
    """Reports vector-store reachability and chunk count."""

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    @property
    def name(self) -> str:
        return "knowledge:vector_store"

    async def check(self) -> HealthResult:
        try:
            count = await self._vector_store.count()
        except Exception as exc:
            return HealthResult(
                name=self.name, healthy=False, detail=f"store error: {type(exc).__name__}"
            )
        return HealthResult(name=self.name, healthy=True, detail=f"{count} chunks indexed")
