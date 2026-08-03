"""Hybrid retriever — the core of the RAG "R" (Retrieval).

Combines the strengths of two complementary search methods and then sharpens the
result:

1. **Semantic search** (vector similarity) finds chunks with *similar meaning*
   even when they share no words ("public bucket" ↔ "world-readable storage").
2. **Lexical search** (keywords) nails *exact terms and identifiers* semantic
   search can blur ("PR.AC-4", "Loi 05-20 article 23").
3. **Reciprocal Rank Fusion** merges the two rankings robustly.
4. **Reranking** re-scores the fused candidates by deep query relevance.
5. **MMR** trims to a diverse, non-redundant final set.
6. A **score threshold** enforces "abstain when nothing is relevant": if nothing
   clears it, the result is empty and the caller must decline to answer (rule 3).

Metadata filters are applied *inside* each search, so irrelevant frameworks are
never ranked in the first place.
"""

from __future__ import annotations

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.fusion import mmr_select, reciprocal_rank_fusion
from complianceiq.domain.knowledge.chunks import ScoredChunk
from complianceiq.domain.knowledge.queries import RetrievalQuery, RetrievalResult
from complianceiq.domain.ports.knowledge import Embedder, KeywordIndex, Reranker, VectorStore


class HybridRetriever:
    """Retrieves ranked corpus chunks for a query via hybrid search + rerank."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        vector_store: VectorStore,
        keyword_index: KeywordIndex,
        reranker: Reranker,
        config: RetrievalConfig,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._keyword_index = keyword_index
        self._reranker = reranker
        self._config = config

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Run the full hybrid retrieval pipeline for ``query``."""
        # 1) Embed the query (records the embedding model for the store guard).
        embeddings = await self._embedder.embed([query.text])
        embedding = embeddings[0]

        candidate_k = query.top_k * self._config.candidate_multiplier

        # 2) Semantic + 3) lexical searches, both metadata-pre-filtered.
        semantic = await self._vector_store.search(
            embedding=embedding.vector,
            embedding_model=embedding.model_id,
            top_k=candidate_k,
            metadata_filter=query.filter,
        )
        lexical = await self._keyword_index.search(
            text=query.text, top_k=candidate_k, metadata_filter=query.filter
        )

        # 4) Fuse the two rankings.
        fused = reciprocal_rank_fusion([semantic, lexical], rrf_k=self._config.rrf_k)
        if not fused:
            return RetrievalResult(query=query.text, chunks=[], embedding_model=embedding.model_id)

        # 5) Rerank the top fused candidates by deep relevance.
        reranked = await self._reranker.rerank(
            query=query.text,
            candidates=fused[: self._config.rerank_top_k],
            top_k=self._config.rerank_top_k,
        )

        # 6) Diversify (MMR) down to top_k, then apply the score threshold.
        selected = mmr_select(reranked, lambda_param=self._config.mmr_lambda, top_k=query.top_k)
        thresholded: list[ScoredChunk] = [
            chunk for chunk in selected if chunk.score >= query.min_score
        ]

        return RetrievalResult(
            query=query.text,
            chunks=thresholded,
            embedding_model=embedding.model_id,
        )
