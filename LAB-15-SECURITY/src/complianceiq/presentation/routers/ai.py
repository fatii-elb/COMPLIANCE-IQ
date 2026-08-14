"""The AI capability endpoints (Phase 5).

These expose the Phase-4 bounded agents over HTTP, under ``/api/v1/ai``. Every
endpoint is JWT-protected (via :func:`get_auth_context`) and tenant-scoped: any
finding in a request body must belong to the caller's tenant, or the request is
rejected (non-negotiable rule 1). The response shapes are the domain contracts
themselves (see ``docs/CORE_SERVICE_HANDOFF.md``).

- ``POST /ai/enrich``    — findings → grounded, cited ``EnrichedFinding``s.
- ``POST /ai/ask``       — a question → grounded ``CopilotAnswer`` (or abstention).
- ``POST /ai/remediate`` — a finding → ``RemediationProposal`` (``approved=false``).
- ``POST /ai/correlate`` — findings → a grounded systemic-risk narrative.
- ``POST /ai/report``    — enriched findings → an executive ``ReportDraft``.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends

from complianceiq.application.agents import AgentSuite
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.copilot import CopilotAnswer
from complianceiq.domain.entities.financial import FinancialRiskAssessment
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.entities.mapping import ControlMapping
from complianceiq.domain.entities.remediation import RemediationProposal
from complianceiq.domain.entities.report import ReportDraft
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.policies.tenant_isolation import assert_same_tenant
from complianceiq.domain.ports.core import CoreClient
from complianceiq.presentation.container import (
    get_agents,
    get_auth_context,
    get_bearer_token,
    get_core_client,
)
from complianceiq.presentation.schemas import (
    AskRequest,
    CorrelateRequest,
    CorrelateResponse,
    EnrichByIdsRequest,
    EnrichRequest,
    FinancialRequest,
    MapRequest,
    RemediateRequest,
    ReportRequest,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _assert_tenant(findings: Iterable[Finding], auth: AuthContext) -> None:
    """Reject the request if any finding belongs to a different tenant."""
    for finding in findings:
        assert_same_tenant(
            expected_tenant_id=auth.tenant_id,
            actual_tenant_id=finding.tenant_id,
            resource_kind="finding",
        )


@router.post("/enrich", response_model=list[EnrichedFinding], summary="Explain findings")
async def enrich(
    body: EnrichRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> list[EnrichedFinding]:
    """Return a grounded, cited explanation for each finding (or an abstention)."""
    _assert_tenant(body.findings, auth)
    return [await agents.compliance_analyst.analyze(f, auth) for f in body.findings]


@router.post(
    "/enrich/by-ids",
    response_model=list[EnrichedFinding],
    summary="Fetch findings from the Core and explain them",
)
async def enrich_by_ids(
    body: EnrichByIdsRequest,
    auth: AuthContext = Depends(get_auth_context),
    token: str = Depends(get_bearer_token),
    agents: AgentSuite = Depends(get_agents),
    core: CoreClient = Depends(get_core_client),
) -> list[EnrichedFinding]:
    """Fetch each finding from the Core (tenant-scoped), then enrich it.

    Demonstrates the Phase-6 Core integration: instead of the client posting
    finding bodies, it posts ids and we pull the authoritative findings from the
    Core, forwarding the caller's token.
    """
    enriched: list[EnrichedFinding] = []
    for finding_id in body.finding_ids:
        finding = await core.get_finding(auth, finding_id, bearer_token=token)
        enriched.append(await agents.compliance_analyst.analyze(finding, auth))
    return enriched


@router.post("/ask", response_model=CopilotAnswer, summary="Ask a grounded question")
async def ask(
    body: AskRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> CopilotAnswer:
    """Answer a natural-language question, grounded in the corpus, or abstain."""
    metadata_filter = MetadataFilter(framework=body.framework) if body.framework else None
    return await agents.copilot.run(body.question, auth, metadata_filter=metadata_filter)


@router.post("/remediate", response_model=RemediationProposal, summary="Propose a fix")
async def remediate(
    body: RemediateRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> RemediationProposal:
    """Propose a validated, never-applied remediation (``approved`` is always false)."""
    _assert_tenant([body.finding], auth)
    return await agents.remediation_engineer.propose(body.finding, auth)


@router.post("/correlate", response_model=CorrelateResponse, summary="Correlate findings")
async def correlate(
    body: CorrelateRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> CorrelateResponse:
    """Correlate a set of findings into one grounded systemic-risk narrative."""
    _assert_tenant(body.findings, auth)
    narrative = await agents.risk_analyst.correlate(body.findings, auth)
    return CorrelateResponse(narrative=narrative)


@router.post("/map", response_model=ControlMapping, summary="Map a control across frameworks")
async def map_control(
    body: MapRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> ControlMapping:
    """Map a finding's control to equivalent controls in other frameworks."""
    _assert_tenant([body.finding], auth)
    return await agents.control_mapper.map(body.finding, auth)


@router.post(
    "/financial",
    response_model=FinancialRiskAssessment,
    summary="Quantify financial exposure (MAD)",
)
async def financial(
    body: FinancialRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> FinancialRiskAssessment:
    """Estimate a finding's monetary exposure range in MAD (deterministic + narrated)."""
    _assert_tenant([body.finding], auth)
    return await agents.financial_analyst.assess(body.finding, auth)


@router.post("/report", response_model=ReportDraft, summary="Draft an executive report")
async def report(
    body: ReportRequest,
    auth: AuthContext = Depends(get_auth_context),
    agents: AgentSuite = Depends(get_agents),
) -> ReportDraft:
    """Draft an executive summary over the caller's enriched findings."""
    _assert_tenant(body.findings, auth)
    return await agents.report_writer.write(body.findings, auth)
