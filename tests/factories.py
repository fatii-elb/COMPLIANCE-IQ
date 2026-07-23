"""Test data builders for domain objects.

Centralised factories keep tests readable and resilient: a new required field on
a contract is added here once, not in dozens of tests. Each builder returns a
valid instance with sensible defaults that individual tests override.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.resource import NormalizedResource
from complianceiq.domain.value_objects.enums import (
    CloudProvider,
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_finding(**overrides: Any) -> Finding:
    """Build a valid :class:`Finding` with overridable fields."""
    defaults: dict[str, Any] = {
        "id": "finding-1",
        "tenant_id": "tenant-a",
        "resource_id": "resource-1",
        "rule_id": "rule-s3-public",
        "framework": Framework.LOI_05_20,
        "control_id": "art-23",
        "domain": RiskDomain.STORAGE,
        "status": ComplianceStatus.FAIL,
        "severity": Severity.HIGH,
        "evidence": {"public": True},
        "detected_at": _NOW,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def make_resource(**overrides: Any) -> NormalizedResource:
    """Build a valid :class:`NormalizedResource` with overridable fields."""
    defaults: dict[str, Any] = {
        "id": "resource-1",
        "tenant_id": "tenant-a",
        "cloud": CloudProvider.AWS,
        "service": "s3",
        "region": "eu-west-1",
        "type": "bucket",
        "config": {"acl": "public-read"},
        "collected_at": _NOW,
    }
    defaults.update(overrides)
    return NormalizedResource(**defaults)
