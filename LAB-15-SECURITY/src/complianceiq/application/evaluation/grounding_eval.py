"""Grounding evaluation — score the "G" of a grounded answer.

Given a golden set of findings, each with the control ids that *should* be cited
(or none, when the correct behaviour is to abstain), this harness runs the
enrichment capability and computes:

- **grounded rate** — fraction of answers marked ``citation_verified`` (the
  product's authoritative trust flag).
- **abstention rate** — fraction that correctly declined ("not covered").
- **citation precision** — of the controls we cited, how many were expected?
  (Did we cite noise?)
- **citation recall** — of the expected controls, how many did we cite? (Did we
  miss the right ones?)
- **mean citations** — average number of citations per grounded answer.

It is pure orchestration over an injected ``enrich`` function, so it runs offline
against the fake gateway and sample corpus in CI — the grounding guarantee is
regression-tested, not hoped for.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT

#: An enrich function turns a finding into an EnrichedFinding (a graph or agent).
EnrichFn = Callable[[Finding, AuthContext], Awaitable[EnrichedFinding]]


class GroundingEvalCase(FrozenModel):
    """One golden grounding example.

    Attributes:
        finding: The finding to enrich.
        expected_control_ids: Control ids that a correct answer should cite. Empty
            means the correct behaviour is to abstain (no relevant sources).
    """

    finding: Finding
    expected_control_ids: list[str] = Field(default_factory=list)


class GroundingMetrics(FrozenModel):
    """Aggregate grounding metrics over a golden set."""

    cases: int
    grounded_rate: float
    abstention_rate: float
    citation_precision: float
    citation_recall: float
    mean_citations: float


def _is_abstention(enriched: EnrichedFinding) -> bool:
    return not enriched.citations and enriched.explanation.strip() == ABSTENTION_TEXT


class GroundingEvaluator:
    """Runs enrichment over golden cases and scores grounding."""

    def __init__(self, enrich: EnrichFn) -> None:
        self._enrich = enrich

    async def evaluate(
        self, cases: Sequence[GroundingEvalCase], auth: AuthContext
    ) -> GroundingMetrics:
        """Evaluate ``cases`` and return aggregate grounding metrics."""
        if not cases:
            return GroundingMetrics(
                cases=0,
                grounded_rate=0.0,
                abstention_rate=0.0,
                citation_precision=0.0,
                citation_recall=0.0,
                mean_citations=0.0,
            )

        grounded = 0
        abstained = 0
        precisions: list[float] = []
        recalls: list[float] = []
        citation_counts: list[int] = []

        for case in cases:
            enriched = await self._enrich(case.finding, auth)
            cited = {c.control_id for c in enriched.citations}
            expected = set(case.expected_control_ids)

            if enriched.citation_verified:
                grounded += 1
            if _is_abstention(enriched):
                abstained += 1
                # An abstention is scored only on whether it was expected (below).
            citation_counts.append(len(cited))

            hits = cited & expected
            if cited:
                precisions.append(len(hits) / len(cited))
            if expected:
                recalls.append(len(hits) / len(expected))

        n = len(cases)
        return GroundingMetrics(
            cases=n,
            grounded_rate=grounded / n,
            abstention_rate=abstained / n,
            citation_precision=_mean(precisions),
            citation_recall=_mean(recalls),
            mean_citations=_mean([float(c) for c in citation_counts]),
        )


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
