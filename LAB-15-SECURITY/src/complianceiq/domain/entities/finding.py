"""The :class:`Finding` contract and its enriched form.

A *finding* is the Core Service's verdict that a resource violates (or satisfies)
a rule. It is the primary input to almost every AI capability: we explain it,
map it, correlate it, price it, and remediate it.

An *enriched finding* is a finding plus the AI's grounded explanation and its
verified citations. The ``citation_verified`` flag is the visible outcome of the
grounding guarantee (non-negotiable rule 3): a caller can trust the explanation
only when every cited control was found in the retrieved corpus context.
"""

from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import (
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)
from complianceiq.domain.value_objects.identifiers import (
    ControlId,
    NonEmptyStr,
    ResourceId,
    TenantId,
)


class Finding(FrozenModel):
    """A compliance verdict on a resource, produced by the Core rule engine.

    Attributes:
        id: Stable finding identifier within the tenant.
        tenant_id: Owning tenant. Scopes all access.
        resource_id: The resource this finding is about.
        rule_id: The rule that produced the verdict.
        framework: The framework the rule belongs to.
        control_id: The control the rule maps to within that framework.
        domain: The control domain (IAM, network, …).
        status: ``pass`` or ``fail``.
        severity: Severity of the finding.
        evidence: Rule-engine evidence (matched fields, expected vs actual).
        detected_at: When the verdict was produced (timezone-aware UTC).
    """

    id: NonEmptyStr
    tenant_id: TenantId
    resource_id: ResourceId
    rule_id: NonEmptyStr
    framework: Framework
    control_id: ControlId
    domain: RiskDomain
    status: ComplianceStatus
    severity: Severity
    evidence: dict[str, Any]
    detected_at: AwareDatetime


class EnrichedFinding(Finding):
    """A finding augmented with a grounded, cited explanation.

    Extends :class:`Finding` with the AI outputs. ``citation_verified`` is
    authoritative: it is set by the grounding policy after every citation has
    been checked against retrieved context, never by the model.

    Attributes:
        explanation: Plain-language explanation of why the resource is in this
            state and why it matters.
        citations: The controls the explanation is grounded in.
        citation_verified: True only if every citation was verified against
            retrieved corpus content. False signals the explanation is not to be
            trusted as authoritative.
    """

    explanation: NonEmptyStr
    citations: list[Citation] = Field(default_factory=list)
    citation_verified: bool
