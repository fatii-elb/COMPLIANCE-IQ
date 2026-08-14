"""Knowledge-base use cases — ingestion, hybrid retrieval, context assembly, eval.

Public surface:

- :class:`IngestionService` — chunk → embed → store (idempotent, versioned).
- :class:`HybridRetriever` — semantic + lexical + fusion + rerank + MMR + threshold.
- :class:`ContextAssembler` — pack retrieved chunks into a cited, budgeted block.
- :class:`GatewayEmbedder` — the :class:`Embedder` port fulfilled via the gateway.
- :class:`RetrievalConfig` — tunable pipeline parameters.
- :func:`evaluate_retrieval` — measure retrieval quality against a golden set.

All of it depends only on domain ports and value objects, so the whole pipeline
runs and is tested offline with the fake embedder and in-memory stores.
"""

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.embedder import SYSTEM_TENANT, GatewayEmbedder
from complianceiq.application.knowledge.evaluation import (
    RetrievalEvalCase,
    RetrievalMetrics,
    evaluate_retrieval,
)
from complianceiq.application.knowledge.fusion import mmr_select, reciprocal_rank_fusion
from complianceiq.application.knowledge.ingestion import IngestionReport, IngestionService
from complianceiq.application.knowledge.retrieval import HybridRetriever

__all__ = [
    "SYSTEM_TENANT",
    "ContextAssembler",
    "GatewayEmbedder",
    "HybridRetriever",
    "IngestionReport",
    "IngestionService",
    "RetrievalConfig",
    "RetrievalEvalCase",
    "RetrievalMetrics",
    "evaluate_retrieval",
    "mmr_select",
    "reciprocal_rank_fusion",
]
