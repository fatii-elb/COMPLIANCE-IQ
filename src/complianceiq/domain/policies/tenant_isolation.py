"""Tenant-isolation policy — the enforcement helper for non-negotiable rule 1.

Tenant isolation must be *impossible to violate*, not merely discouraged. This
module provides the single guard that every data-access path calls before
returning or writing tenant-owned data. Centralising it means the rule is
expressed once, tested once, and cannot drift between call sites.
"""

from __future__ import annotations

from complianceiq.domain.exceptions import TenantIsolationError


def assert_same_tenant(
    *,
    expected_tenant_id: str,
    actual_tenant_id: str,
    resource_kind: str,
) -> None:
    """Assert that a piece of data belongs to the acting tenant.

    Args:
        expected_tenant_id: The tenant from the authenticated context.
        actual_tenant_id: The tenant stamped on the data being accessed.
        resource_kind: What is being accessed (for diagnostics only).

    Raises:
        TenantIsolationError: If the tenants differ. The error deliberately does
            not echo the foreign tenant id to the caller; it records both only in
            structured ``details`` for server-side audit.
    """
    if expected_tenant_id != actual_tenant_id:
        raise TenantIsolationError(
            f"cross-tenant access to {resource_kind} was blocked",
            details={
                "resource_kind": resource_kind,
                "expected_tenant_id": expected_tenant_id,
                "actual_tenant_id": actual_tenant_id,
            },
        )
