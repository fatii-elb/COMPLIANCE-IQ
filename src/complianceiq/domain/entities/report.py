"""The :class:`ReportDraft` — the content of a compliance report.

Produced by the report graph from a set of enriched findings: an executive
summary plus factual breakdowns. The audit-ready PDF *rendering* of this content
is a later phase; this is the grounded content it renders.
"""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, TenantId


class ReportDraft(FrozenModel):
    """Draft content for a per-tenant compliance report.

    Attributes:
        tenant_id: The tenant the report is for.
        executive_summary: The generated executive summary.
        finding_count: Number of findings the report covers.
        severity_breakdown: Count of findings per severity (e.g. ``{"high": 3}``).
        generated_at: When the draft was produced (timezone-aware UTC).
    """

    tenant_id: TenantId
    executive_summary: NonEmptyStr
    finding_count: int = Field(ge=0)
    severity_breakdown: dict[str, int] = Field(default_factory=dict)
    generated_at: AwareDatetime
