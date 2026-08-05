"""Tests for the four LangGraph workflows (offline, deterministic).

Each graph is exercised end-to-end with a fake gateway and the sample corpus, and
the grounding branches (abstain on empty retrieval, citation verification, IaC
safety validation) are asserted directly.
"""

from __future__ import annotations

import pytest

from complianceiq.application.graphs.copilot import CopilotGraph
from complianceiq.application.graphs.enrichment import EnrichmentGraph
from complianceiq.application.graphs.remediation import RemediationGraph
from complianceiq.application.graphs.report import ReportGraph
from complianceiq.domain.exceptions import WorkflowError
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT
from complianceiq.domain.value_objects.enums import Framework
from tests.ai_helpers import (
    AUTH,
    FakeGateway,
    build_retrieval_stack,
    load_prompt_registry,
    make_finding,
)
from tests.conftest import FrozenClock


async def _enrichment_graph(gateway: FakeGateway) -> EnrichmentGraph:
    retriever, assembler, config = await build_retrieval_stack()
    return EnrichmentGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )


async def test_enrichment_produces_verified_citations() -> None:
    gateway = FakeGateway(reply="IAM keys must be rotated within 90 days [1].")
    graph = await _enrichment_graph(gateway)

    enriched = await graph.run(make_finding(), AUTH)

    assert enriched.explanation.startswith("IAM keys")
    assert enriched.citations, "expected grounded citations"
    assert enriched.citation_verified is True
    assert len(gateway.requests) == 1


async def test_enrichment_abstain_node_returns_not_covered() -> None:
    gateway = FakeGateway()
    graph = await _enrichment_graph(gateway)
    state = {"finding": make_finding()}
    out = await graph._abstain(state)
    enriched = out["enriched"]
    assert enriched.explanation == ABSTENTION_TEXT
    assert enriched.citations == []
    assert enriched.citation_verified is False
    # The abstain path must never call the model.
    assert gateway.requests == []


async def test_copilot_answers_grounded() -> None:
    gateway = FakeGateway(reply="Rotate access keys regularly [1].")
    retriever, assembler, config = await build_retrieval_stack()
    graph = CopilotGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )
    answer = await graph.run("How should IAM access keys be managed?", AUTH)
    assert answer.abstained is False
    assert answer.citation_verified is True
    assert answer.citations


async def test_copilot_abstains_on_empty_context() -> None:
    gateway = FakeGateway()
    retriever, assembler, config = await build_retrieval_stack()
    graph = CopilotGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )
    # Filter to a framework absent from the sample corpus -> nothing retrieved.
    answer = await graph.run(
        "unrelated question about quantum widgets",
        AUTH,
        metadata_filter=MetadataFilter(framework=Framework.SOC_2),
    )
    assert answer.abstained is True
    assert answer.answer == ABSTENTION_TEXT
    assert answer.citations == []
    assert gateway.requests == []


async def test_remediation_is_never_approved_and_validated() -> None:
    gateway = FakeGateway(
        reply='resource "aws_iam_policy" "p" { statement { actions = ["iam:GetUser"] } }'
    )
    retriever, assembler, config = await build_retrieval_stack()
    graph = RemediationGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )
    proposal = await graph.run(make_finding(), AUTH)
    assert proposal.approved is False
    assert "aws_iam_policy" in proposal.terraform


async def test_remediation_rejects_unsafe_terraform() -> None:
    gateway = FakeGateway(reply='resource "aws_s3_bucket_acl" "x" { acl = "public-read-write" }')
    retriever, assembler, config = await build_retrieval_stack()
    graph = RemediationGraph(
        retriever=retriever,
        assembler=assembler,
        gateway=gateway,
        prompts=load_prompt_registry(),
        config=config,
    )
    with pytest.raises(WorkflowError):
        await graph.run(make_finding(), AUTH)


async def test_report_counts_severities_and_drafts() -> None:
    gateway = FakeGateway(reply="Overall posture is weak; prioritise IAM hardening.")
    graph = await _enrichment_graph(gateway)
    enriched = await graph.run(make_finding(), AUTH)

    report_gateway = FakeGateway(reply="Executive summary: address IAM gaps.")
    report_graph = ReportGraph(
        gateway=report_gateway,
        prompts=load_prompt_registry(),
        clock=FrozenClock(),
    )
    draft = await report_graph.run([enriched], AUTH)
    assert draft.finding_count == 1
    assert draft.severity_breakdown == {"high": 1}
    assert draft.tenant_id == "tenant-a"
    assert draft.executive_summary


async def test_report_handles_no_findings() -> None:
    report_graph = ReportGraph(
        gateway=FakeGateway(reply=""),
        prompts=load_prompt_registry(),
        clock=FrozenClock(),
    )
    draft = await report_graph.run([], AUTH)
    assert draft.finding_count == 0
    assert draft.severity_breakdown == {}
