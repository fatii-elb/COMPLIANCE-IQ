"""The :class:`FinancialRiskAssessment` contract.

Translates technical risk into a monetary exposure *range* in Moroccan Dirham
(MAD). We deliberately never emit a single point estimate: precision we cannot
justify would be dishonest in an audit. Every assessment carries its rationale
and the explicit assumptions behind it, so a reviewer can challenge the inputs
rather than a black-box number.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class FinancialRiskAssessment(FrozenModel):
    """A monetary exposure range (in MAD) for a finding or correlated risk.

    Exactly one of ``finding_id`` / ``risk_id`` identifies the subject; both
    being absent, or both present, is a contract violation.

    Attributes:
        finding_id: The finding assessed, if the subject is a single finding.
        risk_id: The correlated risk assessed, if the subject is a risk.
        min_mad: Lower bound of exposure in MAD (>= 0).
        max_mad: Upper bound of exposure in MAD (>= min_mad).
        rationale: Human-readable explanation of how the range was derived.
        assumptions: The explicit assumptions the range depends on.
    """

    finding_id: NonEmptyStr | None = None
    risk_id: NonEmptyStr | None = None
    min_mad: Decimal = Field(ge=Decimal(0))
    max_mad: Decimal = Field(ge=Decimal(0))
    rationale: NonEmptyStr
    assumptions: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_subject_and_bounds(self) -> FinancialRiskAssessment:
        """Enforce exactly-one subject and a well-ordered range."""
        if (self.finding_id is None) == (self.risk_id is None):
            raise ValueError("exactly one of finding_id or risk_id must be set")
        if self.max_mad < self.min_mad:
            raise ValueError("max_mad must be greater than or equal to min_mad")
        return self
