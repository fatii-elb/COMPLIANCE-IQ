"""Retrieval/ingestion configuration value object.

Groups the tunable knobs of the RAG pipeline so an operator adjusts behaviour via
configuration, not code. The composition root builds this from :class:`Settings`.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel


class RetrievalConfig(FrozenModel):
    """Tunable parameters for hybrid retrieval and context assembly.

    Attributes:
        candidate_multiplier: Each retriever fetches ``top_k × multiplier``
            candidates before fusion/rerank, so good chunks aren't lost early.
        rerank_top_k: How many fused candidates to pass through the reranker.
        rrf_k: The Reciprocal Rank Fusion constant (higher = flatter weighting).
        mmr_lambda: Relevance/diversity trade-off for MMR (1 = pure relevance,
            0 = pure diversity).
        context_token_budget: Max approximate tokens of assembled context.
        chunk_max_tokens: Soft cap per chunk during ingestion.
        corpus_version: The active corpus version tag.
    """

    candidate_multiplier: int = Field(default=4, ge=1, le=20)
    rerank_top_k: int = Field(default=20, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1)
    mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    context_token_budget: int = Field(default=2000, ge=128)
    chunk_max_tokens: int = Field(default=400, ge=64)
    corpus_version: str = "v1"
