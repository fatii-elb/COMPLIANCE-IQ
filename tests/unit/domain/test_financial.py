"""Tests for :class:`FinancialRiskAssessment` invariants."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from complianceiq.domain.entities.financial import FinancialRiskAssessment


def test_valid_assessment_for_a_finding() -> None:
    assessment = FinancialRiskAssessment(
        finding_id="finding-1",
        min_mad=Decimal("1000"),
        max_mad=Decimal("50000"),
        rationale="Fine band plus remediation labour.",
        assumptions=["50k records", "high data sensitivity"],
    )
    assert assessment.min_mad == Decimal("1000")
    assert assessment.risk_id is None


def test_requires_exactly_one_subject() -> None:
    # Neither subject set.
    with pytest.raises(PydanticValidationError):
        FinancialRiskAssessment(
            min_mad=Decimal("0"),
            max_mad=Decimal("1"),
            rationale="x",
        )
    # Both subjects set.
    with pytest.raises(PydanticValidationError):
        FinancialRiskAssessment(
            finding_id="finding-1",
            risk_id="risk-1",
            min_mad=Decimal("0"),
            max_mad=Decimal("1"),
            rationale="x",
        )


def test_max_must_be_at_least_min() -> None:
    with pytest.raises(PydanticValidationError):
        FinancialRiskAssessment(
            finding_id="finding-1",
            min_mad=Decimal("100"),
            max_mad=Decimal("10"),
            rationale="x",
        )


def test_negative_amounts_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        FinancialRiskAssessment(
            finding_id="finding-1",
            min_mad=Decimal("-1"),
            max_mad=Decimal("10"),
            rationale="x",
        )
