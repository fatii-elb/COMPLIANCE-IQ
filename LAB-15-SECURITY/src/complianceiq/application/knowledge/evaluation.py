"""Retrieval evaluation — measure the "R" of RAG in isolation.

When an answer is wrong, the first question is always: *did retrieval even find
the right sources?* Evaluating retrieval separately from generation lets us answer
that. Given a golden set of queries with their known-relevant control ids, we
compute standard information-retrieval metrics:

- **recall@k** — of the relevant chunks, how many did we retrieve? (Did we find
  them at all?)
- **precision@k** — of what we retrieved, how much was relevant? (How much noise?)
- **MRR** (Mean Reciprocal Rank) — how high up was the first relevant hit?
- **hit-rate** — fraction of queries with at least one relevant hit.

This harness is pure orchestration over the retriever, so it runs offline against
the fake embedder in CI.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.domain._base import FrozenModel
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.knowledge.queries import RetrievalQuery


class RetrievalEvalCase(FrozenModel):
    """One golden retrieval example.

    Attributes:
        query: The query text.
        expected_control_ids: Control ids considered relevant for this query.
        filter: Optional metadata filter to apply (e.g. a framework).
    """

    query: str
    expected_control_ids: list[str] = Field(min_length=1)
    filter: MetadataFilter = Field(default_factory=MetadataFilter)


class RetrievalMetrics(FrozenModel):
    """Aggregate retrieval metrics over a golden set.

    Attributes:
        k: The top-k used.
        cases: Number of evaluated cases.
        recall_at_k: Mean recall@k.
        precision_at_k: Mean precision@k.
        mrr: Mean reciprocal rank of the first relevant hit.
        hit_rate: Fraction of cases with at least one relevant hit.
    """

    k: int
    cases: int
    recall_at_k: float
    precision_at_k: float
    mrr: float
    hit_rate: float


async def evaluate_retrieval(
    retriever: HybridRetriever, cases: Sequence[RetrievalEvalCase], *, k: int = 5
) -> RetrievalMetrics:
    """Run the retriever over ``cases`` and compute aggregate metrics."""
    if not cases:
        return RetrievalMetrics(
            k=k, cases=0, recall_at_k=0.0, precision_at_k=0.0, mrr=0.0, hit_rate=0.0
        )

    recall_sum = 0.0
    precision_sum = 0.0
    rr_sum = 0.0
    hits = 0

    for case in cases:
        result = await retriever.retrieve(
            RetrievalQuery(text=case.query, top_k=k, filter=case.filter)
        )
        retrieved_ids = [scored.chunk.metadata.control_id for scored in result.chunks]
        expected = set(case.expected_control_ids)

        relevant_retrieved = [cid for cid in retrieved_ids if cid in expected]
        recall_sum += len(set(relevant_retrieved)) / len(expected)
        precision_sum += (len(relevant_retrieved) / len(retrieved_ids)) if retrieved_ids else 0.0

        first_rank = next(
            (i for i, cid in enumerate(retrieved_ids, start=1) if cid in expected), None
        )
        if first_rank is not None:
            rr_sum += 1.0 / first_rank
            hits += 1

    n = len(cases)
    return RetrievalMetrics(
        k=k,
        cases=n,
        recall_at_k=recall_sum / n,
        precision_at_k=precision_sum / n,
        mrr=rr_sum / n,
        hit_rate=hits / n,
    )
