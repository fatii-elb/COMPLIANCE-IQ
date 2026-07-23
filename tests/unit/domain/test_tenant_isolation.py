"""Tests for the tenant-isolation policy (non-negotiable rule 1).

Cross-tenant access must be impossible. These are non-skippable security gates.
"""

from __future__ import annotations

import pytest

from complianceiq.domain.exceptions import AuthorizationError, TenantIsolationError
from complianceiq.domain.policies.tenant_isolation import assert_same_tenant


@pytest.mark.security
def test_same_tenant_passes() -> None:
    # Must not raise.
    assert_same_tenant(
        expected_tenant_id="tenant-a",
        actual_tenant_id="tenant-a",
        resource_kind="finding",
    )


@pytest.mark.security
def test_cross_tenant_is_blocked() -> None:
    with pytest.raises(TenantIsolationError) as exc_info:
        assert_same_tenant(
            expected_tenant_id="tenant-a",
            actual_tenant_id="tenant-b",
            resource_kind="finding",
        )
    # It is an authorization failure and carries diagnostic detail for audit,
    # but the error is a distinct, catchable type.
    assert isinstance(exc_info.value, AuthorizationError)
    assert exc_info.value.code == "tenant_isolation_violation"
    assert exc_info.value.details["actual_tenant_id"] == "tenant-b"
    assert exc_info.value.details["expected_tenant_id"] == "tenant-a"
