"""The :class:`ComplianceScore` contract.

Produced by the Core Service's scoring engine and consumed by the report and
risk features. A score summarises pass/fail counts for a scope (a framework, a
domain, a tenant) into a single 0–100 figure.
"""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, TenantId


class ComplianceScore(FrozenModel):
    """A pass/fail rollup for a compliance scope.

    Attributes:
        tenant_id: Owning tenant. Scopes all access.
        scope: The kind of thing being scored (e.g. ``framework``, ``domain``).
        key: The specific instance within the scope (e.g. ``iso_27001``).
        score: Compliance percentage in the closed interval [0, 100].
        passed: Number of controls that passed.
        failed: Number of controls that failed.
        computed_at: When the score was computed (timezone-aware UTC).
    """

    tenant_id: TenantId
    scope: NonEmptyStr
    key: NonEmptyStr
    score: float = Field(ge=0.0, le=100.0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    computed_at: AwareDatetime
