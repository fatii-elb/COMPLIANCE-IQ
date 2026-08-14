"""Tests for the Phase-7 mapping and financial graphs (offline, deterministic)."""

from __future__ import annotations

from decimal import Decimal

from complianceiq.application.graphs.financial import FinancialGraph
from complianceiq.application.graphs.mapping import MappingGraph
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT
from complianceiq.domain.value_objects.enums import Framework, RiskDomain, Severity
from tests.ai_helpers import (
    AUTH,
    FakeGateway,
    build_retrieval_stack,
    load_prompt_registry,
    make_finding,
)


async def _mapping_graph(gateway: FakeGateway) -> MappingGraph:
    retriever, assembler, config = await build_retrieval_stack()
    return MappingGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )


# ------------------------------- mapping ----------------------------------- #


async def test_mapping_produces_cross_framework_equivalents() -> None:
    gateway = FakeGateway(reply="SOC 2 CC6.1 maps to NIST PR.AA-01 [1].")
    graph = await _mapping_graph(gateway)
    # The finding is SOC 2; the corpus is NIST, so the retrieved controls are all
    # cross-framework equivalents.
    finding = make_finding(framework=Framework.SOC_2, control_id="CC6.1")

    mapping = await graph.run(finding, AUTH)

    assert mapping.source_framework is Framework.SOC_2
    assert mapping.citation_verified is True
    assert mapping.mappings, "expected cross-framework equivalents"
    assert all(m.framework is not Framework.SOC_2 for m in mapping.mappings)


async def test_mapping_excludes_same_framework_controls() -> None:
    # A NIST finding over a NIST-only corpus yields no *cross*-framework mappings,
    # even though citations verify.
    gateway = FakeGateway(reply="Related NIST controls [1].")
    graph = await _mapping_graph(gateway)
    finding = make_finding(framework=Framework.NIST_CSF)

    mapping = await graph.run(finding, AUTH)
    assert mapping.citation_verified is True
    assert mapping.mappings == []  # all retrieved controls share the source framework


async def test_mapping_abstain_node_returns_not_covered() -> None:
    gateway = FakeGateway()
    graph = await _mapping_graph(gateway)
    out = await graph._abstain({"finding": make_finding()})
    mapping = out["mapping"]
    assert mapping.summary == ABSTENTION_TEXT
    assert mapping.mappings == []
    assert mapping.citation_verified is False
    assert gateway.requests == []  # abstain never calls the model


# ------------------------------ financial ---------------------------------- #


async def test_financial_numbers_are_deterministic_not_from_model() -> None:
    # The model tries to inject a bogus figure; the numbers must ignore it.
    gateway = FakeGateway(reply="I think the exposure is around 9,999,999,999 MAD.")
    graph = FinancialGraph(gateway=gateway, prompts=load_prompt_registry())
    finding = make_finding(severity=Severity.CRITICAL, domain=RiskDomain.STORAGE)

    assessment = await graph.run(finding, AUTH)
    # CRITICAL base 750000–4000000 × 1.3 (storage) = 975000–5200000, model-independent.
    assert assessment.min_mad == Decimal("975000")
    assert assessment.max_mad == Decimal("5200000")
    assert assessment.finding_id == finding.id
    assert assessment.assumptions


async def test_financial_falls_back_when_model_is_empty() -> None:
    gateway = FakeGateway(reply="")
    graph = FinancialGraph(gateway=gateway, prompts=load_prompt_registry())
    assessment = await graph.run(make_finding(), AUTH)
    assert assessment.rationale  # non-empty fallback rationale
    assert assessment.min_mad >= 0
    assert assessment.max_mad >= assessment.min_mad
