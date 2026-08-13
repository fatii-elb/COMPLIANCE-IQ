"""Tests for core entity/value-object validation rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.entities.risk import CorrelatedRisk
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import Framework, Severity
from tests.factories import make_finding


def test_empty_tenant_id_is_rejected() -> None:
    # An empty tenant would defeat tenant scoping; it must never construct.
    with pytest.raises(PydanticValidationError):
        make_finding(tenant_id="   ")


def test_finding_is_frozen() -> None:
    finding = make_finding()
    with pytest.raises(PydanticValidationError):
        finding.severity = Severity.LOW  # type: ignore[misc]


def test_unknown_field_is_rejected() -> None:
    # extra="forbid": a typo'd field is a contract violation, not silently kept.
    with pytest.raises(PydanticValidationError):
        make_finding(sevirity=Severity.LOW)


def test_enriched_finding_extends_finding() -> None:
    base = make_finding()
    enriched = EnrichedFinding(
        **base.model_dump(),
        explanation="The bucket is publicly readable, violating the storage control.",
        citations=[
            Citation(framework=Framework.LOI_05_20, control_id="art-23", reference="Art. 23")
        ],
        citation_verified=True,
    )
    assert isinstance(enriched, Finding)
    assert enriched.citation_verified is True
    assert enriched.id == base.id


def test_severity_weight_is_ordered() -> None:
    weights = [s.weight for s in (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)]
    assert weights == sorted(weights)
    assert weights[0] < weights[-1]


def test_correlated_risk_requires_findings() -> None:
    with pytest.raises(PydanticValidationError):
        CorrelatedRisk(
            id="risk-1",
            tenant_id="tenant-a",
            finding_ids=[],
            narrative="x",
            severity=Severity.HIGH,
        )


def test_correlated_risk_rejects_duplicate_findings() -> None:
    with pytest.raises(PydanticValidationError):
        CorrelatedRisk(
            id="risk-1",
            tenant_id="tenant-a",
            finding_ids=["f1", "f1"],
            narrative="x",
            severity=Severity.HIGH,
        )
