"""Tests for the grounding evaluation harness."""

from __future__ import annotations

from complianceiq.application.evaluation import GroundingEvalCase, GroundingEvaluator
from complianceiq.application.graphs.enrichment import EnrichmentGraph
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import Framework
from tests.ai_helpers import (
    AUTH,
    FakeGateway,
    build_retrieval_stack,
    load_prompt_registry,
    make_finding,
)

_AUTH = AuthContext(sub="u", tenant_id="tenant-a")


def _cite(control_id: str) -> Citation:
    return Citation(
        framework=Framework.NIST_CSF, control_id=control_id, reference=f"{control_id} ref"
    )


def _enriched(finding: Finding, *, control_ids: list[str], verified: bool) -> EnrichedFinding:
    if not control_ids:
        return EnrichedFinding(
            **finding.model_dump(),
            explanation=ABSTENTION_TEXT,
            citations=[],
            citation_verified=False,
        )
    return EnrichedFinding(
        **finding.model_dump(),
        explanation="Grounded explanation [1].",
        citations=[_cite(c) for c in control_ids],
        citation_verified=verified,
    )


async def test_perfect_grounding_scores_100() -> None:
    # Enricher cites exactly the expected control, verified.
    async def enrich(finding: Finding, auth: AuthContext) -> EnrichedFinding:
        return _enriched(finding, control_ids=["PR.AA-01"], verified=True)

    cases = [GroundingEvalCase(finding=make_finding(), expected_control_ids=["PR.AA-01"])]
    metrics = await GroundingEvaluator(enrich).evaluate(cases, _AUTH)
    assert metrics.grounded_rate == 1.0
    assert metrics.citation_precision == 1.0
    assert metrics.citation_recall == 1.0
    assert metrics.abstention_rate == 0.0


async def test_noisy_citations_lower_precision() -> None:
    # Cites the right one plus an extra: precision 0.5, recall 1.0.
    async def enrich(finding: Finding, auth: AuthContext) -> EnrichedFinding:
        return _enriched(finding, control_ids=["PR.AA-01", "XX.99"], verified=True)

    cases = [GroundingEvalCase(finding=make_finding(), expected_control_ids=["PR.AA-01"])]
    metrics = await GroundingEvaluator(enrich).evaluate(cases, _AUTH)
    assert metrics.citation_precision == 0.5
    assert metrics.citation_recall == 1.0


async def test_abstention_is_counted() -> None:
    async def enrich(finding: Finding, auth: AuthContext) -> EnrichedFinding:
        return _enriched(finding, control_ids=[], verified=False)

    cases = [GroundingEvalCase(finding=make_finding(), expected_control_ids=[])]
    metrics = await GroundingEvaluator(enrich).evaluate(cases, _AUTH)
    assert metrics.abstention_rate == 1.0
    assert metrics.grounded_rate == 0.0


async def test_empty_set_yields_zeroed_metrics() -> None:
    async def enrich(finding: Finding, auth: AuthContext) -> EnrichedFinding:
        raise AssertionError("should not be called")

    metrics = await GroundingEvaluator(enrich).evaluate([], _AUTH)
    assert metrics.cases == 0
    assert metrics.grounded_rate == 0.0


async def test_evaluator_runs_against_real_enrichment_graph() -> None:
    # End-to-end: the real enrichment graph over the sample corpus is fully grounded.
    gateway = FakeGateway(reply="Rotate IAM keys within 90 days [1].")
    retriever, assembler, config = await build_retrieval_stack()
    graph = EnrichmentGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )
    cases = [GroundingEvalCase(finding=make_finding(), expected_control_ids=["PR.AA-01"])]
    metrics = await GroundingEvaluator(graph.run).evaluate(cases, AUTH)
    assert metrics.grounded_rate == 1.0
    assert metrics.citation_recall == 1.0  # the expected control is among the citations
