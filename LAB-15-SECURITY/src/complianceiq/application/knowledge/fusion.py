"""Rank fusion and diversity selection (pure functions).

Two classic RAG techniques live here:

- **Reciprocal Rank Fusion (RRF)** merges the semantic and lexical result lists
  into one ranking. It uses only *ranks* (not raw scores), which makes it robust
  to the two retrievers producing scores on totally different scales — a common,
  subtle problem. A chunk that ranks highly in *both* lists rises to the top.

- **Maximal Marginal Relevance (MMR)** trims the final selection so it isn't five
  near-duplicate chunks. It greedily picks chunks that are relevant *and*
  different from what's already chosen, balancing the two with ``lambda``.
"""

from __future__ import annotations

from collections.abc import Sequence

from complianceiq.domain.knowledge.chunks import RetrievalSource, ScoredChunk
from complianceiq.domain.knowledge.similarity import jaccard_similarity


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[ScoredChunk]], *, rrf_k: int = 60
) -> list[ScoredChunk]:
    """Fuse several ranked lists into one via Reciprocal Rank Fusion.

    Each chunk earns ``1 / (rrf_k + rank)`` from every list it appears in (rank is
    1-based). Contributions are summed per chunk id, so agreement across
    retrievers wins. Returns chunks tagged ``HYBRID``, highest fused score first.
    """
    fused_scores: dict[str, float] = {}
    chunk_by_id: dict[str, ScoredChunk] = {}

    for ranked in ranked_lists:
        for rank, scored in enumerate(ranked, start=1):
            chunk_id = scored.chunk.id
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            chunk_by_id.setdefault(chunk_id, scored)

    ordered_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
    return [
        ScoredChunk(
            chunk=chunk_by_id[cid].chunk,
            score=fused_scores[cid],
            retriever=RetrievalSource.HYBRID,
        )
        for cid in ordered_ids
    ]


def mmr_select(
    candidates: Sequence[ScoredChunk], *, lambda_param: float, top_k: int
) -> list[ScoredChunk]:
    """Select up to ``top_k`` chunks balancing relevance and diversity (MMR).

    Args:
        candidates: Ranked candidates (higher ``score`` = more relevant).
        lambda_param: 1.0 = pure relevance; 0.0 = pure diversity.
        top_k: Maximum number to select.

    Returns:
        The selected chunks, in selection order, preserving their scores/retriever.
    """
    if not candidates:
        return []

    # Normalise relevance to [0, 1] so it mixes stably with the [0, 1] similarity.
    scores = [c.score for c in candidates]
    lo, hi = min(scores), max(scores)
    span = hi - lo

    def relevance(index: int) -> float:
        return (candidates[index].score - lo) / span if span else 1.0

    remaining = list(range(len(candidates)))
    selected: list[int] = []

    while remaining and len(selected) < top_k:
        best_index = remaining[0]
        best_value = float("-inf")
        for index in remaining:
            if selected:
                max_sim = max(
                    jaccard_similarity(candidates[index].chunk.content, candidates[s].chunk.content)
                    for s in selected
                )
            else:
                max_sim = 0.0
            mmr = lambda_param * relevance(index) - (1.0 - lambda_param) * max_sim
            if mmr > best_value:
                best_value = mmr
                best_index = index
        selected.append(best_index)
        remaining.remove(best_index)

    return [candidates[i] for i in selected]
