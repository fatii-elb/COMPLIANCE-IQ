"""Embedder adapter over the AI gateway.

The RAG pipeline needs to turn text into vectors. Rather than call a provider
directly, it goes through the Phase-2 :class:`AIGateway`, so embedding calls get
the same routing, rate limiting, budgeting, and cost accounting as every other
model call. This adapter implements the domain :class:`Embedder` port by wrapping
the gateway with a system identity (corpus ingestion is a platform operation, not
a tenant action).
"""

from __future__ import annotations

from collections.abc import Sequence

from complianceiq.application.gateway.ai_gateway import AIGateway
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.llm.responses import EmbeddingResult
from complianceiq.domain.ports.knowledge import Embedder

#: Tenant used to attribute platform-level embedding cost (corpus ingestion and
#: system queries). Distinct from any customer tenant.
SYSTEM_TENANT = "_platform"


class GatewayEmbedder(Embedder):
    """Fulfils the :class:`Embedder` port using the AI gateway's embedding model."""

    def __init__(self, gateway: AIGateway, *, feature: str = "knowledge") -> None:
        self._gateway = gateway
        self._feature = feature
        self._auth = AuthContext(sub="system", tenant_id=SYSTEM_TENANT)

    async def embed(self, texts: Sequence[str]) -> list[EmbeddingResult]:
        """Embed texts via the gateway (routing to the configured embedding model)."""
        return await self._gateway.embed(texts, self._auth, feature=self._feature)
