"""Tests for the deterministic financial exposure model (pure, auditable)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.policies.financial_model import estimate_exposure
from complianceiq.domain.value_objects.enums import (
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)


def _finding(
    *,
    severity: Severity = Severity.HIGH,
    domain: RiskDomain = RiskDomain.LOGGING,
    status: ComplianceStatus = ComplianceStatus.FAIL,
) -> Finding:
    return Finding(
        id="f1",
        tenant_id="tenant-a",
        resource_id="arn:x",
        rule_id="r1",
        framework=Framework.NIST_CSF,
        control_id="PR.AA-01",
        domain=domain,
        status=status,
        severity=severity,
        evidence={},
        detected_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_band_increases_with_severity() -> None:
    low = estimate_exposure(_finding(severity=Severity.LOW))
    crit = estimate_exposure(_finding(severity=Severity.CRITICAL))
    assert crit.min_mad > low.min_mad
    assert crit.max_mad > low.max_mad


def test_range_is_well_ordered_and_nonnegative() -> None:
    band = estimate_exposure(_finding(severity=Severity.MEDIUM))
    assert band.min_mad >= 0
    assert band.max_mad >= band.min_mad


def test_domain_multiplier_applies() -> None:
    # LOGGING has a 1.0x multiplier; STORAGE has 1.3x — same severity, higher band.
    logging_band = estimate_exposure(_finding(domain=RiskDomain.LOGGING))
    storage_band = estimate_exposure(_finding(domain=RiskDomain.STORAGE))
    assert storage_band.max_mad > logging_band.max_mad


def test_high_logging_matches_base_band_exactly() -> None:
    # LOGGING multiplier is 1.0, so HIGH maps to the raw base band 150000–750000.
    band = estimate_exposure(_finding(severity=Severity.HIGH, domain=RiskDomain.LOGGING))
    assert band.min_mad == Decimal("150000")
    assert band.max_mad == Decimal("750000")


def test_passing_finding_has_zero_exposure() -> None:
    band = estimate_exposure(_finding(status=ComplianceStatus.PASS))
    assert band.min_mad == Decimal(0)
    assert band.max_mad == Decimal(0)
    assert band.assumptions  # still explains why it's zero


def test_assumptions_are_explicit() -> None:
    band = estimate_exposure(_finding(severity=Severity.HIGH, domain=RiskDomain.STORAGE))
    joined = " ".join(band.assumptions)
    assert "planning" in joined
    assert "multiplier" in joined
