"""Lexical reranker (deterministic default) implementing the Reranker port.

**Reranking** takes a shortlist of candidate chunks and re-scores them by *deep*
relevance to the query, fixing ordering mistakes the first-pass retrievers made.
The gold standard is a **cross-encoder** — a model that reads the query and each
chunk *together* and outputs a relevance score — but that needs a heavy ML model
and a GPU, which we don't want in the default offline path.

So the default is this deterministic **lexical reranker**: it scores each
candidate by *query-term coverage* (what fraction of the query's distinct terms
appear in the chunk). It's simple, free, and offline, and it plugs into the same
:class:`Reranker` port, so a real cross-encoder adapter can replace it later with
zero changes to the retriever.
"""

from __future__ import annotations

from collections.abc import Sequence

from complianceiq.domain.knowledge.chunks import RetrievalSource, ScoredChunk
from complianceiq.domain.knowledge.similarity import token_set
from complianceiq.domain.ports.knowledge import Reranker


class LexicalReranker(Reranker):
    """Re-scores candidates by the fraction of query terms they cover."""

    async def rerank(
        self, *, query: str, candidates: Sequence[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]:
        query_terms = token_set(query)
        if not query_terms:
            return list(candidates[:top_k])

        rescored: list[ScoredChunk] = []
        for candidate in candidates:
            chunk_terms = token_set(candidate.chunk.content)
            coverage = len(query_terms & chunk_terms) / len(query_terms)
            rescored.append(
                ScoredChunk(
                    chunk=candidate.chunk,
                    score=coverage,
                    retriever=RetrievalSource.RERANK,
                )
            )
        rescored.sort(key=lambda item: item.score, reverse=True)
        return rescored[:top_k]
