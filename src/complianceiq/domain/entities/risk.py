"""The :class:`CorrelatedRisk` contract.

The risk engine (Phase 5) combines several related findings into a single risk
with an attack-path narrative — e.g. a public bucket *plus* an over-permissive
IAM role *plus* absent logging together describe a data-exfiltration path that
none of the findings expresses alone. The aggregated severity is explainable and
unit-tested (it is never a magic number).
"""

from __future__ import annotations

from pydantic import Field, field_validator

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.enums import Severity
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, TenantId


class CorrelatedRisk(FrozenModel):
    """Several related findings unified into one risk with a narrative.

    Attributes:
        id: Stable risk identifier within the tenant.
        tenant_id: Owning tenant. Scopes all access.
        finding_ids: The findings this risk correlates. Must be non-empty — a
            risk with no supporting findings is meaningless.
        narrative: The attack-path / impact narrative explaining the risk.
        severity: Aggregated severity across the correlated findings.
    """

    id: NonEmptyStr
    tenant_id: TenantId
    finding_ids: list[NonEmptyStr] = Field(min_length=1)
    narrative: NonEmptyStr
    severity: Severity

    @field_validator("finding_ids")
    @classmethod
    def _reject_duplicate_findings(cls, value: list[str]) -> list[str]:
        """A finding must not appear twice in the same correlated risk."""
        if len(set(value)) != len(value):
            raise ValueError("finding_ids must not contain duplicates")
        return value
